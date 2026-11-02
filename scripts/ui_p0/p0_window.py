# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
P0-2：窗口默认尺寸按屏幕比例、同一进程换窗、关闭工作区回到启动器。

Windows、macOS、Linux 用同一套做法，不为某个系统单独处理：
- 屏幕尺寸：Flet 没有读取屏幕尺寸的接口，这里把窗口（透明时）最大化一次，读出可用区域
  （去掉菜单栏、Dock、任务栏后）的尺寸，再还原；读不到时用默认值。
- 两个窗口都用系统标题栏，移动、缩放、关闭都是系统自己的操作。
- 换窗时把窗口透明度设为 0，换好内容、尺寸并居中后再设回 1。不隐藏窗口：
  在 macOS 上隐藏唯一的窗口（window.visible = False）会让程序直接退出。

运行（在仓库根目录）：
    uv run python scripts/ui_p0/p0_window.py

自动换窗：用环境变量 P0_BENCH=1 运行，启动后自动在启动器和工作区之间来回切换 3 次并记录用时，
结果写入 results/window.txt，之后停在启动器，可以继续手动操作。
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
from _common import window_size  # noqa: E402

MIN_SIZE = (560, 420)  # 两个窗口共用的最小尺寸
LAUNCHER = dict(ratio_w=0.42, ratio_h=0.52, min_size=MIN_SIZE, max_size=(960, 700))
WORKSPACE = dict(ratio_w=0.85, ratio_h=0.90, min_size=(960, 640))  # 这里的 min_size 只用于计算默认尺寸
FALLBACK_AREA = (1440.0, 860.0)  # 读不到可用区域时假定的尺寸
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
    state = {"mode": "launcher", "close_to_launcher": True, "swaps": [], "resized_at": 0.0, "size": None,
             "area": FALLBACK_AREA, "area_note": "未测量"}
    info = ft.Text("", size=12, selectable=True)
    log = ft.Text("", size=12, color=ft.Colors.BLUE_GREY_600, selectable=True)

    def sizes_text():
        aw, ah = state["area"]
        lw, lh = window_size(aw, ah, **LAUNCHER)
        ww, wh = window_size(aw, ah, **WORKSPACE)
        return (f"可用区域 {aw:.0f} × {ah:.0f}（{state['area_note']}）\n"
                f"启动器默认 {lw} × {lh}　工作区默认 {ww} × {wh}")

    # ---------- 两种界面（都用系统标题栏） ----------
    def launcher_view():
        return ft.Container(padding=20, expand=True, content=ft.Column([
            ft.Text("OpenGMA · 启动器", size=18, weight=ft.FontWeight.BOLD),
            ft.Text("用系统标题栏移动、缩放、关闭窗口；关闭启动器即退出。", size=13),
            info,
            ft.Row([ft.Button("进入工作区", icon=ft.Icons.ARROW_FORWARD, on_click=to_workspace)]),
            log,
        ], spacing=12))

    def workspace_view():
        return ft.Container(padding=20, expand=True, content=ft.Column([
            ft.Text("工作区", size=18, weight=ft.FontWeight.BOLD),
            info,
            ft.Switch(label="关闭窗口时回到启动器（关闭此项则直接退出）", value=state["close_to_launcher"],
                      on_change=lambda e: state.update(close_to_launcher=bool(e.control.value))),
            ft.Row([ft.Button("回到启动器", icon=ft.Icons.ARROW_BACK, on_click=to_launcher)]),
            log,
        ], spacing=12))

    # ---------- 可用区域：最大化一次再还原 ----------
    async def measure_area(timeout=3.0, settle=0.3):
        """窗口透明时最大化，等尺寸稳定（settle 秒内没有新的尺寸变化）后读出，再还原。"""
        t0 = time.perf_counter()
        page.window.opacity = 0
        page.window.maximized = True
        page.update()
        size = None
        while time.perf_counter() - t0 < timeout:
            await asyncio.sleep(0.05)
            changed_at = state["resized_at"]
            if changed_at > t0 and time.perf_counter() - changed_at > settle and state["size"]:
                size = state["size"]
                break
        page.window.maximized = False
        page.update()
        t1 = time.perf_counter()  # 等还原完成，否则还原会覆盖接下来设定的尺寸
        while time.perf_counter() - t1 < timeout:
            await asyncio.sleep(0.05)
            if state["resized_at"] > t1 and time.perf_counter() - state["resized_at"] > settle:
                break
        ms = 1000 * (time.perf_counter() - t0)
        if size is None:
            state["area"], state["area_note"] = FALLBACK_AREA, f"没有读到，用默认值（等了 {ms:.0f} ms）"
        else:
            state["area"], state["area_note"] = size, f"最大化窗口测得，用时 {ms:.0f} ms"
        log_line(f"可用区域 {state['area'][0]:.0f} × {state['area'][1]:.0f}（{state['area_note']}）")

    # ---------- 换窗 ----------
    async def show(view, size):
        """换窗：透明度设为 0，换内容和尺寸，居中后再设回 1。"""
        t0 = time.perf_counter()
        name = "工作区" if state["mode"] == "workspace" else "启动器"
        page.window.opacity = 0
        page.update()
        page.window.width, page.window.height = size
        page.controls.clear()
        page.add(view)
        await page.window.center()
        page.window.opacity = 1
        page.update()
        await bring_to_front(page)
        dt = (time.perf_counter() - t0) * 1000
        info.value = sizes_text() + f"\n当前窗口设定 {size[0]} × {size[1]}"
        log.value = f"上一次换窗用时 {dt:.0f} ms（请留意换窗时是否闪烁、位置是否居中）"
        page.update()
        state["swaps"].append((state["mode"], dt))
        log_line(f"换到{name}：{dt:.0f} ms，设定 {size[0]} × {size[1]}")

    async def to_workspace(e=None):
        state["mode"] = "workspace"
        await show(workspace_view(), window_size(*state["area"], **WORKSPACE))

    async def to_launcher(e=None):
        state["mode"] = "launcher"
        await show(launcher_view(), window_size(*state["area"], **LAUNCHER))

    async def close_window(e=None):
        page.window.prevent_close = False
        await page.window.destroy()

    async def on_window_event(e: ft.WindowEvent):
        if e.type == ft.WindowEventType.RESIZED:
            state["resized_at"] = time.perf_counter()
            state["size"] = (page.window.width, page.window.height)
        if e.type in (ft.WindowEventType.RESIZED, ft.WindowEventType.MOVED, ft.WindowEventType.MAXIMIZE,
                      ft.WindowEventType.UNMAXIMIZE):
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
        aw, ah = state["area"]
        lines = [f"可用区域 {aw:.0f} × {ah:.0f}（{state['area_note']}）",
                 f"启动器默认 {window_size(aw, ah, **LAUNCHER)}，工作区默认 {window_size(aw, ah, **WORKSPACE)}"]
        for mode, name in (("workspace", "进入工作区"), ("launcher", "回到启动器")):
            times = [dt for m, dt in state["swaps"][1:] if m == mode]  # 第一次打开启动器不计
            if times:
                lines.append(f"{name}：{len(times)} 次，中位数 {statistics.median(times):.0f} ms，"
                             f"最慢 {max(times):.0f} ms")
        RESULTS.mkdir(exist_ok=True)
        (RESULTS / "window.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        for line in lines:
            log_line(line)
        log.value = "自动换窗完成，现在可以手动操作。" + log.value
        page.update()

    # 最小尺寸只设一次，两个窗口共用：换窗时改最小尺寸，有的系统会先按旧的最小尺寸调整大小
    # （Linux 上从工作区回到启动器时窗口停在 960 × 640）。工作区缩得更小时由界面自己适应。
    page.window.min_width, page.window.min_height = MIN_SIZE
    page.window.prevent_close = True
    page.window.on_event = on_window_event
    await measure_area()
    await to_launcher()
    if BENCH:
        page.run_task(bench)


if __name__ == "__main__":
    try:
        ft.run(main)
        log_line("窗口已关闭")
    except KeyboardInterrupt:
        log_line("被 Ctrl+C 中断")
