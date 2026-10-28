# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
拟合谱（分峰）静态出版图（matplotlib），各表征方法共用：XPS 元素谱、Raman 拟合谱。

支持两种数据（横轴列名由各表征方法的 schema.py 规定）：
1. 未拟合：[横轴列, "Intensity"]
2. 已拟合：[横轴列, "Intensity", "Fitting Curve", 分峰列..., "Background"]，分峰列可以为 0 个

函数分两层：
- draw_*：画在传入的 ax 上并返回 ax，可以自己组合多面板图；
- plot_fits_static：生成整张图（单条谱，或多条谱按子图排列），负责样式、保存和显示。
"""
from __future__ import annotations

from collections.abc import Mapping

from .data import (
    BG_COL,
    FIT_COL,
    INTENSITY_COL,
    as_mapping,
    check_component_mode,
    clean_spectrum,
    component_columns,
    component_curve,
    detect_fit_type,
)
from .palette import assign_colors
from .spectra_static import draw_spectrum
from .style import (
    DEFAULT_FONT_FAMILY,
    DEFAULT_FONT_SIZE,
    add_mpl_legend,
    finish_figure,
    label_with_legend,
    make_subplot_grid,
    mpl_style,
    style_mpl_axes,
)


def draw_fit(
        ax,
        df,
        axis,
        *,
        palette=None,
        component_colors=None,
        component_mode="absolute",
        raw_color="black",
        raw_size=4,
        fit_color="red",
        bg_color="gray",
        component_alpha=0.35,
        show_legend=True,
        legend_loc="best",
        hide_y_ticks=False,
):
    """
    画拟合后的谱：原始数据点、拟合包络线、背景和各分峰。

    palette : 通用色卡名或颜色列表，None 时使用 common/color_tables.py 中的 DEFAULT_PALETTE。
    component_colors : {分峰名: 颜色}，可选
        定制色表，按分峰名（化学键、谱峰）固定颜色；表里没有的分峰按 palette 取色并给出警告。
    component_mode
        "absolute"：分峰列本身已经包含背景；
        "relative"：分峰列为扣背景后的峰强度，绘图时自动加上 Background。
    """
    check_component_mode(component_mode)
    df = clean_spectrum(df, axis, fitted=True)
    components = component_columns(df, axis)
    colors = assign_colors(
        components,
        palette,
        component_colors,
        warn_missing=True,
        custom_name="component_colors",
    )

    x = df[axis.column].to_numpy()
    bg = df[BG_COL].to_numpy()

    # 原始数据
    ax.scatter(
        x,
        df[INTENSITY_COL].to_numpy(),
        s=raw_size,
        color=raw_color,
        alpha=0.65,
        label="Raw data",
        zorder=2,
    )

    # 拟合包络线
    ax.plot(
        x,
        df[FIT_COL].to_numpy(),
        color=fit_color,
        linewidth=1.2,
        label="Fit",
        zorder=4,
    )

    # 背景
    ax.plot(
        x,
        bg,
        color=bg_color,
        linestyle="--",
        linewidth=1.0,
        label="Background",
        zorder=3,
    )

    # 分峰，可以为 0 个
    for col, color in zip(components, colors, strict=True):
        y = component_curve(df, col, component_mode)
        ax.fill_between(
            x,
            bg,
            y,
            color=color,
            alpha=component_alpha,
            label=col,
            zorder=1,
        )
        ax.plot(x, y, color=color, linewidth=0.8, zorder=3)

    style_mpl_axes(ax, axis, hide_y_ticks=hide_y_ticks)
    if show_legend:
        add_mpl_legend(ax, legend_loc)
    return ax


def draw_fit_or_spectrum(
        ax,
        df,
        axis,
        *,
        palette=None,
        component_colors=None,
        component_mode="absolute",
        raw_color="black",
        raw_line_color=None,
        raw_size=4,
        fit_color="red",
        bg_color="gray",
        component_alpha=0.35,
        show_legend=True,
        legend_loc="best",
        hide_y_ticks=False,
):
    """
    自动判断 df 是未拟合谱还是拟合谱：未拟合时画一条谱线，拟合时调用 draw_fit。

    raw_line_color : 未拟合谱的线条颜色，None 时用通用色卡的第一个颜色。
    其余参数见 draw_fit。
    """
    if detect_fit_type(df, axis) == "raw":
        return draw_spectrum(
            ax,
            df,
            axis,
            color=raw_line_color,
            linewidth=1.0,
            label="Raw data",
            palette=palette,
            show_legend=show_legend,
            legend_loc=legend_loc,
            hide_y_ticks=hide_y_ticks,
        )

    return draw_fit(
        ax,
        df,
        axis,
        palette=palette,
        component_colors=component_colors,
        component_mode=component_mode,
        raw_color=raw_color,
        raw_size=raw_size,
        fit_color=fit_color,
        bg_color=bg_color,
        component_alpha=component_alpha,
        show_legend=show_legend,
        legend_loc=legend_loc,
        hide_y_ticks=hide_y_ticks,
    )


def plot_fits_static(
        data,
        axis,
        *,
        palette=None,
        component_colors=None,
        raw_line_color=None,
        n_cols=3,
        figsize=None,
        label_scale=1.2,
        save_path=None,
        dpi=600,
        show=True,
        font_family=DEFAULT_FONT_FAMILY,
        font_size=DEFAULT_FONT_SIZE,
        use_latex=False,
        **draw_kwargs,
):
    """
    绘制拟合谱静态出版图，自动判断未拟合 / 拟合。

    传入单个 DataFrame 时画一张图；传入字典时每条谱一个子图，按网格排列。

    Parameters
    ----------
    data : pd.DataFrame 或 dict[str, pd.DataFrame]
        多条谱时 key 为子图标签（如 "C 1s"）。显示图例时作为图例标题，
        与图例一起定位，不会被图例遮挡；不显示图例时写在子图左上角。
    axis : SpectrumAxis
        横轴的列名、标题和方向。
    palette : 通用色卡名或颜色列表，可选
        None 时使用 common/color_tables.py 中的 DEFAULT_PALETTE。
    component_colors : {分峰名: 颜色}，可选
        定制色表，按分峰名固定颜色，所有子图共用。默认不使用。
    raw_line_color : 颜色，或 {子图标签: 颜色}，可选
        未拟合谱的线条颜色，默认用通用色卡的第一个颜色。
    n_cols : int
        每行最多几个子图；谱的数量少于 n_cols 时按实际数量排列。
    label_scale : float
        子图标签字号相对正文字号的倍数。
    save_path : str 或 Path，可选
        保存路径，None 时不保存。
    **draw_kwargs :
        传给 draw_fit_or_spectrum 的其他参数，如 component_mode、fit_color、
        show_legend、legend_loc、hide_y_ticks。

    Returns
    -------
    fig, axes（二维数组；单条谱时为 1×1）
    """
    dfs = as_mapping(data)
    # 图例在这里统一添加，子图标签作为图例标题，避免两者重叠
    show_legend = draw_kwargs.pop("show_legend", True)
    legend_loc = draw_kwargs.pop("legend_loc", "best")

    with mpl_style(font_family, font_size, use_latex):
        fig, axes = make_subplot_grid(len(dfs), n_cols, figsize)

        # 子图数可能多于谱的数量（多余的已隐藏），所以不要求等长
        for ax, (key, df) in zip(axes.ravel(), dfs.items(), strict=False):
            draw_fit_or_spectrum(
                ax,
                df,
                axis,
                palette=palette,
                component_colors=component_colors,
                raw_line_color=_for_subplot(raw_line_color, key),
                show_legend=False,
                **draw_kwargs,
            )
            label_with_legend(
                ax,
                str(key) if key != "" else None,
                show_legend=show_legend,
                legend_loc=legend_loc,
                label_scale=label_scale,
            )

        finish_figure(fig, save_path, dpi, show)

    return fig, axes


def _for_subplot(option, key):
    """option 为 {子图标签: 值} 时取出该子图的值，没写到的子图返回 None（使用默认值）。"""
    if isinstance(option, Mapping):
        return option.get(key)
    return option
