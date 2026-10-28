# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
XRD 标准数据结构，读取、分析、绘图共用。

- 图谱：["2Theta (deg)", "Intensity"]

读取时还会返回 metadata（仪器、测试参数等），见 loader.py。
自己写 reader 时，只要返回这种结构的 DataFrame，就能直接用于后续分析和绘图。
"""
from ..common.axis import SpectrumAxis
from ..common.data import INTENSITY_COL

TWO_THETA_COL = "2Theta (deg)"

PATTERN_COLUMNS = [TWO_THETA_COL, INTENSITY_COL]

# 绘图用的横轴：衍射角 2θ，从小到大显示
AXIS = SpectrumAxis(
    column=TWO_THETA_COL,
    label=r"2$\theta$ (°)",
    label_html="2θ (°)",
    hover_name="2θ",
    unit="°",
    x_format=".3f",
)

__all__ = ["AXIS", "INTENSITY_COL", "PATTERN_COLUMNS", "TWO_THETA_COL"]
