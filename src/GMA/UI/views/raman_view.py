# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
Raman 模块页（方案 8）：与 XPS 共用三栏模板，读取 Horiba LabSpec 导出的 txt（RamanLoader），
也可以用通用表格导入其他软件的结果。谱线可以叠加、标峰位；拟合谱画出分峰，分析与 XPS 相同。
"""
from __future__ import annotations

from ...CM.Raman.loader import READERS
from ..strings import S
from .base_view import MethodView


class RamanView(MethodView):
    FILTERS = (("all", S.FILTER_ALL), ("line", S.FILTER_LINE), ("fit", S.FILTER_FIT))
    SUFFIXES = (".txt",)
    READERS = tuple(READERS)

    def matches(self, record, key: str) -> bool:
        if key == "line":
            return not record.fitted
        if key == "fit":
            return record.fitted
        return True
