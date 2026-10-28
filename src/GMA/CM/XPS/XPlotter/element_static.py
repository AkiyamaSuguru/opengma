"""
XPS 元素谱（高分辨谱）静态出版图，基于 matplotlib。

支持三种数据（列名与 xps_loader 的输出一致）：
1. 未拟合：["Binding Energy (eV)", "Intensity"]
2. 已拟合、无分峰列：["Binding Energy (eV)", "Intensity", "Fitting Curve", "Background"]
3. 已拟合、有分峰列：在 2 的基础上增加若干分峰列

配色：默认按通用色卡 palette 取色；出版绘图时可传 component_colors（如 color_tables.py 中的
COMPONENT_COLORS），按化学键（分峰名）固定颜色。

函数分两层：
- draw_*：画在传入的 ax 上并返回 ax，可以自己组合多面板图；
- plot_element_static：生成整张图（单个元素，或多个元素按子图排列），负责样式、保存和显示。
"""
from __future__ import annotations

from collections.abc import Mapping

from ._common import (
    BE_COL,
    BG_COL,
    DEFAULT_FONT_FAMILY,
    DEFAULT_FONT_SIZE,
    FIT_COL,
    FIT_COLUMNS,
    INTENSITY_COL,
    RAW_COLUMNS,
    add_mpl_legend,
    add_subplot_label,
    as_mapping,
    assign_colors,
    check_component_mode,
    clean_spectrum,
    component_columns,
    component_curve,
    detect_element_type,
    finish_figure,
    make_subplot_grid,
    mpl_style,
    palette_colors,
    style_mpl_axes,
)


def draw_element_raw(
        ax,
        df,
        *,
        color=None,
        linewidth=1.0,
        label="Raw data",
        palette=None,
        show_legend=False,
        legend_loc="best",
        hide_y_ticks=False,
):
    """画未拟合的元素谱。color 为 None 时用通用色卡的第一个颜色。"""
    df = clean_spectrum(df, RAW_COLUMNS)
    if color is None:
        color = palette_colors(1, palette)[0]

    ax.plot(
        df[BE_COL].to_numpy(),
        df[INTENSITY_COL].to_numpy(),
        color=color,
        linewidth=linewidth,
        label=label,
        zorder=2,
    )

    style_mpl_axes(ax, hide_y_ticks=hide_y_ticks)
    if show_legend:
        add_mpl_legend(ax, legend_loc)
    return ax


def draw_element_fit(
        ax,
        df,
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
    画拟合后的元素谱：原始数据点、拟合包络线、背景和各分峰。

    palette : 通用色卡名或颜色列表，None 时使用 color_tables.py 中的 DEFAULT_PALETTE。
    component_colors : {分峰名: 颜色}，可选
        定制色表，按化学键固定分峰颜色，如 {"C-Si": "tab:blue", "C-O": "tab:green"}；
        表里没有的分峰按 palette 取色并给出警告。
    component_mode
        "absolute"：分峰列本身已经包含背景；
        "relative"：分峰列为扣背景后的峰强度，绘图时自动加上 Background。
    """
    check_component_mode(component_mode)
    df = clean_spectrum(df, FIT_COLUMNS)
    components = component_columns(df)
    colors = assign_colors(
        components,
        palette,
        component_colors,
        warn_missing=True,
        custom_name="component_colors",
    )

    be = df[BE_COL].to_numpy()
    bg = df[BG_COL].to_numpy()

    # 原始数据
    ax.scatter(
        be,
        df[INTENSITY_COL].to_numpy(),
        s=raw_size,
        color=raw_color,
        alpha=0.65,
        label="Raw data",
        zorder=2,
    )

    # 拟合包络线
    ax.plot(
        be,
        df[FIT_COL].to_numpy(),
        color=fit_color,
        linewidth=1.2,
        label="Fit",
        zorder=4,
    )

    # 背景
    ax.plot(
        be,
        bg,
        color=bg_color,
        linestyle="--",
        linewidth=1.0,
        label="Background",
        zorder=3,
    )

    # 分峰，可以为 0 个
    for col, color in zip(components, colors):
        y = component_curve(df, col, component_mode)
        ax.fill_between(
            be,
            bg,
            y,
            color=color,
            alpha=component_alpha,
            label=col,
            zorder=1,
        )
        ax.plot(be, y, color=color, linewidth=0.8, zorder=3)

    style_mpl_axes(ax, hide_y_ticks=hide_y_ticks)
    if show_legend:
        add_mpl_legend(ax, legend_loc)
    return ax


def draw_element(
        ax,
        df,
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
    自动判断 df 是未拟合谱还是拟合谱，并调用对应的 draw 函数。

    raw_line_color : 未拟合谱的线条颜色，None 时用通用色卡的第一个颜色。
    其余参数见 draw_element_fit。
    """
    if detect_element_type(df) == "raw":
        return draw_element_raw(
            ax,
            df,
            color=raw_line_color,
            palette=palette,
            show_legend=show_legend,
            legend_loc=legend_loc,
            hide_y_ticks=hide_y_ticks,
        )

    return draw_element_fit(
        ax,
        df,
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


def plot_element_static(
        data,
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
    绘制元素谱静态出版图，自动判断未拟合 / 拟合。

    传入单个 DataFrame 时画一张图；传入字典时每条谱一个子图，按网格排列。

    Parameters
    ----------
    data : pd.DataFrame 或 dict[str, pd.DataFrame]
        多条谱时 key 为子图标签（如 "C 1s"），写在子图左上角。
    palette : 通用色卡名或颜色列表，可选
        None 时使用 color_tables.py 中的 DEFAULT_PALETTE。
    component_colors : {分峰名: 颜色}，可选
        定制色表，按化学键固定分峰颜色，所有子图共用，
        例如 color_tables.py 中的 COMPONENT_COLORS。默认不使用。
    raw_line_color : 颜色，或 {子图标签: 颜色}，可选
        未拟合谱的线条颜色，默认用通用色卡的第一个颜色。
    n_cols : int
        每行最多几个子图；谱的数量少于 n_cols 时按实际数量排列。
    label_scale : float
        子图标签字号相对正文字号的倍数。
    save_path : str 或 Path，可选
        保存路径，None 时不保存。
    **draw_kwargs :
        传给 draw_element 的其他参数，如 component_mode、fit_color、
        show_legend、hide_y_ticks。

    Returns
    -------
    fig, axes（二维数组；单个元素时为 1×1）
    """
    dfs = as_mapping(data)

    with mpl_style(font_family, font_size, use_latex):
        fig, axes = make_subplot_grid(len(dfs), n_cols, figsize)

        for ax, (key, df) in zip(axes.ravel(), dfs.items()):
            draw_element(
                ax,
                df,
                palette=palette,
                component_colors=component_colors,
                raw_line_color=_for_subplot(raw_line_color, key),
                **draw_kwargs,
            )
            if key != "":
                add_subplot_label(ax, key, label_scale)

        finish_figure(fig, save_path, dpi, show)

    return fig, axes


def _for_subplot(option, key):
    """option 为 {子图标签: 值} 时取出该子图的值，没写到的子图返回 None（使用默认值）。"""
    if isinstance(option, Mapping):
        return option.get(key)
    return option