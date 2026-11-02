# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""界面中反复用到的小部件：图标、面板、按钮、标签。颜色都从当前的 Palette 取。"""
from __future__ import annotations

import flet as ft

from .. import theme as th
from ..theme import Palette
from ..views.registry import ModuleSpec


def app_icon(size: float = 28) -> ft.Control:
    return ft.Image(src="icons/app.svg", width=size, height=size)


def module_icon(spec: ModuleSpec, dark: bool, size: float = 18, color: str | None = None) -> ft.Control:
    """模块图标（单色线条），按模块色着色。"""
    return ft.Image(src=spec.icon_src, width=size, height=size, color=color or spec.color_for(dark))


def module_tile(spec: ModuleSpec, dark: bool, size: float = 36, icon_size: float = 21) -> ft.Control:
    """带底色的模块图标块，用在模块卡片、统计块上。"""
    return ft.Container(width=size, height=size, border_radius=size * 0.28, bgcolor=spec.tint_for(dark),
                        alignment=ft.Alignment.CENTER, content=module_icon(spec, dark, icon_size))


def text(value: str, p: Palette, size: float = th.SIZE_BODY, *, color: str | None = None, bold: bool = False,
         weight: ft.FontWeight | None = None, selectable: bool = False, max_lines: int | None = None,
         expand: bool | int | None = None, tooltip: str | None = None) -> ft.Text:
    return ft.Text(value, size=size, color=color or p.text, selectable=selectable, expand=expand, tooltip=tooltip,
                   weight=weight or (ft.FontWeight.W_600 if bold else None), max_lines=max_lines,
                   overflow=ft.TextOverflow.ELLIPSIS if max_lines else None)


def muted(value: str, p: Palette, size: float = th.SIZE_SMALL, **kw) -> ft.Text:
    return text(value, p, size, color=p.muted, **kw)


def faint(value: str, p: Palette, size: float = th.SIZE_TINY, **kw) -> ft.Text:
    return text(value, p, size, color=p.faint, **kw)


def label(value: str, p: Palette) -> ft.Text:
    """小节标题：面板内的“模块”“最近项目”等。"""
    return ft.Text(value, size=th.SIZE_SMALL, weight=ft.FontWeight.W_600, color=p.muted)


def panel(content: ft.Control, p: Palette, *, padding=12, expand=None, width=None, height=None) -> ft.Container:
    return ft.Container(content=content, bgcolor=p.panel, border=ft.Border.all(1, p.border),
                        border_radius=th.RADIUS_PANEL, padding=padding, expand=expand, width=width, height=height)


def chip(value: str, p: Palette, *, color: str | None = None, bgcolor: str | None = None) -> ft.Container:
    """全圆角的小标签：数量、“规划中”等。"""
    return ft.Container(content=ft.Text(value, size=10.5, color=color or p.muted, weight=ft.FontWeight.W_600),
                        bgcolor=bgcolor or p.subtle, border_radius=99,
                        padding=ft.Padding.symmetric(horizontal=7, vertical=1))


def dot(color: str, size: float = 7) -> ft.Container:
    return ft.Container(width=size, height=size, border_radius=size, bgcolor=color)


def icon_button(icon, tooltip: str, on_click, p: Palette, *, size: float = 18, color: str | None = None,
                disabled: bool = False) -> ft.IconButton:
    return ft.IconButton(icon=icon, icon_size=size, icon_color=color or p.muted, tooltip=tooltip,
                         on_click=on_click, disabled=disabled,
                         style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=th.RADIUS_CONTROL),
                                              padding=ft.Padding.all(6)))


def ghost_button(value: str, icon, on_click, p: Palette, *, color: str | None = None, disabled: bool = False,
                 tooltip: str | None = None) -> ft.TextButton:
    """不带底色的文字按钮，用在面板标题右侧：“全部模块”“打开项目…”。"""
    return ft.TextButton(
        content=ft.Row([ft.Icon(icon, size=16, color=color or p.primary),
                        ft.Text(value, size=th.SIZE_SMALL, weight=ft.FontWeight.W_600, color=color or p.primary)],
                       spacing=6, tight=True),
        on_click=on_click, disabled=disabled, tooltip=tooltip,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=th.RADIUS_CONTROL),
                             padding=ft.Padding.symmetric(horizontal=8, vertical=4)))


def hoverable(content: ft.Control, p: Palette, *, on_click=None, padding=None, radius: float = th.RADIUS_CONTROL,
              hover_color: str | None = None, base_color: str | None = None, tooltip: str | None = None,
              disabled: bool = False, expand=None, width=None, height=None) -> ft.Container:
    """悬停时换底色的可点击区域（列表行、标签等）。"""
    box = ft.Container(content=content, padding=padding, border_radius=radius, bgcolor=base_color,
                       on_click=None if disabled else on_click, tooltip=tooltip, expand=expand, width=width,
                       height=height, animate=ft.Animation(150, ft.AnimationCurve.EASE_OUT))

    def on_hover(e):
        if disabled:
            return
        box.bgcolor = (hover_color or p.subtle) if e.data in (True, "true") else base_color
        box.update()

    box.on_hover = on_hover
    return box


def vsep(p: Palette, height: float = 20) -> ft.Container:
    return ft.Container(width=1, height=height, bgcolor=p.border)


def hsep(p: Palette) -> ft.Container:
    return ft.Container(height=1, bgcolor=p.border)
