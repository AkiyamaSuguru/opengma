# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
Salts：熔盐配比。按各盐的摩尔分数和混合盐的总质量，计算每种盐的质量。

用法：
    from GMA.SC.Salts import PRESETS, molar_mass, salt_masses

    molar_mass("LiF")                                   # 25.94 g/mol
    salt_masses(PRESETS["FLiNaK"], total_mass=100)      # LiF-NaF-KF 46.5-11.5-42 mol%，共 100 g
    salt_masses({"LiF": 2, "BeF2": 1}, 50, molar_masses={"LiF": 26.0})   # 比例自动归一化；可以覆盖摩尔质量
"""
from .elements import ATOMIC_WEIGHTS
from .mixture import (
    COLUMNS,
    MASS,
    MASS_PERCENT,
    MOLAR_MASS,
    MOLE_PERCENT,
    PRESETS,
    SALT,
    molar_mass,
    parse_formula,
    salt_masses,
)

__all__ = [
    "ATOMIC_WEIGHTS",
    "COLUMNS",
    "MASS",
    "MASS_PERCENT",
    "MOLAR_MASS",
    "MOLE_PERCENT",
    "PRESETS",
    "SALT",
    "molar_mass",
    "parse_formula",
    "salt_masses",
]
