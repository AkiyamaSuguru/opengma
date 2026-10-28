"""
XPS 全谱（survey）静态出版图，基于 matplotlib。

数据只需要两列：["Binding Energy (eV)", "Intensity"]，与 xps_loader 读出的全谱一致。

三种画法：
- 单条谱：传入一个 DataFrame；
- 多条谱画在同一个坐标轴中：传入字典（默认），可用 offset 上下错开；
- 多条谱各占一个子图：传入字典，并设置 subplots=True，排布方式与元素谱相同。

配色：默认按通用色卡 palette 取色；出版绘图时可传 sample_colors（如 color_tables.py 中的
SAMPLE_COLORS），按样品指定颜色，不同样品可以同色。

函数分两层：
- draw_survey / draw_peak_labels：画在传入的 ax 上并返回 ax；
- plot_survey_static：生成整张图，负责样式、保存和显示。
"""
from __future__ import annotations

import matplotlib.pyplot as plt

from ._common import (
    DEFAULT_FONT_FAMILY,
    DEFAULT_FONT_SIZE,
    PANEL_SIZE,
    add_mpl_legend,
    add_subplot_label,
    as_mapping,
    assign_colors,
    check_peaks,
    finish_figure,
    make_subplot_grid,
    merge_peaks,
    mpl_style,
    peaks_by_spectrum,
    prepare_survey,
    style_mpl_axes,
)


def draw_survey(
        ax,
        df,
        *,
        color=None,
        linewidth=0.8,
        label=None,
        offset=0.0,
        normalize=False,
        hide_y_ticks=False,
):
    """
    画一条全谱。

    offset : 整条谱向上平移的量，多条谱错开显示时使用；
    normalize : True 时强度先除以最大值（最大值变为 1）。
    """
    be, intensity = prepare_survey(df, normalize)
    ax.plot(be, intensity + offset, color=color, linewidth=linewidth, label=label)
    style_mpl_axes(ax, hide_y_ticks=hide_y_ticks)
    return ax


def draw_peak_labels(
        ax,
        peaks,
        *,
        color="gray",
        linewidth=0.5,
        rotation=90,
        fontsize=None,
):
    """
    标出元素峰：在峰位画竖直虚线，并把标签写在坐标轴上方。

    peaks : {标签: 结合能}，例如 {"C 1s": 284.8, "O 1s": 532.0, "F 1s": 685.0}
        峰位很近时（如 C 1s 和 K 2p）标签会重叠，可以合并成一个，
        例如 {"C 1s / K 2p": 289.0}。
    """
    check_peaks(peaks)
    transform = ax.get_xaxis_transform()  # x 用数据坐标，y 用坐标轴比例

    for label, be in peaks.items():
        ax.axvline(be, color=color, linestyle="--", linewidth=linewidth, zorder=0)
        ax.text(
            be,
            1.02,
            str(label),
            transform=transform,
            rotation=rotation,
            ha="center",
            va="bottom",
            fontsize=fontsize,
        )
    return ax


def plot_survey_static(
        data,
        *,
        subplots=False,
        palette=None,
        sample_colors=None,
        peaks=None,
        offset=0.0,
        normalize=False,
        linewidth=0.8,
        n_cols=3,
        figsize=None,
        label_scale=1.2,
        show_legend=True,
        legend_loc="best",
        hide_y_ticks=False,
        save_path=None,
        dpi=600,
        show=True,
        font_family=DEFAULT_FONT_FAMILY,
        font_size=DEFAULT_FONT_SIZE,
        use_latex=False,
):
    """
    绘制全谱静态出版图。

    Parameters
    ----------
    data : pd.DataFrame 或 dict[str, pd.DataFrame]
        单个 DataFrame 画一条谱；字典的 key 为样品名，同一张图时显示在图例中，
        子图时写在子图左上角。
    subplots : bool
        False（默认）：所有谱画在同一个坐标轴中，第一条在最上面；
        True：每条谱一个子图，按网格排列。
    palette : 通用色卡名或颜色列表，可选
        None 时使用 color_tables.py 中的 DEFAULT_PALETTE。
    sample_colors : {样品名: 颜色}，可选
        定制色表，按样品指定颜色，不同样品可以同色，例如 color_tables.py 中的
        SAMPLE_COLORS。表里没有的样品按 palette 取色。默认不使用。
    peaks : dict，可选
        要标注的元素峰，可以是：
        1. 所有谱共用：{"C 1s": 284.8, "O 1s": 532.0}；
        2. 按样品分别写：{"As-deposited": {"C 1s": 284.8}, "Corroded": {"F 1s": 685.0}}，
           子图模式下各子图标注自己的峰，同一张图时合并标注。
    offset : float
        同一张图时相邻两条谱的上下间距，0 表示不错开；子图模式下不使用。
        错开后 y 轴数值不再有意义，建议同时设置 hide_y_ticks=True。
    normalize : bool
        True 时每条谱除以自身最大值，配合 offset=1 左右使用。
    n_cols : int
        子图模式下每行最多几个子图。
    figsize : tuple，可选
        默认每个坐标轴 3.2 × 2.4 英寸，子图模式按子图数量计算。
    label_scale : float
        子图模式下样品名字号相对正文字号的倍数。
    show_legend : bool
        同一张图时是否显示图例（单条谱没有图例）。
    save_path : str 或 Path，可选
        保存路径，None 时不保存。

    Returns
    -------
    同一张图：fig, ax
    子图模式：fig, axes（二维数组）
    """
    dfs = as_mapping(data)
    colors = assign_colors(list(dfs), palette, sample_colors, custom_name="sample_colors")
    peaks_per_key = peaks_by_spectrum(peaks, dfs)

    with mpl_style(font_family, font_size, use_latex):
        if subplots:
            fig, axes = make_subplot_grid(len(dfs), n_cols, figsize)
            for ax, (key, df), color in zip(axes.ravel(), dfs.items(), colors):
                draw_survey(
                    ax,
                    df,
                    color=color,
                    linewidth=linewidth,
                    normalize=normalize,
                    hide_y_ticks=hide_y_ticks,
                )
                if peaks_per_key[key]:
                    draw_peak_labels(ax, peaks_per_key[key])
                if key != "":
                    add_subplot_label(ax, key, label_scale)
            result = (fig, axes)

        else:
            fig, ax = plt.subplots(figsize=figsize or PANEL_SIZE)
            n = len(dfs)
            for i, ((key, df), color) in enumerate(zip(dfs.items(), colors)):
                draw_survey(
                    ax,
                    df,
                    color=color,
                    linewidth=linewidth,
                    label=str(key) if key != "" else None,
                    offset=(n - 1 - i) * offset,
                    normalize=normalize,
                    hide_y_ticks=hide_y_ticks,
                )
            all_peaks = merge_peaks(peaks_per_key)
            if all_peaks:
                draw_peak_labels(ax, all_peaks)
            if show_legend:
                add_mpl_legend(ax, legend_loc)
            result = (fig, ax)

        finish_figure(fig, save_path, dpi, show)

    return result