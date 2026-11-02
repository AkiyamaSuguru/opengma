# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
SRIM：读取 TRIM 的 VACANCY.txt、RANGE.txt，计算离子辐照的损伤（dpa）和注入离子浓度随深度的分布。

用法：
    from GMA.SC.SRIM import SRIMPlotter, average, depth_profile, peak, read_range, read_vacancy

    vacancy = read_vacancy("VACANCY.txt")    # Quick K-P 和 Full Cascade 的输出都可以
    ions = read_range("RANGE.txt")           # 可选：注入离子的分布
    profile = depth_profile(vacancy, ions, fluence=1e16)   # 注量 ions/cm²；原子密度默认取文件头中的值
    peak(profile)                            # (峰值 dpa, 所在深度 nm)
    average(profile, start=0, end=500)       # 0–500 nm 内的平均 dpa
    SRIMPlotter().plot_profile_static(profile, save_path="dpa.png")

计算方法见 damage.py：dpa = 空位（vacancies/(Å·ion)）× 10⁸ × 注量 ÷ 原子密度；
注入离子浓度 C = 离子分布 × 注量，at.% = C ÷ (C + N) × 100。
"""
from .damage import (
    DENSITY,
    DEPTH,
    DPA,
    IONS,
    IONS_PERCENT,
    VACANCIES,
    average,
    centroid,
    depth_profile,
    element_column,
    layer_densities,
    peak,
)
from .plotter import SRIMPlotter
from .reader import (
    Layer,
    RangeTable,
    SRIMFileError,
    VacancyTable,
    parse_range,
    parse_vacancy,
    read_range,
    read_vacancy,
)

__all__ = [
    "DENSITY",
    "DEPTH",
    "DPA",
    "IONS",
    "IONS_PERCENT",
    "VACANCIES",
    "Layer",
    "RangeTable",
    "SRIMFileError",
    "SRIMPlotter",
    "VacancyTable",
    "average",
    "centroid",
    "depth_profile",
    "element_column",
    "layer_densities",
    "parse_range",
    "parse_vacancy",
    "peak",
    "read_range",
    "read_vacancy",
]
