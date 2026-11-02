# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
打包后的自检：环境变量 OPENGMA_SMOKE_TEST 指定一个结果文件时，界面启动到启动器后运行下面的检查，
把结果写成 JSON，然后退出。GitHub Actions 打包后在三个系统上各运行一次（scripts/build_app.py smoke），
确认打包进程序的 Python 和依赖都能用，不依赖电脑上安装的 Python。

检查只用临时文件夹，不碰用户的设置和项目（运行时另外用 OPENGMA_HOME 指向临时文件夹）。
"""
from __future__ import annotations

import io
import json
import os
import platform
import sys
import tempfile
import traceback
from pathlib import Path

SMOKE_ENV = "OPENGMA_SMOKE_TEST"

# 一个很小的 Quick K-P VACANCY.txt（格式与 TRIM 输出相同，数值取自 tests/data/srim 中的合成数据）
_VACANCY = """\
 Ion    = Ar   Energy = 2000 keV
============= TARGET MATERIAL ======================================
Layer  1 : SiC
Layer Width =     4.E+02 A ;
  Layer # 1- Density = 9.643E22 atoms/cm3 = 3.21 g/cm3
  Layer # 1- Si = 50  Atomic Percent = 70.04  Mass Percent
  Layer # 1-  C = 50  Atomic Percent = 29.96  Mass Percent
====================================================================
 Total Ions calculated =10000.00
==========================================================
   TARGET     VACANCIES     VACANCIES
   DEPTH         by            by
   (Ang.)       IONS         RECOILS
-----------  -----------  ------------
100000.E-03  1261.73E-05  9250.38E-05
200000.E-03  1264.79E-05  9251.74E-05
300000.E-03  1269.40E-05  9254.77E-05
400000.E-03  1275.53E-05  9260.15E-05
"""


def requested() -> Path | None:
    """自检结果文件的路径；没有要求自检时为 None。"""
    value = os.environ.get(SMOKE_ENV)
    return Path(value) if value else None


def run_checks() -> dict:
    """依次检查项目文件、Excel、出版图、SRIM 和熔盐计算，返回结果（不抛出异常）。"""
    result = {
        "python": sys.version.split()[0],
        "executable": sys.executable,
        "prefix": sys.prefix,
        "platform": platform.platform(),
        "embedded": os.environ.get("FLET_PLATFORM"),
        "numpy": _location("numpy"),   # 依赖从哪里导入：打包的程序中应在程序自己的文件夹里
        "checks": {},
    }
    with tempfile.TemporaryDirectory(prefix="opengma-smoke-") as folder:
        folder = Path(folder)
        for name, check in (("project", _project), ("excel", _excel), ("figure", _figure), ("srim", _srim),
                            ("salt", _salt)):
            try:
                check(folder)
                result["checks"][name] = "ok"
            except Exception as exc:  # noqa: BLE001 - 每项检查的失败都记下来，继续下一项
                result["checks"][name] = f"{type(exc).__name__}: {exc}"
                result.setdefault("tracebacks", {})[name] = traceback.format_exc()
    result["ok"] = all(v == "ok" for v in result["checks"].values())
    return result


def _location(module: str) -> str:
    try:
        return str(Path(__import__(module).__file__).parent)
    except Exception as exc:  # noqa: BLE001
        return f"{type(exc).__name__}: {exc}"


def write_result(path: Path, result: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


# ============================================================
# 各项检查
# ============================================================
def _frame():
    import numpy as np
    import pandas as pd
    x = np.linspace(10, 80, 200)
    return pd.DataFrame({"2Theta (deg)": x, "Intensity": 100 + 1000 * np.exp(-((x - 35.6) / 0.3) ** 2)})


def _project(folder: Path) -> None:
    """NetCDF 项目文件（xarray、h5netcdf、h5py）：保存后读回。"""
    from ...project import Project, Record, load_project, save_project
    project = Project("smoke")
    project.add_record(Record.from_dataframe(_frame(), "XRD", "XRD", "样品 A"))
    again = load_project(save_project(project, folder / "smoke.nc"))
    assert again.records_of(method="XRD")[0].point_count == 200


def _excel(folder: Path) -> None:
    """Excel 导出（openpyxl）和读取（pandas）。"""
    import pandas as pd

    from ...project import Project, Record, export_excel
    project = Project("smoke")
    record = Record.from_dataframe(_frame(), "XRD", "XRD", "S1")
    project.add_record(record)
    path = export_excel([record], folder / "smoke.xlsx", project=project)
    assert len(pd.read_excel(path, sheet_name=None)) == 2


def _figure(folder: Path) -> None:
    """出版图（matplotlib，附带的字体）：画一张 XRD 图并存为 PNG。"""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from ...CM.XRD import XRDPlotter
    from .figures import CJK_FONT, register_fonts
    register_fonts()
    fig, _ = XRDPlotter(font_family=["Liberation Serif", CJK_FONT]).plot_pattern_static(
        {"样品 A": _frame()}, references={"β-SiC": {"(111)": 35.6}}, show=False)
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=100)
    plt.close(fig)
    assert buffer.getvalue()[:4] == b"\x89PNG"


def _srim(folder: Path) -> None:
    """SRIM：读取 VACANCY.txt 的内容，计算 dpa。"""
    from ...SC.SRIM import depth_profile, parse_vacancy, peak
    profile = depth_profile(parse_vacancy(_VACANCY, "VACANCY.txt"), fluence=1e16)
    value, depth = peak(profile)
    assert 0 < value < 10 and depth > 0


def _salt(folder: Path) -> None:
    """熔盐配比：FLiNaK 的质量。"""
    from ...SC.Salts import MASS, PRESETS, salt_masses
    table = salt_masses(PRESETS["FLiNaK"], total_mass=100)
    assert abs(table[MASS].sum() - 100) < 1e-6
