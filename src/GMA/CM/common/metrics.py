# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
谱图的数值指标，各表征方法共用：数据范围、最大强度位置，以及拟合谱的拟合质量和分峰指标。

只用标准数据结构中已有的列计算（横轴、Intensity、Fitting Curve、分峰列、Background），
不做扣背景或重新拟合。计算方法移植自 OpenXPSAnalyzer 的 analyze_spectrum。

- 拟合质量：比较 Intensity 与 Fitting Curve 的 RMSE、MAE、R²；
- 分峰峰位：分峰扣除背景后在数据点上取最大值的位置，精度等于数据的步长；
- 分峰峰高：该位置上分峰曲线的强度（含背景，与图中看到的一致）；
- 分峰面积：扣除背景后的强度（负值按 0 计）对横轴的梯形积分；
- 面积占比：各分峰面积之比，不是原子百分比。
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .data import (
    BG_COL,
    FIT_COL,
    INTENSITY_COL,
    check_component_mode,
    clean_spectrum,
    component_columns,
    detect_fit_type,
)


@dataclass(frozen=True)
class ComponentMetrics:
    name: str
    position: float
    height: float
    area: float
    area_fraction: float


@dataclass(frozen=True)
class SpectrumMetrics:
    point_count: int
    x_min: float
    x_max: float
    intensity_min: float
    intensity_max: float
    max_intensity_position: float
    fitted: bool
    rmse: float | None = None
    mae: float | None = None
    r_squared: float | None = None
    components: tuple[ComponentMetrics, ...] = ()


def spectrum_metrics(df: pd.DataFrame, axis, component_mode: str = "absolute") -> SpectrumMetrics:
    """
    计算一条谱图的指标。axis 为该表征方法的 SpectrumAxis（各方法 schema.py 中的 AXIS）。

    component_mode："absolute" 表示分峰列已包含背景（Avantage 导出即如此），
    "relative" 表示分峰列是扣除背景后的强度。
    """
    check_component_mode(component_mode)
    fitted = detect_fit_type(df, axis) == "fit"
    df = clean_spectrum(df, axis, fitted=fitted)
    x = df[axis.column].to_numpy(dtype=float)
    y = df[INTENSITY_COL].to_numpy(dtype=float)
    base = dict(
        point_count=len(df),
        x_min=float(x.min()), x_max=float(x.max()),
        intensity_min=float(y.min()), intensity_max=float(y.max()),
        max_intensity_position=float(x[int(np.argmax(y))]),
        fitted=fitted,
    )
    if not fitted:
        return SpectrumMetrics(**base)

    fit = df[FIT_COL].to_numpy(dtype=float)
    bg = df[BG_COL].to_numpy(dtype=float)
    residual = y - fit
    rmse = float(np.sqrt(np.mean(residual**2)))
    mae = float(np.mean(np.abs(residual)))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r_squared = float(1 - np.sum(residual**2) / ss_tot) if ss_tot > 0 else None

    rows = []
    for name in component_columns(df, axis):
        stored = df[name].to_numpy(dtype=float)
        net = stored - bg if component_mode == "absolute" else stored
        plotted = stored if component_mode == "absolute" else stored + bg
        mask = np.isfinite(net)
        if mask.any():
            i = int(np.flatnonzero(mask)[np.argmax(net[mask])])
            position, height = float(x[i]), float(plotted[i])
            area = float(np.trapezoid(np.clip(net[mask], 0, None), x[mask])) if mask.sum() > 1 else 0.0
        else:
            position = height = float("nan")
            area = 0.0
        rows.append((str(name), position, height, area))
    total = sum(r[3] for r in rows)
    components = tuple(
        ComponentMetrics(name, position, height, area, area / total if total > 0 else float("nan"))
        for name, position, height, area in rows
    )
    return SpectrumMetrics(**base, rmse=rmse, mae=mae, r_squared=r_squared, components=components)


def component_table(metrics: SpectrumMetrics, x_label: str = "Position") -> pd.DataFrame:
    """分峰指标表：分峰、峰位、峰高、面积、面积占比（%）。"""
    return pd.DataFrame(
        {
            "Component": [c.name for c in metrics.components],
            x_label: [c.position for c in metrics.components],
            "Height": [c.height for c in metrics.components],
            "Area": [c.area for c in metrics.components],
            "Area fraction (%)": [100 * c.area_fraction for c in metrics.components],
        }
    )
