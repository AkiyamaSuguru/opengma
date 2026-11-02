# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
项目总览（工作区第一个固定标签，Q18）：样品表、数据检查、数据导出。

- 样品表：每个样品一行；样品信息的字段由用户定义，单击单元格编辑；每种方法显示数据的数量，
  点击打开对应模块。添加、重命名、删除样品；删除只是从项目中移除，不删除原始文件。
- 数据检查：清洗记录和命名不一致，只提示、不自动修改（方案 5.3）。
- 数据导出：CSV 或 Excel，范围是选中的样品或整个项目（方案 5.4、Q20）。
"""
from __future__ import annotations

import asyncio
import traceback

import flet as ft

from ...project import export_csv, export_excel
from .. import theme as th
from ..components import widgets as w
from ..components.dialogs import confirm, prompt_text, show_error, toast
from ..services.checks import WARNING, data_issues
from ..services.importing import note_text
from ..services.text import local_time, short_path
from ..strings import S
from . import registry
from .base import TabView

COL_CHECK, COL_SAMPLE, COL_FIELD, COL_COUNT, COL_MENU = 36, 190, 150, 70, 40
ROW_H, ROW_H_COMPACT = 38, 31


class OverviewView(TabView):
    def __init__(self, app, session, workspace):
        super().__init__(app, session, workspace)
        self.selected: set[str] = set()
        self.editing: tuple[str, str] | None = None   # 正在编辑的 (样品, 字段)
        self.export_scope = "all"
        self.export_format = app.settings.export_format
        self.include_components = True

    @property
    def row_h(self) -> int:
        return ROW_H_COMPACT if self.app.settings.density == "compact" else ROW_H

    def methods(self) -> list[registry.ModuleSpec]:
        return [m for m in registry.MODULES if m.method]

    # ============================================================
    # 整体
    # ============================================================
    def build(self) -> ft.Control:
        self.selected &= set(self.project.samples)
        left = ft.Column([self.header(), self.stats(), self.samples_card(), self.checks_card()],
                         spacing=12, expand=True, scroll=ft.ScrollMode.AUTO)
        return ft.Container(padding=ft.Padding.only(left=16, right=16, top=14, bottom=12), expand=True,
                            content=ft.Row([left, self.export_card()], spacing=12, expand=True,
                                           vertical_alignment=ft.CrossAxisAlignment.START))

    def header(self) -> ft.Control:
        p, project = self.p, self.project
        meta = [S.FILE_PATH + " " + short_path(self.session.path) if self.session.path else S.NOT_SAVED_YET]
        created = local_time(project.created_at)
        if created is not None:
            meta.append(S.CREATED_AT.format(time=created.strftime("%Y-%m-%d %H:%M")))
        name = ft.Container(
            content=ft.Row([w.text(project.name, p, th.SIZE_TITLE, bold=True, max_lines=1),
                            ft.Icon(ft.Icons.EDIT_OUTLINED, size=15, color=p.faint)], spacing=6, tight=True),
            on_click=self.rename_project, tooltip=S.RENAME)
        return ft.Column([
            w.muted(S.OVERVIEW_TITLE, p, th.SIZE_SMALL, bold=True), name,
            w.faint(" · ".join(meta), p, th.SIZE_TINY),
        ], spacing=2)

    def stats(self) -> ft.Control:
        p, project = self.p, self.project

        def tile(icon: ft.Control, value: int, title: str) -> ft.Control:
            return w.panel(ft.Row([icon, ft.Column([w.text(str(value), p, 18, bold=True), w.muted(title, p, 11.5)],
                                                   spacing=0, tight=True)], spacing=12),
                           p, padding=ft.Padding.symmetric(horizontal=14, vertical=10), expand=True)

        sample_icon = ft.Container(width=36, height=36, border_radius=10, bgcolor=p.primary_weak,
                                   alignment=ft.Alignment.CENTER,
                                   content=ft.Icon(ft.Icons.SCIENCE_OUTLINED, size=19, color=p.primary))
        tiles = [tile(sample_icon, len(project.samples), S.SAMPLES)]
        tiles += [tile(w.module_tile(m, p.dark, 36, 19), len(project.records_of(method=m.method)), m.title)
                  for m in self.methods()]
        return ft.Row(tiles, spacing=10)

    # ============================================================
    # 样品表
    # ============================================================
    def samples_card(self) -> ft.Control:
        p, project = self.p, self.project
        buttons = [w.ghost_button(S.ADD_FIELD, ft.Icons.VIEW_COLUMN_OUTLINED, self.add_field, p),
                   w.ghost_button(S.ADD_SAMPLE, ft.Icons.ADD_ROUNDED, self.add_sample, p)]
        if self.selected:
            buttons.insert(0, w.ghost_button(S.DELETE_COUNT.format(n=len(self.selected)), ft.Icons.DELETE_OUTLINE,
                                             self.delete_selected, p, color=p.error))
        title = ft.Row([w.text(S.SAMPLES, p, th.SIZE_PANEL_TITLE, bold=True), w.chip(str(len(project.samples)), p),
                        ft.Container(expand=True), *buttons], spacing=8,
                       vertical_alignment=ft.CrossAxisAlignment.CENTER)
        if not project.samples:
            body = self.empty_state()
        else:
            table = ft.Column([self.table_header(), w.hsep(p),
                               *[self.sample_row(name) for name in project.samples]], spacing=0, tight=True)
            body = ft.Column([
                ft.Row([table], scroll=ft.ScrollMode.AUTO),
                w.faint(S.SAMPLE_TABLE_HINT, p, th.SIZE_TINY),
            ], spacing=8, tight=True)
        return w.panel(ft.Column([title, body], spacing=8, tight=True), p, padding=14)

    def empty_state(self) -> ft.Control:
        p = self.p
        return ft.Container(padding=ft.Padding.symmetric(vertical=26), alignment=ft.Alignment.CENTER, content=ft.Column([
            ft.Icon(ft.Icons.INBOX_OUTLINED, size=34, color=p.faint),
            w.text(S.EMPTY_PROJECT, p, th.SIZE_PANEL_TITLE, bold=True),
            ft.Container(width=460, content=ft.Text(S.EMPTY_PROJECT_HINT, size=th.SIZE_SMALL, color=p.muted,
                                                   text_align=ft.TextAlign.CENTER)),
            self.import_menu(),
        ], spacing=8, tight=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER))

    def import_menu(self) -> ft.Control:
        """空项目中的“导入数据…”：选择表征方法后打开（或切到）那个模块，并打开它的导入对话框。"""
        p = self.p

        async def import_into(key):
            self.workspace.open_module(key, reuse=True)
            view = self.workspace.current_view()
            handler = getattr(view, "on_shortcut", None)
            if handler is not None:
                await handler("i", False)

        items = [ft.PopupMenuItem(
            content=ft.Row([w.module_icon(m, p.dark, 16), ft.Text(m.title, size=th.SIZE_BODY, color=p.text)],
                           spacing=10),
            on_click=lambda e, k=m.key: self.app.page.run_task(import_into, k))
            for m in registry.available() if m.method]
        button = ft.Container(
            content=ft.Row([ft.Icon(ft.Icons.UPLOAD_FILE_OUTLINED, size=18, color=p.on_primary),
                            ft.Text(S.IMPORT_DATA, size=th.SIZE_BODY, color=p.on_primary, weight=ft.FontWeight.W_600),
                            ft.Icon(ft.Icons.EXPAND_MORE_ROUNDED, size=16, color=p.on_primary)],
                           spacing=6, tight=True),
            bgcolor=p.primary, border_radius=20, padding=ft.Padding.symmetric(horizontal=16, vertical=9))
        return ft.PopupMenuButton(content=button, items=items, menu_position=ft.PopupMenuPosition.UNDER,
                                  tooltip=S.IMPORT_INTO_MODULE)

    def table_header(self) -> ft.Control:
        p, project = self.p, self.project
        names = list(project.samples)
        all_selected = bool(names) and self.selected >= set(names)

        def head(value, width, align=ft.Alignment.CENTER_LEFT):
            return ft.Container(content=ft.Text(value, size=th.SIZE_TINY, weight=ft.FontWeight.W_600, color=p.muted,
                                                max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                width=width, alignment=align, padding=ft.Padding.symmetric(horizontal=6))

        check = ft.Checkbox(value=all_selected, on_change=self.toggle_all, scale=0.85)
        return ft.Row([
            ft.Container(content=check, width=COL_CHECK),
            head(S.SAMPLE, COL_SAMPLE),
            *[head(f, COL_FIELD) for f in project.sample_fields],
            *[head(m.title, COL_COUNT, ft.Alignment.CENTER_RIGHT) for m in self.methods()],
            ft.Container(width=COL_MENU),
        ], spacing=0, height=32, vertical_alignment=ft.CrossAxisAlignment.CENTER)

    def sample_row(self, name: str) -> ft.Control:
        p, project = self.p, self.project
        sample = project.samples[name]
        counts = project.counts().get(name, {})
        selected = name in self.selected

        cells = [
            ft.Container(content=ft.Checkbox(value=selected, scale=0.85,
                                             on_change=lambda e, n=name: self.toggle(n, bool(e.control.value))),
                         width=COL_CHECK),
            ft.Container(content=w.text(name, p, th.SIZE_BODY, bold=True, max_lines=1), width=COL_SAMPLE,
                         padding=ft.Padding.symmetric(horizontal=6), tooltip=S.RENAME_SAMPLE,
                         on_click=self.later(self.rename_sample, name)),
        ]
        for f in project.sample_fields:
            cells.append(self.field_cell(name, f, sample.info.get(f, "")))
        for m in self.methods():
            n = counts.get(m.method, 0)
            text = ft.Text(str(n) if n else "—", size=th.SIZE_BODY, color=m.color_for(p.dark) if n else p.faint,
                           weight=ft.FontWeight.W_600 if n else None)
            cells.append(ft.Container(
                content=text, width=COL_COUNT, alignment=ft.Alignment.CENTER_RIGHT,
                padding=ft.Padding.symmetric(horizontal=6),
                on_click=(lambda e, k=m.key, s=name: self.workspace.open_module(k, {"sample": s}, reuse=True))
                if n else None,
                tooltip=S.OPEN_IN_MODULE.format(title=m.title, sample=name) if n else None))
        cells.append(ft.Container(width=COL_MENU, content=ft.PopupMenuButton(
            icon=ft.Icons.MORE_HORIZ_ROUNDED, icon_size=18, icon_color=p.faint, items=[
                ft.PopupMenuItem(content=S.RENAME_SAMPLE, icon=ft.Icons.EDIT_OUTLINED,
                                 on_click=self.later(self.rename_sample, name)),
                ft.PopupMenuItem(content=S.DELETE_SAMPLE, icon=ft.Icons.DELETE_OUTLINE,
                                 on_click=self.later(self.delete_samples, [name])),
            ])))
        row = ft.Row(cells, spacing=0, height=self.row_h, vertical_alignment=ft.CrossAxisAlignment.CENTER)
        return ft.Container(content=row, bgcolor=p.primary_weak if selected else None, border_radius=6,
                            border=ft.Border.only(bottom=ft.BorderSide(1, ft.Colors.with_opacity(0.6, p.border))))

    def field_cell(self, sample: str, field_name: str, value: str) -> ft.Control:
        p = self.p
        box = ft.Container(width=COL_FIELD, padding=ft.Padding.symmetric(horizontal=6), height=self.row_h,
                           alignment=ft.Alignment.CENTER_LEFT)
        if self.editing == (sample, field_name):
            def commit(e, s=sample, f=field_name):
                if self.editing != (s, f):
                    return
                self.editing = None
                new = (e.control.value or "").strip()
                if new != self.project.samples[s].info.get(f, ""):
                    self.project.set_sample_info(s, f, new)
                    self.session.changed("data")
                else:
                    self.redraw()

            box.content = ft.TextField(value=value, dense=True, autofocus=True, text_size=th.SIZE_BODY,
                                       content_padding=ft.Padding.symmetric(horizontal=8, vertical=6),
                                       on_submit=commit, on_blur=commit)
        else:
            box.content = ft.Text(value or "—", size=th.SIZE_BODY, color=p.text if value else p.faint, max_lines=1,
                                  overflow=ft.TextOverflow.ELLIPSIS)
            box.on_click = lambda e, s=sample, f=field_name: self.start_edit(s, f)
            box.tooltip = value or None
        return box

    # ============================================================
    # 数据检查
    # ============================================================
    def checks_card(self) -> ft.Control:
        p = self.p
        issues = data_issues(self.project)
        title = ft.Row([w.text(S.DATA_CHECK, p, th.SIZE_PANEL_TITLE, bold=True), w.chip(str(len(issues)), p)],
                       spacing=8)
        if not issues:
            rows = [w.muted(S.NO_ISSUES, p, th.SIZE_SMALL)]
        else:
            rows = []
            for issue in issues[:200]:
                warn = issue.level == WARNING
                rows.append(ft.Row([
                    ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED if warn else ft.Icons.INFO_OUTLINE, size=16,
                            color=p.warning if warn else p.primary),
                    ft.Text(spans=[ft.TextSpan(issue.title + S.TITLE_GAP, ft.TextStyle(weight=ft.FontWeight.W_600,
                                                                                color=p.text)),
                                   ft.TextSpan(issue.text, ft.TextStyle(color=p.muted))],
                            size=th.SIZE_SMALL, expand=True, selectable=True),
                ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.START))
        return w.panel(ft.Column([title, *rows], spacing=8, tight=True), p, padding=14)

    # ============================================================
    # 数据导出
    # ============================================================
    def export_card(self) -> ft.Control:
        p = self.p
        n = len(self.selected)
        if n == 0 and self.export_scope == "selected":
            self.export_scope = "all"
        scope = ft.RadioGroup(value=self.export_scope, on_change=self.set_scope, content=ft.Column([
            ft.Radio(value="selected", label=S.EXPORT_SELECTED.format(n=n), disabled=n == 0),
            ft.Radio(value="all", label=S.EXPORT_ALL),
        ], spacing=0, tight=True))
        fmt = ft.SegmentedButton(
            selected=[self.export_format], on_change=self.set_format, show_selected_icon=False,
            segments=[ft.Segment(value="xlsx", label="Excel (.xlsx)"), ft.Segment(value="csv", label="CSV")])
        components = ft.Checkbox(label=S.EXPORT_COMPONENTS, value=self.include_components,
                                 on_change=lambda e: setattr(self, "include_components", bool(e.control.value)))
        hint = S.EXPORT_HINT_EXCEL if self.export_format == "xlsx" else S.EXPORT_HINT_CSV
        has_data = len(self.project) > 0
        return w.panel(ft.Column([
            w.text(S.EXPORT_DATA, p, th.SIZE_PANEL_TITLE, bold=True),
            w.label(S.EXPORT_SCOPE, p), scope,
            w.label(S.EXPORT_FORMAT, p), fmt,
            w.label(S.EXPORT_CONTENT, p), components,
            w.faint(hint, p, th.SIZE_TINY),
            ft.Container(height=4),
            ft.FilledButton(S.EXPORT_BUTTON, icon=ft.Icons.DOWNLOAD_ROUNDED, on_click=self.export,
                            disabled=not has_data, width=268),
        ], spacing=8, tight=True), p, padding=16, width=300)

    def set_scope(self, e) -> None:
        self.export_scope = e.control.value or "all"

    def set_format(self, e) -> None:
        selected = e.control.selected or ["xlsx"]
        self.export_format = selected[0]
        self.redraw()

    def export_records(self):
        if self.export_scope == "selected" and self.selected:
            return [r for r in self.project.records.values() if r.sample in self.selected]
        return list(self.project.records.values())

    async def export(self, e=None) -> None:
        app, p = self.app, self.p
        records = self.export_records()
        if not records:
            toast(app.page, p, S.NOTHING_TO_EXPORT)
            return
        try:
            if self.export_format == "xlsx":
                path = await app.file_picker.save_file(
                    dialog_title=S.EXPORT_DATA, file_name=f"{self.project.name}.xlsx",
                    file_type=ft.FilePickerFileType.CUSTOM, allowed_extensions=["xlsx"])
                if not path:
                    return
                out = await asyncio.to_thread(export_excel, records, path,
                                              include_components=self.include_components, project=self.project,
                                              labels=S.EXPORT_LABELS, note_text=note_text)
                message = S.EXPORTED_EXCEL.format(path=short_path(out))
            else:
                folder = await app.file_picker.get_directory_path(dialog_title=S.EXPORT_DATA)
                if not folder:
                    return
                files = await asyncio.to_thread(export_csv, records, folder,
                                                include_components=self.include_components)
                message = S.EXPORTED_CSV.format(n=len(files), path=short_path(folder))
        except Exception as exc:  # noqa: BLE001 - 导出失败的原因显示给用户
            show_error(app.page, p, S.EXPORT_FAILED, str(exc), traceback.format_exc())
            return
        app.settings.export_format = self.export_format
        app.save_settings()
        self.workspace.set_status(message)
        toast(app.page, p, message)

    # ============================================================
    # 样品操作
    # ============================================================
    @staticmethod
    def later(fn, *args):
        """把需要等待对话框的协程包成点击事件的处理函数。"""
        async def handler(e):
            await fn(*args)
        return handler

    def toggle(self, name: str, value: bool) -> None:
        (self.selected.add if value else self.selected.discard)(name)
        self.after_selection()

    def toggle_all(self, e) -> None:
        self.selected = set(self.project.samples) if e.control.value else set()
        self.after_selection()

    def selection(self) -> str:
        n = len(self.selected)
        return S.SELECTED_SAMPLES.format(n=n, total=len(self.project.samples)) if n else ""

    def after_selection(self) -> None:
        self.export_scope = "selected" if self.selected else "all"
        self.redraw()
        self.workspace.set_status()

    def start_edit(self, sample: str, field_name: str) -> None:
        self.editing = (sample, field_name)
        self.redraw()

    def _validate_sample(self, current: str | None = None):
        """prompt_text 已经去掉首尾空白并拒绝空名，这里只检查重名。"""
        return lambda text: S.SAMPLE_EXISTS if text != current and text in self.project.samples else None

    async def add_sample(self, e=None) -> None:
        n = len(self.project.samples) + 1
        default = S.NEW_SAMPLE_NAME if S.NEW_SAMPLE_NAME not in self.project.samples else f"{S.NEW_SAMPLE_NAME} {n}"
        name = await prompt_text(self.app.page, self.p, S.ADD_SAMPLE, S.SAMPLE_NAME, default,
                                 validate=self._validate_sample())
        if name:
            self.project.add_sample(name)
            self.session.changed("data")

    async def add_field(self, e=None) -> None:
        name = await prompt_text(self.app.page, self.p, S.ADD_FIELD, S.FIELD_NAME,
                                 validate=lambda t: S.FIELD_EXISTS if t in self.project.sample_fields else None)
        if name:
            self.project.add_field(name)
            self.session.changed("data")

    async def rename_sample(self, old: str) -> None:
        name = await prompt_text(self.app.page, self.p, S.RENAME_SAMPLE, S.SAMPLE_NAME, old,
                                 validate=self._validate_sample(old))
        if name and name != old:
            self.project.rename_sample(old, name)
            if old in self.selected:
                self.selected.discard(old)
                self.selected.add(name)
            self.session.changed("data")

    async def delete_samples(self, names: list[str]) -> None:
        names = [n for n in names if n in self.project.samples]
        if not names:
            return
        count = sum(len(self.project.records_of(sample=n)) for n in names)
        label = names[0] if len(names) == 1 else S.SAMPLES_LABEL.format(first=names[0], n=len(names))
        if not await confirm(self.app.page, self.p, S.DELETE_SAMPLE, S.DELETE_SAMPLE_BODY.format(name=label, n=count),
                             S.DELETE, danger=True):
            return
        for n in names:
            self.project.remove_sample(n)
            self.selected.discard(n)
        self.session.changed("data")

    async def delete_selected(self, e=None) -> None:
        await self.delete_samples(sorted(self.selected))

    async def rename_project(self, e=None) -> None:
        name = await prompt_text(self.app.page, self.p, S.RENAME, S.PROJECT_NAME, self.project.name)
        if name:
            self.session.rename(name)
