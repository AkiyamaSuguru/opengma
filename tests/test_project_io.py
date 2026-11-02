# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""导入（识别类型、清洗记录、来源）与导出（CSV、Excel）。"""
import hashlib
import shutil

import pandas as pd
import pytest

from GMA.project import (
    Project,
    ProjectError,
    commit,
    export_csv,
    export_excel,
    guess_xps_kind,
    inspect_file,
    inspect_files,
    inspect_folder,
    set_kind,
)

from conftest import write_avantage_xlsx


@pytest.fixture
def xps_folder(tmp_path, avantage_files, c1s):
    """一个 Avantage 导出文件夹：全谱、拟合元素谱、未拟合元素谱、一个读不出数据的文件。"""
    folder = tmp_path / "B1_SiC_1100℃"
    folder.mkdir()
    shutil.copy(avantage_files["survey"], folder / "Survey.xlsx")
    shutil.copy(avantage_files["element"], folder / "C1s.xlsx")
    shutil.copy(avantage_files["element_raw"], folder / "O1s.xlsx")
    (folder / "notes.xlsx").write_bytes(b"not an excel file")
    (folder / "readme.txt").write_text("ignored")
    return folder


# ============================================================
# 导入
# ============================================================
def test_guess_xps_kind():
    assert guess_xps_kind("Survey.xlsx") == "survey"
    assert guess_xps_kind("wide-scan.xls") == "survey"
    assert guess_xps_kind("全谱.xlsx") == "survey"
    assert guess_xps_kind("C1s.xlsx") == "element"


def test_inspect_xps_folder(xps_folder):
    items = inspect_folder(xps_folder, "XPS")
    by_name = {item.name: item for item in items}
    assert list(by_name) == ["C1s", "notes", "O1s", "Survey"]
    assert all(item.sample == "B1_SiC_1100℃" for item in items)

    survey, c1s, o1s, bad = by_name["Survey"], by_name["C1s"], by_name["O1s"], by_name["notes"]
    assert survey.kind == "survey" and survey.ok and not survey.fitted
    assert c1s.kind == "element" and c1s.fitted
    assert c1s.file_components == ["C1s A", "C1s B"]  # Avantage 中的原名
    assert c1s.components == ["C1s A", "C1s B"]
    assert o1s.ok and not o1s.fitted
    assert not bad.ok and bad.error and not bad.selected


def test_commit_records_source_and_cleaning(tmp_path, xps_folder, c1s):
    # 带两行空值的元素谱
    broken = c1s.copy()
    broken.loc[[2, 3], "Intensity"] = None
    write_avantage_xlsx(xps_folder / "Si2p.xlsx", broken,
                        ["Binding Energy (E)", None, "Counts / s", "Envelope", "Si2p A", "Si2p B", "Backgnd."])
    items = inspect_folder(xps_folder, "XPS")
    si2p = next(i for i in items if i.name == "Si2p")
    assert [n.code for n in si2p.clean_notes] == ["dropped_rows"]
    assert si2p.clean_notes[0].detail["rows"] == [3, 4]

    c1s_item = next(i for i in items if i.name == "C1s")
    c1s_item.components = ["C-Si", "C-C"]
    with pytest.raises(ProjectError, match="expected 2"):
        c1s_item.components = ["C-Si"]

    project = Project("测试")
    added = commit(project, items)
    assert [r.name for r in added] == ["C1s", "O1s", "Si2p", "Survey"]  # notes.xlsx 读取失败，没有加入
    record = project.get("B1_SiC_1100℃", "XPS", "C1s")
    assert record.components == ["C-Si", "C-C"]
    expected = hashlib.sha256((xps_folder / "C1s.xlsx").read_bytes()).hexdigest()
    assert record.source["sha256"] == expected
    assert record.source["file"] == "C1s.xlsx" and record.source["reader"] == "Avantage"
    assert project.get("B1_SiC_1100℃", "XPS", "Si2p").clean_notes[0].code == "dropped_rows"
    assert project.get("B1_SiC_1100℃", "XPS", "Survey").kind == "survey"

    # 再导入一次：默认另存为副本，也可以跳过
    again = commit(project, inspect_folder(xps_folder, "XPS"), on_conflict="skip")
    assert again == []
    copies = commit(project, inspect_files([xps_folder / "C1s.xlsx"], "XPS"))
    assert copies[0].name == "C1s (2)"


def test_set_kind_rereads(xps_folder):
    item = inspect_file(xps_folder / "O1s.xlsx", "XPS", sample="样品A")
    item.name = "O 1s"
    survey = set_kind(item, "survey")
    assert survey.kind == "survey" and survey.ok
    assert survey.name == "O 1s" and survey.sample == "样品A"


def test_inspect_raman_and_xrd(horiba_file, bruker_file):
    raman = inspect_file(horiba_file, "Raman", sample="B1")
    assert raman.ok and raman.kind == "spectrum" and raman.metadata["Laser (nm)"] == "532.17"
    xrd = inspect_file(bruker_file, "XRD", sample="B1")
    assert xrd.ok and xrd.kind == "pattern"
    assert xrd.metadata["Measurement Conditions"]["Sample ID"] == "SiC coating"
    project = Project()
    commit(project, [raman, xrd])
    assert project.get("B1", "Raman", "raman").metadata["Objective"] == "x50"
    assert project.methods() == ["Raman", "XRD"]


def test_inspect_folder_errors(tmp_path):
    with pytest.raises(ProjectError, match="Folder not found"):
        inspect_folder(tmp_path / "missing", "XPS")
    (tmp_path / "empty").mkdir()
    with pytest.raises(ProjectError, match="No .xls"):
        inspect_folder(tmp_path / "empty", "XPS")


# ============================================================
# 导出
# ============================================================
@pytest.fixture
def project(xps_folder, horiba_file):
    project = Project("测试")
    commit(project, inspect_folder(xps_folder, "XPS"))
    commit(project, [inspect_file(horiba_file, "Raman", sample="B1_SiC_1100℃")])
    project.set_sample_info("B1_SiC_1100℃", "沉积温度", "1100 ℃")
    return project


def test_export_csv(tmp_path, project):
    paths = export_csv(project.records.values(), tmp_path / "out")
    rel = sorted(p.relative_to(tmp_path / "out").as_posix() for p in paths)
    assert rel == ["B1_SiC_1100℃/Raman/raman.csv", "B1_SiC_1100℃/XPS/C1s.csv",
                   "B1_SiC_1100℃/XPS/O1s.csv", "B1_SiC_1100℃/XPS/Survey.csv"]
    df = pd.read_csv(tmp_path / "out" / "B1_SiC_1100℃" / "XPS" / "C1s.csv", encoding="utf-8-sig")
    assert df.columns.tolist() == ["Binding Energy (eV)", "Intensity", "Fitting Curve", "C1s A", "C1s B", "Background"]
    pd.testing.assert_frame_equal(df, project.get("B1_SiC_1100℃", "XPS", "C1s").to_dataframe())
    with pytest.raises(ProjectError, match="Nothing to export"):
        export_csv([], tmp_path)


def test_export_excel(tmp_path, project):
    extra = {"分析结果": pd.DataFrame({"Component": ["C1s A"], "Area": [1.0]})}
    path = export_excel(project.records.values(), tmp_path / "数据", project=project, extra_sheets=extra)
    assert path.name == "数据.xlsx"
    sheets = pd.read_excel(path, sheet_name=None, engine="openpyxl")
    assert list(sheets) == ["B1_SiC_1100℃-C1s", "B1_SiC_1100℃-O1s", "B1_SiC_1100℃-Survey",
                            "B1_SiC_1100℃-raman", "分析结果", "信息"]
    info = sheets["信息"]
    assert info["工作表"].tolist()[:2] == ["B1_SiC_1100℃-C1s", "B1_SiC_1100℃-O1s"]
    assert set(info["沉积温度"]) == {"1100 ℃"}
    assert info.loc[0, "来源文件"].endswith("C1s.xlsx")
    no_components = export_excel([project.get("B1_SiC_1100℃", "XPS", "C1s")], tmp_path / "b.xlsx",
                                 include_components=False)
    df = pd.read_excel(no_components, sheet_name=0, engine="openpyxl")
    assert df.columns.tolist() == ["Binding Energy (eV)", "Intensity", "Fitting Curve", "Background"]


def test_sheet_names_are_valid_and_unique(tmp_path, c1s):
    from GMA.project import Record

    long = "很长的样品名称" * 4
    records = [Record.from_dataframe(c1s, "XPS", f"C1s[{i}]", long) for i in range(3)]
    path = export_excel(records, tmp_path / "x.xlsx")
    names = list(pd.read_excel(path, sheet_name=None, engine="openpyxl"))
    assert len(set(names)) == 4 and all(len(n) <= 31 for n in names)
    assert not any(ch in n for n in names for ch in "[]:*?/\\")
