# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""Raman、XRD 模块页中不需要窗口的部分：出版图的绘图函数、峰位和参考物相、通用表格的列、文字。"""
import os

import pandas as pd
import pytest

from GMA.project import GENERIC_READER, Project, Record, save_project
from GMA.UI.services import codegen, figures, importing
from GMA.UI.services.figures import FigureOptions
from GMA.UI.services.spectra import Display
from GMA.UI.services.text import plain_label, unit

REFERENCES = {"β-SiC": {"(111)": 35.6, "(220)": 60.0}, "Graphite": {"(002)": 26.5}}


@pytest.fixture
def project(raman_spectra, raman_fit, xrd_patterns):
    p = Project("测试")
    for sample, df in raman_spectra.items():
        p.add_record(Record.from_dataframe(df, "Raman", "Raman", sample))
    p.add_record(Record.from_dataframe(raman_fit, "Raman", "Fit", "As-deposited"))
    for sample, df in xrd_patterns.items():
        p.add_record(Record.from_dataframe(df, "XRD", "XRD", sample))
    return p


def displays(records):
    return [Display() for _ in records]


def test_functions_by_method(project):
    o = FigureOptions()
    lines = project.records_of(method="Raman")[:2]
    fit = project.find_by_name("As-deposited", "Raman", "Fit")
    xrd = project.records_of(method="XRD")
    peaks = {"D": 1350.0, "G": 1585.0}
    cases = [
        ("single", [lines[0]], {}, "plot_spectrum_static", "plot_spectrum_interactive", True),
        ("single", [fit], {}, "plot_fit_static", "plot_fit_interactive", False),
        ("overlay", lines, {"peaks": peaks}, "plot_spectrum_static", "plot_spectrum_interactive", True),
        ("side", [fit, lines[0]], {}, "plot_fit_static", None, False),         # 有拟合谱：分峰子图
        ("side", lines, {"peaks": peaks}, "plot_spectrum_static", None, True),  # 都是谱线：谱线子图
        ("single", [xrd[0]], {"references": REFERENCES}, "plot_pattern_static", "plot_pattern_interactive", True),
        ("side", xrd, {"references": REFERENCES}, "plot_pattern_static", None, True),
    ]
    for view, records, marks, function, interactive, supports in cases:
        request = figures.make_request(view, records, displays(records), o, **marks)
        assert (request.function, request.interactive) == (function, interactive), (view, function)
        assert figures.supports_marks(view, records) == supports
        for key in marks:
            assert (key in request.kwargs) == supports
    side = figures.make_request("side", lines, displays(lines), o)
    assert side.kwargs["subplots"] and side.panels == 2 and side.keys == ["As-deposited", "Corroded"]
    # 参考物相只给 XRD
    raman = figures.make_request("single", [lines[0]], displays([lines[0]]), o, references=REFERENCES)
    assert "references" not in raman.kwargs


def test_render_marks(project, tmp_path):
    xrd = project.records_of(method="XRD")
    o = FigureOptions(dpi=80)
    colors = {"β-SiC": "#D62728", "Graphite": "#9467BD"}
    request = figures.make_request("overlay", xrd, displays(xrd), o, normalize=True, offset=1.1,
                                   peaks={"C": 26.5}, references=REFERENCES, phase_colors=colors)
    assert request.kwargs["phase_colors"] == colors and request.kwargs["references"] == REFERENCES
    assert figures.render(request, o, fmt="png").data[:4] == b"\x89PNG"
    html = figures.render(request, FigureOptions(format="html"), path=tmp_path / "xrd.html")
    assert "SiC" in html.path.read_text(encoding="utf-8")  # plotly 把 β 写成 \u03b2
    raman = project.records_of(method="Raman")[:2]
    fit = project.find_by_name("As-deposited", "Raman", "Fit")
    for request in (figures.make_request("overlay", raman, displays(raman), o, peaks={"D": 1350.0}),
                    figures.make_request("single", [fit], [Display()], o),
                    figures.make_request("side", [fit, raman[0]], displays(raman), FigureOptions(size="double", dpi=80))):
        assert figures.render(request, o if request.panels == 1 else FigureOptions(size="double", dpi=80),
                              fmt="png").data[:4] == b"\x89PNG"


def test_xrd_code_runs(project, tmp_path):
    """XRD 叠加加参考物相：复制的代码可以独立运行。"""
    path = save_project(project, tmp_path / "项目.nc")
    xrd = project.records_of(method="XRD")
    o = FigureOptions(dpi=60)
    request = figures.make_request("overlay", xrd, displays(xrd), o, references=REFERENCES,
                                   phase_colors={"β-SiC": "#D62728", "Graphite": "#9467BD"})
    code = codegen.figure_code(request, o, project_path=path)
    assert "XRDPlotter" in code and "references=" in code and "phase_colors=" in code
    assert "register_fonts" not in code  # 希腊字母在西文字体中，不需要补字
    cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        exec(compile(code, "copied.py", "exec"), {})  # noqa: S102 - 运行生成的代码，检查它能独立运行
    finally:
        os.chdir(cwd)
    assert (tmp_path / "XRD.png").is_file()


def test_guess_columns():
    def guess(columns, method="Raman"):
        return importing.guess_columns(pd.DataFrame([[1.0] * len(columns)], columns=columns), method)

    c = guess(["Raman Shift (cm-1)", "Intensity", "Fitting Curve", "D", "G", "Background"])
    assert (c.x, c.intensity, c.fit, c.background, c.components) == \
        ("Raman Shift (cm-1)", "Intensity", "Fitting Curve", "Background", ["D", "G"])
    c = guess(["BE", "Counts / s", "Envelope", "C1s A", "C1s B", "Backgnd."], "XPS")
    assert (c.x, c.intensity, c.fit, c.background, c.components) == ("BE", "Counts / s", "Envelope", "Backgnd.",
                                                                    ["C1s A", "C1s B"])
    c = guess(["Angle", "PSD", "Fit", "Background"], "XRD")  # XRD 只有横轴和强度
    assert (c.x, c.intensity, c.fit, c.background) == ("Angle", "PSD", None, None)
    c = guess(["Column 1", "Column 2", "Column 3"])  # 认不出：第一列、第二列
    assert (c.x, c.intensity, c.fit) == ("Column 1", "Column 2", None)
    c = guess(["Shift", "Counts", "Fit", "D"])  # 只有拟合曲线、没有背景：当作谱线
    assert c.fit is None and c.components == []


def test_labels(avantage_files, horiba_file, bruker_file):
    raman = importing.inspect([horiba_file], method="Raman")[0]
    xrd = importing.inspect([bruker_file], method="XRD")[0]
    assert importing.kind_options(raman) == [("spectrum", "谱线")]
    assert importing.kind_options(xrd) == [("pattern", "图谱")]
    assert importing.reader_label(GENERIC_READER) == "通用表格（CSV 等）" and importing.reader_label("Avantage") == "Avantage"
    assert plain_label("Raman Shift (cm$^{-1}$)") == "Raman Shift (cm-1)"
    assert plain_label("2$\\theta$ (°)") == "2θ (°)" and plain_label("Binding Energy (eV)") == "Binding Energy (eV)"
    assert unit("deg") == "°" and unit("cm-1") == "cm-1" and unit("eV") == "eV"
