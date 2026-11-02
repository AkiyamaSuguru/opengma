# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""关于：名称、版本、简介；作者、仓库、许可证；运行环境（可以一键复制）；免责声明（方案 10.2）。"""
from __future__ import annotations

import flet as ft

from .. import theme as th
from ..services.text import app_version, environment
from ..strings import S
from . import widgets as w
from .dialogs import toast


def show_about(app) -> None:
    p, page = app.p, app.page
    env = environment()

    async def copy_env(e):
        await app.clipboard.set(env)
        toast(page, p, S.COPIED)

    async def open_repo(e):
        await app.open_url()

    content = ft.Column([
        ft.Row([w.app_icon(48), ft.Column([
            w.text(S.APP_NAME, p, 18, bold=True),
            w.muted(S.VERSION.format(version=app_version()), p, th.SIZE_SMALL),
        ], spacing=2, tight=True)], spacing=14),
        w.text(S.APP_DESCRIPTION, p, th.SIZE_BODY),
        ft.Row([w.muted(S.AUTHOR, p), w.vsep(p, 12), w.muted(S.LICENSE, p), w.vsep(p, 12),
                ft.Container(content=ft.Text(S.HOMEPAGE, size=th.SIZE_SMALL, color=p.primary,
                                             weight=ft.FontWeight.W_600), on_click=open_repo)], spacing=10),
        w.hsep(p),
        ft.Row([w.text(S.ENVIRONMENT, p, th.SIZE_SMALL, bold=True), ft.Container(expand=True),
                w.ghost_button(S.COPY_ENVIRONMENT, ft.Icons.CONTENT_COPY_ROUNDED, copy_env, p)]),
        ft.Container(content=ft.Text(env, size=11.5, color=p.muted, selectable=True, font_family="monospace"),
                     bgcolor=p.subtle, border_radius=th.RADIUS_CONTROL, padding=10),
        w.faint(S.DISCLAIMER, p),
    ], spacing=12, tight=True)
    page.show_dialog(ft.AlertDialog(
        bgcolor=p.panel, shape=ft.RoundedRectangleBorder(radius=th.RADIUS_PANEL),
        content=ft.Container(width=440, content=content),
        actions=[ft.FilledButton(S.CLOSE, on_click=lambda e: page.pop_dialog())]))
