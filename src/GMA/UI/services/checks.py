# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
项目总览中的“数据检查”：列出清洗记录和命名不一致等提示，只提示、不自动修改（方案 5.3）。
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from ...project import Project
from ..strings import S
from .importing import note_text

INFO, WARNING = "info", "warning"


@dataclass(frozen=True)
class Issue:
    level: str          # INFO / WARNING
    title: str          # 粗体部分：数据位置或区域名
    text: str
    record_ids: tuple[str, ...] = ()   # 相关的谱图，以后可以跳到对应的数据


def data_issues(project: Project) -> list[Issue]:
    issues = []
    records = sorted(project.records.values(), key=lambda r: (r.sample, r.method, r.name))
    # 导入时的清洗记录
    for r in records:
        for note in r.clean_notes:
            issues.append(Issue(INFO, f"{r.sample} / {r.method} / {r.name}", note_text(note), (r.record_id,)))
    # 同一方法、同名的拟合谱（如各样品的 C1s）分峰名不一致
    groups = defaultdict(list)
    for r in records:
        if r.fitted and r.components:
            groups[(r.method, r.name)].append(r)
    for (_method, name), rs in groups.items():
        variants = []
        for r in rs:
            names = tuple(r.components)
            if names not in variants:
                variants.append(names)
        if len(variants) > 1 and len({r.sample for r in rs}) > 1:
            text = S.NAMING_INCONSISTENT.format(n=len({r.sample for r in rs}), variants=_differences(variants))
            issues.append(Issue(WARNING, name, text, tuple(r.record_id for r in rs)))
    return issues


def _differences(variants: list[tuple[str, ...]]) -> str:
    """分峰数相同时只列出不一致的位置，例如“C-C ／ C-C/C-H”；分峰数不同时列出各自的全部分峰名。"""
    if len({len(v) for v in variants}) == 1:
        parts = []
        for names in zip(*variants, strict=True):
            unique = list(dict.fromkeys(names))
            if len(unique) > 1:
                parts.append(S.VARIANT_SEP.join(unique))
        return S.GROUP_SEP.join(parts)
    return S.VARIANT_SEP.join(S.LIST_SEP.join(v) for v in variants)
