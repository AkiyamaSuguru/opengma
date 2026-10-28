# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
各表征方法 Plotter（XPSPlotter、RamanPlotter、XRDPlotter）的基类。
"""
from __future__ import annotations

from .axis import SpectrumAxis
from .data import as_mapping, detect_fit_type
from .style import (
    DEFAULT_FONT_FAMILY,
    DEFAULT_FONT_SIZE,
    DEFAULT_INTERACTIVE_FONT_SIZE,
    mpl_style,
)


class BasePlotter:
    """
    保存各种图共用的设置（字体、通用色卡），数据在调用时传入。

    Parameters
    ----------
    font_family : str
        字体，静态图和交互图共用。
    font_size : int 或 float
        静态图字号（pt）。
    interactive_font_size : int 或 float
        交互图字号（px）。
    palette : 通用色卡名或颜色列表，可选
        这个 Plotter 的所有图共用，None 时使用 common/color_tables.py 中的
        DEFAULT_PALETTE。可以写 matplotlib 的色卡名（如 "tab10"、"Set2"、"viridis"）
        或颜色列表。
    use_latex : bool
        静态图是否用 LaTeX 渲染文字（需要安装 LaTeX）。

    定制色表不在这里设置，而是在各绘图方法中传入（如 component_colors、sample_colors）。
    各绘图方法的其他参数原样传给对应的绘图函数，调用时传入的参数优先。
    子类需要设置 AXIS（SpectrumAxis）。
    """

    AXIS: SpectrumAxis

    def __init__(
            self,
            font_family=DEFAULT_FONT_FAMILY,
            font_size=DEFAULT_FONT_SIZE,
            interactive_font_size=DEFAULT_INTERACTIVE_FONT_SIZE,
            palette=None,
            use_latex=False,
    ):
        self.font_family = font_family
        self.font_size = font_size
        self.interactive_font_size = interactive_font_size
        self.palette = palette
        self.use_latex = use_latex

    def style(self):
        """
        返回 matplotlib 样式上下文。用 draw_* 函数自己组合多面板图时，
        把建图和保存都放在 with 块内：

            with plotter.style():
                fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(6.4, 2.4))
                ...
                fig.savefig("figure.png", dpi=600, bbox_inches="tight")
        """
        return mpl_style(self.font_family, self.font_size, self.use_latex)

    @classmethod
    def info(cls, data):
        """打印每条谱的类型（raw：谱线 / fit：拟合谱）、形状和列名。"""
        for key, df in as_mapping(data).items():
            try:
                kind = detect_fit_type(df, cls.AXIS)
            except ValueError as exc:
                kind = f"invalid ({exc})"

            print(f"[{key}]" if key != "" else "[spectrum]")
            print(f"Type: {kind}")
            print(f"Shape: {df.shape}")
            print(f"Columns: {list(df.columns)}\n")

    def _options(self, kwargs, *, interactive=False):
        """把实例上的字体、通用色卡设置和调用时传入的参数合并，调用时传入的优先。"""
        options = {"font_family": self.font_family, "palette": self.palette}
        if interactive:
            options["font_size"] = self.interactive_font_size
        else:
            options["font_size"] = self.font_size
            options["use_latex"] = self.use_latex
        return {**options, **kwargs}
