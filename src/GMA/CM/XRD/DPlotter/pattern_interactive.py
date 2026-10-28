# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
XRD 图谱交互图，基于 plotly。

传入一个 DataFrame 画单条图谱；传入字典时多条图谱画在同一张图中，可上下错开，
并可标出参考物相（references）和峰位（peaks）。

图谱部分的实现在 GMA.CM.common.spectra_interactive，这里绑定 XRD 的横轴（2θ）
并加上参考物相标记。
"""
from ...common import spectra_interactive
from ..schema import AXIS
from .references import add_references, check_references, reference_colors


def plot_pattern_interactive(data, *, references=None, phase_colors=None, **kwargs):
    """
    绘制 XRD 图谱交互图，返回 plotly Figure（.show() 显示，.write_html() 保存）。

    references、phase_colors 的写法同 pattern_static.plot_pattern_static；
    其他参数见 common.spectra_interactive.plot_spectra_interactive，常用的有
    sample_colors、peaks、normalize、offset。
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

        def decorate(fig):
            add_references(fig, references, colors)

    options = {"default_name": "Pattern", **kwargs}
    return spectra_interactive.plot_spectra_interactive(data, AXIS, decorate=decorate, **options)
