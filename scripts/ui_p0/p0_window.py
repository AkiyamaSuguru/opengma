# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
P0-2：窗口尺寸按屏幕比例、同一进程换窗、关闭工作区回到启动器。

运行（在仓库根目录）：
    uv run python scripts/ui_p0/p0_window.py

要验证的内容见同目录 README.md。

自动换窗：用环境变量 P0_BENCH=1 运行（run_mac.sh 就是这样运行的），启动后自动在启动器和工作区之间
来回切换 3 次并记录用时，结果写入 results/window.txt，之后停在启动器，可以继续手动操作。
"""
from __future__ import annotations

import asyncio
import contextlib
import os
import statistics
import sys
import time
from pathlib import Path

import flet as ft

sys.path.insert(0, str(Path(__file__).parent))
from _common import screen_size, window_size  # noqa: E402

LAUNCHER = dict(ratio_w=0.42, ratio_h=0.50, min_size=(560, 420), max_size=(960, 680))
WORKSPACE = dict(ratio_w=0.80, ratio_h=0.85, min_size=(960, 640))
RESULTS = Path(__file__).parent / "results"
BENCH = os.environ.get("P0_BENCH") == "1"


async def bring_to_front(page):
    """把窗口拿到最前面；网页模式等不支持时忽略。"""
    with contextlib.suppress(Exception):
        await asyncio.wait_for(page.window.to_front(), 3)


def log_line(text):
    print(f"[window] {text}", flush=True)


async def main(page: ft.Page):
    page.title = "P0-2 · 换窗"
    page.padding = 0
    sw, sh, source = screen_size()
    state = {"mode": "launcher", "close_to_launcher": True, "swaps": []}
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
    async def show(view, title_bar_hidden, size, min_size, resizable=True, how="opacity"):
        """
        换窗：先让窗口看不见，换内容、尺寸、标题栏，居中后再显示。
        how="opacity" 把窗口透明度设为 0（窗口仍在）；how="hide" 隐藏窗口。
        第一轮在 Mac 上窗口一启动就关掉了，怀疑与隐藏窗口有关，所以每一步都记一行。
        """
        t0 = time.perf_counter()
        name = "工作区" if state["mode"] == "workspace" else "启动器"

        def mark(text):
            log_line(f"  {name}·{how}：{text}（{1000 * (time.perf_counter() - t0):.0f} ms）")

        if how == "hide":
            page.window.visible = False
        else:
            page.window.opacity = 0
        page.update()
        mark("已隐藏")
        page.window.title_bar_hidden = title_bar_hidden
        page.window.title_bar_buttons_hidden = False
        page.window.min_width, page.window.min_height = min_size
        page.window.width, page.window.height = size
        page.window.resizable = resizable
        page.controls.clear()
        page.add(view)
        mark("已换内容和尺寸")
        await page.window.center()
        mark("已居中")
        if how == "hide":
            page.window.visible = True
        else:
            page.window.opacity = 1
        page.update()
        await bring_to_front(page)
        dt = (time.perf_counter() - t0) * 1000
        info.value = sizes_text() + f"\n当前窗口设定 {size[0]} × {size[1]}"
        log.value = f"上一次换窗用时 {dt:.0f} ms（请留意换窗时是否闪烁、位置是否居中）"
        page.update()
        state["swaps"].append((state["mode"], how, dt))
        log_line(f"换到{name}（{how}）：{dt:.0f} ms，设定 {size[0]} × {size[1]}")

    async def to_workspace(e=None, how="opacity"):
        state["mode"] = "workspace"
        await show(workspace_view(), False, window_size(sw, sh, **WORKSPACE), WORKSPACE["min_size"], how=how)

    async def to_launcher(e=None, how="opacity"):
        state["mode"] = "launcher"
        await show(launcher_view(), True, window_size(sw, sh, **LAUNCHER), LAUNCHER["min_size"], how=how)

    async def close_window(e=None):
        page.window.prevent_close = False
        await page.window.destroy()

    async def on_window_event(e: ft.WindowEvent):
        if e.type in (ft.WindowEventType.RESIZED, ft.WindowEventType.MOVED):
            w = page.window
            log_line(f"窗口事件 {e.type.value}：位置 ({w.left}, {w.top})，尺寸 {w.width} × {w.height}")
            return
        if e.type != ft.WindowEventType.CLOSE:
            return
        log_line(f"点了关闭按钮（当前：{'工作区' if state['mode'] == 'workspace' else '启动器'}）")
        if state["mode"] == "workspace" and state["close_to_launcher"]:
            await to_launcher()
        else:
            await close_window()

    async def bench():
        await asyncio.sleep(2)
        for _ in range(3):
            await to_workspace()
            await asyncio.sleep(1.5)
            await to_launcher()
            await asyncio.sleep(1.5)
        lines = [f"屏幕 {sw:.0f} × {sh:.0f}（来源：{source}）",
                 f"启动器默认 {window_size(sw, sh, **LAUNCHER)}，工作区默认 {window_size(sw, sh, **WORKSPACE)}"]
        for mode, name in (("workspace", "进入工作区"), ("launcher", "回到启动器")):
            times = [dt for m, how, dt in state["swaps"][1:] if m == mode and how == "opacity"]  # 第一次打开不计
            if times:
                lines.append(f"{name}（透明度方式）：{len(times)} 次，中位数 {statistics.median(times):.0f} ms，"
                             f"最慢 {max(times):.0f} ms")
        RESULTS.mkdir(exist_ok=True)
        (RESULTS / "window.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        for line in lines:
            log_line(line)
        # 最后单独试一次“隐藏窗口”的换窗方式，看它是不是让窗口关掉的原因
        log_line("开始测试隐藏窗口的换窗方式")
        await to_workspace(how="hide")
        await asyncio.sleep(1.5)
        await to_launcher(how="hide")
        log_line("隐藏窗口的换窗方式正常")
        with (RESULTS / "window.txt").open("a", encoding="utf-8") as f:
            f.write("隐藏窗口的换窗方式也正常\n")
        log.value = "自动换窗完成，现在可以手动操作。" + log.value
        page.update()

    page.window.prevent_close = True
    page.window.on_event = on_window_event
    log_line(f"屏幕 {sw:.0f} × {sh:.0f}（来源：{source}）")
    await to_launcher()
    if BENCH:
        page.run_task(bench)


if __name__ == "__main__":
    try:
        ft.run(main)
        log_line("窗口已关闭")
    except KeyboardInterrupt:
        log_line("被 Ctrl+C 中断")
