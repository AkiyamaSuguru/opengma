# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
表格文件：

- read_table：读取其他软件导出的数据表格（CSV、TSV 或文本），导入时由用户指定各列的含义
  （见 importers.TableColumns）；
- 峰位表、参考物相表与 CSV 之间的读写，方便在项目之间复用，也可以在 Excel 中编辑。
"""
from __future__ import annotations

import csv
import io
import re
from collections import Counter
from pathlib import Path

import pandas as pd

from .model import ProjectError, check_peak_rows, check_phase_rows

ENCODINGS = ("utf-8-sig", "gb18030", "latin-1")
SEPARATORS = ("\t", ",", ";")
NUMBER = re.compile(r"^[+-]?(\d+([.,]\d*)?|[.,]\d+)([eE][+-]?\d+)?$")

PEAK_COLUMNS = ("label", "position")
PHASE_COLUMNS = ("phase", "hkl", "two_theta")
# 读 CSV 时认得的表头（不区分大小写）
_ALIASES = {
    "label": {"label", "name", "peak", "标签", "名称", "峰"},
    "position": {"position", "pos", "center", "x", "位置", "峰位"},
    "phase": {"phase", "物相", "物相名"},
    "hkl": {"hkl", "(hkl)", "plane", "晶面", "晶面指数"},
    "two_theta": {"two_theta", "2theta", "2θ", "2-theta", "two theta", "2theta (deg)", "2θ (°)"},
}


def _read_text(path: Path) -> str:
    data = path.read_bytes()
    for encoding in ENCODINGS:
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1", errors="replace")


def _split(line: str, sep: str | None) -> list[str]:
    parts = line.split(sep) if sep else line.split()
    return [p.strip().strip('"').strip("'").strip() for p in parts]


def _is_number(text: str) -> bool:
    return bool(NUMBER.match(text.replace(" ", "")))


def _guess_separator(lines: list[str]) -> str | None:
    """在看起来是数据的行中找分隔符：每行都出现、分出的列数相同且至少 2 列的那个；都不是时按空白分隔。"""
    sample = [line for line in lines if any(ch.isdigit() for ch in line)][:50]
    for sep in SEPARATORS:
        widths = [len(_split(line, sep)) for line in sample]
        if widths and min(widths) >= 2 and len(set(widths)) == 1:
            return sep
    for sep in SEPARATORS:  # 列数不完全相同（如某些行末尾多一个分隔符）时，取最常见的列数
        widths = [len(_split(line, sep)) for line in sample]
        if widths and Counter(widths).most_common(1)[0][1] >= 0.8 * len(widths) and min(widths) >= 2:
            return sep
    return None


def read_table(path) -> pd.DataFrame:
    """
    读取数据表格：自动识别编码（UTF-8、GBK）、分隔符（制表符、逗号、分号、空白）、表头和开头的说明行。

    数据从第一个至少有两列数值的行开始；它前面连续的文字行中，非空格子最多的一行作为表头（去掉开头的 #）。
    没有表头时列名为 Column 1、Column 2…。分隔符不是逗号时，1,5 这样的小数逗号按小数点处理。
    返回各列转成数值的 DataFrame，不是数值的格为 NaN（导入时由清洗步骤去掉并记录）。
    """
    path = Path(path).expanduser()
    lines = [line.strip() for line in _read_text(path).splitlines()]
    lines = [line for line in lines if line]
    if not lines:
        raise ProjectError(f"{path.name}: the file is empty.")
    sep = _guess_separator(lines)
    rows = [_split(line, sep) for line in lines]

    def numeric(row) -> int:
        return sum(1 for cell in row if cell and _is_number(cell))

    start = next((i for i, row in enumerate(rows) if numeric(row) >= 2), None)
    if start is None:
        raise ProjectError(f"{path.name}: no rows with at least two numeric columns.")
    width = Counter(len(r) for r in rows[start:]).most_common(1)[0][0]
    # 表头：数据前面连续的文字行（至少两列）中，非空格子最多的一行；
    # 如 Origin 导出的“名称、单位、注释”三行，取名称一行
    block = []
    i = start - 1
    while i >= 0 and numeric(rows[i]) == 0 and len(rows[i]) >= 2:
        block.insert(0, rows[i])
        i -= 1
    header = max(block, key=lambda r: sum(1 for c in r if c)) if block else None
    names = []
    for i in range(width):
        name = header[i].lstrip("#").strip() if header and i < len(header) else ""
        if not name or name in names:
            name = f"Column {i + 1}"
        names.append(name)
    body = [(r + [""] * width)[:width] for r in rows[start:]]
    decimal_comma = sep != ","

    def to_float(text: str) -> float:
        text = text.replace(" ", "")
        if decimal_comma and "," in text and "." not in text:
            text = text.replace(",", ".")
        try:
            return float(text)
        except ValueError:
            return float("nan")

    table = pd.DataFrame([[to_float(c) for c in row] for row in body], columns=names)
    # 整列都不是数值的列（如备注）去掉
    keep = [c for c in table.columns if table[c].notna().any()]
    if len(keep) < 2:
        raise ProjectError(f"{path.name}: fewer than two numeric columns.")
    return table[keep]


# ============================================================
# 峰位表、参考物相表与 CSV
# ============================================================
def _read_rows(path, columns: tuple[str, ...]) -> list[dict]:
    """读取按列存放的小表格：有表头时按表头对应列，没有表头时按列的顺序。"""
    path = Path(path).expanduser()
    text = _read_text(path)
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return []
    try:
        dialect = csv.Sniffer().sniff("\n".join(lines[:20]), delimiters=",\t;")
    except csv.Error:
        dialect = csv.excel
    rows = [[c.strip() for c in row] for row in csv.reader(io.StringIO("\n".join(lines)), dialect)]
    rows = [r for r in rows if any(r)]
    first = [c.lower() for c in rows[0]]
    index = {}
    for key in columns:
        for i, name in enumerate(first):
            if name in _ALIASES[key]:
                index[key] = i
                break
    if len(index) == len(columns):
        rows = rows[1:]
    else:
        # 没有认得的表头：按列的顺序；第一行的数值列不是数值时当作表头跳过
        index = {key: i for i, key in enumerate(columns)}
        if not _is_number(rows[0][index[columns[-1]]] if len(rows[0]) > index[columns[-1]] else ""):
            rows = rows[1:]
    out = []
    for row in rows:
        out.append({key: row[i] if i < len(row) else "" for key, i in index.items()})
    return out


def _write_rows(rows: list[dict], path, columns: tuple[str, ...]) -> Path:
    path = Path(path).expanduser()
    with open(path, "w", newline="", encoding="utf-8-sig") as f:  # 带 BOM，Excel 打开中文不乱码
        writer = csv.writer(f)
        writer.writerow(columns)
        for row in rows:
            writer.writerow([row[c] for c in columns])
    return path


def read_peak_csv(path) -> list[dict]:
    """读取峰位表 CSV：两列，标签和位置（表头 label,position，也认得“标签”“位置”）。"""
    return check_peak_rows(_read_rows(path, PEAK_COLUMNS))


def write_peak_csv(rows, path) -> Path:
    return _write_rows(check_peak_rows(rows), path, PEAK_COLUMNS)


def read_phase_csv(path) -> list[dict]:
    """读取参考物相 CSV：三列，物相名、晶面指数和 2θ（表头 phase,hkl,two_theta，也认得“物相”“晶面指数”“2θ”）。"""
    return check_phase_rows(_read_rows(path, PHASE_COLUMNS))


def write_phase_csv(rows, path) -> Path:
    return _write_rows(check_phase_rows(rows), path, PHASE_COLUMNS)
