# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
绘图样式，各表征方法共用：出版图样式（matplotlib）和交互图布局（plotly）。

出版图样式内置在 PUBLICATION_STYLE 中（刻度朝内、显示次刻度、细坐标轴线、
无边框图例等），不依赖 scienceplots，任何环境下画出来都一样。
"""
from __future__ import annotations

import math
from contextlib import contextmanager

import matplotlib as mpl
import matplotlib.pyplot as plt

DEFAULT_FONT_FAMILY = "Times New Roman"
DEFAULT_FONT_SIZE = 8  # 静态图字号（pt），适合期刊单栏图
DEFAULT_INTERACTIVE_FONT_SIZE = 12  # 交互图字号（px），在屏幕上查看
PANEL_SIZE = (3.2, 2.4)  # 静态图单个坐标轴的默认尺寸（英寸）

PUBLICATION_STYLE = {
    "axes.linewidth": 0.6,
    "axes.unicode_minus": False,
    "xtick.direction": "in",
    "ytick.direction": "in",
    "xtick.top": True,
    "ytick.right": True,
    "xtick.minor.visible": True,
    "ytick.minor.visible": True,
    "xtick.major.size": 3,
    "ytick.major.size": 3,
    "xtick.minor.size": 1.5,
    "ytick.minor.size": 1.5,
    "xtick.major.width": 0.6,
    "ytick.major.width": 0.6,
    "xtick.minor.width": 0.5,
    "ytick.minor.width": 0.5,
    "lines.linewidth": 1.0,
    "legend.frameon": False,
    "mathtext.fontset": "stix",  # 公式字体与 Times New Roman 风格一致
    "mathtext.default": "regular",  # 上下标等使用正文字体
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.05,
}


# ============================================================
# matplotlib
# ============================================================
@contextmanager
def mpl_style(
        font_family=DEFAULT_FONT_FAMILY,
        font_size=DEFAULT_FONT_SIZE,
        use_latex=False,
):
    """
    出版图样式，只在 with 块内生效，退出后恢复原来的全局设置。

        with mpl_style():
            fig, ax = plt.subplots()
            ...
    """
    with plt.rc_context():
        plt.style.use("default")  # 从默认样式开始，结果不受本机其他设置影响
        plt.rcParams.update(
            {
                **PUBLICATION_STYLE,
                "font.family": font_family,
                "font.size": font_size,
                "text.usetex": use_latex,
            }
        )
        yield


def style_mpl_axes(ax, axis, hide_y_ticks=False) -> None:
    """按横轴设置坐标轴：坐标轴标题、横轴方向、刻度朝内。"""
    if axis.reversed and not ax.xaxis_inverted():
        ax.invert_xaxis()

    ax.xaxis.set_ticks_position("bottom")
    ax.set_xlabel(axis.label)
    ax.set_ylabel(axis.y_label)

    if hide_y_ticks:
        ax.set_yticks([])

    ax.tick_params(axis="both", direction="in", length=3, width=0.8)


def add_mpl_legend(ax, loc="best", title=None, title_scale=1.2) -> bool:
    """
    图例字号为正文的 0.75 倍、无边框；没有带标签的曲线时不画图例。

    title 不为 None 时作为图例标题（粗体，字号为正文的 title_scale 倍），
    与图例一起定位，不会互相遮挡。返回是否画了图例。
    """
    handles, _ = ax.get_legend_handles_labels()
    if not handles:
        return False

    base = mpl.rcParams["font.size"]
    ax.legend(
        fontsize=0.75 * base,
        frameon=False,
        loc=loc,
        title=title,
        title_fontproperties={"weight": "bold", "size": title_scale * base},
        alignment="left",
    )
    return True


def make_subplot_grid(n_plots: int, n_cols=3, figsize=None):
    """
    按谱的数量建子图网格：每行最多 n_cols 个，谱少于 n_cols 时按实际数量排列，
    多余的子图隐藏。返回 (fig, axes)，axes 为二维数组。
    """
    if not isinstance(n_cols, int) or n_cols < 1:
        raise ValueError("n_cols must be a positive integer.")

    n_cols = min(n_cols, n_plots)
    n_rows = math.ceil(n_plots / n_cols)
    if figsize is None:
        figsize = (PANEL_SIZE[0] * n_cols, PANEL_SIZE[1] * n_rows)

    fig, axes = plt.subplots(
        nrows=n_rows,
        ncols=n_cols,
        figsize=figsize,
        squeeze=False,
    )
    for ax in axes.ravel()[n_plots:]:
        ax.axis("off")
    return fig, axes


def add_subplot_label(ax, text, scale=1.2) -> None:
    """在子图左上角写粗体标签，字号为正文的 scale 倍。"""
    ax.text(
        0.03,
        0.96,
        str(text),
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=scale * mpl.rcParams["font.size"],
        fontweight="bold",
    )


def label_with_legend(ax, label, show_legend=True, legend_loc="best", label_scale=1.2) -> None:
    """
    子图的标签和图例：有图例时标签作为图例标题，一起定位、不会互相遮挡；
    没有图例时标签写在左上角。label 为 None 时只处理图例。
    """
    has_legend = show_legend and add_mpl_legend(
        ax, legend_loc, title=label, title_scale=label_scale
    )
    if label and not has_legend:
        add_subplot_label(ax, label, label_scale)


def finish_figure(fig, save_path=None, dpi=600, show=True) -> None:
    """调整布局，按需保存和显示。"""
    fig.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=dpi, bbox_inches="tight")
    if show:
        plt.show()


# ============================================================
# plotly
# ============================================================
def hover_template(name, axis, y_field="y") -> str:
    """plotly 悬停提示：名称、横轴数值和强度。"""
    return (
        f"<b>{name}</b><br>"
        f"{axis.hover_name}: %{{x:{axis.x_format}}} {axis.unit}<br>"
        f"Intensity: %{{{y_field}:.3f}}"
        "<extra></extra>"
    )


def style_plotly_figure(
        fig,
        axis,
        font_family=DEFAULT_FONT_FAMILY,
        font_size=DEFAULT_INTERACTIVE_FONT_SIZE,
        hide_y_ticks=False,
):
    """统一交互图布局：白色主题、刻度朝内，横轴方向和标题按 axis 设置。"""
    fig.update_layout(
        template="plotly_white",
        hovermode="closest",  # 只显示鼠标最近的数据点
        autosize=True,
        xaxis_title=axis.label_html,
        yaxis_title=axis.y_label,
        font=dict(family=font_family, size=font_size),
        hoverlabel=dict(
            bgcolor="white",
            bordercolor="gray",
            font=dict(family=font_family, size=font_size),
            align="left",
            namelength=-1,
        ),
        legend=dict(
            x=0.01,
            y=0.99,
            xanchor="left",
            yanchor="top",
            bgcolor="rgba(255, 255, 255, 0.70)",
            borderwidth=0,
            groupclick="togglegroup",  # 点击图例时，同组图层一起显示 / 隐藏
        ),
        margin=dict(l=70, r=55, t=60, b=65),  # 留出顶部空间，避免工具栏显示不完整
    )

    axis_style = dict(
        showspikes=False,
        showline=True,
        mirror=True,
        ticks="inside",
        ticklen=5,
        linewidth=1,
    )
    fig.update_xaxes(autorange="reversed" if axis.reversed else True, **axis_style)
    fig.update_yaxes(showticklabels=not hide_y_ticks, **axis_style)
    return fig


def add_peak_line(fig, position, label, color="gray", dash="dot", text_color=None) -> None:
    """交互图中在峰位画竖直虚线，并在图顶部写标签；text_color 为 None 时用默认文字颜色。"""
    annotation = {"annotation_font_color": text_color} if text_color else {}
    fig.add_vline(
        x=position,
        line=dict(color=color, width=1, dash=dash),
        layer="below",
        annotation_text=str(label),
        annotation_position="top",
        **annotation,
    )
