# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
OPEN GMA（Open General Material Analyzer）：材料表征数据的读取、分析与绘图。

常用入口：
    from GMA import XPSLoader, XPSAnalyzer, XPSPlotter, RamanLoader, RamanPlotter, XRDLoader, XRDPlotter

其他子包：GMA.SC（SRIM 损伤与注入离子浓度、熔盐配比）、GMA.project（项目文件、导入与导出）、
GMA.UI（图形界面，运行 python -m GMA.UI）。说明见仓库的 README 和 NoteBooks/开发者笔记。
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
