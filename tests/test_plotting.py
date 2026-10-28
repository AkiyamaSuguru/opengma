# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""绘图模块：三种表征方法的谱线图、拟合谱图、配色和样式。"""
import warnings

import matplotlib
import matplotlib.pyplot as plt
import pytest
from matplotlib.colors import to_hex

from GMA import RamanPlotter, XPSPlotter, XRDPlotter
from GMA.CM.common import color_tables

TAB10 = [to_hex(c) for c in matplotlib.color_sequences["tab10"]]


def line_colors(ax):
    return [to_hex(line.get_color()) for line in ax.lines if line.get_linestyle() == "-"]


def fill_colors(ax):
    return {
        c.get_label(): to_hex(c.get_facecolor()[0])
        for c in ax.collections
        if not c.get_label().startswith("_") and c.get_label() != "Raw data"
    }


@pytest.fixture
def plotter_and_data(request, surveys, raman_spectra, xrd_patterns):
    """三种表征方法的谱线图：(Plotter, 静态方法名, 交互方法名, 数据, 横轴是否反向)。"""
    cases = {
        "xps": (XPSPlotter(), "plot_survey_static", "plot_survey_interactive", surveys, True),
        "raman": (RamanPlotter(), "plot_spectrum_static", "plot_spectrum_interactive", raman_spectra, False),
        "xrd": (XRDPlotter(), "plot_pattern_static", "plot_pattern_interactive", xrd_patterns, False),
    }
    return cases[request.param]


TECHNIQUES = pytest.mark.parametrize("plotter_and_data", ["xps", "raman", "xrd"], indirect=True)


# ============================================================
# 谱线图：XPS 全谱、Raman 谱、XRD 图谱
# ============================================================
@TECHNIQUES
def test_line_plots_single_overlay_subplots(plotter_and_data):
    plotter, static, _, data, reversed_axis = plotter_and_data
    plot = getattr(plotter, static)
    first = next(iter(data.values()))

    fig, ax = plot(first, show=False)
    assert bool(ax.xaxis_inverted()) == reversed_axis
    assert ax.get_xlabel() == plotter.AXIS.label
    assert ax.get_legend() is None  # 单条谱没有图例

    fig, ax = plot(data, normalize=True, offset=1.0, hide_y_ticks=True, show=False)
    assert line_colors(ax) == TAB10[:2]
    assert [t.get_text() for t in ax.get_legend().get_texts()] == list(data)
    assert len(ax.get_yticks()) == 0

    fig, axes = plot(data, subplots=True, n_cols=1, show=False)
    assert axes.shape == (2, 1)
    assert [t.get_text() for t in axes[0, 0].texts] == [list(data)[0]]


@TECHNIQUES
def test_sample_colors_and_peaks(plotter_and_data):
    plotter, static, _, data, _ = plotter_and_data
    first, second = list(data)
    peaks = {first: {"A": 50.0}, second: {"A": 50.0, "B": 60.0}}
    fig, axes = getattr(plotter, static)(
        data, subplots=True, sample_colors={first: "black", second: "black"}, peaks=peaks, show=False,
    )
    assert [line_colors(ax)[0] for ax in axes.ravel()] == ["#000000", "#000000"]
    assert [len(ax.texts) for ax in axes.ravel()] == [2, 3]  # 峰标签 + 样品名


@TECHNIQUES
def test_interactive_line_plot(plotter_and_data):
    plotter, _, interactive, data, reversed_axis = plotter_and_data
    fig = getattr(plotter, interactive)(data, peaks={"A": 50.0}, offset=1000.0)
    assert [trace.line.color for trace in fig.data[:2]] == TAB10[:2]
    assert fig.layout.xaxis.autorange == ("reversed" if reversed_axis else True)
    assert fig.layout.xaxis.title.text == plotter.AXIS.label_html
    assert len(fig.layout.shapes) == 1
    assert "customdata" in fig.data[0].hovertemplate  # 错开显示时悬停显示原始强度
    assert fig.layout.font.size == 12


# ============================================================
# 拟合谱：XPS 元素谱、Raman 拟合谱
# ============================================================
def test_xps_element_static(c1s, si2p, f1s_raw):
    colors = {"C-Si": "tab:blue", "Si-C": "tab:blue", "C-C": "tab:orange", "Si-O": "tab:red"}
    fig, axes = XPSPlotter().plot_element_static(
        {"C 1s": c1s, "Si 2p": si2p, "F 1s": f1s_raw}, component_colors=colors, show=False,
    )
    c_ax, si_ax, f_ax = axes.ravel()
    assert fill_colors(c_ax) == {"C-Si": TAB10[0], "C-C": TAB10[1]}
    assert fill_colors(si_ax) == {"Si-C": TAB10[0], "Si-O": TAB10[3]}
    assert c_ax.get_legend().get_title().get_text() == "C 1s"  # 元素名是图例标题，不会被遮挡
    assert line_colors(f_ax) == [TAB10[0]]  # 未拟合谱用通用色卡的第一个颜色
    assert c_ax.xaxis_inverted()


def test_raman_fit_static_and_interactive(raman_fit):
    plotter = RamanPlotter()
    fig, axes = plotter.plot_fit_static(
        {"PyC": raman_fit}, component_colors={"D": "black", "G": "tab:red"}, show=False,
    )
    ax = axes[0, 0]
    assert fill_colors(ax) == {"D": "#000000", "G": TAB10[3]}
    assert not ax.xaxis_inverted()
    assert ax.get_legend().get_title().get_text() == "PyC"

    fig = plotter.plot_fit_interactive(raman_fit)
    markers = {t.name: float(t.x[0]) for t in fig.data if t.name and t.name.endswith(" peak")}
    assert markers == pytest.approx({"D peak": 1350.0, "G peak": 1586.0}, abs=2.0)


def test_missing_component_color_warns(c1s):
    with pytest.warns(UserWarning, match="component_colors has no color"):
        XPSPlotter().plot_element_static(c1s, component_colors={"C-Si": "black"}, show=False)


# ============================================================
# XRD 参考物相
# ============================================================
def test_xrd_references(xrd_patterns):
    references = {"β-SiC": {"(111)": 35.6, "(220)": 60.0}, "Graphite": {"(002)": 26.5}}
    plotter = XRDPlotter()

    fig, ax = plotter.plot_pattern_static(xrd_patterns, references=references, show=False)
    legend = [t.get_text() for t in ax.get_legend().get_texts()]
    assert legend == ["As-deposited", "Corroded", "β-SiC", "Graphite"]
    phase_lines = [line for line in ax.lines if line.get_linestyle() == "--"]
    assert {to_hex(line.get_color()) for line in phase_lines}.isdisjoint(TAB10[:2])  # 避开曲线颜色

    with pytest.warns(UserWarning, match=r"phase_colors has no color for \['Graphite'\]"):
        fig, axes = plotter.plot_pattern_static(
            xrd_patterns, subplots=True, references=references, phase_colors={"β-SiC": "black"}, show=False,
        )
    assert axes[0, 0].get_legend().get_title().get_text() == "As-deposited"

    fig = plotter.plot_pattern_interactive(xrd_patterns, references=references)
    assert len(fig.layout.shapes) == 3
    assert [t.name for t in fig.data][-2:] == ["β-SiC", "Graphite"]


def test_xrd_references_format():
    with pytest.raises(TypeError, match="references must be"):
        XRDPlotter().plot_pattern_interactive({}, references={"β-SiC": 35.6})


# ============================================================
# 配色与样式
# ============================================================
def test_palette_global_and_per_call(surveys):
    fig, ax = XPSPlotter(palette="Set2").plot_survey_static(surveys, show=False)
    assert line_colors(ax) == [to_hex(c) for c in matplotlib.color_sequences["Set2"][:2]]

    fig, ax = XPSPlotter(palette="Set2").plot_survey_static(surveys, palette=["black"], show=False)
    assert line_colors(ax) == ["#000000", "#000000"]


def test_default_palette_can_be_changed(surveys, monkeypatch):
    monkeypatch.setattr(color_tables, "DEFAULT_PALETTE", "Dark2")
    fig, ax = RamanPlotter().plot_spectrum_static(
        {"a": surveys["As-deposited"].rename(columns={"Binding Energy (eV)": "Raman Shift (cm-1)"})},
        show=False,
    )
    assert line_colors(ax) == [to_hex(matplotlib.color_sequences["Dark2"][0])]


def test_palette_rejects_dict(surveys):
    with pytest.raises(TypeError, match="sample_colors"):
        XPSPlotter().plot_survey_static(surveys, palette={"As-deposited": "black"}, show=False)


def test_style_does_not_change_global_settings(c1s, surveys):
    before = dict(plt.rcParams)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        XPSPlotter().plot_element_static(c1s, show=False)
        XPSPlotter().plot_survey_static(surveys, subplots=True, show=False)
    assert all(plt.rcParams[key] == value for key, value in before.items())


def test_info(capsys, c1s, f1s_raw):
    XPSPlotter.info({"C 1s": c1s, "F 1s": f1s_raw})
    out = capsys.readouterr().out
    assert "[C 1s]\nType: fit" in out and "[F 1s]\nType: raw" in out
