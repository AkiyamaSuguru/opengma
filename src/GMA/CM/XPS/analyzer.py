# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
XPS 分析入口。只处理 Avantage 等软件已经拟合好的结果，不做扣背景和峰拟合。

具体实现在 XAnalyzer 文件夹：
- metrics：数据范围、拟合质量（RMSE、MAE、R²）、分峰峰位 / 峰高 / 面积 / 面积占比

用法：
    from GMA import XPSAnalyzer

    analyzer = XPSAnalyzer()
    m = analyzer.metrics(c1s)              # SpectrumMetrics
    print(m.r_squared, m.components[0].position)
    analyzer.component_table(m)            # 分峰指标表（DataFrame）

面积占比是各分峰面积之比，不是原子百分比。
"""
from __future__ import annotations

import pandas as pd

from ..common.metrics import SpectrumMetrics
from .XAnalyzer import element_component_table, element_metrics, survey_metrics


class XPSAnalyzer:
    """XPS 分析统一入口，数据为 XPS 标准数据结构的 DataFrame。"""

    def metrics(self, df: pd.DataFrame, component_mode: str = "absolute") -> SpectrumMetrics:
        """
        元素谱或全谱的指标。component_mode 与绘图中的含义相同：
        "absolute" 分峰列已包含背景，"relative" 分峰列是扣除背景后的强度。
        """
        return element_metrics(df, component_mode=component_mode)

    def survey_metrics(self, df: pd.DataFrame) -> SpectrumMetrics:
        return survey_metrics(df)

    @staticmethod
    def component_table(metrics: SpectrumMetrics) -> pd.DataFrame:
        return element_component_table(metrics)
