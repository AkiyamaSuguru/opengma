# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
熔盐配比：按各盐的摩尔分数和混合盐的总质量，计算每种盐要称多少。

    m_i = M_total × x_i·M_i ÷ Σ x_j·M_j

x 为摩尔分数（按比例给出即可，自动归一化，如 46.5 : 11.5 : 42 或 2 : 1），M 为摩尔质量，
由化学式和 IUPAC 标准原子质量计算，也可以直接给出（如 ⁷Li 富集的 LiF）。
"""
from __future__ import annotations

import math
import re
from collections.abc import Mapping

import pandas as pd

from .elements import ATOMIC_WEIGHTS

SALT, MOLE_PERCENT, MOLAR_MASS, MASS_PERCENT, MASS = (
    "Salt", "Mole fraction (mol%)", "Molar mass (g/mol)", "Mass fraction (wt%)", "Mass (g)")
COLUMNS = [SALT, MOLE_PERCENT, MOLAR_MASS, MASS_PERCENT, MASS]

# 常用的熔盐组成（mol%）。界面中可以修改、另存为自己的组成。
PRESETS: dict[str, dict[str, float]] = {
    "FLiNaK": {"LiF": 46.5, "NaF": 11.5, "KF": 42.0},
    "FLiBe": {"LiF": 67.0, "BeF2": 33.0},
    "NaCl-KCl": {"NaCl": 50.0, "KCl": 50.0},
    "LiCl-KCl": {"LiCl": 58.5, "KCl": 41.5},
    "NaCl-MgCl2": {"NaCl": 58.0, "MgCl2": 42.0},
    "KCl-MgCl2": {"KCl": 68.0, "MgCl2": 32.0},
}

_SUBSCRIPTS = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")
_ELEMENT = re.compile(r"[A-Z][a-z]?")
_COUNT = re.compile(r"\d+(?:\.\d+)?")
_HYDRATE = re.compile(r"\s*[·•*]\s*")


def parse_formula(formula: str) -> dict[str, float]:
    """
    化学式 → {元素: 个数}。支持括号（Ca(NO3)2、[...]）、下标数字（BeF₂）和结晶水（MgCl2·6H2O，
    也可以写成 MgCl2*6H2O）。不接受以数字开头的写法（如表示同位素的 7LiF），这时请直接给出摩尔质量。
    """
    text = str(formula).translate(_SUBSCRIPTS).strip()
    if not text:
        raise ValueError("The formula is empty.")
    if text[0].isdigit() or text[0] in "⁰¹²³⁴⁵⁶⁷⁸⁹":
        # 7LiF 这样的写法多半是同位素，按“7 个 LiF”算会差很多，所以不接受；同位素富集的盐请直接给出摩尔质量
        raise ValueError(f"Formula {formula!r} starts with a number; for isotopes such as 7LiF, "
                         "give the molar mass directly.")
    counts: dict[str, float] = {}
    for part in _HYDRATE.split(text):
        if not part:
            raise ValueError(f"Invalid formula {formula!r}.")
        multiplier = 1.0
        if m := _COUNT.match(part):
            multiplier, part = float(m.group()), part[m.end():]
        for element, n in _parse_group(part, formula).items():
            counts[element] = counts.get(element, 0.0) + multiplier * n
    return counts


def _parse_group(text: str, formula: str) -> dict[str, float]:
    stack: list[dict[str, float]] = [{}]
    i = 0
    while i < len(text):
        ch = text[i]
        if ch.isspace():
            i += 1
        elif ch in "([":
            stack.append({})
            i += 1
        elif ch in ")]":
            if len(stack) == 1:
                raise ValueError(f"Unbalanced brackets in formula {formula!r}.")
            group = stack.pop()
            i += 1
            n = 1.0
            if m := _COUNT.match(text, i):
                n, i = float(m.group()), m.end()
            for element, count in group.items():
                stack[-1][element] = stack[-1].get(element, 0.0) + count * n
        elif m := _ELEMENT.match(text, i):
            symbol = m.group()
            if symbol not in ATOMIC_WEIGHTS and symbol[0] in ATOMIC_WEIGHTS:
                symbol = symbol[0]  # 如 “Bf”：B 后面是不认识的字母，下一轮报错
            if symbol not in ATOMIC_WEIGHTS:
                raise ValueError(f"Unknown element {symbol!r} in formula {formula!r}.")
            i += len(symbol)
            n = 1.0
            if m := _COUNT.match(text, i):
                n, i = float(m.group()), m.end()
            stack[-1][symbol] = stack[-1].get(symbol, 0.0) + n
        else:
            raise ValueError(f"Unexpected character {ch!r} in formula {formula!r}.")
    if len(stack) != 1:
        raise ValueError(f"Unbalanced brackets in formula {formula!r}.")
    if not stack[0]:
        raise ValueError(f"No elements in formula {formula!r}.")
    return stack[0]


def molar_mass(formula: str) -> float:
    """摩尔质量（g/mol），如 molar_mass("LiF") = 25.94。"""
    return sum(ATOMIC_WEIGHTS[element] * n for element, n in parse_formula(formula).items())


def salt_masses(composition, total_mass: float, *, molar_masses: Mapping[str, float] | None = None) -> pd.DataFrame:
    """
    各盐的质量。

    composition : {化学式: 摩尔比例} 或 [(化学式, 摩尔比例), ...]。比例可以是 mol%，也可以是任意比例
        （如 2 : 1），按总和归一化；比例为 0 的盐质量为 0。
    total_mass : 混合盐的总质量（g；用其他单位时结果也是那个单位）。
    molar_masses : {化学式: 摩尔质量（g/mol）}，可选，覆盖按化学式计算的值，如 ⁷Li 富集的 LiF。

    返回列：Salt、Mole fraction (mol%)、Molar mass (g/mol)、Mass fraction (wt%)、Mass (g)，按输入的顺序。
    """
    items = list(composition.items() if isinstance(composition, Mapping) else composition)
    if not items:
        raise ValueError("The composition is empty.")
    total_mass = _number(total_mass, "total mass", positive=True)
    overrides = dict(molar_masses or {})
    salts, amounts, masses = [], [], []
    for salt, amount in items:
        salt = str(salt).strip()
        if not salt:
            raise ValueError("A salt has no formula.")
        if salt in salts:
            raise ValueError(f"{salt} appears more than once.")
        salts.append(salt)
        amounts.append(_number(amount, f"mole fraction of {salt}"))
        given = overrides.get(salt)
        masses.append(_number(given, f"molar mass of {salt}", positive=True) if given is not None
                      else molar_mass(salt))
    total = sum(amounts)
    if total <= 0:
        raise ValueError("The mole fractions add up to zero.")
    fractions = [a / total for a in amounts]
    weights = [x * m for x, m in zip(fractions, masses, strict=True)]
    weight = sum(weights)
    return pd.DataFrame({
        SALT: salts,
        MOLE_PERCENT: [x * 100 for x in fractions],
        MOLAR_MASS: masses,
        MASS_PERCENT: [w / weight * 100 for w in weights],
        MASS: [total_mass * w / weight for w in weights],
    })


def _number(value, name: str, *, positive: bool = False) -> float:
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"The {name} must be a number, got {value!r}.") from None
    if not math.isfinite(value) or value < 0 or (positive and value == 0):
        raise ValueError(f"The {name} must be {'positive' if positive else 'zero or positive'}, got {value!r}.")
    return value
