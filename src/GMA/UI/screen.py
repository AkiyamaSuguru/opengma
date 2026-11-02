# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
可用屏幕区域与默认窗口尺寸。

Flet 没有读取屏幕尺寸的接口。这里在窗口透明时把它最大化一次，读出可用区域（去掉菜单栏、Dock、
任务栏后）的尺寸，再还原。Windows、macOS、Linux 用同一段代码，不按系统分别处理（P0-2 验证）。
"""
from __future__ import annotations

import asyncio
import time

import flet as ft

FALLBACK_AREA = (1440.0, 860.0)  # 读不到可用区域时假定的尺寸
MIN_SIZE = (560, 420)            # 启动器和工作区共用的最小尺寸，只在启动时设一次
LAUNCHER_LIMITS = ((560, 420), (960, 700))
WORKSPACE_LIMITS = ((960, 640), None)


def window_size(area, ratio, min_size, max_size=None) -> tuple[int, int]:
    """按可用区域的比例计算窗口尺寸，限制在 [min_size, max_size] 之间，并且不超过可用区域。"""
    w = max(min_size[0], area[0] * ratio[0])
    h = max(min_size[1], area[1] * ratio[1])
    if max_size:
        w, h = min(w, max_size[0]), min(h, max_size[1])
    return round(min(w, area[0])), round(min(h, area[1]))


class WindowTracker:
    """
    记录窗口事件：最近一次尺寸变化的时间和尺寸，并把事件转给其他处理函数。
    page.window.on_event 只能有一个处理函数，所以由它统一分发。
    """

    def __init__(self, page: ft.Page):
        self.page = page
        self.resized_at = 0.0
        self.size: tuple[float, float] | None = None
        self.handlers = []
        page.window.on_event = self._on_event

    async def _on_event(self, e: ft.WindowEvent):
        if e.type == ft.WindowEventType.RESIZED:
            self.resized_at = time.perf_counter()
            self.size = (self.page.window.width, self.page.window.height)
        for handler in list(self.handlers):
            result = handler(e)
            if asyncio.iscoroutine(result):
                await result

    async def wait_settled(self, since: float, timeout: float = 3.0, settle: float = 0.3) -> bool:
        """等到 since 之后有过尺寸变化，并且 settle 秒内没有新的变化。超时返回 False。"""
        while time.perf_counter() - since < timeout:
            await asyncio.sleep(0.05)
            if self.resized_at > since and time.perf_counter() - self.resized_at > settle:
                return True
        return False


async def measure_work_area(page: ft.Page, tracker: WindowTracker) -> tuple[float, float] | None:
    """窗口透明时最大化一次，读出可用区域再还原；读不到时返回 None。调用前窗口应当是透明的。"""
    t0 = time.perf_counter()
    page.window.maximized = True
    page.update()
    ok = await tracker.wait_settled(t0)
    size = tracker.size if ok else None
    t1 = time.perf_counter()
    page.window.maximized = False
    page.update()
    await tracker.wait_settled(t1)  # 等还原完成，否则还原会覆盖接下来设定的尺寸
    if size and size[0] and size[1]:
        return float(size[0]), float(size[1])
    return None
