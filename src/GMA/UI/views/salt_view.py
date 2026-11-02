# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
计算工具：熔盐配比。按各盐的摩尔分数和混合盐的总质量，计算每种盐要称多少（GMA.SC.Salts.salt_masses）。

左边是组成：从预设（内置几种常用组成，可以修改、另存为自己的预设，保存在设置中）开始，逐行填写化学式、
摩尔比例，需要时直接填写摩尔质量（如 ⁷Li 富集的 LiF）；右边是称量表，可以复制到 Excel 或实验记录中。
输入时立即重新计算，只更新结果，不重建输入框。
"""
from __future__ import annotations

import asyncio
import traceback
from pathlib import Path
from typing import ClassVar

import flet as ft

from ...SC.Salts import (
    MASS,
    MASS_PERCENT,
    MOLAR_MASS,
    MOLE_PERCENT,
    PRESETS,
    SALT,
    molar_mass,
    salt_masses,
)
from .. import theme as th
from ..components import widgets as w
from ..components.dialogs import confirm, prompt_text
from ..services import tools
from ..services.text import field_text, parse_number
from ..strings import S
from .tool_view import ToolView

LEFT_W = 470
NARROW = 920


def builtin_presets() -> list[dict]:
    return [{"name": name, "salts": [[salt, float(amount), None] for salt, amount in salts.items()]}
            for name, salts in PRESETS.items()]


def preset_rows(preset: dict) -> list[dict]:
    return [{"salt": salt, "amount": field_text(amount), "molar_mass": field_text(mass) if mass else ""}
            for salt, amount, mass in preset["salts"]]


class SaltView(ToolView):
    DEFAULTS: ClassVar[dict] = {
        "preset": "FLiNaK",
        "rows": preset_rows(builtin_presets()[0]),   # 输入框中的文字：{"salt", "amount", "molar_mass"}
        "total": 100.0,                             # 总质量（g）
    }

    def __init__(self, app, session, workspace, spec, state):
        super().__init__(app, session, workspace, spec, state)
        rows = [r for r in self.st["rows"] if isinstance(r, dict)]
        self.st["rows"] = [{k: str(r.get(k) or "") for k in ("salt", "amount", "molar_mass")} for r in rows] or \
            [{"salt": "", "amount": "", "molar_mass": ""}]
        self.table = None
        self.errors: list[str] = []
        self.composition: list[tuple[str, float]] = []
        self.overrides: dict[str, float] = {}
        self.width = None
        self.fields: list[tuple[ft.TextField, ft.TextField, ft.TextField]] = []
        self.result_box = ft.Column(spacing=10)
        self.sum_text = ft.Text("")
        self.modified = ft.Container()

    # ============================================================
    # 预设
    # ============================================================
    def presets(self) -> list[dict]:
        saved = self.app.settings.salt_presets
        return builtin_presets() if saved is None else saved

    def preset(self, name: str | None) -> dict | None:
        return next((p for p in self.presets() if p["name"] == name), None)

    def is_modified(self) -> bool:
        preset = self.preset(self.st["preset"])
        if preset is None:
            return True
        return self.signature(self.st["rows"]) != self.signature(preset_rows(preset))

    @staticmethod
    def signature(rows: list[dict]) -> list[tuple]:
        def number(text):
            try:
                return round(parse_number(text), 9) if str(text).strip() else None
            except ValueError:
                return str(text)
        return [(r["salt"].strip(), number(r["amount"]), number(r["molar_mass"])) for r in rows
                if r["salt"].strip() or r["amount"].strip() or r["molar_mass"].strip()]

    def apply_preset(self, name: str) -> None:
        preset = self.preset(name)
        if preset is None:
            return
        self.touch()
        self.st["preset"] = name
        self.st["rows"] = preset_rows(preset)
        self.redraw()

    async def save_preset(self) -> None:
        settings = self.app.settings
        names = [p["name"] for p in self.presets()]
        name = await prompt_text(self.app.page, self.p, S.SALT_SAVE_PRESET.rstrip("…"), S.SALT_PRESET_NAME,
                                 self.st["preset"] or "")
        if not name:
            return
        if name in names and not await confirm(self.app.page, self.p, S.SALT_SAVE_PRESET.rstrip("…"),
                                               S.SALT_PRESET_EXISTS.format(name=name)):
            return
        composition, overrides, errors = tools.salt_rows(self.st["rows"])
        if errors or not composition:
            self.app.toast(errors[0] if errors else S.SALT_EMPTY)
            return
        entry = {"name": name, "salts": [[salt, amount, overrides.get(salt)] for salt, amount in composition]}
        presets = [dict(p) for p in self.presets()]
        index = next((i for i, p in enumerate(presets) if p["name"] == name), None)
        if index is None:
            presets.append(entry)
        else:
            presets[index] = entry
        settings.salt_presets = presets
        self.app.save_settings()
        self.st["preset"] = name
        self.redraw()
        self.app.toast(S.SALT_PRESET_SAVED.format(name=name))

    async def delete_preset(self) -> None:
        name = self.st["preset"]
        if self.preset(name) is None or not await confirm(self.app.page, self.p, S.DELETE,
                                                          S.SALT_DELETE_PRESET_BODY.format(name=name), S.DELETE,
                                                          danger=True):
            return
        self.app.settings.salt_presets = [p for p in self.presets() if p["name"] != name]
        self.app.save_settings()
        self.st["preset"] = None
        self.redraw()
        self.app.toast(S.SALT_PRESET_DELETED.format(name=name))

    async def restore_presets(self) -> None:
        if not await confirm(self.app.page, self.p, S.SALT_RESTORE_PRESETS, S.SALT_RESTORE_BODY):
            return
        self.app.settings.salt_presets = None
        self.app.save_settings()
        self.redraw()
        self.app.toast(S.SALT_PRESETS_RESTORED)

    # ============================================================
    # 计算
    # ============================================================
    def compute(self) -> None:
        composition, overrides, errors = tools.salt_rows(self.st["rows"])
        self.errors, self.table = errors, None
        self.composition, self.overrides = composition, overrides
        if errors:   # 有填错的行时不给出结果，以免少称一种盐
            return
        if not composition:
            self.errors = [S.SALT_EMPTY]
            return
        try:
            self.table = salt_masses(composition, self.st["total"], molar_masses=overrides)
        except ValueError as exc:
            self.errors.append(S.SALT_ZERO if "add up to zero" in str(exc) else str(exc))

    # ============================================================
    # 界面
    # ============================================================
    def build(self) -> ft.Control:
        self.compute()
        width = self.width or (self.app.page.width or 1400) - 24
        narrow = width < NARROW
        self.sum_text = ft.Text("", size=th.SIZE_SMALL, color=self.p.muted)
        self.modified = ft.Container()
        left = self.card(S.SALT_COMPOSITION, self.composition_controls(), width=None if narrow else LEFT_W,
                         fill=not narrow)
        footer = ft.Row([
            ft.OutlinedButton(S.COPY_CODE, icon=ft.Icons.CODE_ROUNDED, on_click=self.copy_code),
            ft.OutlinedButton(S.SALT_COPY_TABLE, icon=ft.Icons.CONTENT_COPY_ROUNDED, on_click=self.copy_table),
            ft.FilledButton(S.EXPORT_BUTTON, icon=ft.Icons.DOWNLOAD_ROUNDED, on_click=self.export),
        ], spacing=8, alignment=ft.MainAxisAlignment.END, wrap=True)
        right = self.card(S.SALT_WEIGH, [self.result_box], expand=not narrow, footer=footer, fill=not narrow)
        self.refresh_results(update=False)
        if narrow:
            body = ft.Column([left, right], spacing=12, scroll=ft.ScrollMode.AUTO, expand=True)
        else:
            body = ft.Row([left, right], spacing=12, expand=True, vertical_alignment=ft.CrossAxisAlignment.STRETCH)
        return ft.Container(content=body, padding=12, expand=True, on_size_change=self.on_size,
                            size_change_interval=200)

    def on_size(self, e: ft.LayoutSizeChangeEvent) -> None:
        old, self.width = self.width, e.width
        if old is not None and (old < NARROW) != (e.width < NARROW):
            self.redraw()

    def composition_controls(self) -> list[ft.Control]:
        p = self.p
        names = [preset["name"] for preset in self.presets()]
        current = self.st["preset"] if self.st["preset"] in names else None
        menu = ft.PopupMenuButton(icon=ft.Icons.MORE_HORIZ_ROUNDED, icon_color=p.muted, tooltip=S.SALT_PRESET_MENU,
                                  items=[
                                      ft.PopupMenuItem(content=ft.Text(S.SALT_SAVE_PRESET, size=th.SIZE_BODY),
                                                       on_click=lambda e: self.app.page.run_task(self.save_preset)),
                                      ft.PopupMenuItem(content=ft.Text(S.SALT_DELETE_PRESET.format(name=current or "—"),
                                                                       size=th.SIZE_BODY),
                                                       disabled=current is None,
                                                       on_click=lambda e: self.app.page.run_task(self.delete_preset)),
                                      ft.PopupMenuItem(),
                                      ft.PopupMenuItem(content=ft.Text(S.SALT_RESTORE_PRESETS, size=th.SIZE_BODY),
                                                       on_click=lambda e: self.app.page.run_task(self.restore_presets)),
                                  ])
        preset = ft.Row([
            ft.Text(S.SALT_PRESET, size=th.SIZE_BODY, color=p.muted),
            ft.Dropdown(value=current, width=190, dense=True, text_size=th.SIZE_BODY,
                        options=[ft.DropdownOption(key=n, text=n) for n in names],
                        on_select=lambda e: self.apply_preset(e.control.value)),
            self.modified, ft.Container(expand=True), menu,
        ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER)
        head = ft.Row([
            ft.Text(S.SALT_FORMULA, size=th.SIZE_SMALL, color=p.muted, width=130),
            ft.Text(S.SALT_AMOUNT, size=th.SIZE_SMALL, color=p.muted, width=100, tooltip=S.SALT_AMOUNT_TIP),
            ft.Text(S.SALT_MOLAR_MASS, size=th.SIZE_SMALL, color=p.muted, width=130, tooltip=S.SALT_MOLAR_MASS_TIP),
        ], spacing=8)
        self.fields = []
        rows = [self.row_control(i, row) for i, row in enumerate(self.st["rows"])]
        add = w.ghost_button(S.SALT_ADD, ft.Icons.ADD_ROUNDED, lambda e: self.add_row(), p)
        total = self.number_field(self.st["total"], self.set_total, label=S.SALT_TOTAL_MASS, suffix="g", width=200)
        return [preset, head, ft.Column(rows, spacing=6, tight=True), ft.Row([add, ft.Container(expand=True),
                                                                              self.sum_text]),
                w.hsep(p), total, w.faint(S.SALT_NOTE, p, th.SIZE_TINY)]

    def row_control(self, index: int, row: dict) -> ft.Control:
        p = self.p

        def field(key, width, hint=None, tooltip=None, number=False):
            def on_change(e):
                self.st["rows"][index][key] = e.control.value or ""
                self.touch()
                if key == "salt":
                    self.update_hint(index)
                self.refresh_results()
            return ft.TextField(value=row[key], width=width, dense=True, text_size=th.SIZE_BODY, hint_text=hint,
                                tooltip=tooltip, on_change=on_change,
                                keyboard_type=ft.KeyboardType.NUMBER if number else None,
                                content_padding=ft.Padding.symmetric(horizontal=10, vertical=9))

        salt = field("salt", 130)
        amount = field("amount", 100, number=True)
        mass = field("molar_mass", 130, tooltip=S.SALT_MOLAR_MASS_TIP, number=True)
        self.fields.append((salt, amount, mass))
        self.update_hint(index, update=False)
        return ft.Row([salt, amount, mass,
                       w.icon_button(ft.Icons.REMOVE_CIRCLE_OUTLINE_ROUNDED, S.SALT_REMOVE,
                                     lambda e: self.remove_row(index), p, size=17)],
                      spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER)

    def update_hint(self, index: int, update: bool = True) -> None:
        """摩尔质量框的提示：按化学式算出的值（留空时使用）。"""
        mass = self.fields[index][2]
        try:
            mass.hint_text = f"{molar_mass(self.st['rows'][index]['salt']):.3f}"
        except ValueError:
            mass.hint_text = ""
        if update and mass.page is not None:
            mass.update()

    def add_row(self) -> None:
        self.touch()
        self.st["rows"].append({"salt": "", "amount": "", "molar_mass": ""})
        self.redraw()

    def remove_row(self, index: int) -> None:
        self.touch()
        del self.st["rows"][index]
        if not self.st["rows"]:
            self.st["rows"] = [{"salt": "", "amount": "", "molar_mass": ""}]
        self.redraw()

    def set_total(self, value: float) -> None:
        if value != self.st["total"]:
            self.touch()
        self.st["total"] = value
        self.refresh_results()

    # ---------- 结果 ----------
    def refresh_results(self, update: bool = True) -> None:
        self.compute()
        p = self.p
        controls: list[ft.Control] = [self.note(e, p.error, ft.Icons.ERROR_OUTLINE_ROUNDED) for e in self.errors]
        if self.table is not None:
            controls.insert(0, self.result_table())
        self.result_box.controls = controls
        total = sum(amount for _, amount in self.composition)
        if total and abs(total - 100) < 1e-6:
            self.sum_text.value = S.SALT_SUM_PERCENT.format(value=f"{total:g}")
        elif total:
            self.sum_text.value = S.SALT_SUM_RATIO.format(value=f"{total:g}")
        else:
            self.sum_text.value = ""
        self.modified.content = w.chip(S.SALT_PRESET_MODIFIED, p) if self.is_modified() else None
        if update:
            for c in (self.result_box, self.sum_text, self.modified):
                if c.page is not None:
                    c.update()

    def result_table(self) -> ft.Control:
        p, table = self.p, self.table
        widths = [110, 140, 140, 130, 120]
        heads = [S.SALT_COL_SALT, S.SALT_COL_MOLE, S.SALT_COL_MOLAR_MASS, S.SALT_COL_MASS_PERCENT, S.SALT_COL_MASS]

        def cells(values, *, header=False, strong=False):
            out = []
            for i, (value, width) in enumerate(zip(values, widths, strict=True)):
                out.append(ft.Container(width=width, padding=ft.Padding.symmetric(horizontal=10, vertical=8),
                                        alignment=ft.Alignment.CENTER_LEFT if i == 0 else ft.Alignment.CENTER_RIGHT,
                                        content=ft.Text(value, size=th.SIZE_SMALL if header else th.SIZE_BODY,
                                                        color=p.muted if header else p.text, selectable=not header,
                                                        weight=ft.FontWeight.W_600 if header or strong or i == 4
                                                        else None)))
            return ft.Row(out, spacing=0)

        rows = [ft.Container(content=cells(heads, header=True), bgcolor=p.subtle)]
        for r in table.itertuples(index=False):
            v = dict(zip(table.columns, r, strict=True))
            rows.append(cells([v[SALT], f"{v[MOLE_PERCENT]:.4g}", f"{v[MOLAR_MASS]:.3f}", f"{v[MASS_PERCENT]:.3f}",
                               f"{v[MASS]:.4f}"]))
            rows.append(w.hsep(p))
        rows.append(cells([S.SALT_TOTAL, f"{table[MOLE_PERCENT].sum():.4g}", "", f"{table[MASS_PERCENT].sum():.3f}",
                           f"{table[MASS].sum():.4f}"], strong=True))
        return ft.Container(content=ft.Row([ft.Column(rows, spacing=0, tight=True)], scroll=ft.ScrollMode.AUTO),
                            border=ft.Border.all(1, p.border), border_radius=th.RADIUS_CONTROL,
                            clip_behavior=ft.ClipBehavior.HARD_EDGE)

    # ============================================================
    # 复制、导出
    # ============================================================
    async def copy_table(self, e=None) -> None:
        if self.table is None:
            self.app.toast(self.errors[0] if self.errors else S.SALT_EMPTY)
            return
        await self.app.clipboard.set(tools.salt_table_text(self.table))
        self.app.toast(S.SALT_TABLE_COPIED)

    async def copy_code(self, e=None) -> None:
        if self.table is None:
            self.app.toast(self.errors[0] if self.errors else S.SALT_EMPTY)
            return
        await self.app.clipboard.set(tools.salt_code(self.composition, self.st["total"], self.overrides))
        self.app.toast(S.CODE_COPIED)

    async def export(self, e=None) -> None:
        if self.table is None:
            self.app.toast(self.errors[0] if self.errors else S.SALT_EMPTY)
            return
        fmt = "csv" if self.app.settings.export_format == "csv" else "xlsx"
        name = tools.safe_name(self.st["preset"] or S.SALT_DEFAULT_NAME)
        path = await self.app.file_picker.save_file(dialog_title=S.EXPORT_BUTTON.rstrip("…"), file_name=f"{name}.{fmt}",
                                                    file_type=ft.FilePickerFileType.CUSTOM,
                                                    allowed_extensions=["xlsx", "csv"])
        if not path:
            return
        path = Path(path)
        if path.suffix.lower() not in (".xlsx", ".csv"):
            path = path.with_name(f"{path.name}.{fmt}")
        info = [("Preset", self.st["preset"] or "—"), ("Total mass (g)", f"{self.st['total']:g}"),
                ("Atomic weights", "IUPAC standard atomic weights (conventional values)")]
        try:
            await asyncio.to_thread(tools.export_salts, self.table, path, info)
        except Exception as exc:  # noqa: BLE001
            self.app.show_error(S.EXPORT_FAILED, str(exc), traceback.format_exc())
            return
        self.app.toast(S.EXPORTED_TO.format(path=path))
