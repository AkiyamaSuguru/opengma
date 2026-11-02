# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
生成一个演示项目（模拟数据），用来在导入对话框完成（P3）之前试用界面：项目总览、保存、重新打开。

运行（在仓库根目录）：
    uv run python scripts/ui_p2/demo_project.py              # 写到 scripts/ui_p2/演示项目.nc
    uv run python scripts/ui_p2/demo_project.py 路径.nc

数据都是计算出来的模拟谱，不是真实测量结果。其中有意放了一条清洗记录和一处分峰名不一致，
用来查看“数据检查”。
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

from GMA.CM.common.data import BG_COL, FIT_COL, INTENSITY_COL
from GMA.project import CleanNote, Project, Record, save_project
from GMA.project.model import METHODS

RNG = np.random.default_rng(11)
SAMPLES = {
    "B1_SiC_1100℃": {"沉积温度": "1100 ℃", "状态": "沉积态"},
    "B2_SiC_1200℃": {"沉积温度": "1200 ℃", "状态": "沉积态"},
    "B3_SiC_腐蚀后": {"沉积温度": "1100 ℃", "状态": "FLiNaK 700 ℃ 100 h"},
}


def gauss(x, center, fwhm, height):
    return height * np.exp(-4 * np.log(2) * (x - center) ** 2 / fwhm ** 2)


def xps_c1s(shift=0.0, names=("C-Si", "C-C", "C-O")):
    be = np.round(np.arange(292.0, 279.95, -0.05), 2)
    bg = 600 + 2600 / (1 + np.exp(-(be - 284.4 - shift) / 0.9))
    comps = {names[0]: gauss(be, 283.3 + shift, 1.0, 8000), names[1]: gauss(be, 284.8 + shift, 1.3, 3000),
             names[2]: gauss(be, 286.4 + shift, 1.6, 800)}
    fit = bg + sum(comps.values())
    data = {METHODS["XPS"].x_column: be, INTENSITY_COL: fit + RNG.normal(0, 90, be.size), FIT_COL: fit}
    data.update({k: bg + v for k, v in comps.items()})
    data[BG_COL] = bg
    return pd.DataFrame(data)


def xps_survey():
    be = np.arange(1100.0, -0.1, -1.0)
    y = 2000 + 8 * be + gauss(be, 284.8, 3, 9000) + gauss(be, 531.0, 3, 15000) + gauss(be, 100.5, 3, 7000)
    return pd.DataFrame({METHODS["XPS"].x_column: be, INTENSITY_COL: y + RNG.normal(0, 80, be.size)})


def raman(ratio=1.0):
    shift = np.arange(1000.0, 1800.0, 1.0)
    bg = 200 + 0.05 * (shift - 1000)
    d, g = gauss(shift, 1350, 60, 900 * ratio), gauss(shift, 1585, 45, 1000)
    fit = bg + d + g
    return pd.DataFrame({METHODS["Raman"].x_column: shift, INTENSITY_COL: fit + RNG.normal(0, 15, shift.size),
                         FIT_COL: fit, "D": bg + d, "G": bg + g, BG_COL: bg})


def xrd(scale=1.0):
    tt = np.round(np.arange(10.0, 90.0, 0.02), 2)
    y = 300 + 800 * np.exp(-(tt - 10) / 8)
    for center, height in ((26.5, 4000), (35.6, 10000), (41.4, 2000), (60.0, 4500), (71.8, 3400)):
        y = y + gauss(tt, center, 0.25, height * scale)
    return pd.DataFrame({METHODS["XRD"].x_column: tt, INTENSITY_COL: y + RNG.normal(0, 40, tt.size)})


def build() -> Project:
    project = Project("演示项目")
    for name, info in SAMPLES.items():
        project.add_sample(name, info)
    for i, sample in enumerate(SAMPLES):
        # B3 的分峰名与另外两个不同，“数据检查”中会提示
        names = ("C-Si", "C-C/C-H", "C-O") if i == 2 else ("C-Si", "C-C", "C-O")
        notes = [CleanNote("dropped_rows", {"rows": [1205, 1206], "count": 2})] if i == 2 else []
        project.add_record(Record.from_dataframe(xps_c1s(0.1 * i, names), "XPS", "C1s", sample,
                                                 kind="element", clean_notes=notes))
        project.add_record(Record.from_dataframe(xps_survey(), "XPS", "Survey", sample, kind="survey"))
        project.add_record(Record.from_dataframe(xrd(1 - 0.2 * i), "XRD", "XRD", sample))
        if i < 2:
            project.add_record(Record.from_dataframe(raman(1 + 0.3 * i), "Raman", "Raman", sample))
    return project


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "演示项目.nc"
    print("写入", save_project(build(), target))
