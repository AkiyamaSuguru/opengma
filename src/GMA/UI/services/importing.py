# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
导入对话框的适配：读取仍然调用 GMA.project 的 inspect_files / inspect_folder（内部用各方法的 Loader），
这里只负责对话框中要显示的文字，以及整批修改样品名、读取器、类型（方案 7.1）；
通用表格（其他软件导出的 CSV 等）先猜各列的含义，再由用户在对话框中确认（方案 8）。
"""
from __future__ import annotations

import re

import pandas as pd

from ...project import (
    GENERIC_READER,
    ImportItem,
    TableColumns,
    inspect_file,
    inspect_files,
    inspect_folder,
)
from ...project.importers import TABLE_SUFFIXES, set_kind
from ..strings import S

__all__ = ["GENERIC_READER", "TABLE_SUFFIXES", "change_kind", "check_text", "common_sample", "guess_columns",
           "inspect", "kind_options", "reader_label", "reread"]

# 猜通用表格各列的含义时认得的列名（不区分大小写，只看字母、数字和中文）
_X_WORDS = ("ramanshift", "shift", "wavenumber", "wave", "2theta", "2θ", "twotheta", "angle", "bindingenergy",
            "energy", "be", "x", "拉曼位移", "结合能", "角度")
_Y_WORDS = ("intensity", "counts", "count", "cps", "int", "raw", "y", "强度", "计数")
_FIT_WORDS = ("fittingcurve", "fit", "fitted", "envelope", "sum", "cumulative", "cumulativefitpeak", "拟合",
              "拟合曲线")
_BG_WORDS = ("background", "backgnd", "bg", "base", "baseline", "背景", "基线")


def group(n: int) -> str:
    """1201 → 1 201。"""
    return f"{n:,}".replace(",", " ")


def note_short(note) -> str:
    d = note.detail
    if note.code == "dropped_rows":
        return S.NOTE_DROPPED.format(n=d.get("count", 0))
    if note.code == "empty_component":
        return S.NOTE_EMPTY_COMPONENT.format(column=d.get("column", ""))
    if note.code == "duplicate_x":
        return S.NOTE_DUPLICATE_X.format(n=d.get("count", 0))
    if note.code == "sorted":
        return S.NOTE_SORTED
    return note.text()


def check_text(item: ImportItem) -> tuple[bool, str]:
    """“检查”一列：(是否可以导入, 说明)。可以导入时写点数、分峰数和清洗记录，不能时写原因。"""
    if not item.ok:
        return False, S.READ_FAILED.format(reason=item.error or "?")
    parts = [S.POINTS.format(n=group(item.point_count))]
    if item.fitted:
        parts.append(S.N_PEAKS.format(n=len(item.file_components)))
    parts += [note_short(n) for n in item.clean_notes]
    return True, " · ".join(parts)


def kind_options(item: ImportItem) -> list[tuple[str, str]]:
    """“识别为”下拉框的选项：XPS 为全谱 / 元素谱，元素谱注明是否已拟合；Raman、XRD 只有一种类型。"""
    if item.method == "Raman":
        return [(item.kind, S.KIND_RAMAN_FITTED if item.ok and item.fitted else S.KIND_RAMAN)]
    if item.method != "XPS":
        return [(item.kind, S.KIND_XRD)]
    element = S.KIND_ELEMENT
    if item.kind == "element" and item.ok:
        element = S.KIND_ELEMENT_FITTED if item.fitted else S.KIND_ELEMENT_RAW
    return [("survey", S.KIND_SURVEY), ("element", element)]


def reader_label(reader: str) -> str:
    return S.GENERIC_READER if reader == GENERIC_READER else reader


def inspect(paths=None, folder=None, *, method: str, reader: str | None = None,
            columns: TableColumns | None = None) -> list[ImportItem]:
    """读取选中的文件或文件夹（在后台线程中调用）；通用表格按 columns 读取。"""
    if folder is not None:
        return inspect_folder(folder, method, reader=reader, columns=columns)
    return inspect_files(paths or [], method, reader=reader, columns=columns)


def _key(name: str) -> str:
    return re.sub(r"[^0-9a-zα-ω\u4e00-\u9fff]", "", str(name).lower().split("(")[0])


def _find(columns: list[str], words: tuple[str, ...], used: set[str]) -> str | None:
    for word in words:  # 按 words 的顺序，先找完全相同的，再找包含的
        for col in columns:
            if col not in used and _key(col) == word:
                return col
    for word in words:
        if len(word) < 3:
            continue
        for col in columns:
            if col not in used and word in _key(col):
                return col
    return None


def guess_columns(table: pd.DataFrame, method: str) -> TableColumns:
    """
    按列名猜各列的含义：横轴、强度；有拟合曲线和背景列时（XRD 除外），其余列作为分峰。
    猜不出时横轴取第一列、强度取第二列。结果只是对话框中的初始值，由用户确认。
    """
    columns = [str(c) for c in table.columns]
    used: set[str] = set()
    x = _find(columns, _X_WORDS, used) or columns[0]
    used.add(x)
    y = _find(columns, _Y_WORDS, used) or next(c for c in columns if c not in used)
    used.add(y)
    fit = bg = None
    components: list[str] = []
    if method != "XRD":
        fit = _find(columns, _FIT_WORDS, used)
        bg = _find(columns, _BG_WORDS, used | ({fit} if fit else set()))
        if fit and bg:
            used |= {fit, bg}
            components = [c for c in columns if c not in used]
        else:
            fit = bg = None
    return TableColumns(x, y, fit, bg, components)


def reread(items: list[ImportItem], *, reader: str) -> list[ImportItem]:
    """换读取器后重新读取，保留用户改过的样品名、谱图名、类型和勾选。"""
    out = []
    for old in items:
        new = inspect_file(old.path, old.method, sample=old.sample, kind=old.kind, reader=reader,
                           columns=old.columns)
        new.name = old.name
        if new.ok and old.ok and old.selected is False:
            new.selected = False
        out.append(new)
    return out


def change_kind(item: ImportItem, kind: str) -> ImportItem:
    """修改识别结果（全谱 ↔ 元素谱）后重新读取。"""
    new = set_kind(item, kind)
    new.sample = item.sample
    return new


def common_sample(items: list[ImportItem]) -> str:
    samples = {i.sample for i in items}
    return next(iter(samples)) if len(samples) == 1 else ""
