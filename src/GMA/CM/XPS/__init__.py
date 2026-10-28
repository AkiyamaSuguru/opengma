# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
XPS：读取（XPSLoader）和绘图（XPSPlotter）。标准数据结构见 schema.py。
"""
from .loader import XPSLoader
from .plotter import XPSPlotter

__all__ = ["XPSLoader", "XPSPlotter"]
