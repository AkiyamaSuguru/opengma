# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
XRD 参考物相标记：在标准峰位画竖直虚线，并在图顶部写晶面指数，每个物相一种颜色，
物相名显示在图例中。

references 的写法：{物相名: {标签: 2θ}}，例如
    {"β-SiC": {"(111)": 35.6, "(200)": 41.4, "(220)": 60.0, "(311)": 71.8},
     "Graphite": {"(002)": 26.5}}
标准峰位请以所用射线（如 Cu Kα）对应的 PDF 卡片为准。
"""
from __future__ import annotations

from collections.abc import Mapping

import plotly.graph_objects as go

from ...common.data import as_mapping, check_peaks
from ...common.palette import assign_colors
from ...common.spectra_static import draw_peak_labels
from ...common.style import add_peak_line


def check_references(references) -> dict:
    """检查 references 的写法：{物相名: {标签: 2θ}}。"""
    if not isinstance(references, Mapping) or not all(
        isinstance(peaks, Mapping) for peaks in references.values()
    ):
        raise TypeError(
            "references must be a dict such as "
            "{'β-SiC': {'(111)': 35.6, '(220)': 60.0}, 'Graphite': {'(002)': 26.5}}."
        )
    for peaks in references.values():
        check_peaks(peaks)
    return dict(references)


def reference_colors(
        references,
        data=None,
        palette=None,
        phase_colors=None,
        sample_colors=None,
) -> dict:
    """
    给每个物相分配颜色：phase_colors 中有的用指定颜色，其余按通用色卡取色，
    并避开 data 中各条图谱曲线的颜色，避免物相标记和曲线同色。
    """
    phases = list(references)
    avoid = []
    if data is not None:
        avoid = assign_colors(list(as_mapping(data)), palette, sample_colors)
    colors = assign_colors(
        phases,
        palette,
        phase_colors,
        avoid=avoid,
        warn_missing=True,
        custom_name="phase_colors",
    )
    return dict(zip(phases, colors, strict=True))


def draw_references(ax, references, *, colors=None, palette=None, phase_colors=None, linewidth=0.8):
    """
    在静态图的 ax 上画参考物相标记。

    colors : {物相名: 颜色}，可选；不给时按 phase_colors 和 palette 分配。
    """
    references = check_references(references)
    if colors is None:
        colors = reference_colors(references, palette=palette, phase_colors=phase_colors)

    for phase, peaks in references.items():
        draw_peak_labels(
            ax,
            peaks,
            color=colors[phase],
            linewidth=linewidth,
            text_color=colors[phase],
            label=phase,
        )
    return ax


def add_references(fig, references, colors) -> None:
    """在交互图上画参考物相标记，并在图例中列出物相名。"""
    for phase, peaks in check_references(references).items():
        color = colors[phase]
        for label, position in peaks.items():
            add_peak_line(fig, position, label, color=color, dash="dash", text_color=color)

        # 图例：用一条不可见的线代表这个物相
        fig.add_trace(
            go.Scatter(
                x=[None],
                y=[None],
                mode="lines",
                name=phase,
                line=dict(color=color, width=1, dash="dash"),
                hoverinfo="skip",
            )
        )
