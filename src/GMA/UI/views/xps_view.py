# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
XPS 模块页（方案 7）：三栏模板 base_view.MethodView 加上 XPS 自己的设置——
读取器（Thermo Fisher Avantage 导出的 Excel）、支持的文件、按全谱 / 元素谱筛选。

全谱、元素谱的识别和读取在 GMA.project 的导入函数中（内部调用 XPSLoader），交互图、分析、出版图
分别调用 GMA 的数据整理函数、XPSAnalyzer 和 XPSPlotter，与在 marimo 中使用 GMA 的结果一致。
"""
from __future__ import annotations

from ...CM.XPS.loader import READERS
from ..strings import S
from .base_view import MethodView


class XPSView(MethodView):
    FILTERS = (("all", S.FILTER_ALL), ("survey", S.KIND_SURVEY), ("element", S.KIND_ELEMENT))
    SUFFIXES = (".xlsx", ".xls", ".xlsm")
    READERS = tuple(READERS)

    def badge(self, record) -> str:
        if record.kind == "survey":
            return S.BADGE_SURVEY
        return super().badge(record) if record.fitted else S.BADGE_UNFITTED

    def kind_label(self, record) -> str:
        if record.kind == "survey":
            return S.KIND_SURVEY
        return S.CHIP_FITTED if record.fitted else S.KIND_ELEMENT_RAW

    def side_records(self, records):
        """并排视图只放元素谱；只勾选了全谱时并排全谱。"""
        return [r for r in records if r.kind != "survey"] or records
