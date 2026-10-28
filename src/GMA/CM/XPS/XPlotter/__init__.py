"""
XPS 绘图的具体实现，统一入口见上一级的 xps_plotter.py。

- element_static：元素谱静态出版图（matplotlib）
- survey_static：全谱静态出版图（matplotlib）
- element_interactive：元素谱交互图（plotly）
- survey_interactive：全谱交互图（plotly）
- color_tables：默认通用色卡和定制色表
"""
from ._common import detect_element_type, mpl_style
from .color_tables import COMPONENT_COLORS, SAMPLE_COLORS
from .element_interactive import plot_element_interactive
from .element_static import (
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