"""
XPS 元素谱交互图，基于 plotly，适合在 Notebook 或浏览器中查看数据。

自动判断未拟合 / 拟合谱。拟合谱会画出各分峰的填充区域、轮廓线和峰值位置标记，
点击图例中的分峰名，可以同时隐藏这三个图层。

配色与静态图一致：默认按通用色卡 palette 取色，可传 component_colors 按化学键固定颜色。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from ._common import (
    BE_COL,
    BG_COL,
    DEFAULT_FONT_FAMILY,
    DEFAULT_INTERACTIVE_FONT_SIZE,
    FIT_COL,
    FIT_COLUMNS,
    INTENSITY_COL,
    RAW_COLUMNS,
    assign_colors,
    check_component_mode,
    clean_spectrum,
    component_columns,
    component_curve,
    detect_element_type,
    hover_template,
    palette_colors,
    style_plotly_figure,
    to_rgba_string,
)


def plot_element_interactive(
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
        component_alpha=0.28,
        hide_y_ticks=False,
        font_family=DEFAULT_FONT_FAMILY,
        font_size=DEFAULT_INTERACTIVE_FONT_SIZE,
):
    """
    绘制一条元素谱的交互图。

    参数含义与 element_static.draw_element 相同：
    palette 为通用色卡，component_colors 为按化学键固定颜色的定制色表（默认不使用）。

    Returns
    -------
    plotly.graph_objects.Figure
        fig.show() 显示，fig.write_html(...) 保存为网页。
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError(
            "df must be a pandas DataFrame. "
            "For several spectra, call this function once per spectrum."
        )
    check_component_mode(component_mode)

    fig = go.Figure()
    if detect_element_type(df) == "raw":
        if raw_line_color is None:
            raw_line_color = palette_colors(1, palette)[0]
        _add_raw_trace(fig, df, raw_line_color)
    else:
        _add_fit_traces(
            fig,
            df,
            palette=palette,
            component_colors=component_colors,
            component_mode=component_mode,
            raw_color=raw_color,
            raw_size=raw_size,
            fit_color=fit_color,
            bg_color=bg_color,
            component_alpha=component_alpha,
        )

    return style_plotly_figure(fig, font_family, font_size, hide_y_ticks)


def _add_raw_trace(fig, df, color):
    """未拟合谱：一条曲线。"""
    df = clean_spectrum(df, RAW_COLUMNS)
    fig.add_trace(
        go.Scatter(
            x=df[BE_COL].to_numpy(),
            y=df[INTENSITY_COL].to_numpy(),
            mode="lines",
            name="Raw data",
            showlegend=False,
            line=dict(color=color, width=1.4),
            hovertemplate=hover_template("Raw data"),
        )
    )


def _add_fit_traces(
        fig,
        df,
        *,
        palette,
        component_colors,
        component_mode,
        raw_color,
        raw_size,
        fit_color,
        bg_color,
        component_alpha,
):
    """拟合谱：分峰（填充 + 轮廓 + 峰值标记）、原始数据、拟合曲线和背景。"""
    df = clean_spectrum(df, FIT_COLUMNS)
    components = component_columns(df)
    colors = assign_colors(
        components,
        palette,
        component_colors,
        warn_missing=True,
        custom_name="component_colors",
    )

    be = df[BE_COL].to_numpy(dtype=float)
    bg = df[BG_COL].to_numpy(dtype=float)
    peak_markers = []  # 最后再加，画在拟合曲线和数据点上面，避免被挡住

    for col, color in zip(components, colors):
        y = component_curve(df, col, component_mode)
        valid = np.isfinite(y)
        if not valid.any():
            continue

        x_c, y_c, bg_c = be[valid], y[valid], bg[valid]
        group = str(col)

        # 分峰填充区域
        fig.add_trace(
            go.Scatter(
                x=np.concatenate([x_c, x_c[::-1]]),
                y=np.concatenate([y_c, bg_c[::-1]]),
                mode="lines",
                line=dict(width=0),
                fill="toself",
                fillcolor=to_rgba_string(color, component_alpha),
                hoverinfo="skip",
                showlegend=False,
                legendgroup=group,
            )
        )

        # 分峰轮廓线
        fig.add_trace(
            go.Scatter(
                x=x_c,
                y=y_c,
                mode="lines",
                name=group,
                legendgroup=group,
                line=dict(color=color, width=1.4),
                hovertemplate=hover_template(group),
            )
        )

        # 峰值位置：按扣背景后的峰强度找最大值，倾斜的背景不会让标记偏移
        i = int(np.argmax(y_c - bg_c))
        peak_markers.append(
            go.Scatter(
                x=[x_c[i]],
                y=[y_c[i]],
                mode="markers",
                name=f"{group} peak",
                legendgroup=group,
                showlegend=False,
                marker=dict(
                    color=color,
                    size=7,
                    symbol="diamond",
                    line=dict(color="white", width=0.8),
                ),
                hovertemplate=(
                    f"<b>{group} peak</b><br>"
                    "Peak position: %{x:.3f} eV<br>"
                    "Peak intensity: %{y:.3f}"
                    "<extra></extra>"
                ),
            )
        )

    # 原始数据
    fig.add_trace(
        go.Scatter(
            x=be,
            y=df[INTENSITY_COL].to_numpy(),
            mode="markers",
            name="Raw data",
            marker=dict(size=raw_size, color=raw_color, opacity=0.65),
            hovertemplate=hover_template("Raw data"),
        )
    )

    # 总拟合曲线
    fig.add_trace(
        go.Scatter(
            x=be,
            y=df[FIT_COL].to_numpy(),
            mode="lines",
            name="Fit",
            line=dict(color=fit_color, width=1.8),
            hovertemplate=hover_template("Fit"),
        )
    )

    # 背景
    fig.add_trace(
        go.Scatter(
            x=be,
            y=bg,
            mode="lines",
            name="Background",
            line=dict(color=bg_color, width=1.3, dash="dash"),
            hovertemplate=hover_template("Background"),
        )
    )

    # 分峰峰值标记
    fig.add_traces(peak_markers)