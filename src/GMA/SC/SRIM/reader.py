# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
读取 TRIM（SRIM）输出的 VACANCY.txt 和 RANGE.txt。

两种计算方式的输出都可以读，靠表头区分：
- Quick K-P（Ion Distribution and Quick Calculation of Damage）：
  VACANCY.txt 有“离子产生的空位”“反冲产生的空位”两列；RANGE.txt 有离子分布和一列全为 0 的反冲分布；
- Full Cascade（Detailed Calculation with full Damage Cascades）：
  VACANCY.txt 第 2 列是离子撞出的初级撞出原子数（Knock-Ons），之后按元素分列空位，多层靶按层依次排列；
  RANGE.txt 第 2 列是离子分布，之后按元素分列反冲原子的分布。

文件头中的离子、能量、计算的离子数、各层的名称、厚度、原子密度和组成一并读出。
表中的深度是每个深度区间的右端（SRIM 原样，单位 Å），数据点之间的间隔就是区间宽度。
数值中的小数逗号（某些系统区域设置下的输出）按小数点处理。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

NUMBER = r"[-+]?(?:\d+[.,]?\d*|[.,]\d+)(?:[Ee][-+]?\d+)?"
_SEPARATOR = re.compile(r"^\s*-{4,}(?:\s+-{4,})+\s*$")
_ION = re.compile(rf"Ion\s*=\s*([A-Z][a-z]?)\s+Energy\s*=\s*({NUMBER})\s*keV", re.IGNORECASE)
_IONS_CALCULATED = re.compile(rf"Total\s+Ions\s+calculated\s*=\s*({NUMBER})", re.IGNORECASE)
_TOTAL_VACANCIES = re.compile(rf"Total\s+Target\s+Vacancies\s*=\s*({NUMBER})", re.IGNORECASE)
_RANGE = re.compile(rf"Ion\s+Average\s+Range\s*=\s*({NUMBER})\s*A\s+Straggling\s*=\s*({NUMBER})\s*A", re.IGNORECASE)
_LAYER_NAME = re.compile(r"^\s*Layer\s+(\d+)\s*:\s*(.*?)\s*$")
_LAYER_WIDTH = re.compile(rf"Layer\s+Width\s*=\s*({NUMBER})\s*A", re.IGNORECASE)
_LAYER_DENSITY = re.compile(
    rf"Layer\s*#\s*(\d+)\s*-\s*Density\s*=\s*({NUMBER})\s*atoms/cm3(?:\s*=\s*({NUMBER})\s*g/cm3)?", re.IGNORECASE)
_LAYER_ELEMENT = re.compile(rf"Layer\s*#\s*(\d+)\s*-\s*([A-Z][a-z]?)\s*=\s*({NUMBER})\s*Atomic\s+Percent")


class SRIMFileError(ValueError):
    """文件不是能识别的 SRIM 输出。"""


def number(text: str) -> float:
    """SRIM 输出中的数值：小数逗号按小数点处理，如 1,5E-03。"""
    return float(text.replace(",", "."))


@dataclass(frozen=True)
class Layer:
    """靶的一层：名称、厚度（Å）、原子密度（atoms/cm³）、质量密度（g/cm³）、各元素的原子百分比。"""

    name: str
    width: float
    density: float
    mass_density: float | None = None
    elements: dict[str, float] = field(default_factory=dict)


@dataclass
class SRIMOutput:
    """VACANCY.txt、RANGE.txt 共有的内容：文件头的信息、深度（Å）和表中的其他各列（按文件中的顺序）。"""

    mode: str                        # "quick"（Quick K-P）或 "full"（Full Cascade）
    ion: str                         # 离子的元素符号
    energy: float                    # 离子能量（keV）
    ions_calculated: float | None    # 计算的离子数
    layers: list[Layer]
    depth: np.ndarray                # 每个深度区间的右端（Å）
    columns: dict[str, np.ndarray]   # 深度以外的各列
    source: str = ""                 # 文件名

    @property
    def bin_width(self) -> float:
        """深度区间的宽度（Å）。"""
        return float(self.depth[1] - self.depth[0]) if len(self.depth) > 1 else float(self.depth[0])

    @property
    def target_depth(self) -> float:
        return float(self.depth[-1])

    @property
    def quick(self) -> bool:
        return self.mode == "quick"

    def interfaces(self) -> list[float]:
        """多层靶各层之间界面的深度（Å），单层靶为 []。"""
        if any(layer.width <= 0 for layer in self.layers):
            return []
        edges = np.cumsum([layer.width for layer in self.layers])[:-1]
        return [float(e) for e in edges if 0 < e < self.target_depth]

    def layer_index(self) -> np.ndarray:
        """每个深度区间所在的层（按区间中点判断，0 起）。"""
        centers = self.depth - self.bin_width / 2
        if len(self.layers) < 2 or any(layer.width <= 0 for layer in self.layers):
            return np.zeros(len(self.depth), dtype=int)
        edges = np.cumsum([layer.width for layer in self.layers])[:-1]
        return np.minimum(np.searchsorted(edges, centers, side="right"), len(self.layers) - 1)

    def frame(self) -> pd.DataFrame:
        """表格原样（深度为 Å）。"""
        return pd.DataFrame({"Depth (A)": self.depth, **self.columns})

    @property
    def description(self) -> str:
        """如“Xe 5400 keV → Layer 1（2000 nm）”。"""
        target = " / ".join(layer.name for layer in self.layers) or "target"
        return f"{self.ion} {self.energy:g} keV → {target} ({self.target_depth / 10:g} nm)"


@dataclass
class VacancyTable(SRIMOutput):
    """
    VACANCY.txt：每个离子在每 Å 深度上产生的空位数（vacancies/(Å·ion)）。

    vacancies 是计算 dpa 用的总空位：Quick K-P 为离子产生的 + 反冲产生的；Full Cascade 为各元素空位列之和。
    Full Cascade 的各元素空位已经包含离子直接撞出的原子留下的空位，所以不再加 Knock-Ons 列，
    这样得到的总数与文件头的 Total Target Vacancies 一致。
    """

    reported_vacancies: float | None = None   # 文件头的 Total Target Vacancies（个 / 离子）
    elements: list[tuple[str, int | None]] = field(default_factory=list)  # Full Cascade 各空位列的（元素，层）

    @property
    def vacancies(self) -> np.ndarray:
        names = list(self.columns)
        if self.quick:
            return self.columns[names[0]] + self.columns[names[1]]
        return np.sum([self.columns[n] for n in names[1:]], axis=0)

    def element_vacancies(self) -> dict[str, np.ndarray]:
        """Full Cascade：各元素的空位（不同层中的同一元素合在一起）；Quick K-P 没有按元素的数据，返回 {}。"""
        if self.quick:
            return {}
        out: dict[str, np.ndarray] = {}
        for (symbol, _), values in zip(self.elements, list(self.columns.values())[1:], strict=True):
            out[symbol] = out[symbol] + values if symbol in out else values.copy()
        return out

    def vacancies_per_ion(self) -> float:
        """按表格积分得到的每个离子产生的空位数，可以与文件头的 Total Target Vacancies 核对。"""
        return float(np.sum(self.vacancies) * self.bin_width)


@dataclass
class RangeTable(SRIMOutput):
    """RANGE.txt：离子停留位置的分布，单位 (atoms/cm³)/(atoms/cm²)，乘以注量就是离子浓度（atoms/cm³）。"""

    mean_range: float | None = None    # 文件头的 Ion Average Range（Å）
    straggling: float | None = None    # 射程歧离（Å）

    @property
    def ions(self) -> np.ndarray:
        return next(iter(self.columns.values()))

    def stopped_fraction(self) -> float:
        """停在靶中的离子比例（分布对深度积分）。"""
        return float(np.sum(self.ions) * self.bin_width * 1e-8)


# ============================================================
# 读取
# ============================================================
def read_vacancy(path) -> VacancyTable:
    """读取 VACANCY.txt。"""
    path = Path(path)
    return parse_vacancy(read_text(path), path.name)


def read_range(path) -> RangeTable:
    """读取 RANGE.txt。"""
    path = Path(path)
    return parse_range(read_text(path), path.name)


def read_text(path) -> str:
    data = Path(path).read_bytes()
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1", errors="replace")


def parse_vacancy(text: str, source: str = "") -> VacancyTable:
    """从 VACANCY.txt 的内容读取（界面中保存在项目里的是文件内容）。"""
    head, header, rows = _split(text, source)
    titles = " ".join(header).upper()
    if "KNOCK" in titles:
        mode = "full"
    elif "VACANC" in titles and "RECOIL" in titles:
        mode = "quick"
    else:
        raise SRIMFileError(f"{source or 'The file'} does not look like a SRIM VACANCY.txt "
                            "(no vacancy columns in the table header).")
    info = _header(head)
    n = rows.shape[1] - 1
    if mode == "quick":
        if n != 2:
            raise SRIMFileError(f"Expected 2 vacancy columns in a Quick K-P VACANCY.txt, found {n}.")
        names = ["Vacancies by ions", "Vacancies by recoils"]
        elements: list[tuple[str, int | None]] = []
    else:
        symbols = _symbols(header, n)
        elements = _element_layers(symbols[1:], info["layers"])
        names = [f"Knock-ons ({symbols[0] or info['ion']})"]
        names += _unique([f"Vacancies ({s})" if layer is None or len(info["layers"]) < 2
                          else f"Vacancies ({s}, layer {layer + 1})" for s, layer in elements])
    total = _TOTAL_VACANCIES.search(head)
    return VacancyTable(
        mode=mode, depth=rows[:, 0], columns=dict(zip(names, rows[:, 1:].T, strict=True)), source=source,
        reported_vacancies=number(total.group(1)) if total else None, elements=elements, **info)


def parse_range(text: str, source: str = "") -> RangeTable:
    """从 RANGE.txt 的内容读取。"""
    head, header, rows = _split(text, source)
    titles = " ".join(header).upper()
    if "ION" not in titles or "VACANC" in titles or "KNOCK" in titles or rows.shape[1] < 2:
        raise SRIMFileError(f"{source or 'The file'} does not look like a SRIM RANGE.txt "
                            "(no ion distribution in the table header).")
    info = _header(head)
    n = rows.shape[1] - 1
    mode = "full" if "TGT" in titles or "TARGET ATOM" in titles else "quick"
    if mode == "full":
        symbols = _symbols(header, n)
        layers = _element_layers(symbols[1:], info["layers"])
        names = [f"Ions ({symbols[0] or info['ion']})"]
        names += _unique([f"Recoils ({s})" if layer is None or len(info["layers"]) < 2
                          else f"Recoils ({s}, layer {layer + 1})" for s, layer in layers])
    else:
        names = [f"Ions ({info['ion']})", *[f"Recoils {i}" if n > 2 else "Recoils" for i in range(1, n)]]
    rng = _RANGE.search(head)
    mean_range = number(rng.group(1)) if rng else None
    return RangeTable(
        mode=mode, depth=rows[:, 0], columns=dict(zip(names, rows[:, 1:].T, strict=True)), source=source,
        mean_range=mean_range if mean_range else None,
        straggling=number(rng.group(2)) if rng and mean_range else None, **info)


# ============================================================
# 内部
# ============================================================
def _split(text: str, source: str) -> tuple[str, list[str], np.ndarray]:
    """把文件分成文件头、表头（分隔线上面的几行）和数值表。"""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    sep = next((i for i, line in enumerate(lines) if _SEPARATOR.match(line)), None)
    if sep is None:
        raise SRIMFileError(f"{source or 'The file'} has no SRIM table (no dashed line under the column titles).")
    header = []
    for line in reversed(lines[max(sep - 4, 0):sep]):
        if not line.strip() or line.strip().startswith("="):
            break
        header.insert(0, line)
    width = len(lines[sep].split())
    rows = []
    for line in lines[sep + 1:]:
        parts = line.split()
        if not parts:
            if rows:
                break
            continue
        try:
            values = [number(p) for p in parts]
        except ValueError:
            break
        if len(values) != width:
            raise SRIMFileError(f"Row {len(rows) + 1} of the table has {len(values)} values, expected {width}.")
        rows.append(values)
    if len(rows) < 2:
        raise SRIMFileError(f"{source or 'The file'} has fewer than 2 rows in its table.")
    table = np.asarray(rows, dtype=float)
    if not np.all(np.isfinite(table)) or np.any(np.diff(table[:, 0]) <= 0):
        raise SRIMFileError("The depths in the table must be finite and increasing.")
    return "\n".join(lines[:sep]), header, table


def _header(head: str) -> dict:
    ion = _ION.search(head)
    if ion is None:
        raise SRIMFileError("The ion and its energy were not found in the file header.")
    calculated = _IONS_CALCULATED.search(head)
    layers: dict[int, dict] = {}
    current: int | None = None
    for line in head.split("\n"):
        if (m := _LAYER_NAME.match(line)) and "#" not in line:
            current = int(m.group(1))
            layers.setdefault(current, {"elements": {}})["name"] = m.group(2)
        if (m := _LAYER_WIDTH.search(line)) and current is not None:
            layers[current]["width"] = number(m.group(1))
        if m := _LAYER_DENSITY.search(line):
            entry = layers.setdefault(int(m.group(1)), {"elements": {}})
            entry["density"] = number(m.group(2))
            entry["mass_density"] = number(m.group(3)) if m.group(3) else None
        for m in _LAYER_ELEMENT.finditer(line):
            layers.setdefault(int(m.group(1)), {"elements": {}})["elements"][m.group(2)] = number(m.group(3))
    out = []
    for index in sorted(layers):
        entry = layers[index]
        if "density" not in entry:
            raise SRIMFileError(f"The atomic density of layer {index} was not found in the file header.")
        out.append(Layer(entry.get("name") or f"Layer {index}", float(entry.get("width", 0.0)),
                         entry["density"], entry.get("mass_density"), dict(entry["elements"])))
    if not out:
        raise SRIMFileError("The target layers were not found in the file header.")
    return {"ion": ion.group(1), "energy": number(ion.group(2)),
            "ions_calculated": number(calculated.group(1)) if calculated else None, "layers": out}


def _symbols(header: list[str], n: int) -> list[str]:
    """表头中各列的元素符号（深度列以外，n 列）：在含 DEPTH 的那一行，深度之后依次是离子和各元素。"""
    for line in header:
        parts = line.split()
        if parts and parts[0].upper() == "DEPTH" and len(parts) - 1 == n:
            return parts[1:]
    return [""] * n


def _element_layers(symbols: list[str], layers: list[Layer]) -> list[tuple[str, int | None]]:
    """把按元素排列的列对应到层：文件头中各层的元素依次排列，与表中的列顺序相同。"""
    expected = [(symbol, i) for i, layer in enumerate(layers) for symbol in layer.elements]
    if len(expected) == len(symbols) and all(not s or s == e for s, (e, _) in zip(symbols, expected, strict=True)):
        return expected
    return [(s or f"Element {i + 1}", None) for i, s in enumerate(symbols)]


def _unique(names: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    out = []
    for name in names:
        seen[name] = seen.get(name, 0) + 1
        out.append(name if seen[name] == 1 else f"{name} {seen[name]}")
    return out
