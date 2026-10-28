# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
XRD 绘图的具体实现，统一入口见上一级的 plotter.py（XRDPlotter）。

- pattern_static：图谱静态出版图（单条 / 同一张图 / 子图）
- pattern_interactive：图谱交互图（单条 / 同一张图）
- references：参考物相标记
- color_tables：XRD 定制色表 PHASE_COLORS

图谱绘制与 XPS、Raman 共用，在 GMA.CM.common 中实现；这里绑定 XRD 的横轴，
并提供参考物相标记。
"""
from ...common.color_tables import SAMPLE_COLORS
from ...common.style import mpl_style
from .color_tables import PHASE_COLORS
from .pattern_interactive import plot_pattern_interactive
from .pattern_static import draw_pattern, draw_peak_labels, plot_pattern_static
from .references import draw_references

__all__ = [
    "PHASE_COLORS",
    "SAMPLE_COLORS",
    "draw_pattern",
    "draw_peak_labels",
    "draw_references",
    "mpl_style",
    "plot_pattern_interactive",
    "plot_pattern_static",
]
