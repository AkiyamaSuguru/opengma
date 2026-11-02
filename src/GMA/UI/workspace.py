# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
工作区：标签栏（项目菜单、固定的“项目”标签、模块标签、“+”）、标签内容、状态栏、快捷键。

所有标签共享同一个项目，各自保存自己的选择和显示设置；同一模块可以开多个标签，标题自动加序号，
例如 XPS (2)。标签和各标签的状态在保存项目时一起保存（Q10），重新打开时恢复。
"""
from __future__ import annotations

from dataclasses import dataclass

import flet as ft

from . import theme as th
from .components import widgets as w
from .components.dialogs import close, show
from .services.text import short_path
from .session import ProjectSession, make_ui_state
from .strings import S
from .views import registry
from .views.base import TabView
from .views.module_view import ModuleView
from .views.overview_view import OverviewView
from .views.raman_view import RamanView
from .views.registry import ModuleSpec
from .views.salt_view import SaltView
from .views.srim_view import SRIMView
from .views.xps_view import XPSView
from .views.xrd_view import XRDView

TAB_H, STRIP_H = 34, 42
# 各模块的页面；还没有实现的模块用占位页
VIEW_CLASSES = {"xps": XPSView, "raman": RamanView, "xrd": XRDView, "srim": SRIMView, "salt": SaltView}


def tab_width(title: str) -> int:
    """模块标签的宽度：放得下标题（按字符估算，汉字约为西文的两倍宽），在 140–240 之间。"""
    text = sum(12.5 if ord(ch) >= 0x2E80 else 7.8 for ch in title)
    return int(min(max(72 + text, 140), 240))


@dataclass
class ModuleTab:
    spec: ModuleSpec
    view: TabView
    number: int = 1   # 同一模块的第几个标签

    @property
    def title(self) -> str:
        return self.spec.title if self.number == 1 else f"{self.spec.title} ({self.number})"


class Workspace:
    def __init__(self, app, session: ProjectSession, tabs: list[dict], active: int):
        self.app = app
        self.session = session
        self.overview = OverviewView(app, session, self)
        self.tabs: list[ModuleTab] = []
        for t in tabs:
            spec = registry.get(t["module"])
            if spec is not None and not spec.planned:
                self._add(spec, t.get("state") or {})
        self.active = active if 0 <= active <= len(self.tabs) else 0
        self.status = S.READY
        self.selection_text = ""
        self.readout: ft.Text | None = None   # 交互图的悬停读数
        self.body: ft.Container | None = None
        self.strip: ft.Container | None = None
        self.status_bar: ft.Container | None = None
        session.subscribe(self.on_session_change)

    # ============================================================
    # 标签
    # ============================================================
    def _add(self, spec: ModuleSpec, state: dict) -> ModuleTab:
        used = {t.number for t in self.tabs if t.spec.key == spec.key}
        number = next(n for n in range(1, len(used) + 2) if n not in used)
        view_class = VIEW_CLASSES.get(spec.key, ModuleView)
        tab = ModuleTab(spec, view_class(self.app, self.session, self, spec, state), number)
        self.tabs.append(tab)
        return tab

    def open_module(self, key: str, state: dict | None = None, *, reuse: bool = False) -> None:
        """
        打开模块标签。reuse=True（如从项目总览点击某个样品的数据量）时，已经打开的同一模块标签直接切过去，
        并按 state 只显示对应样品；否则新开一个标签（同一模块可以开多个）。
        """
        spec = registry.get(key)
        if spec is None or spec.planned:
            return
        if reuse:
            for index, tab in enumerate(self.tabs, start=1):
                if tab.spec.key == key:
                    if state and hasattr(tab.view, "open_with"):
                        tab.view.open_with(state)
                    self.select(index)
                    return
        self._add(spec, state or {})
        self.select(len(self.tabs))

    def close_tab(self, index: int) -> None:
        """关闭第 index 个标签（1 起，0 是固定的“项目”标签，不能关闭）。"""
        if not 1 <= index <= len(self.tabs):
            return
        del self.tabs[index - 1]
        if self.active > len(self.tabs) or self.active > index:
            self.active -= 1
        elif self.active == index:
            self.active = min(index, len(self.tabs))
        self.refresh()

    def select(self, index: int) -> None:
        self.active = max(0, min(index, len(self.tabs)))
        self.status = S.READY
        self.refresh()

    def module_keys(self) -> list[str]:
        return [t.spec.key for t in self.tabs]

    def active_key(self) -> str | None:
        return self.tabs[self.active - 1].spec.key if self.active else None

    def ui_state(self) -> dict:
        return make_ui_state([{"module": t.spec.key, "state": t.view.state()} for t in self.tabs], self.active)

    def current_view(self):
        return self.tabs[self.active - 1].view if self.active else self.overview

    # ============================================================
    # 界面
    # ============================================================
    def build(self) -> ft.Control:
        p = self.app.p
        self.strip = ft.Container(height=STRIP_H, bgcolor=p.strip, content=self.strip_row(),
                                  border=ft.Border.only(bottom=ft.BorderSide(1, p.border)),
                                  padding=ft.Padding.only(left=8, right=8))
        self.body = ft.Container(content=self.current_view().control(), expand=True, bgcolor=p.bg)
        self.readout = ft.Text("", size=th.SIZE_TINY, color=p.text, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
                               expand=True)
        self.status_bar = ft.Container(height=26, content=self.status_row(), bgcolor=p.panel,
                                       border=ft.Border.only(top=ft.BorderSide(1, p.border)),
                                       padding=ft.Padding.symmetric(horizontal=12))
        for view in [self.overview, *(t.view for t in self.tabs)]:
            view.invalidate()
        self.body.content = self.current_view().control()
        return ft.Column([self.strip, self.body, self.status_bar], spacing=0, expand=True)

    def refresh(self) -> None:
        """标签、项目名、未保存标记、状态栏有变化时刷新外框；标签内容按需切换。"""
        if self.strip is None:
            return
        self.strip.content = self.strip_row()
        self.body.content = self.current_view().control()
        if self.readout is not None:
            self.readout.value = ""
        self.status_bar.content = self.status_row()
        self.app.page.title = self.app.window_title()
        self.app.page.update()

    def strip_row(self) -> ft.Row:
        p = self.app.p
        tabs = [self.pinned_tab()] + [self.module_tab(i + 1, t) for i, t in enumerate(self.tabs)]
        return ft.Row([
            self.project_menu(), w.vsep(p, 24), ft.Container(width=2),
            ft.Row(tabs, spacing=2, scroll=ft.ScrollMode.HIDDEN, vertical_alignment=ft.CrossAxisAlignment.END),
            self.add_menu(),
            ft.Container(expand=True),
            w.icon_button(ft.Icons.SAVE_OUTLINED, S.SHORTCUT_HINT.format(action=S.SAVE, keys="Ctrl+S"),
                          self.on_save, p),
            w.icon_button(ft.Icons.SETTINGS_OUTLINED, S.SETTINGS, self.app.open_settings, p),
            w.icon_button(ft.Icons.INFO_OUTLINE, S.ABOUT, self.app.open_about, p),
        ], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER)

    def _tab_box(self, content: ft.Control, selected: bool, on_click, *, min_width=None, pad_right=8) -> ft.Control:
        p = self.app.p
        box = ft.Container(
            content=content, height=TAB_H, padding=ft.Padding.only(left=12, right=pad_right),
            bgcolor=p.bg if selected else None, on_click=on_click, width=min_width,
            border_radius=ft.BorderRadius.only(top_left=10, top_right=10),
            border=ft.Border.only(left=ft.BorderSide(1, p.border), right=ft.BorderSide(1, p.border),
                                  top=ft.BorderSide(1, p.border)) if selected else None,
            margin=ft.Margin.only(top=STRIP_H - TAB_H - 1),
            animate=ft.Animation(150, ft.AnimationCurve.EASE_OUT))
        if not selected:
            def on_hover(e):
                box.bgcolor = ft.Colors.with_opacity(0.55, p.subtle) if e.data in (True, "true") else None
                box.update()
            box.on_hover = on_hover
        return box

    def pinned_tab(self) -> ft.Control:
        p = self.app.p
        selected = self.active == 0
        content = ft.Row([
            ft.Icon(ft.Icons.INVENTORY_2_OUTLINED, size=15, color=p.primary),
            ft.Text(S.PROJECT_TAB, size=12.5, color=p.text if selected else p.muted,
                    weight=ft.FontWeight.W_600 if selected else None),
        ], spacing=7, tight=True, vertical_alignment=ft.CrossAxisAlignment.CENTER)
        return self._tab_box(content, selected, lambda e: self.select(0), pad_right=14)

    def module_tab(self, index: int, tab: ModuleTab) -> ft.Control:
        p = self.app.p
        selected = self.active == index
        close = ft.Container(
            content=ft.Icon(ft.Icons.CLOSE_ROUNDED, size=14, color=p.faint), width=20, height=20,
            border_radius=6, alignment=ft.Alignment.CENTER, tooltip=S.SHORTCUT_HINT.format(
                action=S.CLOSE_TAB, keys="Ctrl+W"), on_click=lambda e, i=index: self.close_tab(i))
        content = ft.Row([
            w.module_icon(tab.spec, p.dark, 15),
            ft.Text(tab.title, size=12.5, color=p.text if selected else p.muted,
                    weight=ft.FontWeight.W_600 if selected else None, expand=True, max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS),
            close,
        ], spacing=7, vertical_alignment=ft.CrossAxisAlignment.CENTER)
        return self._tab_box(content, selected, lambda e, i=index: self.select(i), min_width=tab_width(tab.title),
                             pad_right=6)

    def add_menu(self) -> ft.Control:
        p = self.app.p
        items = []
        for modules in registry.by_category().values():
            if not modules:
                continue
            if items:
                items.append(ft.PopupMenuItem())  # 分隔线
            for m in modules:
                items.append(ft.PopupMenuItem(
                    content=ft.Row([w.module_icon(m, p.dark, 16),
                                    ft.Text(m.title, size=th.SIZE_BODY, color=p.faint if m.planned else p.text),
                                    *([w.chip(S.PLANNED, p)] if m.planned else [])], spacing=10),
                    on_click=None if m.planned else (lambda e, k=m.key: self.open_module(k)),
                    disabled=m.planned))
        return ft.PopupMenuButton(
            icon=ft.Icons.ADD_ROUNDED, icon_color=p.muted, icon_size=18, items=items,
            tooltip=S.SHORTCUT_HINT.format(action=S.NEW_TAB, keys="Ctrl+T"), menu_position=ft.PopupMenuPosition.UNDER)

    def project_menu(self) -> ft.Control:
        p = self.app.p
        app = self.app

        async def new(e):
            await app.new_project()

        async def open_(e):
            await app.open_project()

        async def save_as(e):
            await app.save(save_as=True)

        async def back(e):
            await app.close_workspace(quit_app=False)

        def entry(icon, label, handler, keys=None):
            return ft.PopupMenuItem(content=ft.Row([
                ft.Icon(icon, size=17, color=p.muted), ft.Text(label, size=th.SIZE_BODY, color=p.text, expand=True),
                *([ft.Text(keys, size=th.SIZE_TINY, color=p.faint)] if keys else [])], spacing=10), on_click=handler)

        items = [
            entry(ft.Icons.NOTE_ADD_OUTLINED, S.NEW_PROJECT, new),
            entry(ft.Icons.FOLDER_OPEN_OUTLINED, S.OPEN_PROJECT, open_, "Ctrl+O"),
            entry(ft.Icons.SAVE_OUTLINED, S.SAVE_PROJECT, self.on_save, "Ctrl+S"),
            entry(ft.Icons.SAVE_AS_OUTLINED, S.SAVE_PROJECT_AS, save_as, "Ctrl+Shift+S"),
            entry(ft.Icons.OPEN_IN_NEW_ROUNDED, S.NEW_WINDOW, app.new_window, "Ctrl+Shift+N"),
        ]
        recent = [r for r in app.settings.recent if r.exists and (self.session.path is None
                                                                  or r.path != str(self.session.path))][:5]
        if recent:
            items.append(ft.PopupMenuItem())
            for r in recent:
                async def open_recent(e, path=r.path):
                    await app.open_project(path)
                items.append(ft.PopupMenuItem(content=ft.Row([
                    ft.Icon(ft.Icons.HISTORY_ROUNDED, size=17, color=p.muted),
                    ft.Text(short_path(r.path), size=th.SIZE_SMALL, color=p.text, max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS, width=260)], spacing=10), on_click=open_recent))
        items += [
            ft.PopupMenuItem(),
            entry(ft.Icons.INFO_OUTLINE, S.PROJECT_INFO, lambda e: self.select(0)),
            entry(ft.Icons.HOME_OUTLINED, S.BACK_TO_LAUNCHER, back),
        ]
        dirty = [w.dot(p.warning)] if self.session.dirty else []
        return ft.PopupMenuButton(
            content=ft.Container(padding=ft.Padding.only(left=4, right=6), height=STRIP_H - 6, content=ft.Row([
                w.app_icon(22),
                ft.Text(self.session.name, size=13, weight=ft.FontWeight.BOLD, color=p.text, max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS),
                *dirty,
                ft.Icon(ft.Icons.EXPAND_MORE_ROUNDED, size=16, color=p.muted),
            ], spacing=8, tight=True, vertical_alignment=ft.CrossAxisAlignment.CENTER)),
            items=items, tooltip=S.PROJECT_MENU, menu_position=ft.PopupMenuPosition.UNDER)

    def status_row(self) -> ft.Row:
        p = self.app.p
        if self.session.read_only:
            state, color = S.READ_ONLY, p.warning
        elif self.session.path is None:
            state, color = S.NOT_SAVED_YET, p.faint
        elif self.session.dirty:
            state, color = S.UNSAVED, p.warning
        else:
            state, color = S.SAVED, p.success
        location = short_path(self.session.path) if self.session.path else ""
        view = self.current_view()
        self.selection_text = view.selection() if hasattr(view, "selection") else ""
        return ft.Row([
            w.muted(self.status, p, th.SIZE_TINY),
            *([w.vsep(p, 12), w.muted(self.selection_text, p, th.SIZE_TINY)] if self.selection_text else []),
            ft.Container(width=8),
            self.readout if self.readout is not None else ft.Container(expand=True),
            w.faint(location, p, th.SIZE_TINY, max_lines=1, tooltip=str(self.session.path or "")),
            w.dot(color, 6), w.muted(state, p, th.SIZE_TINY, tooltip=S.READ_ONLY_HINT if self.session.read_only
                                     else None),
        ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER)

    def set_status(self, text: str | None = None) -> None:
        """状态栏左侧的状态文字；选择（如“已选 2 / 6 条谱图”）由当前标签的 selection() 给出。"""
        if text is not None:
            self.status = text
        if self.status_bar is not None:
            self.status_bar.content = self.status_row()
            self.status_bar.update()

    def set_readout(self, text: str) -> None:
        """交互图的悬停读数：只更新这一段文字，不重画状态栏（悬停时调用得很频繁）。"""
        if self.readout is None or self.readout.value == text:
            return
        self.readout.value = text
        self.readout.update()

    # ============================================================
    # 事件
    # ============================================================
    def on_session_change(self, kind: str, source=None) -> None:
        """
        项目变了：需要重画的标签标记为过期，切换到它时重新生成。数据变了时所有标签都要重画；
        保存、改项目名只影响项目总览（文件路径、项目名）。发起修改的标签自己已经刷新过，不再重画。
        """
        if kind == "data":
            views = [self.overview, *(t.view for t in self.tabs)]
        elif kind in ("renamed", "saved"):
            views = [self.overview]
        else:
            views = []
        for view in views:
            if view is not source:
                view.invalidate()
        if kind == "saved":
            self.status = S.SAVED
        self.refresh()

    async def on_save(self, e=None) -> None:
        await self.app.save()

    async def on_shortcut(self, key: str, shift: bool) -> None:
        if key == "s":
            await self.app.save(save_as=shift)
        elif key == "w" and self.active:
            self.close_tab(self.active)
        elif key == "tab":
            count = len(self.tabs) + 1
            self.select((self.active + (-1 if shift else 1)) % count)
        elif key == "t":
            self.ask_open_module()
        elif key in ("i", "e"):  # 导入、出版图：交给当前的模块标签
            handler = getattr(self.current_view(), "on_shortcut", None)
            if handler is None or not await handler(key, shift):
                self.app.toast(S.SHORTCUT_NOT_HERE if self.active else S.SHORTCUT_IN_MODULE)

    def ask_open_module(self) -> None:
        """Ctrl+T：列出可以打开的模块。"""
        p, page = self.app.p, self.app.page

        def choose(key):
            close(box)
            self.open_module(key)

        buttons = [w.hoverable(ft.Row([w.module_tile(m, p.dark, 30, 18), w.text(m.title, p, 14, bold=True)],
                                      spacing=12), p, on_click=lambda e, k=m.key: choose(k),
                               padding=ft.Padding.symmetric(horizontal=10, vertical=8))
                   for m in registry.available()]
        box = ft.AlertDialog(
            bgcolor=p.panel, shape=ft.RoundedRectangleBorder(radius=th.RADIUS_PANEL),
            title=ft.Text(S.NEW_TAB, size=16, weight=ft.FontWeight.W_600, color=p.text),
            content=ft.Container(width=280, content=ft.Column(buttons, spacing=2, tight=True)),
            actions=[ft.TextButton(S.CANCEL, on_click=lambda e: close(box))])
        show(page, box)
