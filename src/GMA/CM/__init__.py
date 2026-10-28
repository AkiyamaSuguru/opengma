# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
CM（Characterization Methods）：按表征方法组织的读取和绘图模块。

- XPS：XPSLoader、XPSPlotter
- Raman：RamanLoader、RamanPlotter
- XRD：XRDLoader、XRDPlotter
- common：各表征方法共用的数据检查、配色、样式和绘图实现
"""
from .Raman import RamanLoader, RamanPlotter
from .XPS import XPSLoader, XPSPlotter
from .XRD import XRDLoader, XRDPlotter

__all__ = [
    "RamanLoader",
    "RamanPlotter",
    "XPSLoader",
    "XPSPlotter",
    "XRDLoader",
    "XRDPlotter",
]
