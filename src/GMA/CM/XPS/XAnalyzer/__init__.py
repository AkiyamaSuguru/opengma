# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
XPS 分析的具体实现，统一入口见上一级的 analyzer.py（XPSAnalyzer）。

- metrics：数据范围、拟合质量和分峰指标
"""
from .metrics import element_component_table, element_metrics, survey_metrics

__all__ = ["element_component_table", "element_metrics", "survey_metrics"]
