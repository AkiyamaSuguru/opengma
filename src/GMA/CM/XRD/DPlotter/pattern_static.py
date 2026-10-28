# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
XRD 图谱静态出版图，基于 matplotlib。

三种画法：
- 单条图谱：传入一个 DataFrame；
- 多条图谱画在同一个坐标轴中：传入字典（默认），可用 offset 上下错开；
- 多条图谱各占一个子图：传入字典，并设置 subplots=True。

标注：
- references：参考物相标记，{物相名: {晶面指数: 2θ}}，每个物相一种颜色，物相名显示在图例中；
- peaks：普通峰位标记，{标签: 2θ}，灰色虚线。

配色：默认按通用色卡 palette 取色；出版绘图时可传 sample_colors（按样品）
和 phase_colors（按物相，如 DPlotter/color_tables.py 中的 PHASE_COLORS）。

图谱部分的实现在 GMA.CM.common.spectra_static（XPS 全谱、Raman 谱、XRD 图谱共用），
这里绑定 XRD 的横轴（2θ）并加上参考物相标记。
"""
from ...common import spectra_static
from ...common.spectra_static import draw_peak_labels
from ..schema import AXIS
from .references import check_references, draw_references, reference_colors


def draw_pattern(ax, df, **kwargs):
    """
    画一条 XRD 图谱。

    参数见 common.spectra_static.draw_spectrum，常用的有 color、offset、normalize、
    hide_y_ticks。
    """
    return spectra_static.draw_spectrum(ax, df, AXIS, **kwargs)


def plot_pattern_static(data, *, references=None, phase_colors=None, **kwargs):
    """
    XRD 图谱静态出版图：单条、多条画在同一张图（可错开），或多条各占一个子图。

    references : {物相名: {标签: 2θ}}，可选，参考物相标记，例如
        {"β-SiC": {"(111)": 35.6, "(220)": 60.0}, "Graphite": {"(002)": 26.5}}。
    phase_colors : {物相名: 颜色}，可选，如 DPlotter/color_tables.py 中的 PHASE_COLORS。
    其他参数见 common.spectra_static.plot_spectra_static，常用的有 subplots、sample_colors、
    peaks、normalize、offset、hide_y_ticks、save_path。
    同一张图时返回 (fig, ax)，子图模式返回 (fig, axes)。
    """
    decorate = None
    if references:
        references = check_references(references)
        colors = reference_colors(
            references,
            data,
            palette=kwargs.get("palette"),
            phase_colors=phase_colors,
            sample_colors=kwargs.get("sample_colors"),
        )

        def decorate(ax, key):
            draw_references(ax, references, colors=colors)

    return spectra_static.plot_spectra_static(data, AXIS, decorate=decorate, **kwargs)


__all__ = ["draw_pattern", "draw_peak_labels", "draw_references", "plot_pattern_static"]
