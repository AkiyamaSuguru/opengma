# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
XPS 谱图的数值指标：全谱和元素谱的数据范围、最大强度位置；拟合后的元素谱另有
拟合质量（RMSE、MAE、R²）和各分峰的峰位、峰高、面积、面积占比。

计算在 GMA.CM.common.metrics 中实现，这里只绑定 XPS 的横轴（结合能）。
"""
from __future__ import annotations

import pandas as pd

from ...common.metrics import SpectrumMetrics, component_table, spectrum_metrics
from ..schema import AXIS


def element_metrics(df: pd.DataFrame, component_mode: str = "absolute") -> SpectrumMetrics:
    """元素谱的指标；未拟合的元素谱只有数据范围和最大强度位置。"""
    return spectrum_metrics(df, AXIS, component_mode=component_mode)


def survey_metrics(df: pd.DataFrame) -> SpectrumMetrics:
    """全谱的数据范围和最大强度位置。"""
    return spectrum_metrics(df, AXIS)


def element_component_table(metrics: SpectrumMetrics) -> pd.DataFrame:
    """分峰指标表，峰位一列名为 "Position (eV)"。"""
    return component_table(metrics, x_label="Position (eV)")
