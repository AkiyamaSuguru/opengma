# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
XPS 全谱（survey）静态出版图，基于 matplotlib。

三种画法：
- 单条谱：传入一个 DataFrame；
- 多条谱画在同一个坐标轴中：传入字典（默认），可用 offset 上下错开；
- 多条谱各占一个子图：传入字典，并设置 subplots=True。

配色：默认按通用色卡 palette 取色；出版绘图时可传 sample_colors（如
common/color_tables.py 中的 SAMPLE_COLORS），按样品指定颜色，不同样品可以同色。

具体实现在 GMA.CM.common.spectra_static（XPS 全谱、Raman 谱、XRD 图谱共用），
这里绑定 XPS 的横轴（结合能，从高到低）。
"""
from ...common import spectra_static
from ...common.spectra_static import draw_peak_labels
from ..schema import AXIS


def draw_survey(ax, df, **kwargs):
    """
    画一条全谱。

    参数见 common.spectra_static.draw_spectrum，常用的有 color、offset、normalize、
    hide_y_ticks。
    """
    return spectra_static.draw_spectrum(ax, df, AXIS, **kwargs)


def plot_survey_static(data, **kwargs):
    """
    全谱静态出版图：单条、多条画在同一张图（可错开），或多条各占一个子图。

    参数见 common.spectra_static.plot_spectra_static，常用的有 subplots、sample_colors、
    peaks、normalize、offset、hide_y_ticks、save_path。
    同一张图时返回 (fig, ax)，子图模式返回 (fig, axes)。
    """
    return spectra_static.plot_spectra_static(data, AXIS, **kwargs)


__all__ = ["draw_peak_labels", "draw_survey", "plot_survey_static"]
