# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
SC 模块：SRIM 的 dpa 和注入离子浓度、熔盐配比。

tests/data/srim 中是一次真实的 Quick K-P 计算（Xe 5.4 MeV → 石墨）的 VACANCY.txt、RANGE.txt；
Full Cascade、多层靶用下面手写的小文件（格式与 SRIM-2013 的输出相同）。
"""
from pathlib import Path

import numpy as np
import pytest

from GMA.SC.Salts import PRESETS, molar_mass, parse_formula, salt_masses
from GMA.SC.SRIM import (
    DENSITY,
    DPA,
    IONS,
    IONS_PERCENT,
    SRIMFileError,
    SRIMPlotter,
    average,
    centroid,
    depth_profile,
    parse_range,
    parse_vacancy,
    peak,
    read_range,
    read_vacancy,
)

DATA = Path(__file__).parent / "data" / "srim"

FULL_HEADER = """\
====== Synthetic two-layer run       =======
        SRIM-2013.00
==========================================
    Ion and Target VACANCY production
==========================================
 Ion    = He   Energy = 3000 keV
============= TARGET MATERIAL ======================================
Layer  1 : Coating
Layer Width =     2.E+02 A ;
  Layer # 1- Density = 8.000E22 atoms/cm3 = 3.0 g/cm3
  Layer # 1- Si = 50   Atomic Percent = 70.0 Mass Percent
  Layer # 1-  C = 50   Atomic Percent = 30.0 Mass Percent
Layer  2 : Substrate
Layer Width =     2.E+02 A ;
  Layer # 2- Density = 5.000E22 atoms/cm3 = 2.3 g/cm3
  Layer # 2- Si = 100  Atomic Percent = 100  Mass Percent
====================================================================
 Total Ions calculated =100.00
 Total Target Vacancies     = 3 /Ion
"""
FULL_VACANCY = FULL_HEADER + """
==========================================================
  Table Units are  >>>> Vacancies/(Angstrom-Ion)  <<<<
==========================================================
   TARGET
   DEPTH         He           Si            C           Si
   (Ang.)     Knock-Ons    Vacancies    Vacancies    Vacancies
-----------  -----------  -----------  -----------  -----------
100001.E-03  1.0000E-03  2.0000E-03  1.0000E-03  0.0000E+00
200001.E-03  1.0000E-03  4.0000E-03  2.0000E-03  0.0000E+00
300001.E-03  1.0000E-03  0.0000E+00  0.0000E+00  8.0000E-03
400001.E-03  1.0000E-03  0.0000E+00  0.0000E+00  1.0000E-02

 To convert to Energy Lost - multiply by Average Binding Energy =  0  eV/Vacancy
"""
FULL_RANGE = FULL_HEADER.replace("VACANCY production", "and final RECOIL ATOM Distributions") + """
=================================================================
  Table Distribution Units are >>>  (Atoms/cm3) / (Atoms/cm2)  <<<
=================================================================
   DEPTH         He         Si          C         Si
   (Ang.)       Ions     Tgt. Atoms  Tgt. Atoms  Tgt. Atoms
-----------  ----------  ----------  ----------  ----------
100001.E-03  0.0000E+00  1.0000E+04  1.0000E+04  0.0000E+00
200001.E-03  1.0000E+04  1.0000E+04  1.0000E+04  0.0000E+00
300001.E-03  5.0000E+04  0.0000E+00  0.0000E+00  2.0000E+04
400001.E-03  2.0000E+04  0.0000E+00  0.0000E+00  2.0000E+04
"""


# ============================================================
# SRIM：Quick K-P（真实文件）
# ============================================================
def test_quick_vacancy():
    v = read_vacancy(DATA / "VACANCY.txt")
    assert (v.mode, v.ion, v.energy, v.ions_calculated) == ("quick", "Xe", 5400.0, 30000.0)
    layer = v.layers[0]
    assert (layer.name, layer.width, layer.density, layer.mass_density, layer.elements) == \
        ("Layer 1", 20000.0, 10.79e22, 2.153, {"C": 100.0})
    assert len(v.depth) == 100 and v.bin_width == pytest.approx(200.0) and v.depth[-1] == pytest.approx(20000.0)
    assert list(v.columns) == ["Vacancies by ions", "Vacancies by recoils"]
    # 按表格积分的空位数与文件头的 Total Target Vacancies 一致
    assert v.vacancies_per_ion() == pytest.approx(v.reported_vacancies, rel=1e-3)
    assert v.interfaces() == [] and v.element_vacancies() == {}


def test_quick_range():
    r = read_range(DATA / "RANGE.txt")
    assert (r.mode, r.ion, r.energy) == ("quick", "Xe", 5400.0)
    assert (r.mean_range, r.straggling) == (16430.0, 1651.0)
    assert r.stopped_fraction() == pytest.approx((30000 - 137) / 30000, rel=1e-3)  # 137 个离子穿过了靶


def test_dpa_and_concentration_match_reference_scripts():
    """与 Damage.get_dpa、Concentration.get_concentration 的算法一致。"""
    v, r = read_vacancy(DATA / "VACANCY.txt"), read_range(DATA / "RANGE.txt")
    phi, n = 1e16, 10.79e22
    p = depth_profile(v, r, fluence=phi)
    table = v.frame()
    expected = phi * (table["Vacancies by ions"] + table["Vacancies by recoils"]) * 1e8 / n
    assert np.allclose(p[DPA], expected) and np.allclose(p[DENSITY], n)
    c = r.ions * phi
    assert np.allclose(p[IONS], c) and np.allclose(p[IONS_PERCENT], c / (c + n) * 100)
    assert np.allclose(p["Depth (nm)"], v.depth / 10)
    value, depth = peak(p)
    assert value == pytest.approx(10.649, rel=1e-3) and depth == pytest.approx(1480.0)
    assert centroid(p) == pytest.approx(r.mean_range / 10, rel=1e-3)  # 平均射程与文件头一致
    assert p.attrs["ion"] == "Xe" and p.attrs["fluence"] == phi
    # 原子密度可以改；只有 RANGE.txt 时只算浓度
    assert np.allclose(depth_profile(v, fluence=phi, densities=2 * n)[DPA], expected / 2)
    only = depth_profile(ions=r, fluence=phi)
    assert DPA not in only and IONS_PERCENT in only


def test_decimal_comma():
    """某些区域设置下 SRIM 用小数逗号。"""
    text = (DATA / "VACANCY.txt").read_text(encoding="latin-1")
    comma = parse_vacancy(text.replace(".E", ",E").replace("10.79E22", "10,79E22"))
    assert np.allclose(comma.vacancies, read_vacancy(DATA / "VACANCY.txt").vacancies)
    assert comma.layers[0].density == 10.79e22


# ============================================================
# SRIM：Full Cascade、多层靶
# ============================================================
def test_full_cascade_layers():
    v = parse_vacancy(FULL_VACANCY, "VACANCY.txt")
    assert v.mode == "full" and [layer.name for layer in v.layers] == ["Coating", "Substrate"]
    assert list(v.columns) == ["Knock-ons (He)", "Vacancies (Si, layer 1)", "Vacancies (C, layer 1)",
                               "Vacancies (Si, layer 2)"]
    assert v.elements == [("Si", 0), ("C", 0), ("Si", 1)]
    # 总空位是各元素空位之和，不加 Knock-Ons
    assert np.allclose(v.vacancies, [3e-3, 6e-3, 8e-3, 1e-2])
    assert v.interfaces() == [200.0] and v.layer_index().tolist() == [0, 0, 1, 1]
    p = depth_profile(v, fluence=1e18)
    assert np.allclose(p[DENSITY], [8e22, 8e22, 5e22, 5e22])
    assert np.allclose(p[DPA], [3.75, 7.5, 16.0, 20.0])
    assert np.allclose(p["dpa (Si)"], [2.5, 5.0, 16.0, 20.0]) and np.allclose(p["dpa (C)"], [1.25, 2.5, 0, 0])
    assert p.attrs["interfaces"] == [20.0]
    # 按层改原子密度：None 的层用文件中的值
    p2 = depth_profile(v, fluence=1e18, densities=[None, 1e23])
    assert np.allclose(p2[DPA], [3.75, 7.5, 8.0, 10.0])
    r = parse_range(FULL_RANGE)
    assert r.mode == "full" and next(iter(r.columns)) == "Ions (He)"
    both = depth_profile(v, r, fluence=1e18)
    assert np.allclose(both[IONS], [0, 1e22, 5e22, 2e22])


def test_profile_rules():
    v = parse_vacancy(FULL_VACANCY)
    for fluence in (0, -1, float("nan"), "abc"):
        with pytest.raises(ValueError, match="fluence"):
            depth_profile(v, fluence=fluence)
    with pytest.raises(ValueError, match="2 layer"):
        depth_profile(v, fluence=1e15, densities=[1e22])
    with pytest.raises(ValueError, match="same TRIM run"):  # 离子不同
        depth_profile(read_vacancy(DATA / "VACANCY.txt"), parse_range(FULL_RANGE), fluence=1e15)
    other = parse_range(FULL_RANGE.replace("400001.E-03", "500001.E-03"))
    with pytest.raises(ValueError, match="depth bins"):
        depth_profile(v, other, fluence=1e15)
    with pytest.raises(ValueError, match="VACANCY"):
        depth_profile(fluence=1e15)
    p = depth_profile(v, fluence=1e18)
    # 平均值：区间内的值看作常数，范围只覆盖区间的一部分时按长度计入
    assert average(p) == pytest.approx(np.mean([3.75, 7.5, 16.0, 20.0]))
    # SRIM 的深度比区间右端多 0.001 Å（100.001 Å），所以只核对到 1e-4
    assert average(p, start=5, end=15) == pytest.approx((3.75 + 7.5) / 2, rel=1e-4)
    assert average(p, start=15, end=25) == pytest.approx((7.5 + 16.0) / 2, rel=1e-4)
    with pytest.raises(ValueError, match="empty"):
        average(p, start=30, end=30)


def test_not_srim_files(tmp_path):
    with pytest.raises(SRIMFileError, match="no SRIM table"):
        parse_vacancy("hello\nworld\n")
    with pytest.raises(SRIMFileError, match="VACANCY"):  # RANGE.txt 当作 VACANCY.txt
        read_vacancy(DATA / "RANGE.txt")
    with pytest.raises(SRIMFileError, match="RANGE"):
        read_range(DATA / "VACANCY.txt")
    bad = tmp_path / "bad.txt"
    bad.write_text(FULL_VACANCY.replace("4.0000E-03  2.0000E-03", "4.0000E-03"), encoding="utf-8")
    with pytest.raises(SRIMFileError, match="Row 2"):
        read_vacancy(bad)
    with pytest.raises(SRIMFileError, match="ion and its energy"):
        parse_vacancy(FULL_VACANCY.replace(" Ion    = He   Energy = 3000 keV", ""))


def test_profile_figure(tmp_path):
    p = depth_profile(read_vacancy(DATA / "VACANCY.txt"), read_range(DATA / "RANGE.txt"), fluence=1e16)
    _, (ax, ax_ions) = SRIMPlotter(font_size=7).plot_profile_static(p, depth_unit="um", show=False,
                                                                    save_path=tmp_path / "dpa.png", dpi=80)
    assert ax.get_xlabel() == "Depth (μm)" and "Xe" in ax_ions.get_ylabel()
    assert (tmp_path / "dpa.png").read_bytes()[:4] == b"\x89PNG"
    _, ax = SRIMPlotter().plot_profile_static(depth_profile(parse_vacancy(FULL_VACANCY), fluence=1e15),
                                                elements=True, show=False)
    assert [line.get_label() for line in ax.get_lines()][:3] == ["dpa", "Si", "C"]
    with pytest.raises(ValueError, match="depth unit"):
        SRIMPlotter().plot_profile_static(p, depth_unit="mm", show=False)


# ============================================================
# 熔盐配比
# ============================================================
def test_flinak_matches_reference_script():
    """与 FLiNaKs 的结果相同：质量比 0.29211 : 0.11694 : 0.59095。"""
    t = salt_masses(PRESETS["FLiNaK"], total_mass=100.0)
    assert list(t["Salt"]) == ["LiF", "NaF", "KF"]
    assert np.allclose(t["Mass (g)"], [29.211, 11.694, 59.095], atol=1e-3)
    assert t["Mass (g)"].sum() == pytest.approx(100.0) and t["Mole fraction (mol%)"].sum() == pytest.approx(100.0)
    assert t["Molar mass (g/mol)"][0] == pytest.approx(6.94 + 18.998403162)


def test_molar_mass_and_formulas():
    assert molar_mass("LiF") == pytest.approx(25.938, abs=1e-3)
    assert molar_mass("BeF₂") == pytest.approx(molar_mass("BeF2")) == pytest.approx(47.009, abs=1e-3)
    assert molar_mass("MgCl2·6H2O") == pytest.approx(203.30, abs=0.01)
    assert parse_formula("Ca(NO3)2") == {"Ca": 1, "N": 2, "O": 6}
    assert parse_formula("K2[PtCl6]") == {"K": 2, "Pt": 1, "Cl": 6}
    for bad, message in (("", "empty"), ("Xx", "Unknown element"), ("(LiF", "Unbalanced"), ("lif", "Unexpected"),
                         ("LiF·", "Invalid"), ("7LiF", "isotopes"), ("⁷LiF", "isotopes")):
        with pytest.raises(ValueError, match=message):
            parse_formula(bad)


def test_salt_masses_rules():
    t = salt_masses([("LiF", 2), ("BeF2", 1)], 50, molar_masses={"LiF": 26.0})  # 比例自动归一化
    assert np.allclose(t["Mole fraction (mol%)"], [200 / 3, 100 / 3])
    assert t["Molar mass (g/mol)"][0] == 26.0 and t["Mass (g)"].sum() == pytest.approx(50)
    zero = salt_masses({"NaCl": 50, "KCl": 50, "MgCl2": 0}, 10)
    assert zero["Mass (g)"].iloc[-1] == 0
    for composition, mass, message in (({}, 1, "empty"), ({"LiF": 1}, 0, "total mass"),
                                       ({"LiF": -1}, 1, "mole fraction"), ({"LiF": 0}, 1, "add up to zero"),
                                       ([("LiF", 1), ("LiF", 2)], 1, "more than once"),
                                       ({"LiF": "x"}, 1, "must be a number")):
        with pytest.raises(ValueError, match=message):
            salt_masses(composition, mass)
