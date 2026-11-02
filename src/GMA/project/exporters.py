# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
导出提取的数据：CSV（每条谱图一个文件）或 Excel（每条谱图一个工作表，另附“信息”表）。

导出的列名就是 GMA 的标准数据结构，可以直接用于其他软件，或者再用 GMA 读回来作图。
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from .model import Project, ProjectError

INVALID_SHEET = re.compile(r"[\[\]:*?/\\]")
INVALID_FILE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
MAX_SHEET = 31  # Excel 工作表名的长度上限
INFO_SHEET = "信息"


def safe_filename(name: str) -> str:
    text = INVALID_FILE.sub("_", str(name)).strip(" .")
    return text or "_"


def sheet_name(base: str, used: set[str]) -> str:
    """生成合法且不重复的工作表名：去掉 []:*?/\\，长度不超过 31。"""
    clean = INVALID_SHEET.sub("_", str(base)).strip("'") or "Sheet"
    name, i = clean[:MAX_SHEET], 2
    while name.casefold() in used or name == INFO_SHEET:
        suffix = f" ({i})"
        name = clean[: MAX_SHEET - len(suffix)] + suffix
        i += 1
    used.add(name.casefold())
    return name


def info_frame(records, project: Project | None = None, sheets: list[str] | None = None) -> pd.DataFrame:
    """每条谱图一行：工作表名、样品、方法、类型、名称、来源、清洗记录，以及样品信息字段。"""
    fields = list(project.sample_fields) if project is not None else []
    rows = []
    for i, r in enumerate(records):
        src = r.source
        row = {
            "工作表": sheets[i] if sheets else "",
            "样品": r.sample, "方法": r.method, "类型": r.kind, "名称": r.name,
            "点数": r.point_count, "分峰": "、".join(r.components),
            "分峰数据模式": r.component_mode if r.fitted else "",
            "来源文件": src["path"], "SHA-256": src["sha256"], "读取器": src["reader"],
            "导入时间": src["imported_at"], "GMA 版本": src["gma_version"],
            "清洗记录": "；".join(n.text() for n in r.clean_notes),
            "备注": r.notes,
        }
        if project is not None and r.sample in project.samples:
            info = project.samples[r.sample].info
            row.update({f: info.get(f, "") for f in fields})
        rows.append(row)
    if not sheets:
        for row in rows:
            row.pop("工作表")
    return pd.DataFrame(rows)


def export_csv(records, folder, *, include_components: bool = True) -> list[Path]:
    """每条谱图写一个 CSV：{folder}/{样品}/{方法}/{名称}.csv，返回写入的文件。"""
    records = list(records)
    if not records:
        raise ProjectError("Nothing to export.")
    folder = Path(folder).expanduser()
    written, used = [], set()
    for r in records:
        directory = folder / safe_filename(r.sample) / safe_filename(r.method)
        directory.mkdir(parents=True, exist_ok=True)
        base, i = safe_filename(r.name), 2
        path = directory / f"{base}.csv"
        while path in used:
            path = directory / f"{base} ({i}).csv"
            i += 1
        used.add(path)
        r.to_dataframe(include_components=include_components).to_csv(path, index=False, encoding="utf-8-sig")
        written.append(path)
    return written


def export_excel(records, path, *, include_components: bool = True, project: Project | None = None,
                 extra_sheets: dict[str, pd.DataFrame] | None = None) -> Path:
    """
    写一个 .xlsx：每条谱图一个工作表（名称为“样品-谱图名”），最后是“信息”表。
    extra_sheets 可以附加其他表，例如界面中的分析结果。
    """
    records = list(records)
    if not records:
        raise ProjectError("Nothing to export.")
    path = Path(path).expanduser()
    if path.suffix.lower() != ".xlsx":
        path = path.with_name(path.name + ".xlsx")
    path.parent.mkdir(parents=True, exist_ok=True)
    used: set[str] = set()
    sheets = [sheet_name(f"{r.sample}-{r.name}", used) for r in records]
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        for r, sheet in zip(records, sheets, strict=True):
            r.to_dataframe(include_components=include_components).to_excel(writer, sheet_name=sheet, index=False)
        for name, df in (extra_sheets or {}).items():
            df.to_excel(writer, sheet_name=sheet_name(name, used), index=False)
        info_frame(records, project, sheets).to_excel(writer, sheet_name=INFO_SHEET, index=False)
    return path
