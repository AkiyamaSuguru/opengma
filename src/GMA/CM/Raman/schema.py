# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
Raman 标准数据结构，读取、分析、绘图共用。

- 谱线：["Raman Shift (cm-1)", "Intensity"]
- 拟合谱：["Raman Shift (cm-1)", "Intensity", "Fitting Curve", 分峰列..., "Background"]，
  分峰列可以为 0 个，列名通常写谱峰名（如 "D"、"G"）。

读取时还会返回 metadata（仪器、采集参数等），见 loader.py。
自己写 reader 时，只要返回这种结构的 DataFrame，就能直接用于后续分析和绘图。
"""
from ..common.axis import SpectrumAxis
from ..common.data import BG_COL, FIT_COL, INTENSITY_COL

SHIFT_COL = "Raman Shift (cm-1)"

SPECTRUM_COLUMNS = [SHIFT_COL, INTENSITY_COL]
FIT_COLUMNS = [SHIFT_COL, INTENSITY_COL, FIT_COL, BG_COL]

# 绘图用的横轴：拉曼位移，从小到大显示
AXIS = SpectrumAxis(
    column=SHIFT_COL,
    label=r"Raman Shift (cm$^{-1}$)",
    label_html="Raman Shift (cm<sup>-1</sup>)",
    hover_name="Raman Shift",
    unit="cm<sup>-1</sup>",
    x_format=".1f",
)

__all__ = [
    "AXIS",
    "BG_COL",
    "FIT_COL",
    "FIT_COLUMNS",
    "INTENSITY_COL",
    "SHIFT_COL",
    "SPECTRUM_COLUMNS",
]
