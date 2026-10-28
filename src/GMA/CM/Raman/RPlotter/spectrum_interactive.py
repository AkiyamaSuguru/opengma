# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
Raman 谱交互图，基于 plotly。

传入一个 DataFrame 画单条谱；传入字典时多条谱画在同一张图中，可上下错开，
并可标出谱峰位置。

具体实现在 GMA.CM.common.spectra_interactive，这里绑定 Raman 的横轴（拉曼位移）。
"""
from ...common import spectra_interactive
from ..schema import AXIS


def plot_spectrum_interactive(data, **kwargs):
    """
    绘制 Raman 谱交互图，返回 plotly Figure（.show() 显示，.write_html() 保存）。

    参数见 common.spectra_interactive.plot_spectra_interactive，常用的有 sample_colors、
    peaks、normalize、offset。
    """
    return spectra_interactive.plot_spectra_interactive(data, AXIS, **kwargs)
