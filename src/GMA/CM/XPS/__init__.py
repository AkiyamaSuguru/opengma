# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
XPS：读取（XPSLoader）、分析（XPSAnalyzer）和绘图（XPSPlotter）。标准数据结构见 schema.py。
"""
from .analyzer import XPSAnalyzer
from .loader import XPSLoader
from .plotter import XPSPlotter

__all__ = ["XPSAnalyzer", "XPSLoader", "XPSPlotter"]
