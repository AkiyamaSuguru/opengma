# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
谱图横轴的描述。

XPS、Raman、XRD 的谱图只有横轴不同（列名、标题、单位、方向），
共用的绘图代码按 SpectrumAxis 取数据列、写坐标轴标题、决定横轴方向。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SpectrumAxis:
    """
    一种谱图的横轴。

    column : 横轴数据列名，如 "Binding Energy (eV)"
    label : matplotlib 坐标轴标题，可以用 mathtext，如 r"Raman Shift (cm$^{-1}$)"
    label_html : plotly 坐标轴标题，上下标用 HTML，如 "Raman Shift (cm<sup>-1</sup>)"
    hover_name : 交互图悬停提示中横轴的名称，如 "Binding Energy"
    unit : 交互图悬停提示中横轴的单位，如 "eV"
    reversed : True 时横轴从大到小显示（XPS 结合能）
    x_format : 悬停提示中横轴数值的格式（d3-format），如 ".3f"
    y_label : 纵轴标题
    """

    column: str
    label: str
    label_html: str
    hover_name: str
    unit: str
    reversed: bool = False
    x_format: str = ".3f"
    y_label: str = "Intensity (a.u.)"
