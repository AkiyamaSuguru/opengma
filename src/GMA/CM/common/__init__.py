# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
CM 中各表征方法共用的部分，XPS、Raman、XRD 的读取和绘图都建立在它上面。

- axis：SpectrumAxis，描述谱图的横轴（列名、标题、方向）
- data：标准数据结构的检查与整理
- color_tables：通用色卡 DEFAULT_PALETTE 和样品色表 SAMPLE_COLORS
- palette：颜色分配
- style：出版图样式和交互图布局
- spectra_static / spectra_interactive：谱线图（单条 / 同一张图 / 子图）
- fit_static / fit_interactive：拟合谱（分峰）图
- plotter：各表征方法 Plotter 的基类 BasePlotter
"""
from .axis import SpectrumAxis
from .color_tables import SAMPLE_COLORS
from .palette import palette_colors
from .plotter import BasePlotter
from .spectra_static import draw_peak_labels
from .style import mpl_style

__all__ = [
    "SAMPLE_COLORS",
    "BasePlotter",
    "SpectrumAxis",
    "draw_peak_labels",
    "mpl_style",
    "palette_colors",
]
