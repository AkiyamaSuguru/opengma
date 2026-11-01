# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
P0-2：窗口尺寸按屏幕比例、同一进程换窗、关闭工作区回到启动器。

运行（在仓库根目录）：
    uv run python scripts/ui_p0/p0_window.py

要验证的内容见同目录 README.md。
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import flet as ft

sys.path.insert(0, str(Path(__file__).parent))
from _common import screen_size, window_size  # noqa: E402

LAUNCHER = dict(ratio_w=0.42, ratio_h=0.50, min_size=(560, 420), max_size=(960, 680))
WORKSPACE = dict(ratio_w=0.80, ratio_h=0.85, min_size=(960, 640))


async def main(page: ft.Page):
    page.title = "P0-2 · 换窗"
    page.padding = 0
    sw, sh, source = screen_size()
    state = {"mode": "launcher", "close_to_launcher": True}
    is_mac = page.platform == ft.PagePlatform.MACOS
    info = ft.Text("", size=12, selectable=True)
    log = ft.Text("", size=12, color=ft.Colors.BLUE_GREY_600, selectable=True)

    def sizes_text():
        lw, lh = window_size(sw, sh, **LAUNCHER)
        ww, wh = window_size(sw, sh, **WORKSPACE)
        return (f"屏幕 {sw:.0f} × {sh:.0f}（来源：{source}）\n"
                f"启动器默认 {lw} × {lh}　工作区默认 {ww} × {wh}")

    # ---------- 两种界面 ----------
    def launcher_view():
        header = ft.WindowDragArea(content=ft.Container(
            content=ft.Row([
                ft.Container(width=72 if is_mac else 0),  # macOS 左上角红黄绿按钮的位置
                ft.Text("OpenGMA · 启动器", size=15, weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                ft.IconButton(ft.Icons.CLOSE, tooltip="关闭", visible=not is_mac, on_click=close_window),
            ]),
            padding=ft.Padding.symmetric(horizontal=12, vertical=8), bgcolor="#EEF2F5"))
        return ft.Column([
            header,
            ft.Container(padding=20, content=ft.Column([
                ft.Text("拖动顶部灰色区域可以移动窗口；拖动边缘可以缩放窗口。", size=13),
                info,
                ft.Row([ft.Button("进入工作区", icon=ft.Icons.ARROW_FORWARD, on_click=to_workspace)]),
                log,
            ], spacing=12)),
        ], spacing=0, expand=True)

    def workspace_view():
        return ft.Container(padding=20, expand=True, content=ft.Column([
            ft.Text("工作区（使用系统标题栏）", size=18, weight=ft.FontWeight.BOLD),
            info,
            ft.Switch(label="关闭窗口时回到启动器（关闭此项则直接退出）", value=state["close_to_launcher"],
                      on_change=lambda e: state.update(close_to_launcher=bool(e.control.value))),
            ft.Row([ft.Button("回到启动器", icon=ft.Icons.ARROW_BACK, on_click=to_launcher)]),
            log,
        ], spacing=12))

    # ---------- 换窗 ----------
    async def show(view, title_bar_hidden, size, min_size, resizable=True):
        t0 = time.perf_counter()
        page.window.visible = False
        page.update()
        page.window.title_bar_hidden = title_bar_hidden
        page.window.title_bar_buttons_hidden = False
        page.window.min_width, page.window.min_height = min_size
        page.window.width, page.window.height = size
        page.window.resizable = resizable
        page.controls.clear()
        page.add(view)
        await page.window.center()
        page.window.visible = True
        page.update()
        dt = (time.perf_counter() - t0) * 1000
        info.value = sizes_text() + f"\n当前窗口设定 {size[0]} × {size[1]}"
        log.value = f"上一次换窗用时 {dt:.0f} ms（请留意换窗时是否闪烁、位置是否居中）"
        page.update()

    async def to_workspace(e=None):
        state["mode"] = "workspace"
        await show(workspace_view(), False, window_size(sw, sh, **WORKSPACE), WORKSPACE["min_size"])

    async def to_launcher(e=None):
        state["mode"] = "launcher"
        await show(launcher_view(), True, window_size(sw, sh, **LAUNCHER), LAUNCHER["min_size"])

    async def close_window(e=None):
        page.window.prevent_close = False
        await page.window.destroy()

    async def on_window_event(e: ft.WindowEvent):
        if e.type != ft.WindowEventType.CLOSE:
            return
        if state["mode"] == "workspace" and state["close_to_launcher"]:
            await to_launcher()
        else:
            await close_window()

    page.window.prevent_close = True
    page.window.on_event = on_window_event
    await to_launcher()


if __name__ == "__main__":
    ft.run(main)
