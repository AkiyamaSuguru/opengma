# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
由 VACANCY.txt、RANGE.txt 计算损伤（dpa）和注入离子浓度随深度的分布。

    dpa(x) = V(x) × 10⁸ × Φ ÷ N(x)
    C(x)   = R(x) × Φ，  at.% = C ÷ (C + N) × 100

- V：每个离子在每 Å 深度上产生的空位（vacancies/(Å·ion)），见 VacancyTable.vacancies：
  Quick K-P 为离子产生的 + 反冲产生的空位，Full Cascade 为各元素空位之和；
- 10⁸：Å 换算成 cm；Φ：注量（ions/cm²）；
- N：深度 x 所在层的原子密度（atoms/cm³），默认取文件头中的值，可以改；
- R：RANGE.txt 的离子分布（(atoms/cm³)/(atoms/cm²)）。

结果是一个 DataFrame，深度用 nm（SRIM 原样的区间右端，Å ÷ 10），列名见下面的常量。
"""
from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np
import pandas as pd

from .reader import RangeTable, SRIMOutput, VacancyTable

DEPTH = "Depth (nm)"
VACANCIES = "Vacancies (1/(A*ion))"   # A 即 Å
DENSITY = "Atomic density (atoms/cm3)"
DPA = "dpa"
IONS = "Ions (atoms/cm3)"
IONS_PERCENT = "Ions (at.%)"


def element_column(symbol: str) -> str:
    """Full Cascade 中某个元素的空位对应的 dpa（各元素之和就是总的 dpa）。"""
    return f"dpa ({symbol})"


def depth_profile(vacancy: VacancyTable | None = None, ions: RangeTable | None = None, *, fluence: float,
                  densities=None) -> pd.DataFrame:
    """
    损伤和注入离子浓度随深度的分布。

    vacancy : read_vacancy() 的结果，可选；有它时计算 dpa（Full Cascade 另有各元素的 dpa）。
    ions : read_range() 的结果，可选；有它时计算注入离子浓度。两个都给时必须来自同一次计算
        （离子、能量和深度区间相同）。
    fluence : 注量（ions/cm²）。按束流和时间计算时：注量 = 束流（ions/(cm²·s)）× 时间（s）。
    densities : 各层的原子密度（atoms/cm³），可选。None 用文件头中的值；一个数用于所有层；
        列表按层给出，其中为 None 的层用文件头中的值。

    返回列：Depth (nm)、Atomic density (atoms/cm3)，有 VACANCY.txt 时有 Vacancies (1/(A*ion))、dpa
    （Full Cascade 还有 dpa (元素)），有 RANGE.txt 时有 Ions (atoms/cm3)、Ions (at.%)。
    attrs 中记录离子、能量、注量、各层名称和界面深度（nm），供绘图使用。
    """
    if vacancy is None and ions is None:
        raise ValueError("Give a VACANCY.txt (vacancy), a RANGE.txt (ions), or both.")
    fluence = positive(fluence, "fluence")
    base: SRIMOutput = vacancy if vacancy is not None else ions
    if vacancy is not None and ions is not None:
        check_same_run(vacancy, ions)
    n = layer_densities(base, densities)[base.layer_index()]
    data = {DEPTH: base.depth / 10, DENSITY: n}
    if vacancy is not None:
        v = vacancy.vacancies
        data[VACANCIES] = v
        data[DPA] = v * 1e8 * fluence / n
        for symbol, values in vacancy.element_vacancies().items():
            data[element_column(symbol)] = values * 1e8 * fluence / n
    if ions is not None:
        c = ions.ions * fluence
        data[IONS] = c
        data[IONS_PERCENT] = c / (c + n) * 100
    profile = pd.DataFrame(data)
    profile.attrs.update({
        "ion": base.ion, "energy": base.energy, "fluence": fluence,
        "layers": [layer.name for layer in base.layers],
        "interfaces": [x / 10 for x in base.interfaces()],
    })
    return profile


def layer_densities(table: SRIMOutput, densities=None) -> np.ndarray:
    """各层的原子密度（atoms/cm³）。densities 的写法见 depth_profile。"""
    defaults = [layer.density for layer in table.layers]
    if densities is None:
        values = defaults
    elif isinstance(densities, (int, float)) and not isinstance(densities, bool):
        values = [densities] * len(defaults)
    elif isinstance(densities, Sequence) and not isinstance(densities, str):
        if len(densities) != len(defaults):
            raise ValueError(f"The target has {len(defaults)} layer(s) but {len(densities)} densities were given.")
        values = [d if v is None else v for v, d in zip(densities, defaults, strict=True)]
    else:
        raise TypeError("densities must be None, a number or a list with one value per layer.")
    return np.array([positive(v, "atomic density") for v in values], dtype=float)


def check_same_run(vacancy: VacancyTable, ions: RangeTable) -> None:
    """VACANCY.txt 和 RANGE.txt 应来自同一次计算：离子、能量和深度区间都相同。"""
    if vacancy.ion != ions.ion or not math.isclose(vacancy.energy, ions.energy, rel_tol=1e-6):
        raise ValueError(f"RANGE.txt is for {ions.ion} {ions.energy:g} keV but VACANCY.txt is for "
                         f"{vacancy.ion} {vacancy.energy:g} keV; use the files from the same TRIM run.")
    if len(vacancy.depth) != len(ions.depth) or not np.allclose(vacancy.depth, ions.depth, rtol=1e-6, atol=1e-3):
        raise ValueError("RANGE.txt and VACANCY.txt have different depth bins; use the files from the same TRIM run.")


# ============================================================
# 读数
# ============================================================
def peak(profile: pd.DataFrame, column: str = DPA) -> tuple[float, float]:
    """最大值和所在深度（nm）。"""
    values = profile[column].to_numpy(dtype=float)
    i = int(np.nanargmax(values))
    return float(values[i]), float(profile[DEPTH].iloc[i])


def average(profile: pd.DataFrame, column: str = DPA, start: float | None = None,
            end: float | None = None) -> float:
    """
    深度范围 [start, end]（nm）内的平均值。每个深度区间内的值看作常数，范围只覆盖区间的一部分时按覆盖的
    长度计入，所以结果不受范围端点是否正好落在区间边界上的影响。None 表示从表面 / 到最深处。
    """
    right = profile[DEPTH].to_numpy(dtype=float)
    width = right[1] - right[0] if len(right) > 1 else right[0]
    left = right - width
    lo = left[0] if start is None else max(float(start), left[0])
    hi = right[-1] if end is None else min(float(end), right[-1])
    if not hi > lo:
        raise ValueError("The depth range is empty or outside the profile.")
    overlap = np.clip(np.minimum(right, hi) - np.maximum(left, lo), 0, None)
    return float(np.sum(profile[column].to_numpy(dtype=float) * overlap) / (hi - lo))


def centroid(profile: pd.DataFrame, column: str = IONS) -> float:
    """分布的平均深度（nm，按区间中点），如注入离子的平均射程。"""
    right = profile[DEPTH].to_numpy(dtype=float)
    width = right[1] - right[0] if len(right) > 1 else right[0]
    values = profile[column].to_numpy(dtype=float)
    total = float(np.sum(values))
    if total <= 0:
        raise ValueError(f"{column} is zero everywhere.")
    return float(np.sum((right - width / 2) * values) / total)


def positive(value, name: str) -> float:
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"The {name} must be a number, got {value!r}.") from None
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"The {name} must be a positive number, got {value!r}.")
    return value
