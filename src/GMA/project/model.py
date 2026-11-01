# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
项目的数据模型：Record（一条谱图）、Sample（样品）、Project（项目）。

一条数据在内存中是一个 xarray.Dataset，在项目文件中是 DataTree 的一个叶节点
/{样品}/{方法}/{名称}。读取、分析、绘图仍然使用 GMA 的标准 DataFrame：
Record.from_dataframe() 把标准 DataFrame 存进来，Record.to_dataframe() 原样取出。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from importlib import metadata as importlib_metadata
from uuid import uuid4

import numpy as np
import pandas as pd
import xarray as xr

from ..CM.common.axis import SpectrumAxis
from ..CM.common.data import BG_COL, FIT_COL, INTENSITY_COL, require_columns
from ..CM.Raman.schema import AXIS as RAMAN_AXIS
from ..CM.Raman.schema import SHIFT_COL
from ..CM.XPS.schema import AXIS as XPS_AXIS
from ..CM.XPS.schema import BE_COL
from ..CM.XRD.schema import AXIS as XRD_AXIS
from ..CM.XRD.schema import TWO_THETA_COL

RECORD_SCHEMA_VERSION = "1.0"
COMPONENT_MODES = ("absolute", "relative")


class ProjectError(ValueError):
    """项目数据不符合约定时抛出，信息中说明哪条数据、哪一步、为什么。"""


# ============================================================
# 表征方法
# ============================================================
@dataclass(frozen=True)
class MethodSpec:
    """一种表征方法在项目中的存储方式。"""

    name: str  # "XPS"
    x_column: str  # 标准 DataFrame 中的横轴列名，如 "Binding Energy (eV)"
    x_var: str  # Dataset 中的横轴坐标名，如 "binding_energy"
    x_unit: str
    kinds: tuple[str, ...]  # 这种方法的数据类型，第一个是默认值
    axis: SpectrumAxis


METHODS: dict[str, MethodSpec] = {
    "XPS": MethodSpec("XPS", BE_COL, "binding_energy", "eV", ("element", "survey"), XPS_AXIS),
    "Raman": MethodSpec("Raman", SHIFT_COL, "raman_shift", "cm-1", ("spectrum",), RAMAN_AXIS),
    "XRD": MethodSpec("XRD", TWO_THETA_COL, "two_theta", "deg", ("pattern",), XRD_AXIS),
}


def method_spec(method: str) -> MethodSpec:
    try:
        return METHODS[method]
    except KeyError:
        raise ProjectError(f"Unknown method {method!r}. Available methods: {list(METHODS)}") from None


def gma_version() -> str:
    try:
        return importlib_metadata.version("opengma")
    except importlib_metadata.PackageNotFoundError:
        return "unknown"


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


# ============================================================
# 清洗：只做不改变科学含义的整理，每一步都记下来
# ============================================================
@dataclass(frozen=True)
class CleanNote:
    """清洗记录中的一项。code 供程序判断，detail 保存具体信息，text() 给出中文说明。"""

    code: str  # dropped_rows / empty_component / duplicate_x / sorted
    detail: dict = field(default_factory=dict)

    def text(self) -> str:
        d = self.detail
        if self.code == "dropped_rows":
            rows = "、".join(str(r) for r in d.get("rows", [])[:10])
            more = "等" if d.get("count", 0) > 10 else ""
            return f"去除 {d.get('count', 0)} 行空值或非数值数据（数据第 {rows} 行{more}）"
        if self.code == "empty_component":
            return f"分峰列 {d.get('column')} 中没有数值，已忽略"
        if self.code == "duplicate_x":
            return f"横轴有 {d.get('count', 0)} 个重复的值，已保留"
        if self.code == "sorted":
            return "横轴不是单调的，已按横轴从小到大排列"
        return self.code

    def to_dict(self) -> dict:
        return {"code": self.code, "detail": self.detail}

    @classmethod
    def from_dict(cls, d: dict) -> CleanNote:
        return cls(code=str(d.get("code", "")), detail=dict(d.get("detail", {})))


def _component_names(df: pd.DataFrame, spec: MethodSpec, fitted: bool) -> list[str]:
    if not fitted:
        return []
    standard = {spec.x_column, INTENSITY_COL, FIT_COL, BG_COL}
    return [str(c) for c in df.columns if c not in standard]


def clean_frame(df: pd.DataFrame, method: str) -> tuple[pd.DataFrame, list[CleanNote]]:
    """
    整理一条谱图的标准 DataFrame，返回 (整理后的 DataFrame, 清洗记录)。

    - 所有列转成数值，必需列为空或不是数值的行去掉，并记下行号（从 1 开始，按原始顺序）；
    - 分峰列整列没有数值时忽略这一列；
    - 横轴有重复值时只提示，不删除；
    - 横轴从大到小时直接倒序；不单调时按横轴排序并记下来。
    列的顺序整理为：横轴、Intensity、[Fitting Curve、分峰…、Background]。
    """
    spec = method_spec(method)
    require_columns(df, [spec.x_column, INTENSITY_COL])
    has_fit, has_bg = FIT_COL in df.columns, BG_COL in df.columns
    if has_fit != has_bg:
        missing = FIT_COL if not has_fit else BG_COL
        raise ProjectError(f"Incomplete fitted spectrum: missing column {missing!r}.")
    fitted = has_fit and has_bg
    notes: list[CleanNote] = []

    data = df.reset_index(drop=True).apply(pd.to_numeric, errors="coerce")
    components = []
    for col in _component_names(df, spec, fitted):
        if data[col].notna().any():
            components.append(col)
        else:
            notes.append(CleanNote("empty_component", {"column": col}))
    required = [spec.x_column, INTENSITY_COL] + ([FIT_COL, BG_COL] if fitted else [])
    bad = data[required].isna().any(axis=1).to_numpy()
    if bad.any():
        rows = (np.flatnonzero(bad) + 1).tolist()
        notes.append(CleanNote("dropped_rows", {"count": len(rows), "rows": rows}))
    columns = [spec.x_column, INTENSITY_COL] + ([FIT_COL, *components, BG_COL] if fitted else [])
    data = data.loc[~bad, columns].reset_index(drop=True)
    if data.empty:
        raise ProjectError("No valid numeric data after cleaning.")

    x = data[spec.x_column].to_numpy(dtype=float)
    duplicates = len(x) - len(np.unique(x))
    if duplicates:
        notes.append(CleanNote("duplicate_x", {"count": int(duplicates)}))
    diff = np.diff(x)
    if len(diff) and (diff < 0).all():
        data = data.iloc[::-1].reset_index(drop=True)
    elif (diff < 0).any():
        data = data.sort_values(spec.x_column, kind="stable", ignore_index=True)
        notes.append(CleanNote("sorted"))
    return data, notes


# ============================================================
# Record：一条谱图
# ============================================================
def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _loads(text, default):
    if not text:
        return default
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return default


@dataclass
class Record:
    """
    一条谱图。数据保存在 data（xarray.Dataset）中：

    - 坐标：横轴（XPS 为 binding_energy，Raman 为 raman_shift，XRD 为 two_theta）、component（分峰名）；
    - 变量：intensity；拟合谱另有 fitting_curve、background、component_intensity（component × point）；
    - 属性：方法、类型、名称、样品、来源、清洗记录、仪器元数据（JSON）等。
    """

    data: xr.Dataset

    # ---------- 创建 ----------
    @classmethod
    def from_dataframe(
            cls,
            df: pd.DataFrame,
            method: str,
            name: str,
            sample: str,
            *,
            kind: str | None = None,
            component_mode: str = "absolute",
            metadata: dict | None = None,
            source: dict | None = None,
            clean_notes: list[CleanNote] | None = None,
            record_id: str | None = None,
    ) -> Record:
        """
        从标准 DataFrame 创建。df 会先经过 clean_frame()，清洗记录与传入的 clean_notes 合并。

        source 可以包含 path、file、sha256、reader、imported_at，用于追溯来源。
        """
        spec = method_spec(method)
        kind = kind or spec.kinds[0]
        if kind not in spec.kinds:
            raise ProjectError(f"Unknown kind {kind!r} for {method}. Available kinds: {list(spec.kinds)}")
        if component_mode not in COMPONENT_MODES:
            raise ProjectError(f"component_mode must be one of {COMPONENT_MODES}, got {component_mode!r}.")
        name, sample = _check_name(name, "name"), _check_name(sample, "sample")
        clean, notes = clean_frame(df, method)
        notes = list(clean_notes or []) + notes
        fitted = FIT_COL in clean.columns
        components = _component_names(clean, spec, fitted)

        coords: dict = {spec.x_var: ("point", clean[spec.x_column].to_numpy(dtype=float))}
        data_vars: dict = {"intensity": ("point", clean[INTENSITY_COL].to_numpy(dtype=float))}
        if fitted:
            data_vars["fitting_curve"] = ("point", clean[FIT_COL].to_numpy(dtype=float))
            data_vars["background"] = ("point", clean[BG_COL].to_numpy(dtype=float))
            if components:
                coords["component"] = np.asarray(components, dtype=str)
                data_vars["component_intensity"] = (
                    ("component", "point"), clean[components].to_numpy(dtype=float).T,
                )
        source = dict(source or {})
        attrs = {
            "node_type": "record",
            "record_schema_version": RECORD_SCHEMA_VERSION,
            "record_id": record_id or uuid4().hex,
            "method": method,
            "kind": kind,
            "name": name,
            "sample": sample,
            "fitted": int(fitted),
            "component_mode": component_mode,
            "source_path": str(source.get("path", "")),
            "source_file": str(source.get("file", "")),
            "source_sha256": str(source.get("sha256", "")),
            "reader": str(source.get("reader", "")),
            "imported_at": str(source.get("imported_at", "")) or now_iso(),
            "gma_version": gma_version(),
            "clean_report": _json([n.to_dict() for n in notes]),
            "metadata": _json(metadata or {}),
            "notes": "",
            "derived_from": str(source.get("derived_from", "")),
        }
        ds = xr.Dataset(data_vars=data_vars, coords=coords, attrs=attrs)
        ds[spec.x_var].attrs.update(units=spec.x_unit, long_name=spec.x_column)
        return cls(ds)

    # ---------- 属性 ----------
    @property
    def spec(self) -> MethodSpec:
        return method_spec(self.method)

    @property
    def record_id(self) -> str:
        return str(self.data.attrs["record_id"])

    @property
    def method(self) -> str:
        return str(self.data.attrs["method"])

    @property
    def kind(self) -> str:
        return str(self.data.attrs["kind"])

    @property
    def name(self) -> str:
        return str(self.data.attrs["name"])

    @name.setter
    def name(self, value: str) -> None:
        self.data.attrs["name"] = _check_name(value, "name")

    @property
    def sample(self) -> str:
        return str(self.data.attrs["sample"])

    @sample.setter
    def sample(self, value: str) -> None:
        self.data.attrs["sample"] = _check_name(value, "sample")

    @property
    def fitted(self) -> bool:
        return bool(int(self.data.attrs.get("fitted", 0)))

    @property
    def components(self) -> list[str]:
        if "component" not in self.data.coords:
            return []
        return [str(v) for v in self.data["component"].values.tolist()]

    @property
    def component_mode(self) -> str:
        return str(self.data.attrs.get("component_mode", "absolute"))

    @component_mode.setter
    def component_mode(self, value: str) -> None:
        if value not in COMPONENT_MODES:
            raise ProjectError(f"component_mode must be one of {COMPONENT_MODES}, got {value!r}.")
        self.data.attrs["component_mode"] = value

    @property
    def point_count(self) -> int:
        return int(self.data.sizes["point"])

    @property
    def metadata(self) -> dict:
        return _loads(self.data.attrs.get("metadata"), {})

    @property
    def clean_notes(self) -> list[CleanNote]:
        return [CleanNote.from_dict(d) for d in _loads(self.data.attrs.get("clean_report"), [])]

    @property
    def source(self) -> dict:
        a = self.data.attrs
        return {
            "path": a.get("source_path", ""), "file": a.get("source_file", ""),
            "sha256": a.get("source_sha256", ""), "reader": a.get("reader", ""),
            "imported_at": a.get("imported_at", ""), "gma_version": a.get("gma_version", ""),
            "derived_from": a.get("derived_from", ""),
        }

    @property
    def notes(self) -> str:
        return str(self.data.attrs.get("notes", ""))

    @notes.setter
    def notes(self, value: str) -> None:
        self.data.attrs["notes"] = str(value)

    @property
    def x(self) -> np.ndarray:
        return self.data[self.spec.x_var].values

    # ---------- 修改 ----------
    def rename_components(self, names) -> None:
        """按原来的顺序重命名分峰。名称不能为空、不能重复，也不能与标准列名相同。"""
        names = [str(n).strip() for n in names]
        if len(names) != len(self.components):
            raise ProjectError(
                f"{self.name}: expected {len(self.components)} component names, got {len(names)}."
            )
        reserved = {self.spec.x_column, INTENSITY_COL, FIT_COL, BG_COL}
        if any(not n for n in names):
            raise ProjectError(f"{self.name}: component names cannot be empty.")
        if len(set(names)) != len(names):
            raise ProjectError(f"{self.name}: component names must be unique.")
        clash = [n for n in names if n in reserved]
        if clash:
            raise ProjectError(f"{self.name}: component names cannot be standard column names: {clash}")
        if names:
            self.data = self.data.assign_coords(component=np.asarray(names, dtype=str))

    # ---------- 取出 ----------
    def to_dataframe(self, include_components: bool = True) -> pd.DataFrame:
        """返回标准 DataFrame：横轴、Intensity、[Fitting Curve、分峰…、Background]。"""
        spec = self.spec
        out = {spec.x_column: self.data[spec.x_var].values.astype(float),
               INTENSITY_COL: self.data["intensity"].values.astype(float)}
        if self.fitted:
            out[FIT_COL] = self.data["fitting_curve"].values.astype(float)
            if include_components:
                for i, comp in enumerate(self.components):
                    out[comp] = self.data["component_intensity"].values[i].astype(float)
            out[BG_COL] = self.data["background"].values.astype(float)
        return pd.DataFrame(out)

    def copy(self, *, new_id: bool = False) -> Record:
        record = Record(self.data.copy(deep=True))
        if new_id:
            record.data.attrs["record_id"] = uuid4().hex
        return record


def _check_name(value, what: str) -> str:
    text = str(value).strip()
    if not text:
        raise ProjectError(f"{what} cannot be empty.")
    return text


# ============================================================
# Sample 与 Project
# ============================================================
@dataclass
class Sample:
    """样品：名称和用户自己定义的样品信息（字段名 → 文字）。"""

    name: str
    info: dict[str, str] = field(default_factory=dict)


CONFLICT_ACTIONS = ("copy", "replace", "skip")


@dataclass
class Project:
    """
    一个项目：样品、谱图，以及保存在项目中的用户表格和界面状态。

    - sample_fields：样品信息的字段名及顺序；
    - peak_tables：峰位表，{表名: [{"label": 标签, "position": 位置}, ...]}；
    - reference_phases：XRD 参考物相表，[{"phase": 物相名, "hkl": 晶面指数, "two_theta": 2θ}, ...]；
    - ui_state：界面状态（打开的标签、各标签的设置），由界面自己定义内容。
    这些表都由用户填写，GMA 不内置任何峰位或物相。
    """

    name: str = "未命名项目"
    samples: dict[str, Sample] = field(default_factory=dict)
    records: dict[str, Record] = field(default_factory=dict)
    sample_fields: list[str] = field(default_factory=list)
    peak_tables: dict[str, list[dict]] = field(default_factory=dict)
    reference_phases: list[dict] = field(default_factory=list)
    ui_state: dict = field(default_factory=dict)
    created_at: str = field(default_factory=now_iso)
    file_path: object = None  # pathlib.Path | None
    dirty: bool = False

    # ---------- 样品 ----------
    def add_sample(self, name: str, info: dict | None = None) -> Sample:
        name = _check_name(name, "sample")
        sample = self.samples.get(name)
        if sample is None:
            sample = Sample(name)
            self.samples[name] = sample
            self.dirty = True
        for key, value in (info or {}).items():
            self.set_sample_info(name, key, value)
        return sample

    def add_field(self, field_name: str) -> str:
        """添加一个样品信息字段（各样品的值先留空）；已有同名字段时不重复添加。"""
        field_name = _check_name(field_name, "field")
        if field_name not in self.sample_fields:
            self.sample_fields.append(field_name)
            self.dirty = True
        return field_name

    def set_sample_info(self, sample: str, field_name: str, value) -> None:
        field_name = self.add_field(field_name)
        self.add_sample(sample).info[field_name] = "" if value is None else str(value)
        self.dirty = True

    def rename_sample(self, old: str, new: str) -> None:
        new = _check_name(new, "sample")
        if old not in self.samples:
            raise ProjectError(f"Sample not found: {old!r}")
        if new == old:
            return
        if new in self.samples:
            raise ProjectError(f"Sample already exists: {new!r}")
        self.samples = {(new if k == old else k): v for k, v in self.samples.items()}
        self.samples[new].name = new
        for record in self.records_of(sample=old):
            record.sample = new
        self.dirty = True

    def remove_sample(self, name: str) -> list[Record]:
        """移除样品及其中的谱图（只是从项目中移除，不删除原始文件）。"""
        if name not in self.samples:
            raise ProjectError(f"Sample not found: {name!r}")
        removed = [self.records.pop(r.record_id) for r in self.records_of(sample=name)]
        del self.samples[name]
        self.dirty = True
        return removed

    # ---------- 谱图 ----------
    def unique_name(self, sample: str, method: str, name: str) -> str:
        """同一样品、同一方法下的名称不能重复，重复时加序号：C1s (2)。"""
        used = {r.name for r in self.records_of(method=method, sample=sample)}
        if name not in used:
            return name
        i = 2
        while f"{name} ({i})" in used:
            i += 1
        return f"{name} ({i})"

    def add_record(self, record: Record, on_conflict: str = "copy") -> Record | None:
        """
        加入一条谱图。同一样品、同一方法下已有同名谱图时：
        copy 改名为“名称 (2)”后加入；replace 替换原来的；skip 不加入并返回 None。
        """
        if on_conflict not in CONFLICT_ACTIONS:
            raise ProjectError(f"on_conflict must be one of {CONFLICT_ACTIONS}, got {on_conflict!r}.")
        if record.record_id in self.records:
            raise ProjectError(f"Record id already exists: {record.record_id}")
        existing = self.find_by_name(record.sample, record.method, record.name)
        if existing is not None:
            if on_conflict == "skip":
                return None
            if on_conflict == "replace":
                # 放在原来的位置，保持列表顺序
                self.records = {
                    (record.record_id if k == existing.record_id else k): (record if k == existing.record_id else v)
                    for k, v in self.records.items()
                }
                self.dirty = True
                return record
            record.name = self.unique_name(record.sample, record.method, record.name)
        self.add_sample(record.sample)
        self.records[record.record_id] = record
        self.dirty = True
        return record

    def find_by_name(self, sample: str, method: str, name: str) -> Record | None:
        for record in self.records.values():
            if record.sample == sample and record.method == method and record.name == name:
                return record
        return None

    def get(self, sample: str, method: str, name: str) -> Record:
        record = self.find_by_name(sample, method, name)
        if record is None:
            raise ProjectError(f"Record not found: /{sample}/{method}/{name}")
        return record

    def record(self, record_id: str) -> Record:
        try:
            return self.records[record_id]
        except KeyError:
            raise ProjectError(f"Record not found: {record_id}") from None

    def remove_record(self, record_id: str) -> Record:
        record = self.record(record_id)
        del self.records[record_id]
        self.dirty = True
        return record

    def rename_record(self, record_id: str, new_name: str) -> None:
        record = self.record(record_id)
        new_name = _check_name(new_name, "name")
        other = self.find_by_name(record.sample, record.method, new_name)
        if other is not None and other is not record:
            raise ProjectError(f"Name already used in /{record.sample}/{record.method}: {new_name!r}")
        record.name = new_name
        self.dirty = True

    def move_record(self, record_id: str, sample: str) -> None:
        """把谱图移到另一个样品下（不存在时新建样品）；同名时自动加序号。"""
        record = self.record(record_id)
        sample = _check_name(sample, "sample")
        if sample == record.sample:
            return
        self.add_sample(sample)
        record.name = self.unique_name(sample, record.method, record.name)
        record.sample = sample
        self.dirty = True

    def records_of(self, method: str | None = None, sample: str | None = None) -> list[Record]:
        return [r for r in self.records.values()
                if (method is None or r.method == method) and (sample is None or r.sample == sample)]

    def methods(self) -> list[str]:
        """项目中已有数据的方法，按 METHODS 的顺序。"""
        present = {r.method for r in self.records.values()}
        return [m for m in METHODS if m in present]

    def counts(self) -> dict[str, dict[str, int]]:
        """{样品: {方法: 谱图数}}，用于项目总览。"""
        out = {name: {} for name in self.samples}
        for r in self.records.values():
            out.setdefault(r.sample, {})
            out[r.sample][r.method] = out[r.sample].get(r.method, 0) + 1
        return out

    def __len__(self) -> int:
        return len(self.records)
