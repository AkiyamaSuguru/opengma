# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""测试用的模拟数据：XPS、Raman、XRD 的标准数据结构，以及仪器导出文件。"""
import logging

import matplotlib

matplotlib.use("Agg")
# 测试环境可能没有 Times New Roman，不输出找不到字体的提示
logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pytest  # noqa: E402

RNG = np.random.default_rng(0)


def gauss(x, center, fwhm, height):
    return height * np.exp(-4 * np.log(2) * (x - center) ** 2 / fwhm**2)


def fitted_spectrum(x_col, x, components, base, step):
    """拟合谱：Shirley 式背景 + 高斯分峰；分峰列包含背景（absolute）。"""
    nets = {name: gauss(x, *params) for name, params in components.items()}
    net = sum(nets.values())
    order = np.argsort(x)
    cumulative = np.cumsum(net[order])
    cumulative /= cumulative[-1]
    background = np.empty_like(x)
    background[order] = base + step * cumulative
    fit = background + net
    data = {x_col: x, "Intensity": fit + RNG.normal(0, 0.02 * net.max(), x.size), "Fitting Curve": fit}
    data.update({name: background + values for name, values in nets.items()})
    data["Background"] = background
    return pd.DataFrame(data)


def line_spectrum(x_col, x, peaks, base):
    y = np.full(x.size, float(base))
    for center, fwhm, height in peaks:
        y += gauss(x, center, fwhm, height)
    y += RNG.normal(0, 0.01 * max(h for *_, h in peaks), x.size)
    return pd.DataFrame({x_col: x, "Intensity": y})


# ============================================================
# XPS
# ============================================================
@pytest.fixture
def c1s():
    be = np.round(np.arange(280, 292, 0.05), 2)[::-1]
    return fitted_spectrum(
        "Binding Energy (eV)", be,
        {"C-Si": (283.3, 1.0, 8000), "C-C": (284.8, 1.3, 3000)}, 500, 2500,
    )


@pytest.fixture
def si2p():
    be = np.round(np.arange(96, 108, 0.05), 2)[::-1]
    return fitted_spectrum(
        "Binding Energy (eV)", be,
        {"Si-C": (100.4, 1.1, 6000), "Si-O": (102.6, 1.6, 1200)}, 300, 1200,
    )


@pytest.fixture
def f1s_raw():
    be = np.round(np.arange(680, 692, 0.05), 2)[::-1]
    return line_spectrum("Binding Energy (eV)", be, [(685.2, 1.8, 4000)], 800)


@pytest.fixture
def surveys():
    be = np.arange(0.0, 1200.0, 1.0)[::-1]
    return {
        "As-deposited": line_spectrum("Binding Energy (eV)", be, [(101, 3, 9000), (284.8, 3, 12000)], 2000),
        "Corroded": line_spectrum("Binding Energy (eV)", be, [(284.8, 3, 8000), (685, 3, 15000)], 2000),
    }


# ============================================================
# Raman
# ============================================================
@pytest.fixture
def raman_spectra():
    shift = np.arange(100.0, 3200.0, 2.0)
    return {
        "As-deposited": line_spectrum("Raman Shift (cm-1)", shift, [(796, 8, 5000), (972, 12, 1500)], 300),
        "Corroded": line_spectrum(
            "Raman Shift (cm-1)", shift, [(1350, 60, 3000), (1585, 40, 4000), (2700, 80, 1200)], 300,
        ),
    }


@pytest.fixture
def raman_fit():
    shift = np.arange(1000.0, 1800.0, 2.0)
    return fitted_spectrum(
        "Raman Shift (cm-1)", shift, {"D": (1350, 60, 3000), "G": (1585, 40, 4000)}, 200, 100,
    )


# ============================================================
# XRD
# ============================================================
@pytest.fixture
def xrd_patterns():
    two_theta = np.round(np.arange(10.0, 90.0, 0.02), 2)
    sic = [(35.6, 0.3, 9000), (41.4, 0.3, 1500), (60.0, 0.3, 4000), (71.8, 0.3, 3000)]
    return {
        "As-deposited": line_spectrum("2Theta (deg)", two_theta, sic, 200),
        "Corroded": line_spectrum("2Theta (deg)", two_theta, sic + [(26.5, 0.4, 2500)], 200),
    }


# ============================================================
# 仪器导出文件
# ============================================================
@pytest.fixture
def avantage_files(tmp_path, c1s, surveys):
    """Avantage 导出的 Excel：15 行说明、表头、第二列为空列。"""
    openpyxl = pytest.importorskip("openpyxl")

    def export(name, df, header):
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        for i in range(15):
            sheet.append([f"Avantage header line {i}"])
        sheet.append(header)
        for row in df.itertuples(index=False):
            sheet.append([row[0], None, *row[1:]])
        path = tmp_path / name
        workbook.save(path)
        return path

    element_header = ["Binding Energy (E)", None, "Counts / s", "Envelope", "C1s A", "C1s B", "Backgnd."]
    raw = c1s[["Binding Energy (eV)", "Intensity"]]
    return {
        "survey": export("survey.xlsx", surveys["As-deposited"], ["Binding Energy (E)", None, "Counts / s"]),
        "element": export("C1s.xlsx", c1s, element_header),
        "element_raw": export("C1s_raw.xlsx", raw, ["Binding Energy (E)", None, "Counts / s"]),
    }


@pytest.fixture
def horiba_file(tmp_path):
    lines = ["#Acq. time (s)=\t10", "#Laser (nm)=\t532.17", "#Objective=\tx50"]
    lines += [f"{x:.2f}\t{100 + x / 10:.1f}" for x in np.arange(1000.0, 1010.0, 1.0)]
    path = tmp_path / "raman.txt"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


@pytest.fixture
def bruker_file(tmp_path):
    lines = [
        "; exported by DIFFRAC",
        "[Measurement Conditions]",
        "Sample ID = SiC coating",
        "Scan Time = 0.1 ; seconds",
        "[Drive]",
        "Name = Theta",
        "[Data]",
        "Angle, PSD,",
        "10.0000, 253,",
        "10.0200, 260,",
        "10.0400, 248,",
    ]
    path = tmp_path / "xrd.txt"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


@pytest.fixture(autouse=True)
def close_figures():
    yield
    plt.close("all")
