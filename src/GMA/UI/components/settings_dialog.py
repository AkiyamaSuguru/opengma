# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
设置对话框：左侧是分类，右侧是选项（方案 10.1）。改动立即生效并保存到 settings.json。

绘图、数据两类是默认值，P3 起在模块和出版图对话框中使用；每个标签中的设置优先。
"""
from __future__ import annotations

import flet as ft

from ...CM.Raman.loader import READERS as RAMAN_READERS
from ...CM.XPS.loader import READERS as XPS_READERS
from ...CM.XRD.loader import READERS as XRD_READERS
from .. import theme as th
from ..services.figures import FIGURE_FONTS
from ..services.text import short_path
from ..strings import S
from . import widgets as w
from .dialogs import close, show

READERS = {"XPS": list(XPS_READERS), "Raman": list(RAMAN_READERS), "XRD": list(XRD_READERS)}
CATEGORIES = [("appearance", S.SETTINGS_APPEARANCE, ft.Icons.PALETTE_OUTLINED),
              ("window", S.SETTINGS_WINDOW, ft.Icons.WEB_ASSET_OUTLINED),
              ("plot", S.SETTINGS_PLOT, ft.Icons.SHOW_CHART_ROUNDED),
              ("data", S.SETTINGS_DATA, ft.Icons.DATASET_OUTLINED),
              ("general", S.SETTINGS_GENERAL, ft.Icons.TUNE_ROUNDED)]
FONTS = list(FIGURE_FONTS)
COLOR_CYCLES = ["tab10", "tab20", "Set1", "Set2", "Dark2", "Paired"]


class SettingsDialog:
    def __init__(self, app):
        self.app = app
        self.s = app.settings
        self.category = "appearance"
        self.right = ft.Container(expand=True)
        self.nav = ft.Column(spacing=2, width=132)
        self.dialog: ft.AlertDialog | None = None

    def show(self) -> None:
        p, page = self.app.p, self.app.page
        self.refresh(update=False)
        self.dialog = ft.AlertDialog(
            bgcolor=p.panel, shape=ft.RoundedRectangleBorder(radius=th.RADIUS_PANEL),
            title=ft.Text(S.SETTINGS, size=16, weight=ft.FontWeight.W_600, color=p.text),
            content=ft.Container(width=660, height=420, content=ft.Row(
                [self.nav, w.vsep(p, 400), self.right], spacing=16, vertical_alignment=ft.CrossAxisAlignment.START)),
            actions=[ft.Row([w.faint(S.SETTINGS_SAVED_HINT.format(path=short_path(self.app.settings_file)), p),
                             ft.Container(expand=True),
                             ft.FilledButton(S.CLOSE, on_click=lambda e: close(self.dialog))])],
        )
        show(page, self.dialog)

    # ============================================================
    # 结构
    # ============================================================
    def refresh(self, update: bool = True) -> None:
        p = self.app.p
        self.nav.controls = []
        for key, title, icon in CATEGORIES:
            selected = key == self.category
            self.nav.controls.append(w.hoverable(
                ft.Row([ft.Icon(icon, size=17, color=p.primary if selected else p.muted),
                        ft.Text(title, size=th.SIZE_BODY, color=p.text if selected else p.muted,
                                weight=ft.FontWeight.W_600 if selected else None)], spacing=10),
                p, on_click=lambda e, k=key: self.select(k), base_color=p.primary_weak if selected else None,
                padding=ft.Padding.symmetric(horizontal=10, vertical=8)))
        builder = getattr(self, f"page_{self.category}")
        self.right.content = ft.Column(builder(), spacing=14, scroll=ft.ScrollMode.AUTO, expand=True)
        if update:
            self.nav.update()
            self.right.update()

    def select(self, key: str) -> None:
        self.category = key
        self.refresh()

    def changed(self, *, theme: bool = False) -> None:
        """保存设置；主题相关的改动立即应用到界面（对话框随之按新颜色重画）。"""
        self.app.save_settings()
        if theme:
            self.app.apply_theme()
            close(self.dialog)
            self.show()

    # ---------- 小部件 ----------
    def row(self, title: str, control: ft.Control, hint: str | None = None) -> ft.Control:
        p = self.app.p
        parts = [w.text(title, p, th.SIZE_BODY, bold=True), control]
        if hint:
            parts.append(w.faint(hint, p))
        return ft.Column(parts, spacing=6, tight=True)

    def segmented(self, attr: str, options: list[tuple[str, str]], *, theme: bool = False) -> ft.Control:
        def on_change(e):
            value = (e.control.selected or [getattr(self.s, attr)])[0]
            setattr(self.s, attr, value)
            self.changed(theme=theme)
        return ft.SegmentedButton(selected=[getattr(self.s, attr)], show_selected_icon=False, on_change=on_change,
                                  segments=[ft.Segment(value=v, label=t) for v, t in options])

    def switch(self, attr: str, label: str) -> ft.Control:
        def on_change(e):
            setattr(self.s, attr, bool(e.control.value))
            self.changed()
        return ft.Switch(label=label, value=getattr(self.s, attr), on_change=on_change)

    def dropdown(self, value: str, options: list[str], on_select, width: float = 220, labels=None) -> ft.Control:
        return ft.Dropdown(value=value, width=width, dense=True, text_size=th.SIZE_BODY, on_select=on_select,
                           options=[ft.DropdownOption(key=o, text=(labels or {}).get(o, o)) for o in options])

    def number(self, value, on_done, width: float = 90, suffix: str | None = None) -> ft.Control:
        def done(e):
            try:
                on_done(float(e.control.value))
                e.control.error = None
            except ValueError:
                e.control.error = S.NUMBER_REQUIRED
            e.control.update()
        return ft.TextField(value=f"{value:g}", width=width, dense=True, text_size=th.SIZE_BODY, suffix=suffix,
                            on_submit=done, on_blur=done, keyboard_type=ft.KeyboardType.NUMBER)

    # ============================================================
    # 各个分类
    # ============================================================
    def page_appearance(self) -> list[ft.Control]:
        p = self.app.p
        swatches = []
        for name, color in th.PRESETS:
            chosen = self.s.primary.upper() == color

            def pick(e, c=color):
                self.s.primary = c
                self.changed(theme=True)

            swatches.append(ft.Container(
                width=30, height=30, border_radius=99, bgcolor=color, tooltip=f"{name} {color}", on_click=pick,
                border=ft.Border.all(3, p.text if chosen else p.panel),
                content=ft.Icon(ft.Icons.CHECK_ROUNDED, size=16, color="#FFFFFF") if chosen else None,
                alignment=ft.Alignment.CENTER))

        def custom(e):
            value = (e.control.value or "").strip().upper()
            if not value.startswith("#"):
                value = "#" + value
            if not th.is_hex(value):
                e.control.error = S.INVALID_COLOR
                e.control.update()
                return
            if value == self.s.primary.upper():
                return
            self.s.primary = value
            self.changed(theme=True)

        custom_field = ft.TextField(value=self.s.primary, width=130, dense=True, text_size=th.SIZE_BODY,
                                    on_submit=custom, on_blur=custom, hint_text="#RRGGBB",
                                    prefix=ft.Container(width=14, height=14, border_radius=4,
                                                        bgcolor=self.s.primary, margin=ft.Margin.only(right=6)))
        custom_row = ft.Row([w.muted(S.CUSTOM_COLOR, p, th.SIZE_SMALL), custom_field], spacing=10,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER)
        return [
            self.row(S.THEME, self.segmented("theme_mode", [("system", S.SYSTEM), ("light", S.LIGHT), ("dark", S.DARK)],
                                             theme=True)),
            self.row(S.PRIMARY_COLOR, ft.Column([ft.Row(swatches, spacing=8), custom_row], spacing=10, tight=True)),
            self.row(S.DENSITY, self.segmented("density", [("standard", S.DENSITY_STANDARD),
                                                           ("compact", S.DENSITY_COMPACT)], theme=True)),
        ]

    def page_window(self) -> list[ft.Control]:
        def ratio_row(attr: str, title: str) -> ft.Control:
            values = getattr(self.s, attr)

            def setter(i):
                def apply(v):
                    if not 10 <= v <= 100:
                        raise ValueError
                    values[i] = v / 100
                    self.changed()
                return apply
            return self.row(title, ft.Row([self.number(values[0] * 100, setter(0), suffix="%"),
                                           ft.Text("×", color=self.app.p.muted),
                                           self.number(values[1] * 100, setter(1), suffix="%")], spacing=8))
        return [ratio_row("launcher_ratio", S.LAUNCHER_SIZE), ratio_row("workspace_ratio", S.WORKSPACE_SIZE),
                self.switch("remember_size", S.REMEMBER_SIZE)]

    def page_plot(self) -> list[ft.Control]:
        s = self.s

        def setter(attr, cast=str):
            def on_select(e):
                setattr(s, attr, cast(e.control.value))
                self.changed()
            return on_select

        def set_number(attr, cast):
            def apply(v):
                if v <= 0:
                    raise ValueError
                setattr(s, attr, cast(v))
                self.changed()
            return apply

        fonts = FONTS if s.figure_font in FONTS else [s.figure_font, *FONTS]
        return [
            self.row(S.FIGURE_FONT, ft.Row([self.dropdown(s.figure_font, fonts, setter("figure_font")),
                                            self.number(s.figure_font_size, set_number("figure_font_size", float),
                                                        suffix="pt")], spacing=10)),
            self.row(S.COLOR_CYCLE, self.dropdown(s.color_cycle, COLOR_CYCLES, setter("color_cycle"))),
            self.row(S.EXPORT_DPI_FORMAT, ft.Row([
                self.dropdown(str(s.dpi), ["300", "600", "1200"], setter("dpi", int), width=120),
                self.dropdown(s.figure_format, ["png", "svg", "pdf", "tiff", "jpg"], setter("figure_format"),
                              width=120)], spacing=10)),
            self.switch("latex", S.USE_LATEX),
            ft.Row([self.switch("decimate", S.DECIMATE),
                    self.number(s.decimate_points, set_number("decimate_points", int), width=110)], spacing=12),
        ]

    def page_data(self) -> list[ft.Control]:
        s = self.s
        rows = []
        for method, readers in READERS.items():
            def on_select(e, m=method):
                s.readers[m] = e.control.value
                self.changed()
            rows.append(self.row(S.DEFAULT_READER.format(method=method),
                                 self.dropdown(s.readers.get(method, readers[0]), readers, on_select)))
        rows.append(self.row(S.COMPONENT_MODE, self.segmented(
            "component_mode", [("absolute", S.COMPONENT_ABSOLUTE), ("relative", S.COMPONENT_RELATIVE)])))
        rows.append(self.row(S.EXPORT_DEFAULT, self.segmented("export_format", [("xlsx", "Excel"), ("csv", "CSV")])))
        return rows

    def page_general(self) -> list[ft.Control]:
        s = self.s

        def set_limit(e):
            s.recent_limit = int(e.control.value)
            del s.recent[s.recent_limit:]
            self.changed()

        return [
            self.row(S.CLOSE_WORKSPACE, self.segmented("close_workspace", [("launcher", S.CLOSE_TO_LAUNCHER),
                                                                            ("quit", S.CLOSE_TO_QUIT)])),
            self.row(S.ON_STARTUP, self.segmented("startup", [("launcher", S.STARTUP_LAUNCHER),
                                                               ("last_project", S.STARTUP_LAST)])),
            self.row(S.RECENT_LIMIT, self.dropdown(str(s.recent_limit), ["3", "5", "10"], set_limit, width=120)),
            self.row(S.LANGUAGE, self.dropdown("zh", ["zh"], lambda e: None, width=120, labels={"zh": S.LANGUAGE_ZH})),
        ]
