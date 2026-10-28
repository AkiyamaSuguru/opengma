# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
Raman 绘图的具体实现，统一入口见上一级的 plotter.py（RamanPlotter）。

- spectrum_static：谱线静态出版图（单条 / 同一张图 / 子图）
- spectrum_interactive：谱线交互图
- fit_static：拟合谱（分峰）静态出版图
- fit_interactive：拟合谱交互图
- color_tables：Raman 定制色表 COMPONENT_COLORS

绘图逻辑与 XPS、XRD 共用，在 GMA.CM.common 中实现；这里只绑定 Raman 的横轴。
"""
from ...common.color_tables import SAMPLE_COLORS
from ...common.style import mpl_style
from .color_tables import COMPONENT_COLORS
from .fit_interactive import plot_fit_interactive
from .fit_static import draw_fit, plot_fit_static
from .spectrum_interactive import plot_spectrum_interactive
from .spectrum_static import draw_peak_labels, draw_spectrum, plot_spectrum_static

__all__ = [
    "COMPONENT_COLORS",
    "SAMPLE_COLORS",
    "draw_fit",
    "draw_peak_labels",
    "draw_spectrum",
    "mpl_style",
    "plot_fit_interactive",
    "plot_fit_static",
    "plot_spectrum_interactive",
    "plot_spectrum_static",
]
