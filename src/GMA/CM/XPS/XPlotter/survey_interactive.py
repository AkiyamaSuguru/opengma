"""
XPS 全谱（survey）交互图，基于 plotly。

传入一个 DataFrame 画单条谱；传入字典时多条谱画在同一张图中，可上下错开，
并可标出元素峰位置。

配色与静态图一致：默认按通用色卡 palette 取色，可传 sample_colors 按样品指定颜色。
"""
from __future__ import annotations

import plotly.graph_objects as go

from ._common import (
    DEFAULT_FONT_FAMILY,
    DEFAULT_INTERACTIVE_FONT_SIZE,
    as_mapping,
    assign_colors,
    hover_template,
    merge_peaks,
    peaks_by_spectrum,
    prepare_survey,
    style_plotly_figure,
)


def plot_survey_interactive(
        data,
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
):
    """
    绘制全谱交互图。

    参数含义与 survey_static.plot_survey_static 中同一张图的画法相同：
    palette 为通用色卡，sample_colors 为按样品指定颜色的定制色表（默认不使用）。
    peaks 按样品分别写时合并标注。错开显示时，悬停提示中的强度仍是平移前的数值。

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
    for i, ((key, df), color) in enumerate(zip(dfs.items(), colors)):
        be, intensity = prepare_survey(df, normalize)
        name = str(key) if key != "" else "Survey"
        fig.add_trace(
            go.Scatter(
                x=be,
                y=intensity + (n - 1 - i) * offset,
                customdata=intensity,  # 悬停时显示平移前的强度
                mode="lines",
                name=name,
                showlegend=key != "",
                line=dict(color=color, width=linewidth),
                hovertemplate=hover_template(name, y_field="customdata"),
            )
        )

    # 元素峰位置：竖直虚线 + 顶部标签
    for label, be in all_peaks.items():
        fig.add_vline(
            x=be,
            line=dict(color="gray", width=1, dash="dot"),
            layer="below",
            annotation_text=str(label),
            annotation_position="top",
        )

    return style_plotly_figure(fig, font_family, font_size, hide_y_ticks)