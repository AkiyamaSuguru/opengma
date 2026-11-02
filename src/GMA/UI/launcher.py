# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
启动器：应用名、浅色 / 深色切换、设置、关于；模块区（可以左右滑动，也可以展开全部模块）；最近项目。

点击模块卡片新建一个空项目并打开该模块；点击最近项目打开它，恢复上次的标签和停留的模块。
规划中的模块显示为灰色并标“规划中”（Q21）。
"""
from __future__ import annotations

from pathlib import Path

import flet as ft

from . import theme as th
from .components import widgets as w
from .services.text import app_version, short_path, when
from .settings import RecentProject
from .strings import S
from .views import registry
from .views.registry import ModuleSpec

CARD_W, CARD_H, CARD_GAP = 148, 128, 10


class Launcher:
    def __init__(self, app):
        self.app = app
        self.lane: ft.Row | None = None

    # ============================================================
    # 整体
    # ============================================================
    def build(self) -> ft.Control:
        p = self.app.p
        body = ft.Column([
            ft.Row([w.label(S.MODULES, p), ft.Container(expand=True),
                    w.ghost_button(S.ALL_MODULES, ft.Icons.GRID_VIEW_ROUNDED, self.show_all_modules, p)]),
            self.module_lane(),
            ft.Container(height=6),
            ft.Row([w.label(S.RECENT, p), ft.Container(expand=True),
                    w.ghost_button(S.OPEN_PROJECT, ft.Icons.FOLDER_OPEN_OUTLINED, self.open_project, p)]),
            self.recent_list(),
        ], spacing=8, expand=True, scroll=ft.ScrollMode.AUTO)
        return ft.Container(expand=True, bgcolor=p.panel, content=ft.Column([
            self.header(),
            ft.Container(content=body, expand=True, padding=ft.Padding.only(left=22, right=22, top=14, bottom=8)),
            self.footer(),
        ], spacing=0, expand=True))

    def header(self) -> ft.Control:
        p = self.app.p
        theme_icon = ft.Icons.LIGHT_MODE_OUTLINED if p.dark else ft.Icons.DARK_MODE_OUTLINED
        return ft.Container(
            height=58, padding=ft.Padding.only(left=18, right=10),
            border=ft.Border.only(bottom=ft.BorderSide(1, p.border)),
            content=ft.Row([
                w.app_icon(30),
                ft.Column([w.text(S.APP_NAME, p, 15, bold=True), w.muted(S.APP_TAGLINE, p, 11)],
                          spacing=0, tight=True, alignment=ft.MainAxisAlignment.CENTER),
                ft.Container(expand=True),
                w.icon_button(theme_icon, S.TOGGLE_THEME, self.app.toggle_theme, p),
                w.icon_button(ft.Icons.SETTINGS_OUTLINED, S.SETTINGS, self.app.open_settings, p),
                w.icon_button(ft.Icons.INFO_OUTLINE, S.ABOUT, self.app.open_about, p),
            ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER))

    def footer(self) -> ft.Control:
        p = self.app.p

        async def open_repo(e):
            await self.app.open_url()

        return ft.Container(
            height=32, padding=ft.Padding.symmetric(horizontal=22),
            border=ft.Border.only(top=ft.BorderSide(1, p.border)), bgcolor=p.bg if p.dark else "#FAFBFC",
            content=ft.Row([
                w.faint(f"v{app_version()} · AGPL-3.0-only", p, 10.5), ft.Container(expand=True),
                ft.Container(content=w.faint("github.com/AkiyamaSuguru/opengma", p, 10.5), on_click=open_repo,
                             tooltip=S.HOMEPAGE),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER))

    # ============================================================
    # 模块区
    # ============================================================
    def module_card(self, spec: ModuleSpec) -> ft.Control:
        p = self.app.p
        badge = [ft.Container(expand=True), w.chip(S.PLANNED, p)] if spec.planned else []
        content = ft.Column([
            ft.Row([w.module_tile(spec, p.dark), *badge], vertical_alignment=ft.CrossAxisAlignment.START),
            w.text(spec.title, p, 14, bold=True, max_lines=1),
            ft.Text(spec.description, size=11, color=p.muted, max_lines=2),
        ], spacing=6)
        card = ft.Container(
            content=content, width=CARD_W, height=CARD_H, padding=12, bgcolor=p.panel,
            border=ft.Border.all(1, p.border), border_radius=th.RADIUS_PANEL, opacity=0.55 if spec.planned else 1,
            tooltip=S.PLANNED if spec.planned else None, animate=ft.Animation(150, ft.AnimationCurve.EASE_OUT))

        if not spec.planned:
            async def on_click(e, key=spec.key):
                await self.app.new_project(key)

            def on_hover(e):
                hovered = e.data in (True, "true")
                card.bgcolor = p.primary_weak if hovered else p.panel
                card.border = ft.Border.all(1, p.primary if hovered else p.border)
                card.update()

            card.on_click, card.on_hover = on_click, on_hover
        return card

    def module_lane(self) -> ft.Control:
        """模块卡片排成一行，可以左右滑动（触控板、Shift+滚轮或两侧的箭头）；箭头只在还能滑动时显示。"""
        p = self.app.p
        content_width = len(registry.MODULES) * (CARD_W + CARD_GAP) - CARD_GAP
        step = 2 * (CARD_W + CARD_GAP)

        def arrow(icon, tooltip, delta, **position):
            async def on_click(e):
                await self.lane.scroll_to(delta=delta, duration=250)
            return ft.Container(
                content=ft.Icon(icon, size=18, color=p.muted), width=32, height=32, border_radius=99,
                bgcolor=p.panel, border=ft.Border.all(1, p.border), alignment=ft.Alignment.CENTER,
                on_click=on_click, tooltip=tooltip, top=52, **position,
                shadow=ft.BoxShadow(blur_radius=8, color=ft.Colors.with_opacity(0.15, "#000000")))

        left = arrow(ft.Icons.CHEVRON_LEFT_ROUNDED, S.SCROLL_LEFT, -step, left=0)
        right = arrow(ft.Icons.CHEVRON_RIGHT_ROUNDED, S.SCROLL_RIGHT, step, right=0)
        left.visible = False

        def on_scroll(e: ft.OnScrollEvent):
            left.visible = e.pixels > 1
            right.visible = e.pixels < e.max_scroll_extent - 1
            left.update()
            right.update()

        def on_size(e: ft.LayoutSizeChangeEvent):
            if not left.visible:
                right.visible = e.width < content_width
                right.update()

        self.lane = ft.Row([self.module_card(m) for m in registry.MODULES], spacing=CARD_GAP,
                           scroll=ft.ScrollMode.HIDDEN, on_scroll=on_scroll, scroll_interval=50)
        return ft.Stack([
            ft.Container(content=self.lane, padding=ft.Padding.symmetric(vertical=4), on_size_change=on_size),
            left, right,
        ], height=CARD_H + 10)

    def show_all_modules(self, e=None) -> None:
        """“全部模块”：按“表征方法”“计算工具”分组的网格。"""
        p, page = self.app.p, self.app.page
        sections = []
        for category, modules in registry.by_category().items():
            if not modules:
                continue
            sections.append(w.label(registry.CATEGORY_TITLES[category], p))
            sections.append(ft.Row([self.module_card(m) for m in modules], wrap=True, spacing=CARD_GAP,
                                   run_spacing=CARD_GAP))
        dialog = ft.AlertDialog(
            modal=False, bgcolor=p.panel, shape=ft.RoundedRectangleBorder(radius=th.RADIUS_PANEL),
            title=ft.Text(S.ALL_MODULES, size=16, weight=ft.FontWeight.W_600, color=p.text),
            content=ft.Container(width=3 * CARD_W + 2 * CARD_GAP + 4,
                                 content=ft.Column(sections, spacing=10, tight=True, scroll=ft.ScrollMode.AUTO)),
            actions=[ft.TextButton(S.CLOSE, on_click=lambda e: page.pop_dialog())])
        page.show_dialog(dialog)

    # ============================================================
    # 最近项目
    # ============================================================
    def recent_list(self) -> ft.Control:
        p = self.app.p
        items = self.app.settings.recent[: self.app.settings.recent_limit]
        if not items:
            return ft.Container(content=w.faint(S.NO_RECENT, p, th.SIZE_SMALL), padding=ft.Padding.only(top=4))
        return ft.Column([self.recent_row(r) for r in items], spacing=0)

    def recent_row(self, r: RecentProject) -> ft.Control:
        p = self.app.p
        missing = not r.exists
        path = Path(r.path)
        keys = r.modules or ([r.active] if r.active else [])
        icons = [w.module_icon(spec, p.dark, 14) for spec in (registry.get(k) for k in keys[:4]) if spec]
        name_color = p.faint if missing else p.text

        async def open_it(e):
            await self.app.open_project(r.path)

        def remove(e):
            self.app.settings.remove_recent(r.path)
            self.app.save_settings()
            self.app.rebuild()

        row = ft.Row([
            ft.Icon(ft.Icons.DESCRIPTION_OUTLINED, size=16, color=p.faint if missing else p.muted),
            ft.Text(path.name, size=12.5, weight=ft.FontWeight.W_600, color=name_color, max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS),
            ft.Text(S.FILE_MISSING if missing else short_path(path.parent), size=11, color=p.faint, max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS, expand=True),
            ft.Row(icons, spacing=5, tight=True),
            w.faint(when(r.opened_at), p, 11),
            w.icon_button(ft.Icons.CLOSE_ROUNDED, S.REMOVE_FROM_LIST, remove, p, size=14, color=p.faint),
        ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER)
        return w.hoverable(row, p, on_click=None if missing else open_it, disabled=missing,
                           padding=ft.Padding.only(left=10, right=2), height=36,
                           tooltip=S.FILE_MISSING if missing else r.path)

    async def open_project(self, e=None) -> None:
        await self.app.open_project()
