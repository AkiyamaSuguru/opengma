# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
计算工具（SC）页面的共同部分：标签状态、卡片、数字输入框、结果行。

计算工具不读写项目中的数据：输入（以及 SRIM 读取的文件内容）保存在标签的状态中，随项目一起保存，
重新打开项目时恢复。
"""
from __future__ import annotations

import copy
import math
from typing import ClassVar

import flet as ft

from .. import theme as th
from ..components import widgets as w
from ..services.text import field_text, parse_number
from ..strings import S
from .base import TabView
from .registry import ModuleSpec


class ToolView(TabView):
    """计算工具页的基类。子类设置 DEFAULTS（标签状态的默认值）并实现 build()。"""

    DEFAULTS: ClassVar[dict] = {}
    view_mode = "single"   # 出版图对话框按“单条”处理

    def __init__(self, app, session, workspace, spec: ModuleSpec, state: dict):
        super().__init__(app, session, workspace)
        self.spec = spec
        self.st = copy.deepcopy(self.DEFAULTS)
        for key, value in (state or {}).items():
            if key in self.st and (self.st[key] is None or value is None or isinstance(value, type(self.st[key]))
                                   or isinstance(self.st[key], float) and isinstance(value, int)):
                self.st[key] = value

    def state(self) -> dict:
        return copy.deepcopy(self.st)

    def touch(self) -> None:
        """输入改了：计算工具的输入随项目保存，所以标记项目有未保存的修改（标签栏出现圆点）。"""
        if not self.project.dirty:
            self.project.dirty = True
            self.session.changed("state", self)

    def selection(self) -> str:
        return ""

    async def on_shortcut(self, key: str, shift: bool) -> bool:
        return False

    @property
    def palette(self):
        return self.app.settings.color_cycle or None

    # ============================================================
    # 小部件
    # ============================================================
    def card(self, title: str, controls: list[ft.Control], *, width=None, expand=None, footer=None,
             right: ft.Control | None = None, scroll: bool = True, fill: bool = True) -> ft.Container:
        """
        带标题的面板；footer 固定在底部（如“导出”按钮）。fill=False 时面板按内容的高度显示
        （放在可以上下滚动的页面中时），否则填满父容器、内容超出时在面板内滚动。
        """
        p = self.p
        head = [ft.Text(title, size=th.SIZE_PANEL_TITLE, weight=ft.FontWeight.W_600, color=p.text, expand=True,
                        max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, tooltip=title)]
        if right is not None:
            head.append(right)
        body = ft.Column(controls, spacing=12, scroll=ft.ScrollMode.AUTO if scroll and fill else None,
                         expand=fill, tight=not fill)
        parts = [ft.Container(content=ft.Row(head, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                              padding=ft.Padding.only(left=16, right=12, top=12, bottom=4)),
                 ft.Container(content=body, expand=fill, padding=ft.Padding.only(left=16, right=14, bottom=12))]
        if footer is not None:
            parts.append(ft.Container(content=footer, padding=12,
                                      border=ft.Border.only(top=ft.BorderSide(1, p.border))))
        return ft.Container(content=ft.Column(parts, spacing=0, expand=fill, tight=not fill,
                                              horizontal_alignment=ft.CrossAxisAlignment.STRETCH), width=width,
                            expand=expand, bgcolor=p.panel, border=ft.Border.all(1, p.border),
                            border_radius=th.RADIUS_PANEL)

    def section(self, title: str, right: ft.Control | None = None) -> ft.Control:
        p = self.p
        parts = [ft.Text(title, size=th.SIZE_SMALL, weight=ft.FontWeight.W_600, color=p.muted)]
        if right is not None:
            parts += [ft.Container(expand=True), right]
        return ft.Row(parts, vertical_alignment=ft.CrossAxisAlignment.CENTER)

    def number_field(self, value, on_value, *, label: str | None = None, suffix: str | None = None,
                     width: float | None = None, hint: str | None = None, allow_empty: bool = False,
                     positive: bool = True, expand=None, tooltip: str | None = None) -> ft.TextField:
        """
        数字输入框：按 Enter 或离开时检查，合法时调用 on_value(数值)（allow_empty 时空着为 None），
        否则在框下显示原因。
        """
        def done(e):
            text = (e.control.value or "").strip()
            try:
                if not text:
                    if not allow_empty:
                        raise ValueError
                    number = None
                else:
                    number = parse_number(text)
                    if not math.isfinite(number) or (positive and number <= 0) or number < 0:
                        raise ValueError
            except ValueError:
                e.control.error = S.POSITIVE_REQUIRED if positive else S.NUMBER_REQUIRED
                e.control.update()
                return
            if e.control.error:
                e.control.error = None
                e.control.update()
            on_value(number)

        return ft.TextField(value=field_text(value), label=label, suffix=suffix, width=width, hint_text=hint,
                            dense=True, text_size=th.SIZE_BODY, on_submit=done, on_blur=done, expand=expand,
                            keyboard_type=ft.KeyboardType.NUMBER, tooltip=tooltip,
                            content_padding=ft.Padding.symmetric(horizontal=10, vertical=9))

    def value_row(self, key: str, value: str, *, strong: bool = False, tooltip: str | None = None,
                  stacked: bool = False) -> ft.Control:
        """结果中的一行：左边名称，右边数值；数值较长时（stacked）名称在上、数值在下。"""
        p = self.p
        number = ft.Text(value, size=15 if strong else th.SIZE_BODY, color=p.text, selectable=True, tooltip=tooltip,
                         weight=ft.FontWeight.W_600 if strong else None,
                         text_align=ft.TextAlign.LEFT if stacked else ft.TextAlign.RIGHT)
        if stacked:
            return ft.Column([ft.Text(key, size=th.SIZE_SMALL, color=p.muted), number], spacing=2, tight=True)
        return ft.Row([ft.Text(key, size=th.SIZE_BODY, color=p.muted, expand=True), number],
                      vertical_alignment=ft.CrossAxisAlignment.CENTER)

    def note(self, text: str, color: str | None = None, icon=ft.Icons.INFO_OUTLINE) -> ft.Control:
        p = self.p
        return ft.Row([ft.Icon(icon, size=15, color=color or p.faint),
                       ft.Text(text, size=th.SIZE_SMALL, color=color or p.muted, expand=True)],
                      spacing=6, vertical_alignment=ft.CrossAxisAlignment.START)

    def empty(self, title: str, hint: str, button: ft.Control | None = None) -> ft.Control:
        p = self.p
        lines = [w.module_tile(self.spec, p.dark, 64, 36),
                 w.text(title, p, th.SIZE_TITLE, bold=True),
                 ft.Container(width=520, content=ft.Text(hint, size=th.SIZE_BODY, color=p.muted,
                                                        text_align=ft.TextAlign.CENTER))]
        if button is not None:
            lines.append(button)
        return ft.Container(expand=True, alignment=ft.Alignment.CENTER, content=ft.Column(
            lines, spacing=12, tight=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER))
