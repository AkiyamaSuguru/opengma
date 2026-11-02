# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
常用对话框与提示：确认、输入文字、未保存的修改、错误（详情可以复制）、底部提示条。

需要等待用户选择的对话框写成协程，用法：choice = await confirm_unsaved(page, p, "项目名")。
"""
from __future__ import annotations

import asyncio
import contextlib

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


def close(dialog: ft.DialogControl | None) -> None:
    """
    关闭指定的对话框。不用 page.pop_dialog()：它关闭的是最上面一个打开的对话框，
    对话框打开期间显示过底部提示条（SnackBar）时，关掉的会是提示条。
    """
    if dialog is None or not dialog.open:
        return
    dialog.open = False
    with contextlib.suppress(RuntimeError):  # 已经被其他方式关闭、移出页面
        dialog.update()


async def _ask(page: ft.Page, build, dismissed=None) -> object:
    """
    显示对话框并等待结果；build(finish) 返回对话框，finish(value) 关闭对话框并给出结果。
    对话框被其他方式关闭（如按 Esc）时，结果为 dismissed。
    """
    future = asyncio.get_running_loop().create_future()
    box = None

    def finish(value):
        if not future.done():
            close(box)
            future.set_result(value)

    box = build(finish)
    box.on_dismiss = lambda e: finish(dismissed)
    show(page, box)
    return await future


def show(page: ft.Page, dialog: ft.DialogControl) -> None:
    """显示对话框；先收起还没消失的底部提示条（对话框打开期间提示条不会自动消失）。"""
    close(_toasts.pop(id(page), None))
    page.show_dialog(dialog)


async def confirm(page: ft.Page, p: Palette, title: str, body: str, ok: str = S.OK, *, danger: bool = False) -> bool:
    def build(finish):
        ok_button = ft.FilledButton(ok, on_click=lambda e: finish(True),
                                    style=ft.ButtonStyle(bgcolor=p.error, color="#FFFFFF") if danger else None)
        return _dialog(p, title, ft.Text(body, size=th.SIZE_BODY, color=p.muted),
                       [ft.TextButton(S.CANCEL, on_click=lambda e: finish(False)), ok_button])
    return bool(await _ask(page, build, dismissed=False))


async def confirm_unsaved(page: ft.Page, p: Palette, name: str) -> str:
    """有未保存的修改时询问：返回 "save"、"discard" 或 "cancel"。"""
    def build(finish):
        return _dialog(p, S.UNSAVED_TITLE.format(name=name), ft.Text(S.UNSAVED_BODY, size=th.SIZE_BODY, color=p.muted), [
            ft.TextButton(S.DONT_SAVE, on_click=lambda e: finish("discard")),
            ft.TextButton(S.CANCEL, on_click=lambda e: finish("cancel")),
            ft.FilledButton(S.SAVE, on_click=lambda e: finish("save")),
        ])
    return str(await _ask(page, build, dismissed="cancel"))


async def ask_locked(page: ft.Page, p: Palette, name: str, info: dict, *, saving: bool = False) -> str | None:
    """
    项目已在别的窗口（或别的电脑）中打开时询问。打开时返回 "read_only"、"edit"，保存时返回 "edit"；
    取消时返回 None。
    """
    from ..services.text import when

    who = "@".join(x for x in (info.get("user"), info.get("host")) if x) or S.ANOTHER_WINDOW
    body = S.LOCKED_BODY.format(name=name, who=who, time=when(info.get("opened_at") or ""))

    def build(finish):
        actions = [ft.TextButton(S.CANCEL, on_click=lambda e: finish(None))]
        if saving:
            actions.append(ft.FilledButton(S.SAVE_ANYWAY, on_click=lambda e: finish("edit"),
                                           style=ft.ButtonStyle(bgcolor=p.error, color="#FFFFFF")))
        else:
            actions += [ft.TextButton(S.OPEN_ANYWAY, on_click=lambda e: finish("edit")),
                        ft.FilledButton(S.OPEN_READ_ONLY, on_click=lambda e: finish("read_only"))]
        text = S.LOCKED_SAVE_BODY if saving else S.LOCKED_OPEN_BODY
        return _dialog(p, S.LOCKED_TITLE, ft.Column([ft.Text(body, size=th.SIZE_BODY, color=p.text),
                                                     ft.Text(text, size=th.SIZE_SMALL, color=p.muted)],
                                                    spacing=8, tight=True), actions, width=460)
    return await _ask(page, build, dismissed=None)


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


# 选色对话框中的颜色：matplotlib tab10（GMA 的默认色卡），以及几个常用的深色、出版图默认颜色
SWATCHES = ["#1F77B4", "#FF7F0E", "#2CA02C", "#D62728", "#9467BD", "#8C564B", "#E377C2", "#7F7F7F", "#BCBD22",
            "#17BECF", "#2563EB", "#F59E0B", "#10B981", "#DC2626", "#7C3AED", "#0F766E", "#B45309", "#DB2777",
            "#000000", "#FF0000", "#808080", "#1B2730"]


async def pick_color(page: ft.Page, p: Palette, title: str, current: str) -> str | None:
    """选一个颜色：点色块或输入 #RRGGBB；取消时返回 None。"""
    def build(finish):
        field = ft.TextField(value=current.upper(), width=130, dense=True, text_size=th.SIZE_BODY,
                             hint_text="#RRGGBB")
        preview = ft.Container(width=30, height=30, border_radius=8, bgcolor=current, border=ft.Border.all(1, p.border))

        def choose(color):
            field.value, field.error = color, None
            preview.bgcolor = color
            field.update()
            preview.update()

        def typed(e):
            value = (field.value or "").strip().upper()
            value = value if value.startswith("#") else "#" + value
            if th.is_hex(value):
                preview.bgcolor = value
                preview.update()

        def submit(e=None):
            value = (field.value or "").strip().upper()
            value = value if value.startswith("#") else "#" + value
            if not th.is_hex(value):
                field.error = S.INVALID_COLOR
                field.update()
                return
            finish(value)

        field.on_change, field.on_submit = typed, submit
        swatches = ft.Row([ft.Container(width=26, height=26, border_radius=7, bgcolor=c, tooltip=c,
                                        border=ft.Border.all(1, p.border), on_click=lambda e, c=c: choose(c))
                           for c in SWATCHES], wrap=True, spacing=8, run_spacing=8)
        content = ft.Column([swatches, ft.Row([preview, field], spacing=12)], spacing=16, tight=True)
        return _dialog(p, title, content, [ft.TextButton(S.CANCEL, on_click=lambda e: finish(None)),
                                           ft.FilledButton(S.OK, on_click=submit)], width=330)
    return await _ask(page, build)


async def edit_names(page: ft.Page, p: Palette, title: str, names: list[str], labels: list[str]) -> list[str] | None:
    """逐个修改名称（如分峰名）：不能为空、不能重复；取消时返回 None。"""
    def build(finish):
        fields = [ft.TextField(value=n, label=lab, dense=True, text_size=th.SIZE_BODY, autofocus=i == 0)
                  for i, (n, lab) in enumerate(zip(names, labels, strict=True))]
        error = ft.Text("", size=th.SIZE_SMALL, color=p.error, visible=False)

        def submit(e=None):
            values = [(f.value or "").strip() for f in fields]
            problem = S.REQUIRED if any(not v for v in values) else (
                S.NAMES_UNIQUE if len(set(values)) != len(values) else None)
            if problem:
                error.value, error.visible = problem, True
                error.update()
                return
            finish(values)

        for f in fields:
            f.on_submit = submit
        return _dialog(p, title, _field_column([*fields, error]),
                       [ft.TextButton(S.CANCEL, on_click=lambda e: finish(None)),
                        ft.FilledButton(S.OK, on_click=submit)], width=360)
    return await _ask(page, build)


def _field_column(controls: list[ft.Control], max_rows: int = 8) -> ft.Control:
    """对话框中的一列输入框：不多时按内容高度显示；很多时放进固定高度、可以滚动的区域。"""
    if len(controls) <= max_rows:
        return ft.Column(controls, spacing=10, tight=True)
    return ft.Container(height=max_rows * 52, content=ft.Column(controls, spacing=10, scroll=ft.ScrollMode.AUTO))


async def edit_fields(page: ft.Page, p: Palette, title: str, fields: list[str], values: dict) -> dict | None:
    """编辑样品信息等“字段: 值”；取消时返回 None。"""
    def build(finish):
        inputs = [ft.TextField(value=str(values.get(f, "")), label=f, dense=True, text_size=th.SIZE_BODY,
                               autofocus=i == 0) for i, f in enumerate(fields)]

        def submit(e=None):
            finish({f: (i.value or "").strip() for f, i in zip(fields, inputs, strict=True)})

        for i in inputs:
            i.on_submit = submit
        return _dialog(p, title, _field_column(inputs),
                       [ft.TextButton(S.CANCEL, on_click=lambda e: finish(None)),
                        ft.FilledButton(S.OK, on_click=submit)], width=360)
    return await _ask(page, build)


dialog, ask = _dialog, _ask  # 其他组件自己拼对话框时用


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
    box = _dialog(p, title, ft.Column(parts, spacing=10, tight=True), actions, width=460)
    actions.append(ft.FilledButton(S.CLOSE, on_click=lambda e: close(box)))
    show(page, box)


TOAST_SECONDS = 2.6
_toasts: dict[int, ft.SnackBar] = {}  # 每个页面当前显示的提示条


def toast(page: ft.Page, p: Palette, message: str) -> None:
    """
    底部提示条：操作成功等不需要处理的消息。新的提示直接替换还没消失的旧提示，不排队；
    到时间由这里关闭（有些情况下系统不会自动收起提示条，例如对话框打开期间）。
    """
    close(_toasts.pop(id(page), None))
    bg, fg = ("#E3E9EE", "#1B2730") if p.dark else ("#2B3A42", "#FFFFFF")
    bar = ft.SnackBar(content=ft.Text(message, color=fg), bgcolor=bg, duration=int(TOAST_SECONDS * 1000),
                      behavior=ft.SnackBarBehavior.FLOATING, width=480)

    def dismissed(e):
        if _toasts.get(id(page)) is bar:
            del _toasts[id(page)]

    async def expire():
        await asyncio.sleep(TOAST_SECONDS + 0.6)
        if _toasts.get(id(page)) is bar:
            del _toasts[id(page)]
            close(bar)

    bar.on_dismiss = dismissed
    _toasts[id(page)] = bar
    page.show_dialog(bar)
    with contextlib.suppress(RuntimeError, AttributeError):  # 页面已经断开（如网页版关闭了标签页）
        page.run_task(expire)
