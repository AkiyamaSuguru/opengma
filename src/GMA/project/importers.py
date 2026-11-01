# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
导入：读取仪器导出的文件，先生成可以检查和修改的导入项（ImportItem），确认后再加入项目。

读取仍然通过 GMA 的 Loader（XPSLoader、RamanLoader、XRDLoader），它们的列检查全部保留；
这里只负责识别数据类型、默认命名、清洗记录和来源信息。
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from ..CM.common.data import BG_COL, FIT_COL, INTENSITY_COL
from ..CM.Raman.loader import RamanLoader
from ..CM.XPS.loader import XPSLoader
from ..CM.XRD.loader import XRDLoader
from .model import CleanNote, Project, ProjectError, Record, clean_frame, method_spec, now_iso

XPS_SUFFIXES = (".xls", ".xlsx", ".xlsm")
TEXT_SUFFIXES = (".txt",)
# 文件名（不含扩展名，忽略大小写和空格、横线、下划线）是这些时识别为全谱
SURVEY_STEMS = {"survey", "xpssurvey", "wide", "widescan", "fullspectrum", "全谱"}
DEFAULT_READERS = {"XPS": "Avantage", "Raman": "Horiba HR evolution", "XRD": "D8 Advance"}


def file_sha256(path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalized_stem(path: Path) -> str:
    return "".join(ch for ch in path.stem.lower() if ch not in " -_")


def guess_xps_kind(path) -> str:
    """按文件名判断 XPS 数据是全谱（survey）还是元素谱（element）。"""
    return "survey" if _normalized_stem(Path(path)) in SURVEY_STEMS else "element"


@dataclass
class ImportItem:
    """
    一个待导入的文件。界面在导入对话框中显示这些项，用户可以修改 kind、sample、name、
    components，取消 selected；确认后用 commit() 加入项目。
    """

    path: Path
    method: str
    kind: str
    sample: str
    name: str
    reader: str
    frame: pd.DataFrame | None = None
    metadata: dict = field(default_factory=dict)
    clean_notes: list[CleanNote] = field(default_factory=list)
    error: str | None = None
    selected: bool = True
    _components: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.error is None and self.frame is not None

    @property
    def fitted(self) -> bool:
        return self.ok and FIT_COL in self.frame.columns

    @property
    def point_count(self) -> int:
        return len(self.frame) if self.ok else 0

    @property
    def file_components(self) -> list[str]:
        """文件中的分峰列名（如 Avantage 中的 C1s A），也就是没有改名时的名称。"""
        if not self.fitted:
            return []
        spec = method_spec(self.method)
        standard = {spec.x_column, INTENSITY_COL, FIT_COL, BG_COL}
        return [str(c) for c in self.frame.columns if c not in standard]

    @property
    def components(self) -> list[str]:
        return list(self._components) if self._components else self.file_components

    @components.setter
    def components(self, names) -> None:
        names = [str(n).strip() for n in names]
        expected = len(self.file_components)
        if len(names) != expected:
            raise ProjectError(f"{self.path.name}: expected {expected} component names, got {len(names)}.")
        self._components = names

    @property
    def renamed(self) -> bool:
        return bool(self._components) and self._components != self.file_components


# ============================================================
# 读取
# ============================================================
def _read(path: Path, method: str, kind: str, reader: str):
    """用 GMA 的 Loader 读取，返回 (DataFrame, metadata)。"""
    if method == "XPS":
        loader = XPSLoader(reader)
        df = loader.read_survey(path) if kind == "survey" else loader.read_element(path)
        return df, {}
    if method == "Raman":
        df, metadata = RamanLoader(reader).read(path)
        return df, dict(metadata or {})
    if method == "XRD":
        df, metadata = XRDLoader(reader).read(path)
        return df, dict(metadata or {})
    raise ProjectError(f"Unknown method {method!r}")


def inspect_file(path, method: str, *, sample: str | None = None, kind: str | None = None,
                 reader: str | None = None) -> ImportItem:
    """读取一个文件，生成导入项。读取或清洗出错时 item.error 记下原因，不抛出异常。"""
    path = Path(path).expanduser()
    spec = method_spec(method)
    reader = reader or DEFAULT_READERS[method]
    if kind is None:
        kind = guess_xps_kind(path) if method == "XPS" else spec.kinds[0]
    item = ImportItem(path=path, method=method, kind=kind,
                      sample=(sample or path.parent.name or "未命名样品").strip(),
                      name=path.stem.strip() or path.name, reader=reader)
    try:
        df, metadata = _read(path, method, kind, reader)
        item.frame, item.clean_notes = clean_frame(df, method)
        item.metadata = metadata
    except Exception as exc:  # 读取失败的文件显示在导入对话框中，由用户决定
        item.error = str(exc) or type(exc).__name__
        item.selected = False
    return item


def set_kind(item: ImportItem, kind: str) -> ImportItem:
    """用户在导入对话框中修改类型（如 XPS 全谱 ↔ 元素谱）后重新读取，保留样品名和名称。"""
    new = inspect_file(item.path, item.method, sample=item.sample, kind=kind, reader=item.reader)
    new.name = item.name
    return new


def _files_in(folder: Path, suffixes) -> list[Path]:
    if not folder.is_dir():
        raise ProjectError(f"Folder not found: {folder}")
    return sorted((p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in suffixes
                   and not p.name.startswith(("~$", "."))), key=lambda p: p.name.casefold())


def inspect_folder(folder, method: str, *, reader: str | None = None) -> list[ImportItem]:
    """读取文件夹中的所有数据文件：文件夹名作样品名，文件名作谱图名。"""
    folder = Path(folder).expanduser()
    suffixes = XPS_SUFFIXES if method == "XPS" else TEXT_SUFFIXES
    files = _files_in(folder, suffixes)
    if not files:
        raise ProjectError(f"No {', '.join(suffixes)} files in {folder}")
    return [inspect_file(p, method, sample=folder.name, reader=reader) for p in files]


def inspect_files(paths, method: str, *, sample: str | None = None, reader: str | None = None) -> list[ImportItem]:
    """读取多个文件；不给 sample 时用各文件所在文件夹的名称。"""
    return [inspect_file(p, method, sample=sample, reader=reader) for p in paths]


# ============================================================
# 加入项目
# ============================================================
def item_to_record(item: ImportItem, component_mode: str = "absolute") -> Record:
    if not item.ok:
        raise ProjectError(f"{item.path.name}: {item.error or 'nothing to import'}")
    df = item.frame
    if item.renamed:
        df = df.rename(columns=dict(zip(item.file_components, item.components, strict=True)))
    source = {
        "path": str(item.path), "file": item.path.name, "sha256": file_sha256(item.path),
        "reader": item.reader, "imported_at": now_iso(),
    }
    return Record.from_dataframe(
        df, item.method, item.name, item.sample, kind=item.kind, component_mode=component_mode,
        metadata=item.metadata, source=source, clean_notes=item.clean_notes,
    )


def commit(project: Project, items, *, on_conflict: str = "copy",
           component_mode: str = "absolute") -> list[Record]:
    """把选中且读取成功的导入项加入项目，返回实际加入的谱图（skip 掉的不在其中）。"""
    added = []
    for item in items:
        if not (item.selected and item.ok):
            continue
        record = project.add_record(item_to_record(item, component_mode), on_conflict=on_conflict)
        if record is not None:
            added.append(record)
    return added
