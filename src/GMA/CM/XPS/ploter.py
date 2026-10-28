# 这里使用的数据为 loader读取的标准化后的数据
# XPS 绘图使用
import math
from collections.abc import Mapping

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.colors import hex_to_rgb, qualitative

try:
    import scienceplots  # noqa: F401  # 注册 science / no-latex 样式
except ImportError:
    scienceplots = None

DEFAULT_FONT_FAMILY = "Times New Roman"
DEFAULT_FONT_SIZE = 8


class Eplotter:
    """
    XPS element/high-resolution spectrum plotter.

    同时支持：
    1. 未分峰元素谱：
       ["Binding Energy (eV)", "Intensity"]

    2. 已拟合但没有分峰列的谱：
       ["Binding Energy (eV)", "Intensity", "Fitting Curve", "Background"]

    3. 已拟合且包含分峰列的谱：
       ["Binding Energy (eV)", "Intensity", "Fitting Curve", "Background", ...components]

    参数
    ----
    dfs : dict[str, pd.DataFrame]
        key 为子图标签，value 为对应 XPS DataFrame。
    """

    BE_COL = "Binding Energy (eV)"
    INTENSITY_COL = "Intensity"
    FIT_COL = "Fitting Curve"
    BG_COL = "Background"

    RAW_REQUIRED_COLUMNS = [BE_COL, INTENSITY_COL]
    FIT_REQUIRED_COLUMNS = [BE_COL, INTENSITY_COL, FIT_COL, BG_COL]

    def __init__(
            self,
            dfs: dict,
            font_family=DEFAULT_FONT_FAMILY,
            font_size=DEFAULT_FONT_SIZE,
            special_text_scale=1.2,
            use_latex=False,
    ):
        if not isinstance(dfs, Mapping):
            raise TypeError("dfs must be a mapping such as dict[str, pd.DataFrame].")

        if len(dfs) == 0:
            raise ValueError("dfs cannot be empty.")

        invalid = {
            key: type(df).__name__
            for key, df in dfs.items()
            if not isinstance(df, pd.DataFrame)
        }
        if invalid:
            raise TypeError(
                "All values in dfs must be pandas.DataFrame objects. "
                f"Invalid entries: {invalid}"
            )

        self.dfs = dict(dfs)
        self.keys = list(self.dfs.keys())

        # -----------------------------
        # Matplotlib style
        # -----------------------------
        try:
            if use_latex:
                plt.style.use("science")
            else:
                plt.style.use(["science", "no-latex"])
        except OSError:
            # 未安装 scienceplots 或 science 样式不可用时，回退到 Matplotlib 默认样式
            plt.style.use("default")

        # -----------------------------
        # Font settings
        # -----------------------------
        self.font_family = font_family
        self.font_size = font_size
        self.special_text_scale = special_text_scale

        plt.rcParams.update(
            {
                "font.family": self.font_family,
                "font.size": self.font_size,
                "axes.unicode_minus": False,
            }
        )

        # -----------------------------
        # Built-in palettes
        # -----------------------------
        self.color_palettes = {
            "sci_default": [
                "#0173B2",
                "#DE8F05",
                "#029E73",
                "#D55E00",
                "#CC78BC",
                "#CA9161",
            ],
            "tableau": [
                "#1f77b4",
                "#ff7f0e",
                "#2ca02c",
                "#d62728",
                "#9467bd",
                "#8c564b",
                "#e377c2",
                "#7f7f7f",
                "#bcbd22",
                "#17becf",
            ],
            "nature": [
                "#E64B35",
                "#4DBBD5",
                "#00A087",
                "#3C5488",
                "#F39B7F",
                "#8491B4",
                "#91D1C2",
                "#DC0000",
                "#7E6148",
                "#B09C85",
            ],
            "okabe_ito": [
                "#0072B2",
                "#E69F00",
                "#009E73",
                "#D55E00",
                "#CC79A7",
                "#56B4E9",
                "#F0E442",
            ],
            "soft": [
                "#4C72B0",
                "#DD8452",
                "#55A868",
                "#C44E52",
                "#8172B3",
                "#937860",
                "#DA8BC3",
                "#8C8C8C",
                "#CCB974",
                "#64B5CD",
            ],
        }

    # ============================================================
    # Basic information
    # ============================================================
    def info(self):
        """打印载入数据及自动识别出的谱图类型。"""
        print(f"XPS data keys: {self.keys}")

        for key, df in self.dfs.items():
            try:
                plot_type = self._detect_plot_type(df)
            except ValueError as exc:
                plot_type = f"invalid ({exc})"

            print(f"\n[{key}]")
            print(f"Type: {plot_type}")
            print(f"Shape: {df.shape}")
            print(f"Columns: {list(df.columns)}")

    # ============================================================
    # Validation and automatic type detection
    # ============================================================
    @staticmethod
    def _require_columns(df: pd.DataFrame, required_columns):
        missing = [col for col in required_columns if col not in df.columns]
        if missing:
            raise ValueError(
                f"Missing required columns: {missing}\n"
                f"Required columns are: {required_columns}\n"
                f"Current columns are: {list(df.columns)}"
            )

    def _validate_raw_df(self, df: pd.DataFrame):
        self._require_columns(df, self.RAW_REQUIRED_COLUMNS)

    def _validate_fit_df(self, df: pd.DataFrame):
        self._require_columns(df, self.FIT_REQUIRED_COLUMNS)

    def _detect_plot_type(self, df: pd.DataFrame):
        """
        自动判断绘图类型。

        Returns
        -------
        str
            "raw" : 只有原始谱，未进行拟合；
            "fit" : 存在 Fitting Curve 和 Background，可包含或不包含分峰列。
        """
        self._validate_raw_df(df)

        has_fit = self.FIT_COL in df.columns
        has_bg = self.BG_COL in df.columns

        if has_fit and has_bg:
            return "fit"

        if not has_fit and not has_bg:
            return "raw"

        missing = [
            col
            for col in (self.FIT_COL, self.BG_COL)
            if col not in df.columns
        ]
        raise ValueError(
            "Incomplete fitted-spectrum data. "
            f"Missing columns: {missing}. "
            f"'{self.FIT_COL}' and '{self.BG_COL}' must appear together."
        )

    # 保留与旧 Plotter 类相似的接口
    def _validate_df(self, df: pd.DataFrame):
        self._validate_fit_df(df)

    # ============================================================
    # Color handling
    # ============================================================
    def get_colors(
            self,
            component_cols,
            palette="sci_default",
            strict=True,
    ):
        """
        根据分峰列名返回对应颜色。

        规则：
        - 内置色卡：颜色不足时自动循环；
        - 手动颜色列表：颜色不足时自动循环；
        - Matplotlib colormap：按分峰数量动态采样；
        - 字典映射：strict=True 时要求每个分峰都有显式配色，
          strict=False 时缺失项使用 sci_default 循环补色。
        """
        n_peaks = len(component_cols)

        if n_peaks == 0:
            return []

        # 1. 预设色卡 / Matplotlib colormap
        if isinstance(palette, str):
            if palette in self.color_palettes:
                base_colors = list(self.color_palettes[palette])
                if not base_colors:
                    raise ValueError(f"Built-in palette '{palette}' is empty.")

                return [
                    base_colors[i % len(base_colors)]
                    for i in range(n_peaks)
                ]

            try:
                cmap = plt.get_cmap(palette)
            except ValueError as exc:
                raise ValueError(
                    f"Unknown palette: {palette}\n"
                    f"Available built-in palettes are: "
                    f"{list(self.color_palettes.keys())}\n"
                    "You can also use a matplotlib colormap name "
                    "or pass a color list."
                ) from exc

            if n_peaks == 1:
                return [cmap(0.5)]

            return [
                cmap(i / (n_peaks - 1))
                for i in range(n_peaks)
            ]

        # 2. 手动颜色列表：自动循环
        if isinstance(palette, (list, tuple, np.ndarray)):
            base_colors = list(palette)
            if not base_colors:
                raise ValueError("palette color list cannot be empty.")

            return [
                base_colors[i % len(base_colors)]
                for i in range(n_peaks)
            ]

        # 3. 分峰名 -> 颜色
        if isinstance(palette, Mapping):
            missing_components = [
                col for col in component_cols if col not in palette
            ]

            if missing_components and strict:
                raise ValueError(
                    f"Missing colors for component peaks: {missing_components}\n"
                    f"Current palette keys are: {list(palette.keys())}"
                )

            fallback_colors = self.color_palettes["sci_default"]
            return [
                palette[col]
                if col in palette
                else fallback_colors[i % len(fallback_colors)]
                for i, col in enumerate(component_cols)
            ]

        raise TypeError(
            "palette must be str, list, tuple, np.ndarray, or dict."
        )

    # ============================================================
    # Shared axis formatting
    # ============================================================
    def _format_axis(self, ax, hide_y_ticks=False):
        """统一 XPS 坐标轴格式。"""
        if not ax.xaxis_inverted():
            ax.invert_xaxis()

        ax.xaxis.set_ticks_position("bottom")
        ax.set_xlabel("Binding Energy (eV)")
        ax.set_ylabel("Intensity (a.u.)")

        if hide_y_ticks:
            ax.set_yticks([])

        ax.tick_params(
            axis="both",
            direction="in",
            length=3,
            width=0.8,
        )

    # ============================================================
    # Raw / unfitted spectrum
    # ============================================================
    def raw_plot(
            self,
            df_r,
            ax,
            color="#00BFFF",
            linewidth=1.0,
            show_legend=False,
            legend_loc="best",
            label="Raw data",
            hide_y_ticks=False,
    ):
        """绘制未拟合的元素精细谱。"""
        df = df_r.copy()
        self._validate_raw_df(df)

        df = df.sort_values(self.BE_COL)
        be = df[self.BE_COL].to_numpy()
        raw = df[self.INTENSITY_COL].to_numpy()

        ax.plot(
            be,
            raw,
            color=color,
            linewidth=linewidth,
            label=label,
            zorder=2,
        )

        self._format_axis(ax, hide_y_ticks=hide_y_ticks)

        if show_legend:
            ax.legend(
                fontsize=self.font_size * 0.75,
                frameon=False,
                loc=legend_loc,
            )

        return ax

    # ============================================================
    # Fitted spectrum
    # ============================================================
    def fit_plot(
            self,
            df_r,
            ax,
            palette="sci_default",
            component_mode="absolute",
            show_legend=True,
            raw_color="black",
            fit_color="red",
            bg_color="gray",
            raw_size=4,
            component_alpha=0.35,
            legend_loc="best",
            hide_y_ticks=False,
    ):
        """
        绘制拟合后的 XPS 高分辨谱。

        component_mode
        --------------
        "absolute":
            分峰列本身已经包含背景。
        "relative":
            分峰列为扣背景后的峰强度，绘图时自动加 Background。
        """
        if component_mode not in {"absolute", "relative"}:
            raise ValueError(
                "component_mode must be either 'absolute' or 'relative'."
            )

        df = df_r.copy()
        self._validate_fit_df(df)
        df = df.sort_values(self.BE_COL)

        be = df[self.BE_COL].to_numpy()
        raw = df[self.INTENSITY_COL].to_numpy()
        fit = df[self.FIT_COL].to_numpy()
        bg = df[self.BG_COL].to_numpy()

        standard_cols = {
            self.BE_COL,
            self.INTENSITY_COL,
            self.FIT_COL,
            self.BG_COL,
        }
        component_cols = [
            col for col in df.columns if col not in standard_cols
        ]

        colors = self.get_colors(
            component_cols=component_cols,
            palette=palette,
            strict=True,
        )

        # Raw data
        ax.scatter(
            be,
            raw,
            s=raw_size,
            color=raw_color,
            alpha=0.65,
            label="Raw data",
            zorder=2,
        )

        # Fitted envelope
        ax.plot(
            be,
            fit,
            color=fit_color,
            linewidth=1.2,
            label="Fit",
            zorder=4,
        )

        # Background
        ax.plot(
            be,
            bg,
            color=bg_color,
            linestyle="--",
            linewidth=1.0,
            label="Background",
            zorder=3,
        )

        # Component peaks; 可以为 0 个
        for i, col in enumerate(component_cols):
            values = df[col].to_numpy()
            y_comp = values if component_mode == "absolute" else bg + values

            ax.fill_between(
                be,
                bg,
                y_comp,
                color=colors[i],
                alpha=component_alpha,
                label=col,
                zorder=1,
            )

            ax.plot(
                be,
                y_comp,
                color=colors[i],
                linewidth=0.8,
                zorder=3,
            )

        self._format_axis(ax, hide_y_ticks=hide_y_ticks)

        if show_legend:
            ax.legend(
                fontsize=self.font_size * 0.75,
                frameon=False,
                loc=legend_loc,
            )

        return ax

    # ============================================================
    # Automatic single-spectrum dispatcher
    # ============================================================
    def plot(
            self,
            df_r,
            ax,
            palette="sci_default",
            component_mode="absolute",
            show_legend=True,
            legend_loc="best",
            raw_color="black",
            raw_line_color="#00BFFF",
            raw_size=4,
            fit_color="red",
            bg_color="gray",
            component_alpha=0.35,
            hide_y_ticks=False,
    ):
        """
        自动识别 df_r 是未拟合谱还是拟合谱，并调用对应绘图函数。
        """
        plot_type = self._detect_plot_type(df_r)

        if plot_type == "raw":
            return self.raw_plot(
                df_r=df_r,
                ax=ax,
                color=raw_line_color,
                show_legend=show_legend,
                legend_loc=legend_loc,
                hide_y_ticks=hide_y_ticks,
            )

        return self.fit_plot(
            df_r=df_r,
            ax=ax,
            palette=palette,
            component_mode=component_mode,
            show_legend=show_legend,
            raw_color=raw_color,
            fit_color=fit_color,
            bg_color=bg_color,
            raw_size=raw_size,
            component_alpha=component_alpha,
            legend_loc=legend_loc,
            hide_y_ticks=hide_y_ticks,
        )

    # ============================================================
    # Multiple spectra
    # ============================================================
    def plots(
            self,
            save_fig=None,
            palette="sci_default",
            n_cols=3,
            figsize=None,
            component_mode="absolute",
            show_legend=True,
            legend_loc="best",
            dpi=600,
            raw_color="black",
            raw_line_color="#00BFFF",
            fit_color="red",
            bg_color="gray",
            raw_size=4,
            component_alpha=0.35,
            hide_y_ticks=False,
            show=True,
    ):
        """
        批量绘制 self.dfs 中的谱图。

        自动判断每个 DataFrame：
        - 未拟合谱 -> raw_plot
        - 拟合谱   -> fit_plot

        palette 可为：
        1. 全局预设色卡 / colormap / 颜色列表；
        2. 全局 {component_name: color}；
        3. {subplot_key: palette_for_this_subplot}。
        """
        if not isinstance(n_cols, int) or n_cols < 1:
            raise ValueError("n_cols must be a positive integer.")

        n_plots = len(self.dfs)
        n_rows = math.ceil(n_plots / n_cols)

        if figsize is None:
            figsize = (3.2 * n_cols, 2.4 * n_rows)

        fig, axes = plt.subplots(
            nrows=n_rows,
            ncols=n_cols,
            figsize=figsize,
            squeeze=False,
        )

        axes_flat = axes.flatten()

        for ax, (key, df) in zip(axes_flat, self.dfs.items()):
            # 判断 palette 是“按子图配置”还是“按分峰名配置”
            if isinstance(palette, Mapping) and key in palette:
                pal = palette[key]
            else:
                pal = palette

            # raw_line_color 也允许按子图设置
            if isinstance(raw_line_color, Mapping):
                line_color = raw_line_color.get(key, "#00BFFF")
            else:
                line_color = raw_line_color

            self.plot(
                df_r=df,
                ax=ax,
                palette=pal,
                component_mode=component_mode,
                show_legend=show_legend,
                legend_loc=legend_loc,
                raw_color=raw_color,
                raw_line_color=line_color,
                raw_size=raw_size,
                fit_color=fit_color,
                bg_color=bg_color,
                component_alpha=component_alpha,
                hide_y_ticks=hide_y_ticks,
            )

            # 所有类型都添加子图标签
            ax.text(
                0.03,
                0.96,
                str(key),
                transform=ax.transAxes,
                ha="left",
                va="top",
                fontsize=self.font_size * self.special_text_scale,
                fontweight="bold",
            )

        # 隐藏多余子图
        for ax in axes_flat[n_plots:]:
            ax.axis("off")

        fig.tight_layout()

        if save_fig:
            fig.savefig(
                save_fig,
                dpi=dpi,
                bbox_inches="tight",
            )

        if show:
            plt.show()

        return fig, axes


# XPS 数据查看器
def plot_xps(
        df_r,
        font_family=DEFAULT_FONT_FAMILY,
        font_size=DEFAULT_FONT_SIZE,
):
    """
    使用 Plotly 绘制交互式 XPS 高分辨谱图。

    Parameters
    ----------
    df_r : pandas.DataFrame
        必须包含以下标准列：

        - Binding Energy (eV)
        - Intensity
        - Fitting Curve
        - Background

        其余数值列自动识别为拟合分峰。

    font_family : str
        图中文字字体，默认为 Times New Roman。

    font_size : int or float
        图中文字基础字号，默认为 12。

    Returns
    -------
    plotly.graph_objects.Figure
        Plotly 图形对象。
    """

    if not isinstance(df_r, pd.DataFrame):
        raise TypeError("df_r 必须是 pandas.DataFrame。")

    required_cols = [
        "Binding Energy (eV)",
        "Intensity",
        "Fitting Curve",
        "Background",
    ]

    missing_cols = [
        col for col in required_cols
        if col not in df_r.columns
    ]

    if missing_cols:
        raise ValueError(
            f"DataFrame 缺少必要列：{missing_cols}"
        )

    df = df_r.copy()

    # ========================================================
    # 数据预处理
    # ========================================================
    for col in required_cols:
        df[col] = pd.to_numeric(
            df[col],
            errors="coerce",
        )

    df = df.dropna(subset=required_cols)

    if df.empty:
        raise ValueError("没有可用于绘图的有效数据。")

    # 按结合能升序排列，显示时再反转坐标轴
    df = df.sort_values(
        "Binding Energy (eV)"
    ).reset_index(drop=True)

    be = df["Binding Energy (eV)"].to_numpy(dtype=float)
    raw = df["Intensity"].to_numpy(dtype=float)
    fit = df["Fitting Curve"].to_numpy(dtype=float)
    bg = df["Background"].to_numpy(dtype=float)

    # 其余数值列识别为分峰
    component_cols = []

    for col in df.columns:
        if col in required_cols:
            continue

        numeric_data = pd.to_numeric(
            df[col],
            errors="coerce",
        )

        if numeric_data.notna().any():
            df[col] = numeric_data
            component_cols.append(col)

    colors = qualitative.Plotly
    fig = go.Figure()

    # ========================================================
    # 拟合分峰
    # ========================================================
    for i, col in enumerate(component_cols):
        color = colors[i % len(colors)]

        # 当前数据中的分峰已经包含背景
        y_comp = df[col].to_numpy(dtype=float)

        valid_mask = (
                np.isfinite(be)
                & np.isfinite(bg)
                & np.isfinite(y_comp)
        )

        if not valid_mask.any():
            continue

        valid_be = be[valid_mask]
        valid_bg = bg[valid_mask]
        valid_comp = y_comp[valid_mask]

        r, g, b = hex_to_rgb(color)
        fill_color = f"rgba({r}, {g}, {b}, 0.28)"

        # ----------------------------------------------------
        # 分峰填充区域
        # ----------------------------------------------------
        fill_x = np.concatenate(
            [valid_be, valid_be[::-1]]
        )

        fill_y = np.concatenate(
            [valid_comp, valid_bg[::-1]]
        )

        fig.add_trace(
            go.Scatter(
                x=fill_x,
                y=fill_y,
                mode="lines",
                line=dict(width=0),
                fill="toself",
                fillcolor=fill_color,
                hoverinfo="skip",
                showlegend=False,
                legendgroup=col,
            )
        )

        # ----------------------------------------------------
        # 分峰轮廓线
        # ----------------------------------------------------
        fig.add_trace(
            go.Scatter(
                x=valid_be,
                y=valid_comp,
                mode="lines",
                name=col,
                legendgroup=col,
                line=dict(
                    color=color,
                    width=1.4,
                ),
                hovertemplate=(
                    f"<b>{col}</b><br>"
                    "Binding Energy: %{x:.3f} eV<br>"
                    "Intensity: %{y:.3f}"
                    "<extra></extra>"
                ),
            )
        )

        # ----------------------------------------------------
        # 分峰最大值标记
        # ----------------------------------------------------
        peak_index = int(np.nanargmax(valid_comp))
        peak_be = valid_be[peak_index]
        peak_intensity = valid_comp[peak_index]

        fig.add_trace(
            go.Scatter(
                x=[peak_be],
                y=[peak_intensity],
                mode="markers",
                name=f"{col} peak",
                legendgroup=col,
                showlegend=False,
                marker=dict(
                    color=color,
                    size=7,
                    symbol="diamond",
                    line=dict(
                        color="white",
                        width=0.8,
                    ),
                ),
                hovertemplate=(
                    f"<b>{col} peak</b><br>"
                    "Peak position: %{x:.3f} eV<br>"
                    "Peak intensity: %{y:.3f}"
                    "<extra></extra>"
                ),
            )
        )

    # ========================================================
    # 原始数据
    # ========================================================
    fig.add_trace(
        go.Scatter(
            x=be,
            y=raw,
            mode="markers",
            name="Raw data",
            marker=dict(
                size=4,
                color="black",
                opacity=0.65,
            ),
            hovertemplate=(
                "<b>Raw data</b><br>"
                "Binding Energy: %{x:.3f} eV<br>"
                "Intensity: %{y:.3f}"
                "<extra></extra>"
            ),
        )
    )

    # ========================================================
    # 总拟合曲线
    # ========================================================
    fig.add_trace(
        go.Scatter(
            x=be,
            y=fit,
            mode="lines",
            name="Fit",
            line=dict(
                color="red",
                width=1.8,
            ),
            hovertemplate=(
                "<b>Fit</b><br>"
                "Binding Energy: %{x:.3f} eV<br>"
                "Intensity: %{y:.3f}"
                "<extra></extra>"
            ),
        )
    )

    # ========================================================
    # 背景曲线
    # ========================================================
    fig.add_trace(
        go.Scatter(
            x=be,
            y=bg,
            mode="lines",
            name="Background",
            line=dict(
                color="gray",
                width=1.3,
                dash="dash",
            ),
            hovertemplate=(
                "<b>Background</b><br>"
                "Binding Energy: %{x:.3f} eV<br>"
                "Intensity: %{y:.3f}"
                "<extra></extra>"
            ),
        )
    )

    # ========================================================
    # 图形布局
    # ========================================================
    fig.update_layout(
        template="plotly_white",

        # 只显示鼠标最近的数据点
        hovermode="closest",

        autosize=True,
        xaxis_title="Binding Energy (eV)",
        yaxis_title="Intensity (a.u.)",
        font=dict(
            family=font_family,
            size=font_size,
        ),

        hoverlabel=dict(
            bgcolor="white",
            bordercolor="gray",
            font=dict(
                family=font_family,
                size=font_size,
            ),
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

            # 点击图例时，同时隐藏轮廓、填充和峰值标记
            groupclick="togglegroup",
        ),

        # 增加顶部和右侧空间，避免工具栏显示不完整
        margin=dict(
            l=70,
            r=55,
            t=60,
            b=65,
        ),
    )

    # XPS 横坐标由高结合能向低结合能排列
    fig.update_xaxes(
        autorange="reversed",
        showspikes=False,
        showline=True,
        mirror=True,
        ticks="inside",
        ticklen=5,
        linewidth=1,
    )

    fig.update_yaxes(
        showspikes=False,
        showticklabels=False,
        showline=True,
        mirror=True,
        ticks="inside",
        ticklen=5,
        linewidth=1,
    )

    return fig


def plot_xps_single(
        df,
        font_family=DEFAULT_FONT_FAMILY,
        font_size=DEFAULT_FONT_SIZE,
):
    """使用 Plotly 快速绘制未拟合 XPS 精细谱。"""
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df 必须是 pandas.DataFrame。")

    required_cols = ["Binding Energy (eV)", "Intensity"]
    missing_cols = [col for col in required_cols if col not in df.columns]

    if missing_cols:
        raise ValueError(f"DataFrame 缺少必要列：{missing_cols}")

    fig = px.line(
        df,
        x="Binding Energy (eV)",
        y="Intensity",
        labels={"Intensity": "Intensity (a.u.)"},
    )

    fig.update_xaxes(autorange="reversed")
    fig.update_layout(
        template="plotly_white",
        hovermode="closest",
        showlegend=False,
        font=dict(
            family=font_family,
            size=font_size,
        ),
    )
    return fig