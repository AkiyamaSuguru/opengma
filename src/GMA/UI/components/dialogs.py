# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
常用对话框与提示：确认、输入文字、未保存的修改、错误（详情可以复制）、底部提示条。

需要等待用户选择的对话框写成协程，用法：choice = await confirm_unsaved(page, p, "项目名")。
"""
from __future__ import annotations

import asyncio

import flet as ft

from .. import theme as th
from ..strings import S
from ..theme import Palette


def _dialog(p: Palette, title: str, content: ft.Control, actions: list[ft.Control], width: float = 420) -> ft.AlertDialog:
    return ft.AlertDialog(
        modal=True, bgcolor=p.panel,
        title=ft.Text(title, size=16, weight=ft.FontWeight.W_600, color=p.text),
        content=ft.Container(content=content, width=width),
        actions=actions, actions_alignment=ft.MainAxisAlignment.END,
        shape=ft.RoundedRectangleBorder(radius=th.RADIUS_PANEL),
    )


async def _ask(page: ft.Page, build) -> object:
    """显示对话框并等待结果；build(finish) 返回对话框，finish(value) 关闭对话框并给出结果。"""
    future = asyncio.get_running_loop().create_future()

    def finish(value):
        if not future.done():
            page.pop_dialog()
            future.set_result(value)

    page.show_dialog(build(finish))
    return await future


async def confirm(page: ft.Page, p: Palette, title: str, body: str, ok: str = S.OK, *, danger: bool = False) -> bool:
    def build(finish):
        ok_button = ft.FilledButton(ok, on_click=lambda e: finish(True),
                                    style=ft.ButtonStyle(bgcolor=p.error, color="#FFFFFF") if danger else None)
        return _dialog(p, title, ft.Text(body, size=th.SIZE_BODY, color=p.muted),
                       [ft.TextButton(S.CANCEL, on_click=lambda e: finish(False)), ok_button])
    return bool(await _ask(page, build))


async def confirm_unsaved(page: ft.Page, p: Palette, name: str) -> str:
    """有未保存的修改时询问：返回 "save"、"discard" 或 "cancel"。"""
    def build(finish):
        return _dialog(p, S.UNSAVED_TITLE.format(name=name), ft.Text(S.UNSAVED_BODY, size=th.SIZE_BODY, color=p.muted), [
            ft.TextButton(S.DONT_SAVE, on_click=lambda e: finish("discard")),
            ft.TextButton(S.CANCEL, on_click=lambda e: finish("cancel")),
            ft.FilledButton(S.SAVE, on_click=lambda e: finish("save")),
        ])
    return str(await _ask(page, build))


async def prompt_text(page: ft.Page, p: Palette, title: str, label: str, value: str = "", *,
                      validate=None) -> str | None:
    """输入一行文字；取消时返回 None。validate(text) 返回错误说明或 None。"""
    def build(finish):
        field = ft.TextField(label=label, value=value, autofocus=True, dense=True)

        def submit(e=None):
            text = (field.value or "").strip()
            error = S.REQUIRED if not text else (validate(text) if validate else None)
            if error:
                field.error = error
                field.update()
                return
            finish(text)

        field.on_submit = submit
        return _dialog(p, title, field, [ft.TextButton(S.CANCEL, on_click=lambda e: finish(None)),
                                         ft.FilledButton(S.OK, on_click=submit)], width=360)
    return await _ask(page, build)


def show_error(page: ft.Page, p: Palette, title: str, message: str, details: str | None = None) -> None:
    """错误对话框：说明哪一步、为什么；详情（例如原始报错）可以复制，方便反馈。"""
    parts = [ft.Text(message, size=th.SIZE_BODY, color=p.text, selectable=True)]
    actions = []
    if details:
        parts.append(ft.Container(
            content=ft.Text(details, size=11.5, color=p.muted, selectable=True, font_family="monospace"),
            bgcolor=p.subtle, border_radius=th.RADIUS_CONTROL, padding=10, height=140))

        async def copy(e):
            await ft.Clipboard().set(f"{title}\n{message}\n\n{details}")
            toast(page, p, S.COPIED)

        actions.append(ft.TextButton(S.COPY_DETAILS, on_click=copy))
    actions.append(ft.FilledButton(S.CLOSE, on_click=lambda e: page.pop_dialog()))
    page.show_dialog(_dialog(p, title, ft.Column(parts, spacing=10, tight=True, scroll=ft.ScrollMode.AUTO),
                             actions, width=460))


def toast(page: ft.Page, p: Palette, message: str) -> None:
    """底部提示条：操作成功等不需要处理的消息。"""
    bg, fg = ("#E3E9EE", "#1B2730") if p.dark else ("#2B3A42", "#FFFFFF")
    page.show_dialog(ft.SnackBar(content=ft.Text(message, color=fg), bgcolor=bg, duration=2600,
                                 behavior=ft.SnackBarBehavior.FLOATING, width=480))
