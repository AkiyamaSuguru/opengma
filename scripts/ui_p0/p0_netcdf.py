# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
P0-4：含中文名称的 xarray DataTree 能否用 h5netcdf 写入 NetCDF-4 并原样读回。

运行（在仓库根目录）：
    uv run --with xarray --with "h5netcdf[h5py]" python scripts/ui_p0/p0_netcdf.py

只在终端输出结果，最后一行是“全部通过”或失败的项目。
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import numpy as np
import xarray as xr

sys.path.insert(0, str(Path(__file__).parent))
from _common import xps_c1s_frame  # noqa: E402

SAMPLES = ["B1_SiC_1100℃", "样品 2（腐蚀后）", "PyC-α 辐照"]
METADATA = {"仪器": "ESCALAB Xi+", "通能": "30 eV", "nested": {"a": 1, "b": [1, 2, 3]}}


def record(df, sample, name):
    components = [c for c in df.columns if c not in ("Binding Energy (eV)", "Intensity", "Fitting Curve", "Background")]
    ds = xr.Dataset(
        data_vars={
            "intensity": ("point", df["Intensity"].to_numpy()),
            "fitting_curve": ("point", df["Fitting Curve"].to_numpy()),
            "background": ("point", df["Background"].to_numpy()),
            "component_intensity": (("component", "point"), df[components].to_numpy().T),
        },
        coords={"binding_energy": ("point", df["Binding Energy (eV)"].to_numpy()),
                "component": np.asarray(components + [], dtype=str)},
        attrs={"method": "XPS", "name": name, "sample": sample, "备注": "中文属性值",
               "metadata": json.dumps(METADATA, ensure_ascii=False)},
    )
    return ds


def main():
    df = xps_c1s_frame()
    df = df.rename(columns={"C-O": "C–O（含氧）"})  # 分峰名中的中文和特殊字符
    tree = xr.DataTree(dataset=xr.Dataset(attrs={"schema_name": "opengma-project", "project_name": "测试项目"}))
    for i, sample in enumerate(SAMPLES):
        tree[f"/{sample}/XPS/C1s"] = record(df.iloc[: 200 + 10 * i], sample, "C1s")  # 不同点数
    failures = []
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "测试项目.nc"
        tree.to_netcdf(path, engine="h5netcdf")
        back = xr.load_datatree(path, engine="h5netcdf")
        print("写入：", path.name, f"{path.stat().st_size / 1024:.0f} KB")
        print("读回的节点：")
        for group in back.groups:
            print("  ", group)
        for i, sample in enumerate(SAMPLES):
            node = f"/{sample}/XPS/C1s"
            if node not in back.groups:
                failures.append(f"缺少节点 {node}")
                continue
            ds = back[node].to_dataset()
            if ds.sizes["point"] != 200 + 10 * i:
                failures.append(f"{node} 点数不对：{ds.sizes['point']}")
            if list(ds["component"].values) != ["C-Si", "C-C", "C–O（含氧）"]:
                failures.append(f"{node} 分峰名不对：{list(ds['component'].values)}")
            if ds.attrs.get("备注") != "中文属性值":
                failures.append(f"{node} 中文属性不对：{ds.attrs.get('备注')!r}")
            if json.loads(ds.attrs.get("metadata", "{}")) != METADATA:
                failures.append(f"{node} JSON 元数据不对")
            if not np.allclose(ds["intensity"].values, df["Intensity"].to_numpy()[: 200 + 10 * i]):
                failures.append(f"{node} 强度数据不对")
        if back.attrs.get("project_name") != "测试项目":
            failures.append("根节点属性不对")
    print("全部通过" if not failures else "失败：\n  " + "\n  ".join(failures))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
