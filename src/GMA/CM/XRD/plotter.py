# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
XRD 绘图入口：用一个类统一管理 XRD 的两种图。

具体实现在 DPlotter 文件夹：
- pattern_static：图谱静态出版图（单条 / 同一张图 / 子图）
- pattern_interactive：图谱交互图（单条 / 同一张图）
- references：参考物相标记
- color_tables：XRD 定制色表 PHASE_COLORS

传入单个 DataFrame 画单条图谱，传入 {名称: DataFrame} 字典画多条图谱。

配色分两层：
- 通用色卡 palette：默认使用 common/color_tables.py 中的 DEFAULT_PALETTE（"tab10"），
  可以在 XRDPlotter 上全局设置。初期分析时不用管颜色。
- 定制色表：出版绘图时按需传入。图谱用 sample_colors（按样品），
  参考物相用 phase_colors（按物相）。

用法：
    from GMA.CM.XRD import XRDLoader, XRDPlotter
    from GMA.CM.XRD.DPlotter import PHASE_COLORS

    pattern, metadata = XRDLoader("D8 Advance").read("sample.txt")
    references = {"β-SiC": {"(111)": 35.6, "(200)": 41.4, "(220)": 60.0, "(311)": 71.8}}

    plotter = XRDPlotter()
    plotter.plot_pattern_interactive(pattern, references=references).show()
    plotter.plot_pattern_static({"As-deposited": p1, "Corroded": p2},
                                references=references, phase_colors=PHASE_COLORS,
                                normalize=True, offset=1.0, hide_y_ticks=True)
"""
from __future__ import annotations

from ..common.plotter import BasePlotter
from .DPlotter import pattern_interactive, pattern_static
from .schema import AXIS


class XRDPlotter(BasePlotter):
    """
    XRD 绘图统一入口：保存各种图共用的设置（字体、通用色卡），数据在调用时传入。

    构造参数（font_family、font_size、interactive_font_size、palette、use_latex）
    见 GMA.CM.common.plotter.BasePlotter。

    定制色表不在这里设置，而是在各绘图方法中传入：
    图谱用 sample_colors，参考物相用 phase_colors。
    """

    AXIS = AXIS

    def plot_pattern_static(
            self,
            data,
            *,
            sample_colors=None,
            references=None,
            phase_colors=None,
            **kwargs,
    ):
        """
        XRD 图谱静态出版图。

        sample_colors : {样品名: 颜色}，可选，如 common/color_tables.py 中的 SAMPLE_COLORS。
        references : {物相名: {标签: 2θ}}，可选，参考物相标记。
        phase_colors : {物相名: 颜色}，可选，如 DPlotter/color_tables.py 中的 PHASE_COLORS。
        其他参数见 GMA.CM.common.spectra_static.plot_spectra_static。
        """
        return pattern_static.plot_pattern_static(
            data,
            sample_colors=sample_colors,
            references=references,
            phase_colors=phase_colors,
            **self._options(kwargs),
        )

    def plot_pattern_interactive(
            self,
            data,
            *,
            sample_colors=None,
            references=None,
            phase_colors=None,
            **kwargs,
    ):
        """
        XRD 图谱交互图。

        sample_colors、references、phase_colors 同 plot_pattern_static；
        其他参数见 GMA.CM.common.spectra_interactive.plot_spectra_interactive。
        """
        return pattern_interactive.plot_pattern_interactive(
            data,
            sample_colors=sample_colors,
            references=references,
            phase_colors=phase_colors,
            **self._options(kwargs, interactive=True),
        )
