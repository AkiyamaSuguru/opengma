# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
导入对话框的适配：读取仍然调用 GMA.project 的 inspect_files / inspect_folder（内部用各方法的 Loader），
这里只负责对话框中要显示的文字，以及整批修改样品名、读取器、类型（方案 7.1）。
"""
from __future__ import annotations

from ...project import ImportItem, inspect_file, inspect_files, inspect_folder
from ...project.importers import set_kind
from ..strings import S


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
    """“识别为”下拉框的选项：XPS 为全谱 / 元素谱，元素谱注明是否已拟合。"""
    if item.method != "XPS":
        return [(item.kind, item.kind)]
    element = S.KIND_ELEMENT
    if item.kind == "element" and item.ok:
        element = S.KIND_ELEMENT_FITTED if item.fitted else S.KIND_ELEMENT_RAW
    return [("survey", S.KIND_SURVEY), ("element", element)]


def inspect(paths=None, folder=None, *, method: str, reader: str | None = None) -> list[ImportItem]:
    """读取选中的文件或文件夹（在后台线程中调用）。"""
    if folder is not None:
        return inspect_folder(folder, method, reader=reader)
    return inspect_files(paths or [], method, reader=reader)


def reread(items: list[ImportItem], *, reader: str) -> list[ImportItem]:
    """换读取器后重新读取，保留用户改过的样品名、谱图名、类型和勾选。"""
    out = []
    for old in items:
        new = inspect_file(old.path, old.method, sample=old.sample, kind=old.kind, reader=reader)
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
