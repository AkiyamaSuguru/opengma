# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
XPS 绘图入口：用一个类统一管理 XPS 的四种图。

具体实现在 XPlotter 文件夹：
- element_static：元素谱静态出版图（matplotlib）
- survey_static：全谱静态出版图（matplotlib）
- element_interactive：元素谱交互图（plotly）
- survey_interactive：全谱交互图（plotly）
- color_tables：XPS 定制色表 COMPONENT_COLORS

传入单个 DataFrame 画单条谱，传入 {名称: DataFrame} 字典画多条谱。

配色分两层：
- 通用色卡 palette：默认使用 common/color_tables.py 中的 DEFAULT_PALETTE（"tab10"），
  可以在 XPSPlotter 上全局设置，四种图共用。初期分析时不用管颜色。
- 定制色表：出版绘图时按需传入。元素谱用 component_colors（按化学键，如 "C-Si"），
  全谱用 sample_colors（按样品，不同样品可以同色）。

用法：
    from GMA.CM.common import SAMPLE_COLORS
    from GMA.CM.XPS import XPSPlotter
    from GMA.CM.XPS.XPlotter import COMPONENT_COLORS

    plotter = XPSPlotter()  # 全局换通用色卡：XPSPlotter(palette="Set2")

    # 初期分析：不用管颜色
    plotter.plot_element_interactive(c1s).show()
    plotter.plot_survey_interactive({"As-deposited": s1, "Corroded": s2}).show()

    # 出版图：元素谱单个或多个子图；全谱单条、同一张图或多个子图
    plotter.plot_element_static({"C 1s": c1s, "Si 2p": si2p},
                                component_colors=COMPONENT_COLORS, save_path="element.png")
    plotter.plot_survey_static({"As-deposited": s1, "Corroded": s2},
                               sample_colors=SAMPLE_COLORS,
                               normalize=True, offset=1.0, hide_y_ticks=True)
    plotter.plot_survey_static({"As-deposited": s1, "Corroded": s2}, subplots=True)
"""
from __future__ import annotations

from ..common.plotter import BasePlotter
from .schema import AXIS
from .XPlotter import (
    element_interactive,
    element_static,
    survey_interactive,
    survey_static,
)


class XPSPlotter(BasePlotter):
    """
    XPS 绘图统一入口：保存四种图共用的设置（字体、通用色卡），数据在调用时传入。

    构造参数（font_family、font_size、interactive_font_size、palette、use_latex）
    见 GMA.CM.common.plotter.BasePlotter。

    定制色表不在这里设置，而是在各绘图方法中传入：
    元素谱用 component_colors，全谱用 sample_colors。
    """

    AXIS = AXIS

    # ============================================================
    # 元素谱：按化学键定制颜色（component_colors）
    # ============================================================
    def plot_element_static(self, data, *, component_colors=None, **kwargs):
        """
        元素谱静态出版图。

        component_colors : {分峰名: 颜色}，可选，如 XPlotter/color_tables.py 中的
        COMPONENT_COLORS。其他参数见 GMA.CM.common.fit_static.plot_fits_static。
        """
        return element_static.plot_element_static(
            data, component_colors=component_colors, **self._options(kwargs)
        )

    def plot_element_interactive(self, df, *, component_colors=None, **kwargs):
        """
        元素谱交互图（一次一条）。

        component_colors : {分峰名: 颜色}，可选，如 XPlotter/color_tables.py 中的
        COMPONENT_COLORS。其他参数见 GMA.CM.common.fit_interactive.plot_fit_interactive。
        """
        return element_interactive.plot_element_interactive(
            df, component_colors=component_colors, **self._options(kwargs, interactive=True)
        )

    # ============================================================
    # 全谱：按样品定制颜色（sample_colors）
    # ============================================================
    def plot_survey_static(self, data, *, sample_colors=None, **kwargs):
        """
        全谱静态出版图。

        sample_colors : {样品名: 颜色}，可选，如 common/color_tables.py 中的 SAMPLE_COLORS。
        其他参数见 GMA.CM.common.spectra_static.plot_spectra_static。
        """
        return survey_static.plot_survey_static(
            data, sample_colors=sample_colors, **self._options(kwargs)
        )

    def plot_survey_interactive(self, data, *, sample_colors=None, **kwargs):
        """
        全谱交互图。

        sample_colors : {样品名: 颜色}，可选，如 common/color_tables.py 中的 SAMPLE_COLORS。
        其他参数见 GMA.CM.common.spectra_interactive.plot_spectra_interactive。
        """
        return survey_interactive.plot_survey_interactive(
            data, sample_colors=sample_colors, **self._options(kwargs, interactive=True)
        )
