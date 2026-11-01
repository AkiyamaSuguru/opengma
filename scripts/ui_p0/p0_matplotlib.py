# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
P0-3：出版图预览的两种做法对比。

左：MatplotlibChart 直接显示 GMA 的 figure（自带平移、缩放工具栏）。
右：savefig 导出的 PNG，放在 InteractiveViewer 中，可以用触控板 / 滚轮缩放、拖动。

在这里（Linux 无头浏览器）初步看到的情况：MatplotlibChart 会把 figure 拉伸到控件大小，
字号、线宽相对图面变小，与导出的 3.2 × 2.4 in 图不一致；导出的图片则与最终文件完全一致。

运行（在仓库根目录）：
    uv run --with flet-charts==1.0.5 python scripts/ui_p0/p0_matplotlib.py

要验证的内容见同目录 README.md。
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import flet as ft
import flet_charts as fch  # 导入时会把 matplotlib 的后端设为 Flet 专用后端，要在 GMA 之前导入

sys.path.insert(0, str(Path(__file__).parent))
from _common import xps_c1s_frame  # noqa: E402

from GMA import XPSPlotter  # noqa: E402

COLORS = {"C-Si": "#2563EB", "C-C": "#F59E0B", "C-O": "#10B981"}


def figure_and_png(font_family, font_size):
    plotter = XPSPlotter(font_family=font_family, font_size=font_size)
    fig, _ = plotter.plot_element_static(xps_c1s_frame(), show=False, component_colors=COLORS)
    buf = io.BytesIO()
    with plotter.style():
        fig.savefig(buf, format="png", dpi=300)
    return fig, buf.getvalue()


def main(page: ft.Page):
    page.title = "P0-3 · MatplotlibChart"
    page.window.width, page.window.height = 1280, 760
    page.padding = 16
    left, right = ft.Container(expand=True), ft.Container(expand=True)
    note = ft.Text("", size=12, color=ft.Colors.BLUE_GREY_600)

    def render(font_family="Times New Roman", font_size=8):
        fig, png = figure_and_png(font_family, font_size)
        left.content = fch.MatplotlibChartWithToolbar(figure=fig, expand=True)
        right.content = ft.InteractiveViewer(content=ft.Image(src=png, fit=ft.BoxFit.CONTAIN),
                                             min_scale=1, max_scale=8, expand=True)
        size = fig.get_size_inches()
        note.value = f"图尺寸 {size[0]:.1f} × {size[1]:.1f} in · {font_family} {font_size} pt"
        page.update()

    font = ft.Dropdown(label="字体", value="Times New Roman", width=220, dense=True, text_size=13, options=[
        ft.DropdownOption(key=k, text=k) for k in ("Times New Roman", "Arial", "Helvetica", "DejaVu Serif")])
    size = ft.Dropdown(label="字号", value="8", width=110, dense=True, text_size=13, options=[
        ft.DropdownOption(key=k, text=f"{k} pt") for k in ("7", "8", "9", "10")])
    font.on_select = size.on_select = lambda e: render(font.value, float(size.value))

    page.add(ft.Column([
        ft.Text("P0-3 · MatplotlibChart 显示 GMA 出版图", size=18, weight=ft.FontWeight.BOLD),
        ft.Row([font, size, note], spacing=12),
        ft.Row([
            ft.Column([ft.Text("界面中的 MatplotlibChart（可平移、缩放）", size=12), left], expand=True),
            ft.Column([ft.Text("同一个 figure 用 savefig 导出的 PNG（InteractiveViewer，可缩放、拖动）", size=12),
                       right], expand=True),
        ], expand=True, spacing=16),
    ], expand=True))
    render()


if __name__ == "__main__":
    ft.run(main)
