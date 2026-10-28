# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
XPS 绘图的具体实现，统一入口见上一级的 plotter.py（XPSPlotter）。

- element_static：元素谱静态出版图（matplotlib）
- survey_static：全谱静态出版图（matplotlib）
- element_interactive：元素谱交互图（plotly）
- survey_interactive：全谱交互图（plotly）
- color_tables：XPS 定制色表 COMPONENT_COLORS

绘图逻辑与 Raman、XRD 共用，在 GMA.CM.common 中实现；这里只绑定 XPS 的横轴。
"""
from ...common.color_tables import SAMPLE_COLORS
from ...common.style import mpl_style
from .color_tables import COMPONENT_COLORS
from .element_interactive import plot_element_interactive
from .element_static import (
    detect_element_type,
    draw_element,
    draw_element_fit,
    draw_element_raw,
    plot_element_static,
)
from .survey_interactive import plot_survey_interactive
from .survey_static import draw_peak_labels, draw_survey, plot_survey_static

__all__ = [
    "COMPONENT_COLORS",
    "SAMPLE_COLORS",
    "detect_element_type",
    "draw_element",
    "draw_element_fit",
    "draw_element_raw",
    "draw_peak_labels",
    "draw_survey",
    "mpl_style",
    "plot_element_interactive",
    "plot_element_static",
    "plot_survey_interactive",
    "plot_survey_static",
]
