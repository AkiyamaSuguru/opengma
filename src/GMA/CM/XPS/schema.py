# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
XPS 标准数据结构，读取、分析、绘图共用。

- 全谱（survey）：["Binding Energy (eV)", "Intensity"]
- 元素谱（element）：未拟合时同全谱；拟合后为
  ["Binding Energy (eV)", "Intensity", "Fitting Curve", 分峰列..., "Background"]，
  分峰列可以为 0 个，列名通常写化学键（如 "C-Si"）。

自己写 reader 时，只要返回这种结构的 DataFrame，就能直接用于后续分析和绘图。
"""
from ..common.axis import SpectrumAxis
from ..common.data import BG_COL, FIT_COL, INTENSITY_COL

BE_COL = "Binding Energy (eV)"

SURVEY_COLUMNS = [BE_COL, INTENSITY_COL]
FIT_COLUMNS = [BE_COL, INTENSITY_COL, FIT_COL, BG_COL]

# 绘图用的横轴：结合能，从高到低显示
AXIS = SpectrumAxis(
    column=BE_COL,
    label="Binding Energy (eV)",
    label_html="Binding Energy (eV)",
    hover_name="Binding Energy",
    unit="eV",
    reversed=True,
)

__all__ = [
    "AXIS",
    "BE_COL",
    "BG_COL",
    "FIT_COL",
    "FIT_COLUMNS",
    "INTENSITY_COL",
    "SURVEY_COLUMNS",
]
