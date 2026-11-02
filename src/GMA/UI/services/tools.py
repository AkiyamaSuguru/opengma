# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
计算工具页（SRIM、熔盐配比）中不依赖 flet 的部分：输入的整理、复制为代码、导出、复制表格。

生成的代码只调用 GMA.SC 的接口，粘贴到 marimo 中得到与界面相同的结果。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from ...SC.Salts import (
    MASS,
    MASS_PERCENT,
    MOLAR_MASS,
    MOLE_PERCENT,
    SALT,
    parse_formula,
)
from ...SC.SRIM import DEPTH, DPA, IONS_PERCENT
from ..strings import S
from .codegen import safe_stem
from .text import field_text, parse_number

# 深度单位：界面中的键 → (显示的写法, 从 nm 换算的倍数, 导出列名中的写法)；键与 SRIMPlotter 的 depth_unit 相同
DEPTH_UNITS = {"A": ("Å", 10.0, "A"), "nm": ("nm", 1.0, "nm"), "um": ("μm", 1e-3, "um")}


def safe_name(name: str) -> str:
    """导出文件的默认文件名。"""
    return safe_stem(name)


def unit_label(unit: str) -> str:
    return DEPTH_UNITS.get(unit, DEPTH_UNITS["nm"])[0]


def unit_factor(unit: str) -> float:
    return DEPTH_UNITS.get(unit, DEPTH_UNITS["nm"])[1]


# ============================================================
# SRIM
# ============================================================
@dataclass
class SRIMInputs:
    """SRIM 页的输入：文件路径、注量（直接给出或束流 × 时间）、各层原子密度（None 为文件中的值）。"""

    vacancy_path: str | None = None
    range_path: str | None = None
    mode: str = "fluence"          # fluence / flux
    fluence: float = 1e16          # ions/cm²
    flux: float = 1e12             # ions/(cm²·s)
    hours: float = 1.0
    densities: list = field(default_factory=list)

    @property
    def total_fluence(self) -> float:
        return self.flux * self.hours * 3600 if self.mode == "flux" else self.fluence

    @property
    def overrides(self) -> list | None:
        """depth_profile 的 densities 参数：没有改过时为 None。"""
        return list(self.densities) if any(d is not None for d in self.densities) else None


def literal(value) -> str:
    """代码中的数：1e16、5e22、2.5；None 写成 None。"""
    if value is None:
        return "None"
    if isinstance(value, float) and value.is_integer() and abs(value) < 1e5:
        return f"{value:.1f}"
    return field_text(value)


def _import_order(name: str) -> tuple[int, str]:
    """与 ruff（isort）相同的顺序：常量、类、函数。"""
    return (0 if name.isupper() else 1 if name[0].isupper() else 2), name.lower()


def srim_setup(inputs: SRIMInputs, *, imports=(), target: str = "data") -> list[str]:
    """读取 SRIM 文件、计算深度分布并赋给 target 的代码。"""
    names = {"depth_profile", *imports}
    if inputs.vacancy_path:
        names.add("read_vacancy")
    if inputs.range_path:
        names.add("read_range")
    lines = [f"from GMA.SC.SRIM import {', '.join(sorted(names, key=_import_order))}", ""]
    args = []
    if inputs.vacancy_path:
        lines.append(f"vacancy = read_vacancy({inputs.vacancy_path!r})")
        args.append("vacancy")
    if inputs.range_path:
        lines.append(f"ions = read_range({inputs.range_path!r})")
        args.append("ions" if args else "ions=ions")
    if inputs.mode == "flux":
        lines.append(f"fluence = {literal(inputs.flux)} * {literal(inputs.hours)} * 3600  # {S.CODE_FLUX}")
        args.append("fluence=fluence")
    else:
        args.append(f"fluence={literal(inputs.fluence)}")
    if inputs.overrides is not None:
        args.append(f"densities=[{', '.join(literal(d) for d in inputs.overrides)}]")
    lines.append(f"{target} = depth_profile({', '.join(args)})  # {S.CODE_PROFILE}")
    return lines


def srim_code(inputs: SRIMInputs, window: tuple[float | None, float | None] = (None, None)) -> str:
    """“复制为代码”：计算深度分布和峰值、平均值。"""
    has_dpa, has_ions = bool(inputs.vacancy_path), bool(inputs.range_path)
    imports = (["average", "peak"] if has_dpa else []) + (["IONS_PERCENT", "peak"] if has_ions else [])
    lines = [f"# {S.CODE_HEADER_SRIM}", *srim_setup(inputs, imports=set(imports), target="profile"), ""]
    if has_dpa:
        start, end = window
        lines.append(f"dpa_peak, dpa_depth = peak(profile)  # {S.CODE_PEAK}")
        lines.append(f"dpa_mean = average(profile, start={literal(start)}, end={literal(end)})  # {S.CODE_AVERAGE}")
    if has_ions:
        lines.append(f"ions_peak, ions_depth = peak(profile, IONS_PERCENT)  # {S.CODE_IONS_PEAK}")
    lines.append("profile")
    return "\n".join(lines) + "\n"


def profile_for_export(profile: pd.DataFrame, unit: str) -> pd.DataFrame:
    """导出的表：深度换成界面中的单位。"""
    _, factor, ascii_label = DEPTH_UNITS.get(unit, DEPTH_UNITS["nm"])
    out = profile.copy()
    out.insert(0, f"Depth ({ascii_label})", out.pop(DEPTH) * factor)
    return out


def export_profile(profile: pd.DataFrame, path, unit: str, info: list[tuple[str, str]]) -> Path:
    """导出深度分布：.xlsx（另附“信息”表）或 .csv（UTF-8 带 BOM，Excel 打开不乱码）。"""
    path = Path(path)
    table = profile_for_export(profile, unit)
    if path.suffix.lower() == ".csv":
        table.to_csv(path, index=False, encoding="utf-8-sig")
    else:
        with pd.ExcelWriter(path) as writer:
            table.to_excel(writer, sheet_name="Profile", index=False)
            pd.DataFrame(info, columns=[S.INFO_ITEM, S.INFO_VALUE]).to_excel(
                writer, sheet_name=S.SRIM_INFO_SHEET, index=False)
    return path


def has_columns(profile: pd.DataFrame | None) -> tuple[bool, bool]:
    """(有 dpa, 有注入离子浓度)。"""
    if profile is None:
        return False, False
    return DPA in profile, IONS_PERCENT in profile


# ============================================================
# 熔盐配比
# ============================================================
def salt_rows(rows: list[dict]) -> tuple[list[tuple[str, float]], dict[str, float], list[str]]:
    """
    界面中的行（{"salt", "amount", "molar_mass"}，数值是输入框中的文字）→ salt_masses 的参数。
    返回 (组成, 覆盖的摩尔质量, 各行的问题)；有问题的行不计入。空行跳过。
    """
    composition, overrides, errors = [], {}, []
    seen: set[str] = set()
    for i, row in enumerate(rows, start=1):
        salt = str(row.get("salt") or "").strip()
        amount_text = str(row.get("amount") or "").strip()
        mass_text = str(row.get("molar_mass") or "").strip()
        if not salt and not amount_text and not mass_text:
            continue
        try:
            if not salt:
                raise ValueError(S.SALT_BAD_FORMULA)
            if salt in seen:
                raise ValueError(S.SALT_DUPLICATE.format(salt=salt))
            if not mass_text:
                try:
                    parse_formula(salt)
                except ValueError:
                    raise ValueError(S.SALT_BAD_FORMULA) from None
            amount = _number(amount_text, allow_zero=True)
            mass = _number(mass_text) if mass_text else None
        except ValueError as exc:
            errors.append(S.SALT_ERROR_ROW.format(row=i, error=exc))
            continue
        seen.add(salt)
        composition.append((salt, amount))
        if mass is not None:
            overrides[salt] = mass
    return composition, overrides, errors


def _number(text: str, *, allow_zero: bool = False) -> float:
    try:
        value = parse_number(text)
    except ValueError:
        raise ValueError(S.NUMBER_REQUIRED) from None
    if not math.isfinite(value) or value < 0 or (value == 0 and not allow_zero):
        raise ValueError(S.POSITIVE_REQUIRED)
    return value


def salt_table_text(table: pd.DataFrame) -> str:
    """复制表格：制表符分隔，可以直接粘贴到 Excel；最后一行是合计。"""
    head = [S.SALT_COL_SALT, S.SALT_COL_MOLE, S.SALT_COL_MOLAR_MASS, S.SALT_COL_MASS_PERCENT, S.SALT_COL_MASS]
    lines = ["\t".join(head)]
    for row in table.itertuples(index=False):
        values = dict(zip(table.columns, row, strict=True))
        lines.append("\t".join([str(values[SALT]), f"{values[MOLE_PERCENT]:.4g}", f"{values[MOLAR_MASS]:.4f}",
                                f"{values[MASS_PERCENT]:.4f}", f"{values[MASS]:.4f}"]))
    lines.append("\t".join([S.SALT_TOTAL, f"{table[MOLE_PERCENT].sum():.4g}", "",
                            f"{table[MASS_PERCENT].sum():.4f}", f"{table[MASS].sum():.4f}"]))
    return "\n".join(lines) + "\n"


def salt_code(composition: list[tuple[str, float]], total_mass: float, overrides: dict[str, float]) -> str:
    items = ", ".join(f"{salt!r}: {literal(amount)}" for salt, amount in composition)
    args = [f"{{{items}}}", f"total_mass={literal(total_mass)}"]
    if overrides:
        args.append("molar_masses={" + ", ".join(f"{k!r}: {literal(v)}" for k, v in overrides.items()) + "}")
    return "\n".join([
        f"# {S.CODE_HEADER_SALT}",
        "from GMA.SC.Salts import salt_masses",
        "",
        f"table = salt_masses({', '.join(args)})  # {S.CODE_SALT}",
        "table",
    ]) + "\n"


def export_salts(table: pd.DataFrame, path, info: list[tuple[str, str]]) -> Path:
    path = Path(path)
    if path.suffix.lower() == ".csv":
        table.to_csv(path, index=False, encoding="utf-8-sig")
    else:
        with pd.ExcelWriter(path) as writer:
            table.to_excel(writer, sheet_name="Salts", index=False)
            pd.DataFrame(info, columns=[S.INFO_ITEM, S.INFO_VALUE]).to_excel(
                writer, sheet_name=S.SRIM_INFO_SHEET, index=False)
    return path
