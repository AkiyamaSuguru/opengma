# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""XPS 模块页中不需要窗口的部分：交互图的曲线、出版图、复制为代码、分析、导入对话框的适配。"""
import os

import numpy as np
import pandas as pd
import pytest

from GMA.project import Project, Record, commit, save_project
from GMA.UI.services import analysis, codegen, figures, importing, spectra
from GMA.UI.services.figures import FigureOptions
from GMA.UI.services.spectra import Display


@pytest.fixture
def project(c1s, f1s_raw, surveys):
    p = Project("测试")
    p.add_record(Record.from_dataframe(c1s, "XPS", "C1s", "B1_SiC_1100℃"))
    p.add_record(Record.from_dataframe(c1s, "XPS", "C1s", "B2"))
    p.add_record(Record.from_dataframe(f1s_raw, "XPS", "F1s", "B1_SiC_1100℃"))
    for name, df in surveys.items():
        p.add_record(Record.from_dataframe(df, "XPS", "Survey", name, kind="survey"))
    return p


def find(project, sample, name):
    return project.find_by_name(sample, "XPS", name)


# ============================================================
# 交互图的曲线
# ============================================================
def test_display_roundtrip():
    d = Display(component_colors={"C-C": "#123456", "bad": "red"}, x_range=[290, 280], y_mode="fixed",
                y_range=[0, 10], hidden=["bg"])
    again = Display.from_dict(d.to_dict())
    assert again.component_colors == {"C-C": "#123456"} and again.x_range == [280.0, 290.0]
    assert again.y_mode == "fixed" and again.y_range == [0.0, 10.0] and again.hidden == ["bg"]
    assert Display().to_dict() == {}  # 默认值不写进项目
    assert Display.from_dict({"y_mode": "fixed", "x_range": [1, 1]}).y_mode == "auto"  # 没有范围时不能固定
    assert Display.from_dict("not a dict") == Display()


def test_single_series(project):
    fitted = find(project, "B1_SiC_1100℃", "C1s")
    series = spectra.single_series(fitted, Display(component_colors={"C-C": "#123456"}))
    assert [s.key for s in series] == ["raw", "fit", "bg", "c:C-Si", "c:C-C"]
    assert all(np.all(np.diff(s.x) > 0) for s in series)  # 横轴从小到大
    assert series[4].color == "#123456" and series[3].color != "#123456"
    # 分峰曲线与 GMA 出版图相同：已包含背景时就是分峰列本身
    df = fitted.to_dataframe().sort_values("Binding Energy (eV)")
    assert np.allclose(series[3].y, df["C-Si"].to_numpy())
    raw = spectra.single_series(find(project, "B1_SiC_1100℃", "F1s"), Display())
    assert len(raw) == 1 and raw[0].label == "Raw data"


def test_overlay_series(project):
    records = [find(project, "As-deposited", "Survey"), find(project, "Corroded", "Survey")]
    series = spectra.overlay_series(records, [Display(), Display(color="#000000")], normalize=True, offset=0.5)
    assert [s.label for s in series] == ["As-deposited", "Corroded"]  # 谱图名相同：用样品名
    assert series[1].color == "#000000"
    assert series[0].y.max() == pytest.approx(1.5) and series[1].y.max() == pytest.approx(1.0)  # 第一条在上面
    mixed = [find(project, "B1_SiC_1100℃", "C1s"), find(project, "B1_SiC_1100℃", "F1s")]
    assert spectra.overlay_labels(mixed) == ["C1s", "F1s"]  # 同一样品：用谱图名
    twice = [mixed[0], mixed[0]]
    assert spectra.overlay_labels(twice) == ["B1_SiC_1100℃ · C1s", "B1_SiC_1100℃ · C1s (2)"]


def test_chart_helpers():
    x = np.linspace(0, 10, 1001)
    y = np.sin(x)
    y[500] = 50  # 一个很高的峰
    keep = spectra.decimate(x, y, 100)
    assert len(keep) <= 102 and 500 in keep and keep[0] == 0 and keep[-1] == 1000
    assert len(spectra.decimate(x, y, 0)) == 1001  # 默认不抽稀
    s = spectra.Series("a", "a", "#000000", x, y)
    assert spectra.nearest(s, 5.004) == 500 and spectra.nearest(s, -3) == 0 and spectra.nearest(s, 99) == 1000
    assert spectra.point_counts([s, spectra.Series("b", "b", "#000000", x, y)], 0, 1) == (101, 1001)
    lo, hi = spectra.y_range([s], 0, 1)
    assert lo < 0 < hi < 1.5
    values, decimals = spectra.ticks(280.0, 292.0)
    assert values == [280, 282, 284, 286, 288, 290, 292] and decimals == 0
    assert spectra.ticks(0.1, 0.35)[1] == 2
    assert spectra.format_value(12345.6) == "12 346" and spectra.format_value(float("nan")) == "—"


# ============================================================
# 出版图与复制为代码
# ============================================================
def test_figure_options():
    o = FigureOptions.from_dict({"size": "huge", "dpi": "1200", "font_size": 99, "legend": 0, "format": "bmp",
                                 "n_cols": 9, "component_alpha": 3}, font="Arial")
    assert (o.size, o.dpi, o.font_size, o.legend, o.format, o.n_cols, o.component_alpha, o.font) == \
        ("single", 1200, 40.0, False, "png", 6, 1.0, "Arial")
    assert FigureOptions.from_dict(o.to_dict()) == o
    assert figures.figure_size(FigureOptions()) == (3.2, 2.4)
    assert figures.figure_size(FigureOptions(), panels=3) == (3.2, 7.2)  # 单栏：子图排成一列
    assert figures.figure_size(FigureOptions(size="double"), panels=4) == (7.0, 5.2)  # 每行最多 3 个
    assert figures.figure_size(FigureOptions(size="custom", width=5, height=4), panels=4) == (5, 4)


def test_make_request(project):
    o = FigureOptions()
    c1s = find(project, "B1_SiC_1100℃", "C1s")
    single = figures.make_request("single", [c1s], [Display()], o)
    assert single.function == "plot_element_static" and single.single and single.interactive
    assert set(single.kwargs["component_colors"]) == {"C-Si", "C-C"}
    survey = find(project, "Corroded", "Survey")
    assert figures.make_request("single", [survey], [Display(color="#111111")], o).kwargs["palette"] == ["#111111"]
    surveys = [find(project, "As-deposited", "Survey"), survey]
    overlay = figures.make_request("overlay", surveys, [Display(), Display()], o, normalize=True, offset=0.3)
    assert overlay.function == "plot_survey_static" and overlay.keys == ["As-deposited", "Corroded"]
    assert overlay.kwargs["normalize"] and overlay.kwargs["offset"] == 0.3 and overlay.panels == 1
    sub = figures.make_request("overlay", surveys, [Display(), Display()], FigureOptions(subplots=True), offset=0.3)
    assert sub.kwargs["subplots"] and "offset" not in sub.kwargs and sub.panels == 2 and sub.interactive is None
    side = figures.make_request("side", [c1s, find(project, "B2", "C1s")], [Display(), Display()], o)
    assert side.function == "plot_element_static" and side.panels == 2 and side.keys == ["B1_SiC_1100℃", "B2"]


def test_render(project, tmp_path):
    o = FigureOptions(dpi=100)
    c1s = find(project, "B1_SiC_1100℃", "C1s")
    request = figures.make_request("single", [c1s], [Display()], o)
    result = figures.render(request, o, fmt="png")
    assert result.data[:8] == b"\x89PNG\r\n\x1a\n" and result.path is None
    svg = figures.render(request, o, path=tmp_path / "c1s.svg", fmt="svg")
    assert svg.path.read_text(encoding="utf-8").lstrip().startswith("<?xml")
    html = figures.render(request, FigureOptions(format="html"), path=tmp_path / "c1s.html")
    assert "plotly" in html.path.read_text(encoding="utf-8")[:5000].lower()
    # 系统中没有所选字体时用附带的字宽相同的字体代替
    used, substituted = figures.resolve_font("Times New Roman")
    assert (used, substituted) in (("Times New Roman", None), ("Liberation Serif", "Times New Roman"))
    assert figures.resolve_font("No Such Font 123") == (figures.FALLBACK_FONT, "No Such Font 123")


def test_figure_code_runs(project, tmp_path):
    """复制的代码可以独立运行，得到与预览相同参数的图。"""
    path = save_project(project, tmp_path / "项目.nc")
    records = [find(project, "B1_SiC_1100℃", "C1s"), find(project, "B2", "C1s")]
    o = FigureOptions(size="double", dpi=80)
    request = figures.make_request("side", records, [Display(), Display()], o)
    code = codegen.figure_code(request, o, project_path=path)
    assert "register_fonts()" in code  # 样品名中有 ℃：用附带的 Noto Sans SC 补字
    assert "plot_element_static" in code and "figsize=(7.0, 2.6)" in code
    cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        exec(compile(code, "copied.py", "exec"), {})  # noqa: S102 - 运行生成的代码，检查它能独立运行
    finally:
        os.chdir(cwd)
    assert (tmp_path / "C1s.png").is_file()
    unsaved = codegen.figure_code(request, o, project_path=None)
    assert "项目还没有保存" in unsaved and "load_project('项目.nc')" in unsaved
    assert codegen.identifier("Si 2p", set()) == "si_2p" and codegen.identifier("2p", {"s_2p"}) == "s_2p_2"


# ============================================================
# 分析
# ============================================================
def test_analysis(project, tmp_path):
    c1s = find(project, "B1_SiC_1100℃", "C1s")
    m = analysis.metrics_for(c1s)
    assert [k for k, _ in analysis.quality_rows(m)] == ["R²", "RMSE", "MAE"]
    rows = analysis.component_rows(m)
    assert [r["name"] for r in rows] == ["C-Si", "C-C"]
    assert sum(r["fraction_value"] for r in rows) == pytest.approx(1.0)
    assert analysis.spectrum_rows(m, c1s)[0][0] == "结合能范围"
    text = analysis.table_text(c1s, m)
    assert text.splitlines()[0].split("\t")[:3] == ["Sample", "Spectrum", "Points"] and len(text.splitlines()) == 3
    raw = find(project, "B1_SiC_1100℃", "F1s")
    assert analysis.quality_rows(analysis.metrics_for(raw)) == []
    csv = analysis.export([c1s, raw], tmp_path / "a", "csv")
    table = pd.read_csv(csv)
    assert csv.suffix == ".csv" and len(table) == 3 and set(table["Spectrum"]) == {"C1s", "F1s"}
    xlsx = analysis.export([c1s], tmp_path / "a", "xlsx")
    assert pd.read_excel(xlsx, sheet_name="Analysis").shape[0] == 2


# ============================================================
# 导入对话框的适配
# ============================================================
def test_importing(avantage_files, tmp_path):
    paths = [avantage_files["survey"], avantage_files["element"], avantage_files["element_raw"]]
    items = importing.inspect(paths, method="XPS")
    kinds = {i.path.name: (i.kind, i.fitted) for i in items}
    assert kinds == {"survey.xlsx": ("survey", False), "C1s.xlsx": ("element", True),
                     "C1s_raw.xlsx": ("element", False)}
    element = next(i for i in items if i.path.name == "C1s.xlsx")
    ok, text = importing.check_text(element)
    assert ok and "2 峰" in text and "点" in text
    assert dict(importing.kind_options(element))["element"] == "元素谱 · 已拟合"
    assert importing.common_sample(items) == items[0].sample
    # 改识别结果后重新读取：元素谱当作全谱读
    changed = importing.change_kind(element, "survey")
    assert changed.kind == "survey" and changed.sample == element.sample
    # 换读取器重新读取时保留改过的谱图名和不导入的勾选
    element.name, items[0].selected = "C 1s", False
    again = importing.reread(items, reader=items[0].reader)
    assert next(i for i in again if i.path.name == "C1s.xlsx").name == "C 1s" and not again[0].selected
    project = Project()
    added = commit(project, [i for i in again if i.selected])
    assert {r.name for r in added} == {"C 1s", "C1s_raw"}
    broken = tmp_path / "broken.xlsx"
    broken.write_bytes(b"not an excel file")
    bad = importing.inspect([broken], method="XPS")[0]
    ok, text = importing.check_text(bad)
    assert not ok and text.startswith("无法读取")
