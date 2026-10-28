# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""读取模块：各 reader 返回标准数据结构，loader 检查并报出不符合约定的数据。"""
import pandas as pd
import pytest

from GMA import RamanLoader, XPSLoader, XRDLoader


# ============================================================
# XPS
# ============================================================
def test_xps_survey(avantage_files):
    df = XPSLoader("Avantage").read_survey(avantage_files["survey"])
    assert df.columns.tolist() == ["Binding Energy (eV)", "Intensity"]
    assert len(df) > 100


def test_xps_element_with_peak_names(avantage_files):
    df = XPSLoader("Avantage").read_element(avantage_files["element"], peaks=["C-Si", "C-C"])
    assert df.columns.tolist() == [
        "Binding Energy (eV)", "Intensity", "Fitting Curve", "C-Si", "C-C", "Background",
    ]


def test_xps_element_keeps_avantage_names_for_preview(avantage_files):
    df = XPSLoader("Avantage").read_element(avantage_files["element"])
    assert df.columns.tolist()[3:5] == ["C1s A", "C1s B"]


def test_xps_unfitted_element(avantage_files):
    df = XPSLoader("Avantage").read_element(avantage_files["element_raw"])
    assert df.columns.tolist() == ["Binding Energy (eV)", "Intensity"]


def test_xps_wrong_peak_count(avantage_files):
    with pytest.raises(ValueError, match="期望 2 个"):
        XPSLoader("Avantage").read_element(avantage_files["element"], peaks=["C-Si"])


def test_xps_reads_legacy_xls_like_xlsx(avantage_xls_pairs):
    """旧版 .xls 与内容相同的 .xlsx 读出的结果一致：读取引擎由 pandas 按文件格式自动选择。"""
    loader = XPSLoader("Avantage")
    for name, (xls, xlsx) in avantage_xls_pairs.items():
        # 确实是旧版 .xls（OLE2 复合文档），不是改了扩展名的 .xlsx
        assert xls.read_bytes().startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")
        read = loader.read_survey if name == "survey" else loader.read_element
        df = read(xls)
        assert len(df) == 21
        pd.testing.assert_frame_equal(df, read(xlsx), check_dtype=False)


def test_xps_custom_reader_and_checks():
    good = pd.DataFrame({"Binding Energy (eV)": [1.0, 2.0], "Intensity": [3.0, 4.0]})
    bad = pd.DataFrame({"BE": [1.0], "Counts": [2.0]})
    loader = XPSLoader((lambda p: good, lambda p, peaks=None: good))
    assert loader.read_survey("x").equals(good)

    with pytest.raises(ValueError, match="Missing required columns"):
        XPSLoader((lambda p: bad, lambda p, peaks=None: bad)).read_survey("x")
    with pytest.raises(ValueError, match="Unknown reader"):
        XPSLoader("Avantag")
    with pytest.raises(TypeError):
        XPSLoader(lambda p: good)


# ============================================================
# Raman
# ============================================================
def test_raman_horiba(horiba_file):
    df, metadata = RamanLoader("Horiba HR evolution").read(horiba_file)
    assert df.columns.tolist() == ["Raman Shift (cm-1)", "Intensity"]
    assert len(df) == 10
    assert metadata["Laser (nm)"] == "532.17"


def test_raman_result_fields(horiba_file):
    result = RamanLoader("Horiba HR evolution").read(horiba_file)
    assert result.data is result[0] and result.metadata is result[1]


def test_raman_reader_must_return_standard_columns():
    wrong = lambda p: (pd.DataFrame({"Raman_shift": [1.0], "Intensity": [2.0]}), {})  # noqa: E731
    with pytest.raises(ValueError, match="Raman Shift"):
        RamanLoader(wrong).read("x")


# ============================================================
# XRD
# ============================================================
def test_xrd_bruker(bruker_file):
    df, metadata = XRDLoader("D8 Advance").read(bruker_file)
    assert df.columns.tolist() == ["2Theta (deg)", "Intensity"]
    assert df["2Theta (deg)"].tolist() == [10.0, 10.02, 10.04]
    assert df["Intensity"].tolist() == [253.0, 260.0, 248.0]
    # 元数据：保留值里的空格，去掉分号后的注释，跳过 Drive 节
    assert metadata["Measurement Conditions"] == {"Sample ID": "SiC coating", "Scan Time": "0.1"}
    assert "Drive" not in metadata


def test_xrd_reader_must_return_tuple():
    with pytest.raises(TypeError, match="tuple"):
        XRDLoader(lambda p: pd.DataFrame()).read("x")
