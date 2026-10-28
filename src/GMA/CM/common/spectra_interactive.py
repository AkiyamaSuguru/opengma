# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
谱线交互图（plotly），各表征方法共用：XPS 全谱、Raman 谱、XRD 图谱。

传入一个 DataFrame 画单条谱；传入字典时多条谱画在同一张图中，可上下错开，
并可标出峰位。横轴（列名、标题、方向）由 axis（SpectrumAxis）决定。
"""
from __future__ import annotations

import plotly.graph_objects as go

from .data import as_mapping, merge_peaks, peaks_by_spectrum, prepare_spectrum
from .palette import assign_colors
from .style import (
    DEFAULT_FONT_FAMILY,
    DEFAULT_INTERACTIVE_FONT_SIZE,
    add_peak_line,
    hover_template,
    style_plotly_figure,
)


def plot_spectra_interactive(
        data,
        axis,
        *,
        palette=None,
        sample_colors=None,
        peaks=None,
        offset=0.0,
        normalize=False,
        linewidth=1.2,
        hide_y_ticks=False,
        font_family=DEFAULT_FONT_FAMILY,
        font_size=DEFAULT_INTERACTIVE_FONT_SIZE,
        default_name="Spectrum",
        decorate=None,
):
    """
    绘制谱线交互图。

    参数含义与 spectra_static.plot_spectra_static 中同一张图的画法相同：
    palette 为通用色卡，sample_colors 为按样品指定颜色的定制色表（默认不使用）。
    peaks 按样品分别写时合并标注。错开显示时，悬停提示中的强度仍是平移前的数值。
    default_name 为单条谱（没有样品名）在悬停提示中显示的名称。
    decorate(fig) 可在返回前补充内容（如 XRD 参考物相）。

    Returns
    -------
    plotly.graph_objects.Figure
        fig.show() 显示，fig.write_html(...) 保存为网页。
    """
    dfs = as_mapping(data)
    colors = assign_colors(list(dfs), palette, sample_colors, custom_name="sample_colors")
    all_peaks = merge_peaks(peaks_by_spectrum(peaks, dfs))
    n = len(dfs)

    fig = go.Figure()
    for i, ((key, df), color) in enumerate(zip(dfs.items(), colors, strict=True)):
        x, intensity = prepare_spectrum(df, axis, normalize)
        name = str(key) if key != "" else default_name
        fig.add_trace(
            go.Scatter(
                x=x,
                y=intensity + (n - 1 - i) * offset,
                customdata=intensity,  # 悬停时显示平移前的强度
                mode="lines",
                name=name,
                showlegend=key != "",
                line=dict(color=color, width=linewidth),
                hovertemplate=hover_template(name, axis, y_field="customdata"),
            )
        )

    # 峰位：竖直虚线 + 顶部标签
    for label, position in all_peaks.items():
        add_peak_line(fig, position, label)

    if decorate is not None:
        decorate(fig)

    return style_plotly_figure(fig, axis, font_family, font_size, hide_y_ticks)
