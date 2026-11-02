# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""标签视图的共同接口：control() 返回界面（按需重新生成），invalidate() 标记需要重新生成，state() 返回要保存的状态。"""
from __future__ import annotations

import flet as ft


class TabView:
    def __init__(self, app, session, workspace):
        self.app = app
        self.session = session
        self.workspace = workspace
        self._control: ft.Control | None = None

    @property
    def p(self):
        return self.app.p

    @property
    def project(self):
        return self.session.project

    def build(self) -> ft.Control:  # 子类实现
        raise NotImplementedError

    def control(self) -> ft.Control:
        if self._control is None:
            self._control = self.build()
        return self._control

    def invalidate(self) -> None:
        self._control = None

    def redraw(self) -> None:
        """立即重新生成并显示（当前标签是这个视图时）。"""
        self.invalidate()
        if self.workspace.current_view() is self:
            self.workspace.body.content = self.control()
            self.workspace.body.update()

    def state(self) -> dict:
        return {}
