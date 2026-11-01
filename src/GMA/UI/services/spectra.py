# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
交互图的数据整理：把谱图和显示设置整理成一组曲线，交给 components/chart.py 显示。

归一化、错开和分峰曲线都调用 GMA 的整理函数（prepare_spectrum、component_curve），颜色取自
GMA 的通用色卡，原始数据、拟合曲线、背景的默认颜色与出版图相同，所以交互图和出版图的数值、
颜色一致（方案 6.2）。这些设置只影响显示，不修改项目中的数据。
"""
from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field

import numpy as np

from ...CM.common.data import (
    BG_COL,
    FIT_COL,
    INTENSITY_COL,
    component_curve,
    prepare_spectrum,
)
from ...CM.common.palette import assign_colors
from ...project import Record

# GMA 出版图的默认颜色：原始数据 black、拟合曲线 red、背景 gray（虚线）
RAW_COLOR, FIT_COLOR, BG_COLOR = "#000000", "#FF0000", "#808080"
BG_DASH = [6, 4]
VIEWS = ("single", "overlay", "side")
MAX_SIDE = 6  # 并排视图最多几个小图（方案 6.2）


@dataclass
class Series:
    """一条曲线。x 从小到大排列；key 在同一张图中唯一，用来记住隐藏的曲线和颜色。"""

    key: str
    label: str
    color: str
    x: np.ndarray
    y: np.ndarray
    dash: list[int] | None = None
    width: float = 1.4


@dataclass
class Display:
    """一条谱图的显示设置，保存在模块标签的状态中（每个标签各自保存，方案 4.3）。"""

    component_colors: dict[str, str] = field(default_factory=dict)
    raw_color: str = RAW_COLOR
    fit_color: str = FIT_COLOR
    bg_color: str = BG_COLOR
    color: str | None = None              # 叠加时这条谱的颜色；None 时按通用色卡
    x_range: list[float] | None = None    # 横轴范围 [小, 大]；None 时显示全部
    y_mode: str = "auto"                  # auto：按可见数据自动；fixed：用 y_range
    y_range: list[float] | None = None
    hidden: list[str] = field(default_factory=list)  # 隐藏的曲线（Series.key）

    def to_dict(self) -> dict:
        out = {}
        for name, default in DEFAULT_DISPLAY.items():
            value = getattr(self, name)
            if value != default:
                out[name] = value
        return out

    @classmethod
    def from_dict(cls, d) -> Display:
        d = d if isinstance(d, dict) else {}
        display = cls()
        colors = d.get("component_colors")
        if isinstance(colors, dict):
            display.component_colors = {str(k): v for k, v in colors.items() if is_color(v)}
        for name in ("raw_color", "fit_color", "bg_color"):
            if is_color(d.get(name)):
                setattr(display, name, d[name])
        if is_color(d.get("color")):
            display.color = d["color"]
        display.x_range = _pair(d.get("x_range"))
        display.y_range = _pair(d.get("y_range"))
        display.y_mode = "fixed" if d.get("y_mode") == "fixed" and display.y_range else "auto"
        if isinstance(d.get("hidden"), list):
            display.hidden = [str(k) for k in d["hidden"]]
        return display

    def copy(self) -> Display:
        return Display.from_dict(self.to_dict())


DEFAULT_DISPLAY = {name: getattr(Display(), name) for name in Display.__dataclass_fields__}


def is_color(value) -> bool:
    return isinstance(value, str) and len(value) == 7 and value.startswith("#") and all(
        c in "0123456789abcdefABCDEF" for c in value[1:])


def _pair(value) -> list[float] | None:
    try:
        lo, hi = (float(v) for v in value)
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(lo) and math.isfinite(hi)) or lo == hi:
        return None
    return [min(lo, hi), max(lo, hi)]


# ============================================================
# 颜色
# ============================================================
def component_colors(record: Record, display: Display, palette=None) -> dict[str, str]:
    """分峰的颜色：显示设置中指定的优先，其余按通用色卡依次取色（与出版图相同）。"""
    names = record.components
    chosen = {n: c for n, c in display.component_colors.items() if n in names}
    return dict(zip(names, assign_colors(names, palette, chosen), strict=True))


def overlay_colors(labels: list[str], displays: list[Display], palette=None) -> list[str]:
    """叠加时各条谱的颜色：指定了颜色的用指定的，其余按通用色卡取色（与出版图的 sample_colors 相同）。"""
    custom = {label: d.color for label, d in zip(labels, displays, strict=True) if d.color}
    return assign_colors(labels, palette, custom)


def overlay_labels(records: list[Record]) -> list[str]:
    """叠加、并排时每条谱的名称：谱图名都相同时用样品名，样品都相同时用谱图名，否则写“样品 · 谱图”。"""
    if len({r.name for r in records}) == 1 and len({r.sample for r in records}) == len(records):
        labels = [r.sample for r in records]
    elif len({r.sample for r in records}) == 1 and len({r.name for r in records}) == len(records):
        labels = [r.name for r in records]
    else:
        labels = [f"{r.sample} · {r.name}" for r in records]
    # 仍然重复时（极少见）加序号，保证图例和出版图字典的键唯一
    seen: dict[str, int] = {}
    out = []
    for label in labels:
        seen[label] = seen.get(label, 0) + 1
        out.append(label if seen[label] == 1 else f"{label} ({seen[label]})")
    return out


# ============================================================
# 曲线
# ============================================================
def single_series(record: Record, display: Display, palette=None) -> list[Series]:
    """一条谱图：拟合谱为原始数据、拟合曲线、背景和各分峰；未拟合时只有一条谱线。"""
    axis = record.spec.axis
    df = record.to_dataframe()
    x = df[axis.column].to_numpy(dtype=float)
    if not record.fitted:
        color = display.color or assign_colors([record.name], palette)[0]
        label = "Raw data" if record.kind == "element" else record.name
        return [Series("raw", label, color, x, df[INTENSITY_COL].to_numpy(dtype=float), width=1.2)]
    series = [
        Series("raw", "Raw data", display.raw_color, x, df[INTENSITY_COL].to_numpy(dtype=float), width=1.0),
        Series("fit", "Fit", display.fit_color, x, df[FIT_COL].to_numpy(dtype=float), width=1.6),
        Series("bg", "Background", display.bg_color, x, df[BG_COL].to_numpy(dtype=float), dash=BG_DASH, width=1.2),
    ]
    colors = component_colors(record, display, palette)
    for name in record.components:
        series.append(Series(f"c:{name}", name, colors[name], x,
                             component_curve(df, name, record.component_mode), width=1.4))
    return series


def overlay_series(records: list[Record], displays: list[Display], palette=None, *,
                   normalize: bool = False, offset: float = 0.0) -> list[Series]:
    """多条谱画在一起（全谱、Raman、XRD 常用）：可以归一化、上下错开，第一条在最上面（与出版图相同）。"""
    labels = overlay_labels(records)
    colors = overlay_colors(labels, displays, palette)
    n = len(records)
    out = []
    for i, (record, label, color) in enumerate(zip(records, labels, colors, strict=True)):
        x, y = prepare_spectrum(record.to_dataframe(), record.spec.axis, normalize)
        out.append(Series(record.record_id, label, color, x, y + (n - 1 - i) * offset, width=1.2))
    return out


def data_range(series: list[Series]) -> tuple[float, float]:
    """全部曲线的横轴范围。"""
    xs = [s.x for s in series if len(s.x)]
    if not xs:
        return 0.0, 1.0
    lo, hi = min(float(x.min()) for x in xs), max(float(x.max()) for x in xs)
    return (lo, hi) if hi > lo else (lo - 0.5, hi + 0.5)


def y_range(series: list[Series], lo: float, hi: float, hidden=()) -> tuple[float, float]:
    """横轴范围 [lo, hi] 内可见曲线的纵轴范围，上下各留 6% 的空白。"""
    ymin, ymax = math.inf, -math.inf
    for s in series:
        if s.key in hidden or not len(s.x):
            continue
        m = (s.x >= lo) & (s.x <= hi) & np.isfinite(s.y)
        if m.any():
            ymin, ymax = min(ymin, float(s.y[m].min())), max(ymax, float(s.y[m].max()))
    if not math.isfinite(ymin):
        return 0.0, 1.0
    pad = (ymax - ymin) * 0.06 or abs(ymax) * 0.06 or 1.0
    return ymin - pad, ymax + pad


def point_counts(series: list[Series], lo: float, hi: float) -> tuple[int, int]:
    """(横轴范围内的数据点数, 总点数)；共用同一横轴的曲线（拟合谱的各条曲线）只算一次。"""
    seen, visible, total = set(), 0, 0
    for s in series:
        if id(s.x) in seen:
            continue
        seen.add(id(s.x))
        total += len(s.x)
        visible += int(((s.x >= lo) & (s.x <= hi)).sum())
    return visible, total


def nearest(series: Series, x: float) -> int | None:
    """离 x 最近的数据点的下标（x 已从小到大排列）。"""
    n = len(series.x)
    if n == 0:
        return None
    i = int(np.searchsorted(series.x, x))
    if i <= 0:
        return 0
    if i >= n:
        return n - 1
    return i if abs(series.x[i] - x) < abs(x - series.x[i - 1]) else i - 1


def decimate(x: np.ndarray, y: np.ndarray, max_points: int) -> np.ndarray:
    """
    抽稀显示（设置中可选，默认关闭）：把数据分成若干段，每段保留最小值和最大值所在的点，
    峰的高度不会被削掉。只影响显示，悬停读数、分析和导出都用全部数据。返回保留的下标。
    """
    n = len(x)
    if max_points <= 0 or n <= max_points:
        return np.arange(n)
    buckets = max(1, max_points // 2)
    edges = np.linspace(0, n, buckets + 1, dtype=int)
    keep = [0, n - 1]
    for a, b in itertools.pairwise(edges):
        if b <= a:
            continue
        seg = y[a:b]
        finite = np.isfinite(seg)
        if not finite.any():
            continue
        idx = np.flatnonzero(finite)
        keep.append(a + int(idx[np.argmin(seg[idx])]))
        keep.append(a + int(idx[np.argmax(seg[idx])]))
    return np.unique(np.asarray(keep, dtype=int))


# ============================================================
# 坐标轴刻度
# ============================================================
def nice_step(span: float, target: int = 7) -> float:
    raw = span / max(target, 1)
    if raw <= 0 or not math.isfinite(raw):
        return 1.0
    mag = 10 ** math.floor(math.log10(raw))
    r = raw / mag
    return (1 if r < 1.5 else 2 if r < 3 else 5 if r < 7 else 10) * mag


def ticks(lo: float, hi: float, target: int = 7) -> tuple[list[float], int]:
    """lo–hi 之间整齐的刻度值，以及显示时需要的小数位数。"""
    if not (math.isfinite(lo) and math.isfinite(hi)) or hi <= lo:
        return [], 0
    step = nice_step(hi - lo, target)
    start = math.ceil(lo / step - 1e-9) * step
    values = []
    v = start
    while v <= hi + step * 1e-9 and len(values) < 100:
        values.append(0.0 if abs(v) < step * 1e-9 else v)
        v += step
    decimals = max(0, -math.floor(math.log10(step))) if step < 1 else 0
    return values, decimals


def format_value(v: float, decimals: int | None = None) -> str:
    """强度等数值：千位用空格分隔（10 000），很大或很小时用科学计数法。"""
    if not math.isfinite(v):
        return "—"
    if decimals is not None:
        text = f"{v:,.{decimals}f}"
    elif abs(v) >= 1e7 or (0 < abs(v) < 1e-3):
        return f"{v:.3g}"
    elif abs(v) >= 100:
        text = f"{v:,.0f}"
    elif abs(v) >= 1:
        text = f"{v:,.2f}"
    else:
        text = f"{v:.4f}"
    return text.replace(",", " ")
