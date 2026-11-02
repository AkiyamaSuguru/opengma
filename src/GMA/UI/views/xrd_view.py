# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
XRD 模块页（方案 8）：与 XPS 共用三栏模板，读取 Bruker D8 Advance 导出的 txt（XRDLoader），
也可以用通用表格导入。图谱可以叠加、标峰位，并标出用户填写的参考物相（不内置物相库，Q7）。
"""
from __future__ import annotations

from ...CM.XRD.loader import READERS
from ..strings import S
from .base_view import MethodView


class XRDView(MethodView):
    SUFFIXES = (".txt",)
    READERS = tuple(READERS)
    PHASES = True

    def badge(self, record) -> str:
        return S.BADGE_PATTERN

    def kind_label(self, record) -> str:
        return S.BADGE_PATTERN
