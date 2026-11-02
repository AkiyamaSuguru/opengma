# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""结构化存储：Record 与标准 DataFrame 的转换、项目操作、NetCDF 项目文件的读写。"""
import numpy as np
import pandas as pd
import pytest
import xarray as xr

from GMA.project import (
    SCHEMA_NAME,
    CleanNote,
    Project,
    ProjectError,
    Record,
    clean_frame,
    load_project,
    project_to_datatree,
    save_project,
)


def sorted_frame(df, column):
    return df.sort_values(column, ignore_index=True)


# ============================================================
# Record ⇄ 标准 DataFrame
# ============================================================
def test_fitted_element_round_trip(c1s):
    record = Record.from_dataframe(c1s, "XPS", "C1s", "B1")
    assert record.kind == "element"
    assert record.fitted
    assert record.components == ["C-Si", "C-C"]
    assert record.point_count == len(c1s)
    assert "binding_energy" in record.data.coords
    assert record.data["component_intensity"].dims == ("component", "point")
    # Avantage 的结合能从高到低，存储时改为从低到高，数值不变
    pd.testing.assert_frame_equal(record.to_dataframe(), sorted_frame(c1s, "Binding Energy (eV)"))
    assert record.clean_notes == []


def test_raw_spectra_for_each_method(surveys, raman_spectra, xrd_patterns):
    survey = Record.from_dataframe(surveys["As-deposited"], "XPS", "Survey", "B1", kind="survey")
    raman = Record.from_dataframe(raman_spectra["As-deposited"], "Raman", "spot1", "B1")
    xrd = Record.from_dataframe(xrd_patterns["As-deposited"], "XRD", "as-deposited", "B1")
    assert (survey.kind, raman.kind, xrd.kind) == ("survey", "spectrum", "pattern")
    assert not any(r.fitted for r in (survey, raman, xrd))
    assert "raman_shift" in raman.data.coords and "two_theta" in xrd.data.coords
    assert raman.to_dataframe().columns.tolist() == ["Raman Shift (cm-1)", "Intensity"]
    assert xrd.to_dataframe().columns.tolist() == ["2Theta (deg)", "Intensity"]


def test_raman_fit_record(raman_fit):
    record = Record.from_dataframe(raman_fit, "Raman", "fit", "B1")
    assert record.fitted and record.components == ["D", "G"]
    pd.testing.assert_frame_equal(record.to_dataframe(), raman_fit)


def test_to_dataframe_without_components(c1s):
    df = Record.from_dataframe(c1s, "XPS", "C1s", "B1").to_dataframe(include_components=False)
    assert df.columns.tolist() == ["Binding Energy (eV)", "Intensity", "Fitting Curve", "Background"]


def test_metadata_source_and_attrs(c1s):
    record = Record.from_dataframe(
        c1s, "XPS", "C1s", "B1", metadata={"通能": "30 eV"},
        source={"path": "/data/C1s.xlsx", "file": "C1s.xlsx", "sha256": "abc", "reader": "Avantage"},
    )
    assert record.metadata == {"通能": "30 eV"}
    assert record.source["file"] == "C1s.xlsx"
    assert record.source["reader"] == "Avantage"
    assert record.source["imported_at"]
    assert record.component_mode == "absolute"


def test_invalid_inputs(c1s):
    with pytest.raises(ProjectError, match="Unknown method"):
        Record.from_dataframe(c1s, "SEM", "x", "B1")
    with pytest.raises(ProjectError, match="Unknown kind"):
        Record.from_dataframe(c1s, "XPS", "x", "B1", kind="pattern")
    with pytest.raises(ProjectError, match="cannot be empty"):
        Record.from_dataframe(c1s, "XPS", "  ", "B1")
    with pytest.raises(ProjectError, match="Background"):
        Record.from_dataframe(c1s.drop(columns="Background"), "XPS", "x", "B1")


def test_rename_components(c1s):
    record = Record.from_dataframe(c1s, "XPS", "C1s", "B1")
    record.rename_components(["Si–C", "C–C"])
    assert record.components == ["Si–C", "C–C"]
    assert record.to_dataframe().columns.tolist()[3:5] == ["Si–C", "C–C"]
    with pytest.raises(ProjectError, match="expected 2"):
        record.rename_components(["a"])
    with pytest.raises(ProjectError, match="unique"):
        record.rename_components(["a", "a"])
    with pytest.raises(ProjectError, match="standard column"):
        record.rename_components(["Background", "b"])


# ============================================================
# 清洗
# ============================================================
def test_clean_frame_drops_rows_and_reports(c1s):
    df = c1s.copy()
    df.loc[3, "Intensity"] = np.nan
    df["Fitting Curve"] = df["Fitting Curve"].astype(object)
    df.loc[10, "Fitting Curve"] = "n/a"
    df["Empty"] = np.nan
    df = df[[*c1s.columns[:-1], "Empty", "Background"]]
    clean, notes = clean_frame(df, "XPS")
    assert len(clean) == len(c1s) - 2
    assert "Empty" not in clean.columns
    codes = {n.code: n for n in notes}
    assert codes["dropped_rows"].detail == {"count": 2, "rows": [4, 11]}
    assert "第 4、11 行" in codes["dropped_rows"].text()
    assert "Empty" in codes["empty_component"].text()


def test_clean_frame_sorting_and_duplicates(xrd_patterns):
    df = xrd_patterns["As-deposited"].copy()
    shuffled = df.iloc[[2, 0, 1, *range(3, len(df))]].reset_index(drop=True)
    clean, notes = clean_frame(shuffled, "XRD")
    assert clean["2Theta (deg)"].is_monotonic_increasing
    assert [n.code for n in notes] == ["sorted"]
    dup = pd.concat([df.iloc[:5], df.iloc[4:5], df.iloc[5:]], ignore_index=True)
    _, notes = clean_frame(dup, "XRD")
    assert [n.code for n in notes] == ["duplicate_x"]
    # 从大到小只是倒序，不记入清洗记录
    _, notes = clean_frame(df.iloc[::-1], "XRD")
    assert notes == []


def test_clean_note_round_trip():
    note = CleanNote("dropped_rows", {"count": 12, "rows": list(range(1, 13))})
    assert CleanNote.from_dict(note.to_dict()) == note
    assert note.text().endswith("行等）")


# ============================================================
# 项目操作
# ============================================================
def make_project(c1s, surveys, xrd_patterns):
    project = Project("SiC-FLiNaK 腐蚀")
    project.add_record(Record.from_dataframe(surveys["As-deposited"], "XPS", "Survey", "B1_SiC_1100℃", kind="survey"))
    project.add_record(Record.from_dataframe(c1s, "XPS", "C1s", "B1_SiC_1100℃"))
    project.add_record(Record.from_dataframe(xrd_patterns["Corroded"], "XRD", "as-deposited", "B2_SiC_1200℃"))
    project.set_sample_info("B1_SiC_1100℃", "沉积温度", "1100 ℃")
    project.set_sample_info("B2_SiC_1200℃", "沉积温度", "1200 ℃")
    project.set_sample_info("B2_SiC_1200℃", "处理", "FLiNaK 700 ℃ · 100 h")
    return project


def test_project_add_get_and_conflicts(c1s, surveys, xrd_patterns):
    project = make_project(c1s, surveys, xrd_patterns)
    assert list(project.samples) == ["B1_SiC_1100℃", "B2_SiC_1200℃"]
    assert project.sample_fields == ["沉积温度", "处理"]
    assert project.methods() == ["XPS", "XRD"]
    assert project.counts() == {"B1_SiC_1100℃": {"XPS": 2}, "B2_SiC_1200℃": {"XRD": 1}}
    assert project.dirty

    copy = project.add_record(Record.from_dataframe(c1s, "XPS", "C1s", "B1_SiC_1100℃"))
    assert copy.name == "C1s (2)"
    assert project.add_record(Record.from_dataframe(c1s, "XPS", "C1s", "B1_SiC_1100℃"), on_conflict="skip") is None
    old = project.get("B1_SiC_1100℃", "XPS", "C1s")
    new = Record.from_dataframe(c1s.iloc[:50], "XPS", "C1s", "B1_SiC_1100℃")
    project.add_record(new, on_conflict="replace")
    assert old.record_id not in project.records
    assert project.get("B1_SiC_1100℃", "XPS", "C1s").point_count == 50
    # 替换后仍在原来的位置
    assert [r.name for r in project.records_of(method="XPS")] == ["Survey", "C1s", "C1s (2)"]
    with pytest.raises(ProjectError, match="Record not found"):
        project.get("B1_SiC_1100℃", "XPS", "O1s")


def test_project_rename_move_remove(c1s, surveys, xrd_patterns):
    project = make_project(c1s, surveys, xrd_patterns)
    c1s_id = project.get("B1_SiC_1100℃", "XPS", "C1s").record_id
    with pytest.raises(ProjectError, match="already used"):
        project.rename_record(c1s_id, "Survey")
    project.rename_record(c1s_id, "C 1s")
    project.move_record(c1s_id, "B3_新样品")
    assert project.record(c1s_id).sample == "B3_新样品"
    assert "B3_新样品" in project.samples
    project.rename_sample("B1_SiC_1100℃", "B1")
    assert project.get("B1", "XPS", "Survey").sample == "B1"
    assert list(project.samples)[0] == "B1"
    removed = project.remove_sample("B2_SiC_1200℃")
    assert [r.name for r in removed] == ["as-deposited"]
    assert project.methods() == ["XPS"]
    project.remove_record(c1s_id)
    assert len(project) == 1


# ============================================================
# 项目文件
# ============================================================
def test_save_and_load_round_trip(tmp_path, c1s, surveys, xrd_patterns):
    project = make_project(c1s, surveys, xrd_patterns)
    project.add_sample("空样品", {"备注": "还没有数据"})
    project.peak_tables["XPS 全谱"] = [{"label": "C 1s", "position": 284.8}, {"label": "O 1s", "position": 532.0}]
    project.reference_phases = [{"phase": "β-SiC", "hkl": "(111)", "two_theta": 35.6}]
    project.ui_state = {"tabs": [{"module": "XPS", "selected": "C1s"}], "active": 0}
    record = project.get("B1_SiC_1100℃", "XPS", "C1s")
    record.rename_components(["C-Si", "C–C（石墨）"])
    record.notes = "800 ℃ 退火后"

    path = save_project(project, tmp_path / "SiC-FLiNaK 腐蚀")
    assert path.suffix == ".nc" and path.exists()
    assert not project.dirty and project.file_path == path
    assert not list(tmp_path.glob(".*.saving"))

    loaded = load_project(path)
    assert loaded.name == "SiC-FLiNaK 腐蚀"
    assert list(loaded.samples) == list(project.samples)
    assert [r.record_id for r in loaded.records.values()] == [r.record_id for r in project.records.values()]
    assert loaded.samples["空样品"].info == {"备注": "还没有数据"}
    assert loaded.sample_fields == project.sample_fields
    assert loaded.peak_tables == project.peak_tables
    assert loaded.reference_phases == project.reference_phases
    assert loaded.ui_state == project.ui_state
    back = loaded.get("B1_SiC_1100℃", "XPS", "C1s")
    assert back.components == ["C-Si", "C–C（石墨）"]
    assert back.notes == "800 ℃ 退火后"
    pd.testing.assert_frame_equal(back.to_dataframe(), record.to_dataframe())
    assert not loaded.dirty


def test_file_layout_is_plain_xarray(tmp_path, c1s, surveys, xrd_patterns):
    path = save_project(make_project(c1s, surveys, xrd_patterns), tmp_path / "p.nc")
    tree = xr.load_datatree(path, engine="h5netcdf")
    assert tree.attrs["schema_name"] == SCHEMA_NAME
    assert "/B1_SiC_1100℃/XPS/C1s" in tree.groups
    assert "/B2_SiC_1200℃/XRD/as-deposited" in tree.groups
    ds = tree["/B1_SiC_1100℃/XPS/C1s"].to_dataset()
    assert ds["binding_energy"].attrs["units"] == "eV"


def test_names_with_slashes_are_stored(tmp_path, c1s):
    project = Project()
    project.add_record(Record.from_dataframe(c1s, "XPS", "C1s/O1s", "A/B"))
    project.add_record(Record.from_dataframe(c1s, "XPS", "C1s_O1s", "A/B"))
    tree = project_to_datatree(project)
    assert "/A_B/XPS/C1s_O1s" in tree.groups and "/A_B/XPS/C1s_O1s (2)" in tree.groups
    loaded = load_project(save_project(project, tmp_path / "p.nc"))
    assert {r.name for r in loaded.records.values()} == {"C1s/O1s", "C1s_O1s"}
    assert list(loaded.samples) == ["A/B"]


def test_save_failure_keeps_old_file(tmp_path, c1s, monkeypatch):
    project = Project()
    project.add_record(Record.from_dataframe(c1s, "XPS", "C1s", "B1"))
    path = save_project(project, tmp_path / "p.nc")
    before = path.read_bytes()

    def broken(self, *args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(xr.DataTree, "to_netcdf", broken)
    with pytest.raises(ProjectError, match="disk full"):
        save_project(project, path)
    assert path.read_bytes() == before
    assert not list(tmp_path.glob(".*.saving"))


def test_load_rejects_other_files(tmp_path):
    other = tmp_path / "other.nc"
    xr.Dataset({"a": ("x", [1, 2])}).to_netcdf(other, engine="h5netcdf")
    with pytest.raises(ProjectError, match="not an OpenGMA project"):
        load_project(other)
    with pytest.raises(ProjectError, match="not found"):
        load_project(tmp_path / "missing.nc")
    with pytest.raises(ProjectError, match="No file path"):
        save_project(Project())
