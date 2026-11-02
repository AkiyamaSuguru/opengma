# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
峰位表和 XRD 参考物相表的编辑对话框（方案 7.2、8）：由用户填写，保存在项目中，
可以在多个谱图、多个模块之间复用，也可以导入导出 CSV。GMA 不内置任何峰位或物相（Q7）。

编辑的是副本，点“确定”时检查并写回项目；取消时项目不变。
"""
from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path

import flet as ft

from ...project import (
    ProjectError,
    read_peak_csv,
    read_phase_csv,
    write_peak_csv,
    write_phase_csv,
)
from ...project.model import check_peak_rows, check_phase_rows
from .. import theme as th
from ..strings import S
from . import widgets as w
from .dialogs import close, confirm, dialog, prompt_text, show

ROWS_HEIGHT = 300


def _text(value) -> str:
    if isinstance(value, float):
        return f"{value:g}"
    return "" if value is None else str(value)


class _TableDialog:
    """两种表格对话框共用的部分：一列可以增删的行，导入导出 CSV，确定时检查。"""

    FIELDS: tuple[tuple[str, str, float], ...] = ()   # (键, 列名, 宽度)
    TITLE = ""

    def __init__(self, view):
        self.view = view
        self.rows_box = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO, height=ROWS_HEIGHT)
        self.inputs: list[dict[str, ft.TextField]] = []
        self.message = ft.Text("", size=th.SIZE_SMALL, color=view.p.error, max_lines=2,
                               overflow=ft.TextOverflow.ELLIPSIS)
        self.box: ft.AlertDialog | None = None
        self.future: asyncio.Future | None = None

    @property
    def p(self):
        return self.view.p

    @property
    def page(self):
        return self.view.app.page

    # ---------- 行 ----------
    def show_rows(self, rows: list[dict], update: bool = True) -> None:
        self.inputs = []
        controls = []
        for row in rows or [{}]:
            controls.append(self.row_control(row))
        self.rows_box.controls = controls
        if update:
            self.rows_box.update()

    def row_control(self, row: dict) -> ft.Control:
        fields = {key: ft.TextField(value=_text(row.get(key)), label=label, width=width, dense=True,
                                    text_size=th.SIZE_BODY,
                                    keyboard_type=ft.KeyboardType.NUMBER if key in ("position", "two_theta")
                                    else ft.KeyboardType.TEXT)
                  for key, label, width in self.FIELDS}
        self.inputs.append(fields)
        holder = ft.Row([*fields.values()], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER)

        def remove(e):
            index = self.rows_box.controls.index(holder)
            del self.rows_box.controls[index]
            del self.inputs[index]
            self.rows_box.update()

        holder.controls.append(w.icon_button(ft.Icons.CLOSE_ROUNDED, S.DELETE_ROW, remove, self.p, size=16))
        return holder

    def add_row(self, e=None) -> None:
        self.rows_box.controls.append(self.row_control({}))
        self.rows_box.update()

    def collect(self) -> list[dict]:
        """输入框中的行；整行都空的跳过。"""
        rows = []
        for fields in self.inputs:
            row = {key: (f.value or "").strip() for key, f in fields.items()}
            if any(row.values()):
                rows.append(row)
        return rows

    def say(self, message: str) -> None:
        self.message.value = message
        self.message.tooltip = message
        self.message.update()

    # ---------- 对话框 ----------
    def tools(self) -> list[ft.Control]:
        p = self.p
        return [w.ghost_button(S.ADD_ROW, ft.Icons.ADD_ROUNDED, self.add_row, p), ft.Container(expand=True),
                w.ghost_button(S.IMPORT_CSV, ft.Icons.UPLOAD_FILE_OUTLINED, lambda e: self.page.run_task(self.import_csv),
                               p),
                w.ghost_button(S.EXPORT_CSV, ft.Icons.DOWNLOAD_ROUNDED, lambda e: self.page.run_task(self.export_csv),
                               p)]

    async def open(self, top: list[ft.Control], hint: str, width: float):
        p = self.p
        self.future = asyncio.get_running_loop().create_future()
        content = ft.Container(width=width, content=ft.Column([
            *top, w.faint(hint, p, th.SIZE_SMALL),
            ft.Container(content=self.rows_box, border=ft.Border.all(1, p.border), border_radius=th.RADIUS_CONTROL,
                         padding=ft.Padding.only(left=10, right=4, top=10, bottom=10)),
            ft.Row(self.tools(), spacing=4),
        ], spacing=10, tight=True))
        actions = [ft.Row([self.message, ft.Container(expand=True),
                           ft.TextButton(S.CANCEL, on_click=lambda e: self.finish(None)),
                           ft.FilledButton(S.OK, on_click=self.submit)],
                          spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER)]
        self.box = dialog(p, self.TITLE, content, actions, width=width)
        self.box.on_dismiss = lambda e: self.finish(None)
        show(self.page, self.box)
        return await self.future

    def finish(self, value) -> None:
        if self.future is not None and not self.future.done():
            close(self.box)
            self.future.set_result(value)

    def submit(self, e=None) -> None:  # 子类实现
        raise NotImplementedError

    async def import_csv(self) -> None:  # 子类实现
        raise NotImplementedError

    async def export_csv(self) -> None:  # 子类实现
        raise NotImplementedError

    async def pick_csv(self) -> Path | None:
        files = await self.view.app.file_picker.pick_files(
            dialog_title=S.IMPORT_CSV.rstrip("…"), file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["csv", "txt", "tsv"])
        path = next((f.path for f in files or [] if f.path), None)
        return Path(path) if path else None

    async def save_csv(self, name: str) -> Path | None:
        path = await self.view.app.file_picker.save_file(
            dialog_title=S.EXPORT_CSV.rstrip("…"), file_name=f"{name}.csv", file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["csv"])
        return Path(path).with_suffix(".csv") if path else None


def problem(exc: Exception) -> str:
    """把 GMA 的检查结果写成界面上的提示（行号和原因）。"""
    text = str(exc)
    for english, chinese in (("Peak table row", S.ROW), ("Reference phase row", S.ROW),
                             ("the label is empty", S.LABEL_EMPTY), ("duplicate label", S.DUPLICATE_LABEL),
                             ("must be a number", S.MUST_BE_NUMBER), ("must be a finite number", S.MUST_BE_NUMBER),
                             ("the phase name and hkl must not be empty", S.PHASE_EMPTY),
                             ("duplicate", S.DUPLICATE_HKL), ("position", S.POSITION), ("2θ", "2θ")):
        text = text.replace(english, chinese)
    return text


# ============================================================
# 峰位表
# ============================================================
class PeakTablesDialog(_TableDialog):
    """峰位表可以有多个（如“SiC 全谱”“碳材料 Raman”），各自是若干行“标签、位置”。"""

    FIELDS = (("label", S.PEAK_LABEL, 200), ("position", S.PEAK_POSITION, 140))
    TITLE = S.PEAK_TABLES

    def __init__(self, view):
        super().__init__(view)
        project = view.project
        self.tables = {name: [dict(r) for r in rows] for name, rows in project.peak_tables.items()}
        current = view.st.get("peak_table")
        self.current = current if current in self.tables else next(iter(self.tables), None)
        self.selector = ft.Dropdown(width=240, dense=True, text_size=th.SIZE_BODY, label=S.PEAK_TABLE,
                                    on_select=self.on_select)
        self.top = ft.Row(spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER)

    async def show(self) -> str | None:
        """返回点“确定”时选中的峰位表（没有表时为 ""）；取消时为 None。"""
        self.refresh_top(update=False)
        self.show_rows(self.tables.get(self.current, []), update=False)
        return await self.open([self.top], S.PEAK_TABLES_HINT, 520)

    def refresh_top(self, update: bool = True) -> None:
        p = self.p
        self.selector.options = [ft.DropdownOption(key=n, text=n) for n in self.tables]
        self.selector.value = self.current
        has = self.current is not None
        self.top.controls = [
            self.selector,
            w.icon_button(ft.Icons.ADD_ROUNDED, S.NEW_PEAK_TABLE, lambda e: self.page.run_task(self.new_table), p),
            w.icon_button(ft.Icons.EDIT_OUTLINED, S.RENAME, lambda e: self.page.run_task(self.rename_table), p,
                          disabled=not has),
            w.icon_button(ft.Icons.DELETE_OUTLINE, S.DELETE, lambda e: self.page.run_task(self.delete_table), p,
                          disabled=not has, color=p.error if has else None),
        ]
        self.rows_box.disabled = not has
        if update:
            self.top.update()
            self.rows_box.update()

    def keep(self) -> None:
        """切换表格前，把输入框中的内容记到副本中。"""
        if self.current is not None:
            self.tables[self.current] = self.collect()

    def on_select(self, e) -> None:
        self.keep()
        self.current = e.control.value
        self.show_rows(self.tables.get(self.current, []))
        self.refresh_top()

    def unique(self, name: str) -> str:
        base, i = name, 2
        while name in self.tables:
            name = f"{base} ({i})"
            i += 1
        return name

    async def new_table(self) -> None:
        name = await prompt_text(self.page, self.p, S.NEW_PEAK_TABLE, S.PEAK_TABLE_NAME, S.DEFAULT_PEAK_TABLE,
                                 validate=lambda t: S.NAME_TAKEN if t in self.tables else None)
        if not name:
            return
        self.keep()
        self.tables[name] = []
        self.current = name
        self.show_rows([])
        self.refresh_top()

    async def rename_table(self) -> None:
        old = self.current
        name = await prompt_text(self.page, self.p, S.RENAME, S.PEAK_TABLE_NAME, old,
                                 validate=lambda t: S.NAME_TAKEN if t != old and t in self.tables else None)
        if not name or name == old:
            return
        self.keep()
        self.tables = {(name if k == old else k): v for k, v in self.tables.items()}
        self.current = name
        self.refresh_top()

    async def delete_table(self) -> None:
        if not await confirm(self.page, self.p, S.DELETE_PEAK_TABLE, S.DELETE_PEAK_TABLE_BODY.format(name=self.current),
                             S.DELETE, danger=True):
            return
        self.tables.pop(self.current, None)
        self.current = next(iter(self.tables), None)
        self.show_rows(self.tables.get(self.current, []))
        self.refresh_top()

    async def import_csv(self) -> None:
        path = await self.pick_csv()
        if path is None:
            return
        try:
            rows = await asyncio.to_thread(read_peak_csv, path)
        except (ProjectError, OSError) as exc:
            self.say(S.FILE_ERROR.format(name=path.name, error=problem(exc)))
            return
        self.keep()
        name = self.unique(path.stem or S.DEFAULT_PEAK_TABLE)   # 导入为新表，不覆盖已有的表
        self.tables[name] = rows
        self.current = name
        self.show_rows(rows)
        self.refresh_top()
        self.say("")

    async def export_csv(self) -> None:
        if self.current is None:
            return
        try:
            rows = check_peak_rows(self.collect())
        except ProjectError as exc:
            self.say(problem(exc))
            return
        path = await self.save_csv(self.current)
        if path is None:
            return
        try:
            await asyncio.to_thread(write_peak_csv, rows, path)
        except OSError as exc:
            self.say(str(exc))
            return
        self.message.color = self.p.success
        self.say(S.EXPORTED_EXCEL.format(path=path))
        self.message.color = self.p.error

    def submit(self, e=None) -> None:
        self.keep()
        checked = {}
        for name, rows in self.tables.items():
            try:
                checked[name] = check_peak_rows(rows)
            except ProjectError as exc:
                if name != self.current:  # 出错的表切到前面，方便修改
                    self.current = name
                    self.show_rows(rows)
                    self.refresh_top()
                self.say(f"{name}：{problem(exc)}")
                return
        project = self.view.project
        if checked != project.peak_tables:
            project.peak_tables = checked
            project.dirty = True
        self.finish(self.current or "")


# ============================================================
# 参考物相（XRD）
# ============================================================
class PhasesDialog(_TableDialog):
    """一张表：物相名、晶面指数、2θ。同一物相的多行合在一起显示，物相名显示在图例中。"""

    FIELDS = (("phase", S.PHASE_NAME, 170), ("hkl", S.PHASE_HKL, 110), ("two_theta", S.PHASE_TWO_THETA, 110))
    TITLE = S.REFERENCE_PHASES

    async def show(self) -> bool:
        """点“确定”时返回 True（参考物相可能有变化）。"""
        self.show_rows([dict(r) for r in self.view.project.reference_phases], update=False)
        return bool(await self.open([], S.PHASES_HINT, 560))

    async def import_csv(self) -> None:
        path = await self.pick_csv()
        if path is None:
            return
        try:
            rows = await asyncio.to_thread(read_phase_csv, path)
        except (ProjectError, OSError) as exc:
            self.say(S.FILE_ERROR.format(name=path.name, error=problem(exc)))
            return
        # 追加到表中；同一物相、同一晶面的行以导入的为准
        current = self.collect()
        keys = {(r["phase"], r["hkl"]) for r in rows}
        merged = [r for r in current if (r.get("phase"), r.get("hkl")) not in keys] + rows
        self.show_rows(merged)
        self.say("")

    async def export_csv(self) -> None:
        try:
            rows = check_phase_rows(self.collect())
        except ProjectError as exc:
            self.say(problem(exc))
            return
        path = await self.save_csv(S.REFERENCE_PHASES)
        if path is None:
            return
        with contextlib.suppress(OSError):
            await asyncio.to_thread(write_phase_csv, rows, path)
            self.message.color = self.p.success
            self.say(S.EXPORTED_EXCEL.format(path=path))
            self.message.color = self.p.error

    def submit(self, e=None) -> None:
        try:
            rows = check_phase_rows(self.collect())
        except ProjectError as exc:
            self.say(problem(exc))
            return
        project = self.view.project
        if rows != project.reference_phases:
            project.set_reference_phases(rows)
        self.finish(True)
