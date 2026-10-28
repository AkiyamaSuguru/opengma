# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
Raman 绘图入口：用一个类统一管理 Raman 的四种图。

具体实现在 RPlotter 文件夹：
- spectrum_static：谱线静态出版图（单条 / 同一张图 / 子图）
- spectrum_interactive：谱线交互图（单条 / 同一张图）
- fit_static：拟合谱（分峰）静态出版图（单条 / 子图）
- fit_interactive：拟合谱交互图（一次一条）
- color_tables：Raman 定制色表 COMPONENT_COLORS

传入单个 DataFrame 画单条谱，传入 {名称: DataFrame} 字典画多条谱。

配色分两层：
- 通用色卡 palette：默认使用 common/color_tables.py 中的 DEFAULT_PALETTE（"tab10"），
  可以在 RamanPlotter 上全局设置。初期分析时不用管颜色。
- 定制色表：出版绘图时按需传入。谱线用 sample_colors（按样品），
  拟合谱用 component_colors（按谱峰，如 "D"、"G"）。

用法：
    from GMA.CM.common import SAMPLE_COLORS
    from GMA.CM.Raman import RamanLoader, RamanPlotter
    from GMA.CM.Raman.RPlotter import COMPONENT_COLORS

    spectrum, metadata = RamanLoader("Horiba HR evolution").read("sample.txt")
    plotter = RamanPlotter()

    plotter.plot_spectrum_interactive(spectrum, peaks={"D": 1350, "G": 1580}).show()
    plotter.plot_spectrum_static({"As-deposited": s1, "Corroded": s2},
                                 sample_colors=SAMPLE_COLORS,
                                 normalize=True, offset=1.0, hide_y_ticks=True)
    plotter.plot_fit_static(fitted, component_colors=COMPONENT_COLORS)
"""
from __future__ import annotations

from ..common.plotter import BasePlotter
from .RPlotter import fit_interactive, fit_static, spectrum_interactive, spectrum_static
from .schema import AXIS


class RamanPlotter(BasePlotter):
    """
    Raman 绘图统一入口：保存各种图共用的设置（字体、通用色卡），数据在调用时传入。

    构造参数（font_family、font_size、interactive_font_size、palette、use_latex）
    见 GMA.CM.common.plotter.BasePlotter。

    定制色表不在这里设置，而是在各绘图方法中传入：
    谱线用 sample_colors，拟合谱用 component_colors。
    """

    AXIS = AXIS

    # ============================================================
    # 谱线：按样品定制颜色（sample_colors）
    # ============================================================
    def plot_spectrum_static(self, data, *, sample_colors=None, **kwargs):
        """
        Raman 谱静态出版图。

        sample_colors : {样品名: 颜色}，可选，如 common/color_tables.py 中的 SAMPLE_COLORS。
        其他参数见 GMA.CM.common.spectra_static.plot_spectra_static。
        """
        return spectrum_static.plot_spectrum_static(
            data, sample_colors=sample_colors, **self._options(kwargs)
        )

    def plot_spectrum_interactive(self, data, *, sample_colors=None, **kwargs):
        """
        Raman 谱交互图。

        sample_colors : {样品名: 颜色}，可选，如 common/color_tables.py 中的 SAMPLE_COLORS。
        其他参数见 GMA.CM.common.spectra_interactive.plot_spectra_interactive。
        """
        return spectrum_interactive.plot_spectrum_interactive(
            data, sample_colors=sample_colors, **self._options(kwargs, interactive=True)
        )

    # ============================================================
    # 拟合谱：按谱峰定制颜色（component_colors）
    # ============================================================
    def plot_fit_static(self, data, *, component_colors=None, **kwargs):
        """
        拟合谱静态出版图。

        component_colors : {分峰名: 颜色}，可选，如 RPlotter/color_tables.py 中的
        COMPONENT_COLORS。其他参数见 GMA.CM.common.fit_static.plot_fits_static。
        """
        return fit_static.plot_fit_static(
            data, component_colors=component_colors, **self._options(kwargs)
        )

    def plot_fit_interactive(self, df, *, component_colors=None, **kwargs):
        """
        拟合谱交互图（一次一条）。

        component_colors : {分峰名: 颜色}，可选，如 RPlotter/color_tables.py 中的
        COMPONENT_COLORS。其他参数见 GMA.CM.common.fit_interactive.plot_fit_interactive。
        """
        return fit_interactive.plot_fit_interactive(
            df, component_colors=component_colors, **self._options(kwargs, interactive=True)
        )
