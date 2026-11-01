# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
项目文件的读写：一个项目保存为一个 NetCDF-4/HDF5 文件（.nc），内部是 xarray.DataTree：

    /                       根：schema、项目名、时间、样品字段、峰位表、物相表、界面状态
    /{样品}                 样品信息
    /{样品}/{方法}          XPS、Raman、XRD
    /{样品}/{方法}/{名称}   一条谱图（Record.data）

不用界面也可以用 xarray.open_datatree(path, engine="h5netcdf") 直接打开。
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import xarray as xr

from .model import Project, ProjectError, Record, Sample, gma_version, now_iso

SCHEMA_NAME = "opengma-project"
SCHEMA_VERSION = "1.0"
ENGINE = "h5netcdf"
SUFFIX = ".nc"


def _node_name(name: str, used: set[str]) -> str:
    """DataTree 的节点名不能含 /，这里替换掉；替换后重名时加序号。显示用的原名保存在属性中。"""
    base = name.replace("/", "_").replace("\\", "_").strip() or "_"
    node, i = base, 2
    while node in used:
        node = f"{base} ({i})"
        i += 1
    used.add(node)
    return node


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _loads(text, default):
    if not text:
        return default
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return default


# ============================================================
# Project ⇄ DataTree
# ============================================================
def project_to_datatree(project: Project) -> xr.DataTree:
    root_attrs = {
        "schema_name": SCHEMA_NAME,
        "schema_version": SCHEMA_VERSION,
        "project_name": project.name,
        "created_at": project.created_at,
        "saved_at": now_iso(),
        "gma_version": gma_version(),
        "sample_fields": _json(project.sample_fields),
        "sample_order": _json(list(project.samples)),
        "record_order": _json(list(project.records)),
        "peak_tables": _json(project.peak_tables),
        "reference_phases": _json(project.reference_phases),
        "ui_state": _json(project.ui_state),
    }
    tree = xr.DataTree(dataset=xr.Dataset(attrs=root_attrs))
    sample_nodes: dict[str, str] = {}
    used_samples: set[str] = set()
    for sample in project.samples.values():
        node = _node_name(sample.name, used_samples)
        sample_nodes[sample.name] = node
        tree[f"/{node}"] = xr.Dataset(attrs={"node_type": "sample", "name": sample.name,
                                             "info": _json(sample.info)})
    used_records: dict[tuple[str, str], set[str]] = {}
    for record in project.records.values():
        if record.sample not in sample_nodes:  # 谱图的样品不在样品表中时补上
            node = _node_name(record.sample, used_samples)
            sample_nodes[record.sample] = node
            tree[f"/{node}"] = xr.Dataset(attrs={"node_type": "sample", "name": record.sample, "info": "{}"})
        sample_node = sample_nodes[record.sample]
        if record.method not in tree[f"/{sample_node}"].children:
            tree[f"/{sample_node}/{record.method}"] = xr.Dataset(attrs={"node_type": "method", "method": record.method})
        used = used_records.setdefault((sample_node, record.method), set())
        leaf = _node_name(record.name, used)
        tree[f"/{sample_node}/{record.method}/{leaf}"] = record.data
    return tree


def datatree_to_project(tree: xr.DataTree, file_path=None) -> Project:
    attrs = tree.attrs
    if attrs.get("schema_name") != SCHEMA_NAME:
        raise ProjectError("This file is not an OpenGMA project.")
    version = str(attrs.get("schema_version", ""))
    if version != SCHEMA_VERSION:
        raise ProjectError(f"Unsupported project schema version {version!r} (supported: {SCHEMA_VERSION}).")
    project = Project(
        name=str(attrs.get("project_name", "未命名项目")),
        sample_fields=list(_loads(attrs.get("sample_fields"), [])),
        peak_tables=dict(_loads(attrs.get("peak_tables"), {})),
        reference_phases=list(_loads(attrs.get("reference_phases"), [])),
        ui_state=dict(_loads(attrs.get("ui_state"), {})),
        created_at=str(attrs.get("created_at", "")) or now_iso(),
    )
    samples: dict[str, Sample] = {}
    records: dict[str, Record] = {}
    for sample_node in tree.children.values():
        sattrs = sample_node.attrs
        if sattrs.get("node_type") != "sample":
            continue
        name = str(sattrs.get("name") or sample_node.name)
        samples[name] = Sample(name, dict(_loads(sattrs.get("info"), {})))
        for method_node in sample_node.children.values():
            for leaf in method_node.children.values():
                ds = leaf.to_dataset(inherit=False)
                if ds.attrs.get("node_type") != "record":
                    continue
                record = Record(ds.copy(deep=True))
                if record.record_id in records:
                    raise ProjectError(f"Duplicate record id in file: {record.record_id}")
                records[record.record_id] = record
    order = _loads(attrs.get("sample_order"), [])
    project.samples = {n: samples[n] for n in order if n in samples}
    project.samples.update({n: s for n, s in samples.items() if n not in project.samples})
    rorder = _loads(attrs.get("record_order"), [])
    project.records = {i: records[i] for i in rorder if i in records}
    project.records.update({i: r for i, r in records.items() if i not in project.records})
    project.file_path = Path(file_path) if file_path is not None else None
    project.dirty = False
    return project


# ============================================================
# 文件
# ============================================================
def save_project(project: Project, path=None) -> Path:
    """
    保存项目。先写同目录下的临时文件再替换，保存中断时原文件不受影响。
    不给 path 时保存到 project.file_path；扩展名不是 .nc 时自动加上。
    """
    target = Path(path if path is not None else project.file_path or "")
    if not str(target) or target == Path("."):
        raise ProjectError("No file path given for saving the project.")
    target = target.expanduser()
    if target.suffix.lower() != SUFFIX:
        target = target.with_name(target.name + SUFFIX)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.saving")
    tree = project_to_datatree(project)
    try:
        tree.to_netcdf(temporary, engine=ENGINE)
        os.replace(temporary, target)
    except Exception as exc:
        temporary.unlink(missing_ok=True)
        raise ProjectError(f"Could not save project to {target}: {exc}") from exc
    project.file_path = target
    project.dirty = False
    return target


def load_project(path) -> Project:
    """打开项目文件，把全部数据读入内存后关闭文件。"""
    path = Path(path).expanduser()
    if not path.is_file():
        raise ProjectError(f"Project file not found: {path}")
    try:
        tree = xr.load_datatree(path, engine=ENGINE)
    except Exception as exc:
        raise ProjectError(f"Could not open project {path}: {exc}") from exc
    return datatree_to_project(tree, file_path=path)
