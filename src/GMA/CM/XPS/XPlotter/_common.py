"""
XPlotter 公共部分：标准列名、数据整理、颜色分配和绘图样式。

默认色卡和定制色表单独放在 color_tables.py 中。

只在 XPlotter 内部使用；对外请用上一级 xps_plotter.py 中的 XPSPlotter，
或直接调用各绘图模块中的函数。
"""
from __future__ import annotations

import math
import warnings
from collections.abc import Mapping, Sequence
from contextlib import contextmanager

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import to_hex, to_rgb

from . import color_tables

try:
    import scienceplots  # noqa: F401  # 注册 science / no-latex 样式
except ImportError:
    scienceplots = None

# ============================================================
# 标准列名：与 xps_loader 读出的 DataFrame 一致
# ============================================================
BE_COL = "Binding Energy (eV)"
INTENSITY_COL = "Intensity"
FIT_COL = "Fitting Curve"
BG_COL = "Background"

RAW_COLUMNS = [BE_COL, INTENSITY_COL]
FIT_COLUMNS = [BE_COL, INTENSITY_COL, FIT_COL, BG_COL]

COMPONENT_MODES = ("absolute", "relative")

# ============================================================
# 默认样式
# ============================================================
DEFAULT_FONT_FAMILY = "Times New Roman"
DEFAULT_FONT_SIZE = 8  # 静态图字号（pt），适合期刊单栏图
DEFAULT_INTERACTIVE_FONT_SIZE = 12  # 交互图字号（px），在屏幕上查看
PANEL_SIZE = (3.2, 2.4)  # 静态图单个坐标轴的默认尺寸（英寸）


# ============================================================
# 数据检查与整理
# ============================================================
def as_mapping(data) -> dict:
    """把输入统一成 {标签: DataFrame}；传入单个 DataFrame 时标签为空字符串。"""
    if isinstance(data, pd.DataFrame):
        return {"": data}
    if not isinstance(data, Mapping):
        raise TypeError(
            "data must be a pandas DataFrame or a mapping such as "
            "dict[str, pd.DataFrame]."
        )
    if not data:
        raise ValueError("data cannot be empty.")

    invalid = {
        key: type(df).__name__
        for key, df in data.items()
        if not isinstance(df, pd.DataFrame)
    }
    if invalid:
        raise TypeError(
            "All values in data must be pandas.DataFrame objects. "
            f"Invalid entries: {invalid}"
        )
    return dict(data)


def require_columns(df: pd.DataFrame, columns) -> None:
    missing = [col for col in columns if col not in df.columns]
    if missing:
        raise ValueError(
            f"Missing required columns: {missing}\n"
            f"Required columns are: {columns}\n"
            f"Current columns are: {list(df.columns)}"
        )


def detect_element_type(df: pd.DataFrame) -> str:
    """
    判断元素谱的类型。

    Returns
    -------
    "raw" : 只有原始谱，未拟合；
    "fit" : 有 Fitting Curve 和 Background，可包含或不包含分峰列。
    """
    require_columns(df, RAW_COLUMNS)

    has_fit = FIT_COL in df.columns
    has_bg = BG_COL in df.columns
    if has_fit and has_bg:
        return "fit"
    if not has_fit and not has_bg:
        return "raw"

    missing = [col for col in (FIT_COL, BG_COL) if col not in df.columns]
    raise ValueError(
        "Incomplete fitted-spectrum data. "
        f"Missing columns: {missing}. "
        f"'{FIT_COL}' and '{BG_COL}' must appear together."
    )


def clean_spectrum(df: pd.DataFrame, columns) -> pd.DataFrame:
    """检查必需列，转成数值，去掉必需列为空的行，并按结合能升序排列。"""
    require_columns(df, columns)
    df = df.apply(pd.to_numeric, errors="coerce")
    df = df.dropna(subset=columns).sort_values(BE_COL, ignore_index=True)
    if df.empty:
        raise ValueError("No valid numeric data to plot.")
    return df


def component_columns(df: pd.DataFrame) -> list:
    """标准列以外、含有数值的列都视为分峰列（df 需先经过 clean_spectrum）。"""
    return [
        col for col in df.columns
        if col not in FIT_COLUMNS and df[col].notna().any()
    ]


def check_component_mode(component_mode: str) -> None:
    if component_mode not in COMPONENT_MODES:
        raise ValueError(
            f"component_mode must be one of {COMPONENT_MODES}, "
            f"got {component_mode!r}."
        )


def component_curve(df: pd.DataFrame, col, component_mode: str) -> np.ndarray:
    """
    返回分峰在图上的强度曲线。

    "absolute"：分峰列本身已经包含背景；
    "relative"：分峰列为扣背景后的峰强度，绘图时加上 Background。
    """
    values = df[col].to_numpy(dtype=float)
    if component_mode == "relative":
        return values + df[BG_COL].to_numpy(dtype=float)
    return values


def prepare_survey(df: pd.DataFrame, normalize: bool = False):
    """整理全谱，返回 (结合能, 强度) 两个数组；normalize=True 时强度除以最大值。"""
    df = clean_spectrum(df, RAW_COLUMNS)
    be = df[BE_COL].to_numpy(dtype=float)
    intensity = df[INTENSITY_COL].to_numpy(dtype=float)
    if normalize:
        intensity = intensity / intensity.max()
    return be, intensity


def check_peaks(peaks) -> None:
    if not isinstance(peaks, Mapping):
        raise TypeError(
            "peaks must be a dict such as {'C 1s': 284.8, 'O 1s': 532.0}."
        )


def peaks_by_spectrum(peaks, keys) -> dict:
    """
    把要标注的峰统一成 {样品名: {标签: 结合能}}。

    peaks 可以是：
    - 所有谱共用：{"C 1s": 284.8, "O 1s": 532.0}；
    - 按样品分别写：{"As-deposited": {"C 1s": 284.8}, "Corroded": {"F 1s": 685.0}}，
      没写到的样品不标注。
    """
    keys = list(keys)
    if not peaks:
        return {key: {} for key in keys}
    check_peaks(peaks)

    nested = [isinstance(value, Mapping) for value in peaks.values()]
    if not any(nested):
        return {key: dict(peaks) for key in keys}
    if not all(nested):
        raise ValueError(
            "peaks must be either {label: BE} shared by all spectra, "
            "or {sample: {label: BE}} for each spectrum."
        )

    unknown = [key for key in peaks if key not in keys]
    if unknown:
        raise ValueError(f"peaks has unknown samples: {unknown}. Samples are: {keys}")
    return {key: dict(peaks.get(key, {})) for key in keys}


def merge_peaks(peaks_per_key: dict) -> dict:
    """多条谱画在同一张图时，把各样品要标注的峰合并在一起。"""
    merged = {}
    for key_peaks in peaks_per_key.values():
        merged.update(key_peaks)
    return merged


# ============================================================
# 颜色
# ============================================================
def palette_colors(n: int, palette=None) -> list:
    """
    从通用色卡取 n 个颜色，返回十六进制颜色字符串（matplotlib 和 plotly 通用）。

    palette 可以是：
    - None：使用 color_tables.py 中的 DEFAULT_PALETTE；
    - matplotlib 离散色卡名（如 "tab10"、"Set2"，见 matplotlib.color_sequences）：
      按顺序取色，不够时循环；
    - matplotlib 连续色卡名（如 "viridis"）：按数量均匀取色；
    - 颜色列表：按顺序取色，不够时循环。
    """
    if palette is None:
        palette = color_tables.DEFAULT_PALETTE
    if n == 0:
        return []

    if isinstance(palette, str):
        if palette in mpl.color_sequences:
            return _cycle(mpl.color_sequences[palette], n)
        if palette in mpl.colormaps:
            cmap = mpl.colormaps[palette]
            if n == 1:
                return [to_hex(cmap(0.5))]
            return [to_hex(cmap(i / (n - 1))) for i in range(n)]
        raise ValueError(
            f"Unknown palette: {palette!r}\n"
            f"Discrete palettes: {list(mpl.color_sequences)}\n"
            "A matplotlib colormap name (e.g. 'viridis') or a list of colors "
            "also works."
        )

    if isinstance(palette, Mapping):
        raise TypeError(
            "palette must be a palette name or a list of colors. "
            "For {name: color} mappings, use component_colors (element spectra) "
            "or sample_colors (survey spectra)."
        )

    if isinstance(palette, (Sequence, np.ndarray)):
        color_list = list(palette)
        if not color_list:
            raise ValueError("palette color list cannot be empty.")
        return _cycle(color_list, n)

    raise TypeError("palette must be a palette name or a list of colors.")


def _cycle(color_list, n: int) -> list:
    return [to_hex(color_list[i % len(color_list)]) for i in range(n)]


def assign_colors(names, palette=None, custom=None, *, warn_missing=False, custom_name="custom"):
    """
    给每个名称分配颜色。

    custom 为定制色表 {名称: 颜色}：表里有的名称用指定颜色（不同名称可以同色）；
    其余名称按通用色卡 palette 依次取色，并跳过定制色表已经用掉的颜色，避免撞色。
    custom 为 None 或 {} 时全部按 palette 取色。

    warn_missing=True 时，有名称不在定制色表中就给出警告，便于发现漏写或名称写错。
    """
    names = list(names)
    if not custom:
        return palette_colors(len(names), palette)
    if not isinstance(custom, Mapping):
        raise TypeError(
            f"{custom_name} must be a dict such as {{'C-Si': 'tab:blue'}}."
        )

    fixed = {name: to_hex(custom[name]) for name in names if name in custom}
    rest = [name for name in names if name not in fixed]
    if not rest:
        return [fixed[name] for name in names]

    if warn_missing:
        warnings.warn(
            f"{custom_name} has no color for {rest}; using palette colors instead.",
            stacklevel=3,
        )

    used = set(fixed.values())
    pool = palette_colors(len(rest) + len(used), palette)
    free = [color for color in pool if color not in used] or pool
    rest_colors = iter([free[i % len(free)] for i in range(len(rest))])
    return [fixed[name] if name in fixed else next(rest_colors) for name in names]


def to_rgba_string(color, alpha: float) -> str:
    """把颜色转成 plotly 用的 "rgba(r, g, b, a)" 字符串。"""
    r, g, b = (round(255 * c) for c in to_rgb(color))
    return f"rgba({r}, {g}, {b}, {alpha})"


# ============================================================
# matplotlib 样式
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
        try:
            plt.style.use("science" if use_latex else ["science", "no-latex"])
        except OSError:
            # 未安装 scienceplots 时回退到 matplotlib 默认样式
            plt.style.use("default")

        plt.rcParams.update(
            {
                "font.family": font_family,
                "font.size": font_size,
                "axes.unicode_minus": False,
            }
        )
        yield


def style_mpl_axes(ax, hide_y_ticks=False) -> None:
    """统一 XPS 坐标轴：结合能从高到低、刻度朝内、坐标轴标题。"""
    if not ax.xaxis_inverted():
        ax.invert_xaxis()

    ax.xaxis.set_ticks_position("bottom")
    ax.set_xlabel("Binding Energy (eV)")
    ax.set_ylabel("Intensity (a.u.)")

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


def finish_figure(fig, save_path=None, dpi=600, show=True) -> None:
    """调整布局，按需保存和显示。"""
    fig.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=dpi, bbox_inches="tight")
    if show:
        plt.show()


# ============================================================
# plotly 样式
# ============================================================
def hover_template(name, y_field="y") -> str:
    """plotly 悬停提示：名称、结合能和强度。"""
    return (
        f"<b>{name}</b><br>"
        "Binding Energy: %{x:.3f} eV<br>"
        f"Intensity: %{{{y_field}:.3f}}"
        "<extra></extra>"
    )


def style_plotly_figure(
        fig,
        font_family=DEFAULT_FONT_FAMILY,
        font_size=DEFAULT_INTERACTIVE_FONT_SIZE,
        hide_y_ticks=False,
):
    """统一交互图布局：白色主题、结合能从高到低、刻度朝内。"""
    fig.update_layout(
        template="plotly_white",
        hovermode="closest",  # 只显示鼠标最近的数据点
        autosize=True,
        xaxis_title="Binding Energy (eV)",
        yaxis_title="Intensity (a.u.)",
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
    fig.update_xaxes(autorange="reversed", **axis_style)
    fig.update_yaxes(showticklabels=not hide_y_ticks, **axis_style)
    return fig