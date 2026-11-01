# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
OPEN GMA（Open General Material Analyzer）：材料表征数据的读取、分析与绘图。

常用入口：
    from GMA import XPSLoader, XPSAnalyzer, XPSPlotter, RamanLoader, RamanPlotter, XRDLoader, XRDPlotter
"""
from .CM import (
    RamanLoader,
    RamanPlotter,
    XPSAnalyzer,
    XPSLoader,
    XPSPlotter,
    XRDLoader,
    XRDPlotter,
)

__all__ = [
    "RamanLoader",
    "RamanPlotter",
    "XPSAnalyzer",
    "XPSLoader",
    "XPSPlotter",
    "XRDLoader",
    "XRDPlotter",
]
