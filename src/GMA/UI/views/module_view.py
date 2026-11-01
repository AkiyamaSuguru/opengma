# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
模块标签。P2 只有外框：模块图标、支持的文件和项目中已有的数据量；导入、交互图、检查器等
按开发计划在 P3（XPS）、P4（Raman、XRD）中实现。标签的状态原样保存，以后的版本可以直接使用。
"""
from __future__ import annotations

import flet as ft

from .. import theme as th
from ..components import widgets as w
from ..strings import S
from .base import TabView
from .registry import ModuleSpec


class ModuleView(TabView):
    def __init__(self, app, session, workspace, spec: ModuleSpec, state: dict):
        super().__init__(app, session, workspace)
        self.spec = spec
        self._state = dict(state)

    def state(self) -> dict:
        return self._state

    def build(self) -> ft.Control:
        p, spec = self.p, self.spec
        n = len(self.project.records_of(method=spec.method)) if spec.method else 0
        lines = [
            w.module_tile(spec, p.dark, 64, 36),
            w.text(S.MODULE_EMPTY.format(title=spec.title), p, th.SIZE_TITLE, bold=True),
        ]
        if spec.formats:
            lines.append(w.muted(S.MODULE_FORMATS.format(formats=spec.formats), p, th.SIZE_BODY))
        if n:
            lines.append(w.muted(S.MODULE_DATA.format(n=n, title=spec.title), p, th.SIZE_BODY))
        lines.append(ft.FilledButton(S.IMPORT_DATA, icon=ft.Icons.UPLOAD_FILE_OUTLINED, disabled=True,
                                     tooltip=S.NOT_YET.format(phase="P3" if spec.key == "xps" else "P4")))
        return ft.Container(expand=True, alignment=ft.Alignment.CENTER, content=ft.Column(
            lines, spacing=12, tight=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER))
