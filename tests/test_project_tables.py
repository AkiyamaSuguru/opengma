# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""峰位表、参考物相表、通用表格的读取，以及用通用表格导入其他软件的结果。"""
import numpy as np
import pytest

from GMA.project import (
    GENERIC_READER,
    Project,
    ProjectError,
    TableColumns,
    commit,
    inspect_file,
    load_project,
    read_peak_csv,
    read_phase_csv,
    read_table,
    save_project,
    set_kind,
    write_peak_csv,
    write_phase_csv,
)

SIC = [{"phase": "β-SiC", "hkl": "(111)", "two_theta": 35.6}, {"phase": "β-SiC", "hkl": "(220)", "two_theta": "60.0"},
       {"phase": "Graphite", "hkl": "(002)", "two_theta": 26.5}]


# ============================================================
# 峰位表与参考物相
# ============================================================
def test_peak_tables():
    p = Project()
    p.set_peak_table(" 碳材料 ", [{"label": " D ", "position": "1350"}, {"label": "G", "position": 1585}])
    assert p.peak_tables == {"碳材料": [{"label": "D", "position": 1350.0}, {"label": "G", "position": 1585.0}]}
    assert p.peaks("碳材料") == {"D": 1350.0, "G": 1585.0} and p.dirty
    p.set_peak_table("SiC", [])
    p.rename_peak_table("碳材料", "Raman")
    assert list(p.peak_tables) == ["Raman", "SiC"]  # 改名后顺序不变
    with pytest.raises(ProjectError, match="already exists"):
        p.rename_peak_table("SiC", "Raman")
    p.remove_peak_table("SiC")
    assert list(p.peak_tables) == ["Raman"]
    for rows, message in (([{"label": "", "position": 1}], "label is empty"),
                          ([{"label": "D", "position": 1}, {"label": "D", "position": 2}], "duplicate label"),
                          ([{"label": "D", "position": "abc"}], "must be a number"),
                          ([{"label": "D", "position": "nan"}], "finite")):
        with pytest.raises(ProjectError, match=message):
            p.set_peak_table("bad", rows)
    with pytest.raises(ProjectError, match="not found"):
        p.peaks("bad")


def test_reference_phases(tmp_path, c1s):
    p = Project()
    p.set_reference_phases(SIC)
    assert p.phase_names() == ["β-SiC", "Graphite"]
    assert p.references() == {"β-SiC": {"(111)": 35.6, "(220)": 60.0}, "Graphite": {"(002)": 26.5}}
    assert p.references(["Graphite"]) == {"Graphite": {"(002)": 26.5}}
    with pytest.raises(ProjectError, match="duplicate"):
        p.set_reference_phases([*SIC, {"phase": "β-SiC", "hkl": "(111)", "two_theta": 35.7}])
    with pytest.raises(ProjectError, match="must not be empty"):
        p.set_reference_phases([{"phase": "", "hkl": "(111)", "two_theta": 35.6}])
    p.set_peak_table("SiC", [{"label": "C(002)", "position": 26.5}])
    from GMA.project import Record
    p.add_record(Record.from_dataframe(c1s, "XPS", "C1s", "B1"))
    again = load_project(save_project(p, tmp_path / "p.nc"))  # 表格随项目保存
    assert again.reference_phases == p.reference_phases and again.peak_tables == p.peak_tables


def test_table_csv(tmp_path):
    rows = [{"label": "C 1s", "position": 284.8}, {"label": "氧 O 1s", "position": 532.0}]
    path = write_peak_csv(rows, tmp_path / "peaks.csv")
    assert path.read_bytes().startswith(b"\xef\xbb\xbf")  # 带 BOM，Excel 打开不乱码
    assert read_peak_csv(path) == rows
    (tmp_path / "zh.csv").write_text("标签;位置\nD;1350\nG;1585\n", encoding="utf-8")
    assert read_peak_csv(tmp_path / "zh.csv") == [{"label": "D", "position": 1350.0}, {"label": "G", "position": 1585.0}]
    (tmp_path / "plain.csv").write_text("D\t1350\nG\t1585\n", encoding="utf-8")  # 没有表头：按列的顺序
    assert [r["label"] for r in read_peak_csv(tmp_path / "plain.csv")] == ["D", "G"]
    (tmp_path / "bad.csv").write_text("label,position\nD,x\n", encoding="utf-8")
    with pytest.raises(ProjectError, match="must be a number"):
        read_peak_csv(tmp_path / "bad.csv")
    phases = write_phase_csv(SIC, tmp_path / "phases.csv")
    assert read_phase_csv(phases)[1] == {"phase": "β-SiC", "hkl": "(220)", "two_theta": 60.0}
    (tmp_path / "zh_phase.csv").write_text("物相,晶面指数,2θ\nβ-SiC,(111),35.6\n", encoding="gb18030")
    assert read_phase_csv(tmp_path / "zh_phase.csv") == [{"phase": "β-SiC", "hkl": "(111)", "two_theta": 35.6}]


# ============================================================
# 通用表格
# ============================================================
def test_read_table_formats(tmp_path):
    origin = tmp_path / "origin.csv"  # 说明行、名称、单位，然后是数据
    origin.write_text("# exported\nShift,Counts,Fit,D,Base\ncm-1,a.u.,,,\n1000,10,9,5,2\n1001,11,10,6,2\n",
                      encoding="utf-8")
    t = read_table(origin)
    assert list(t.columns) == ["Shift", "Counts", "Fit", "D", "Base"] and t.shape == (2, 5)
    wire = tmp_path / "wire.txt"  # Renishaw WiRE：表头以 # 开头，制表符分隔；小数逗号
    wire.write_text("#Wave\t\t#Intensity\n100,5\t\t3,5\n101,5\t\t4,5\n", encoding="utf-8")
    t = read_table(wire)
    assert list(t.columns) == ["Wave", "Intensity"] and t["Intensity"].tolist() == [3.5, 4.5]
    bare = tmp_path / "bare.dat"  # 空白分隔，没有表头
    bare.write_text("1 2 3\n4 5 6\n", encoding="utf-8")
    assert list(read_table(bare).columns) == ["Column 1", "Column 2", "Column 3"]
    gbk = tmp_path / "gbk.csv"
    gbk.write_text("角度,强度,备注\n10,1,好\n11,2,好\n", encoding="gb18030")
    t = read_table(gbk)
    assert list(t.columns) == ["角度", "强度"]  # 整列不是数值的“备注”去掉
    (tmp_path / "text.csv").write_text("a,b\nx,y\n", encoding="utf-8")
    with pytest.raises(ProjectError, match="numeric"):
        read_table(tmp_path / "text.csv")


def test_generic_import(tmp_path, raman_fit):
    path = tmp_path / "S1" / "fit.csv"
    path.parent.mkdir()
    table = raman_fit.rename(columns={"Raman Shift (cm-1)": "Shift", "Intensity": "Counts", "Fitting Curve": "Sum",
                                      "Background": "Base"})
    table.to_csv(path, index=False)
    columns = TableColumns("Shift", "Counts", "Sum", "Base", ["D", "G"])
    item = inspect_file(path, "Raman", reader=GENERIC_READER, columns=columns)
    assert item.ok and item.fitted and item.file_components == ["D", "G"] and item.sample == "S1"
    item.components = ["D band", "G band"]
    project = Project()
    record = commit(project, [item])[0]
    assert record.components == ["D band", "G band"] and record.source["reader"] == GENERIC_READER
    assert record.metadata["Columns"] == columns.to_dict()
    assert np.allclose(record.to_dataframe()["Intensity"], raman_fit["Intensity"])
    # 只有横轴和强度：谱线；XPS 改类型重新读取时保留各列的含义
    line = inspect_file(path, "XPS", reader=GENERIC_READER, columns=TableColumns("Shift", "Counts"))
    assert line.ok and not line.fitted and line.kind == "element"
    survey = set_kind(line, "survey")
    assert survey.ok and survey.kind == "survey" and survey.columns == line.columns
    # 列名不对时记下原因，不抛出异常
    wrong = inspect_file(path, "Raman", reader=GENERIC_READER, columns=TableColumns("X", "Counts"))
    assert not wrong.ok and "not found" in wrong.error
    missing = inspect_file(path, "Raman", reader=GENERIC_READER)
    assert not missing.ok


def test_table_columns_rules():
    with pytest.raises(ProjectError, match="both"):
        TableColumns("x", "y", fit="f")
    with pytest.raises(ProjectError, match="once"):
        TableColumns("x", "x")
    with pytest.raises(ProjectError, match="need the fitting curve"):
        TableColumns("x", "y", components=["a"])
    c = TableColumns("x", "y", "f", "b", ["a"])
    assert TableColumns.from_dict(c.to_dict()) == c
