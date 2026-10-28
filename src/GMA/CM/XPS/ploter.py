"""
XPS 绘图入口：用一个类统一管理 XPS 的四种图。

具体实现在 XPlotter 文件夹：
- element_static：元素谱静态出版图（matplotlib）
- survey_static：全谱静态出版图（matplotlib）
- element_interactive：元素谱交互图（plotly）
- survey_interactive：全谱交互图（plotly）
- color_tables：默认通用色卡和定制色表

传入单个 DataFrame 画单条谱，传入 {名称: DataFrame} 字典画多条谱。

配色分两层：
- 通用色卡 palette：默认使用 color_tables.py 中的 DEFAULT_PALETTE（"tab10"），
  可以在 XPSPlotter 上全局设置，四种图共用。初期分析时不用管颜色。
- 定制色表：出版绘图时按需传入。元素谱用 component_colors（按化学键，如 "C-Si"），
  全谱用 sample_colors（按样品，不同样品可以同色）。

用法：
    from .XPlotter.color_tables import COMPONENT_COLORS, SAMPLE_COLORS

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

from .XPlotter import (
    element_interactive,
    element_static,
    survey_interactive,
    survey_static,
)
from .XPlotter._common import (
    DEFAULT_FONT_FAMILY,
    DEFAULT_FONT_SIZE,
    DEFAULT_INTERACTIVE_FONT_SIZE,
    as_mapping,
    detect_element_type,
    mpl_style,
)


class XPSPlotter:
    """
    XPS 绘图统一入口：保存四种图共用的设置（字体、通用色卡），数据在调用时传入。

    Parameters
    ----------
    font_family : str
        字体，静态图和交互图共用。
    font_size : int 或 float
        静态图字号（pt）。
    interactive_font_size : int 或 float
        交互图字号（px）。
    palette : 通用色卡名或颜色列表，可选
        四种图共用，None 时使用 color_tables.py 中的 DEFAULT_PALETTE。
        可以写 matplotlib 的色卡名（如 "tab10"、"Set2"、"viridis"）或颜色列表。
    use_latex : bool
        静态图是否用 LaTeX 渲染文字（需要安装 LaTeX）。

    定制色表不在这里设置，而是在各绘图方法中传入：
    元素谱用 component_colors，全谱用 sample_colors。
    各绘图方法的其他参数原样传给 XPlotter 中的同名函数，调用时传入的参数优先。
    """

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

    # ============================================================
    # 元素谱：按化学键定制颜色（component_colors）
    # ============================================================
    def plot_element_static(self, data, *, component_colors=None, **kwargs):
        """
        元素谱静态出版图。

        component_colors : {分峰名: 颜色}，可选，如 color_tables.py 中的 COMPONENT_COLORS。
        其他参数见 XPlotter.element_static.plot_element_static。
        """
        return element_static.plot_element_static(
            data, component_colors=component_colors, **self._options(kwargs)
        )

    def plot_element_interactive(self, df, *, component_colors=None, **kwargs):
        """
        元素谱交互图（一次一条）。

        component_colors : {分峰名: 颜色}，可选，如 color_tables.py 中的 COMPONENT_COLORS。
        其他参数见 XPlotter.element_interactive.plot_element_interactive。
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

        sample_colors : {样品名: 颜色}，可选，如 color_tables.py 中的 SAMPLE_COLORS。
        其他参数见 XPlotter.survey_static.plot_survey_static。
        """
        return survey_static.plot_survey_static(
            data, sample_colors=sample_colors, **self._options(kwargs)
        )

    def plot_survey_interactive(self, data, *, sample_colors=None, **kwargs):
        """
        全谱交互图。

        sample_colors : {样品名: 颜色}，可选，如 color_tables.py 中的 SAMPLE_COLORS。
        其他参数见 XPlotter.survey_interactive.plot_survey_interactive。
        """
        return survey_interactive.plot_survey_interactive(
            data, sample_colors=sample_colors, **self._options(kwargs, interactive=True)
        )

    # ============================================================
    # 工具
    # ============================================================
    def style(self):
        """
        返回 matplotlib 样式上下文。用 XPlotter 中的 draw_* 函数
        自己组合多面板图时，把建图和保存都放在 with 块内：

            with plotter.style():
                fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(6.4, 2.4))
                draw_survey(ax1, survey)
                draw_element(ax2, c1s, component_colors=COMPONENT_COLORS)
                fig.savefig("figure.png", dpi=600, bbox_inches="tight")
        """
        return mpl_style(self.font_family, self.font_size, self.use_latex)

    @staticmethod
    def info(data):
        """打印每条元素谱的类型（raw / fit）、形状和列名。"""
        for key, df in as_mapping(data).items():
            try:
                kind = detect_element_type(df)
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