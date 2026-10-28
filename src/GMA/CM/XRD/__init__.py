# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
XRD：读取（XRDLoader）和绘图（XRDPlotter）。

标准数据结构见 schema.py：两列的 DataFrame ["2Theta (deg)", "Intensity"]。
数据读取与数据处理解耦，任何能返回这种结构的 reader 都可以接入。
"""
from .loader import XRDLoader
from .plotter import XRDPlotter

__all__ = ["XRDLoader", "XRDPlotter"]
