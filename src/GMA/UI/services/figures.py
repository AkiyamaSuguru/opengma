# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
出版图：把界面上的选项翻译成 GMA Plotter 的参数，生成图片（方案 6.3）。

- 只调用 GMA 已有的出版图函数（谱线图 plot_survey_static、plot_spectrum_static、plot_pattern_static，
  拟合谱图 plot_element_static、plot_fit_static，计算工具的 SRIMPlotter.plot_profile_static），
  预览就是导出的图片；
- 字体：系统中没有所选字体时（如 Linux 上通常没有 Times New Roman），用随应用附带的、字宽相同的
  Liberation 字体代替；中文（如样品名）用随应用附带的 Noto Sans SC 显示（方案 11.2）；
- 每次生成后关闭 matplotlib 的 figure，避免内存不断增长（方案 6.6）。

这里不依赖 flet；界面进程中导入 flet_charts 会把 matplotlib 的后端换成 Flet 专用的后端，
所以生成图片前换回 Agg。
"""
from __future__ import annotations

import io
import math
import warnings
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
from matplotlib import font_manager

from ...CM.common.style import DEFAULT_FONT_FAMILY, DEFAULT_FONT_SIZE, mpl_style
from ...CM.Raman import RamanPlotter
from ...CM.XPS import XPSPlotter
from ...CM.XRD import XRDPlotter
from ...project import Record
from ...SC.SRIM import SRIMPlotter
from .spectra import Display, component_colors, overlay_colors, overlay_labels

FONT_DIR = Path(__file__).resolve().parents[1] / "assets" / "fonts"
CJK_FONT = "Noto Sans SC"
# 系统中没有这些字体时，用随应用附带的、字宽相同的字体代替
SUBSTITUTES = {"Times New Roman": "Liberation Serif", "Times": "Liberation Serif",
               "Arial": "Liberation Sans", "Helvetica": "Liberation Sans"}
FALLBACK_FONT = "DejaVu Sans"  # matplotlib 自带
# 出版图字体的候选（设置和出版图对话框中的下拉框）；也可以在设置中写其他已安装的字体
FIGURE_FONTS = ("Times New Roman", "Arial", "Helvetica", "Liberation Serif", "Liberation Sans", "DejaVu Serif",
                "DejaVu Sans")

SIZE_PRESETS = {"single": (3.2, 2.4), "double": (7.0, 2.6)}  # 英寸：单栏、双栏
FORMATS = ("png", "svg", "pdf", "tiff", "jpg")
HTML = "html"  # 交互 HTML（plotly）
LEGEND_LOCS = ("best", "upper right", "upper left", "lower left", "lower right", "center right", "center left",
               "upper center", "lower center")
PLOTTERS = {"XPS": XPSPlotter, "Raman": RamanPlotter, "XRD": XRDPlotter, "SRIM": SRIMPlotter}
# 各方法的谱线图（可以叠加、标峰位）和拟合谱图（画分峰）；XRD 没有拟合谱图
LINE_FUNCTIONS = {"XPS": "plot_survey_static", "Raman": "plot_spectrum_static", "XRD": "plot_pattern_static"}
FIT_FUNCTIONS = {"XPS": "plot_element_static", "Raman": "plot_fit_static"}
INTERACTIVE = {"plot_survey_static": "plot_survey_interactive", "plot_spectrum_static": "plot_spectrum_interactive",
               "plot_pattern_static": "plot_pattern_interactive", "plot_element_static": "plot_element_interactive",
               "plot_fit_static": "plot_fit_interactive"}
# 交互图（plotly）接受的参数；出版图专用的参数（图例位置、子图等）不传
_FIT_INTERACTIVE = {"component_colors", "component_mode", "raw_color", "raw_line_color", "fit_color", "bg_color",
                    "component_alpha", "hide_y_ticks", "palette"}
_LINE_INTERACTIVE = {"palette", "sample_colors", "peaks", "offset", "normalize", "hide_y_ticks"}
INTERACTIVE_KWARGS = {
    "plot_element_interactive": _FIT_INTERACTIVE,
    "plot_fit_interactive": _FIT_INTERACTIVE,
    "plot_survey_interactive": _LINE_INTERACTIVE,
    "plot_spectrum_interactive": _LINE_INTERACTIVE,
    "plot_pattern_interactive": _LINE_INTERACTIVE | {"references", "phase_colors"},
}


@dataclass
class FigureOptions:
    """出版图对话框中的选项，保存在模块标签的状态中。"""

    size: str = "single"            # single / double / custom
    width: float = 3.2              # 自定义尺寸（英寸）
    height: float = 2.4
    font: str = DEFAULT_FONT_FAMILY
    font_size: float = DEFAULT_FONT_SIZE
    legend: bool = True
    legend_loc: str = "best"
    hide_y_ticks: bool = False
    component_alpha: float = 0.35
    n_cols: int = 0                 # 子图列数；0 表示自动
    subplots: bool = False          # 叠加视图中每条谱各占一个子图
    format: str = "png"
    dpi: int = 600

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d, **defaults) -> FigureOptions:
        options = cls(**defaults)
        d = d if isinstance(d, dict) else {}
        for f in fields(cls):
            if f.name not in d:
                continue
            value, default = d[f.name], getattr(options, f.name)
            try:
                if isinstance(default, bool):
                    value = bool(value)
                elif isinstance(default, int):
                    value = int(value)
                elif isinstance(default, float):
                    value = float(value)
                else:
                    value = str(value)
            except (TypeError, ValueError):
                continue
            setattr(options, f.name, value)
        options.size = options.size if options.size in (*SIZE_PRESETS, "custom") else "single"
        options.format = options.format if options.format in (*FORMATS, HTML) else "png"
        options.legend_loc = options.legend_loc if options.legend_loc in LEGEND_LOCS else "best"
        options.width = min(max(options.width, 0.5), 30.0)
        options.height = min(max(options.height, 0.5), 30.0)
        options.font_size = min(max(options.font_size, 4.0), 40.0)
        options.component_alpha = min(max(options.component_alpha, 0.0), 1.0)
        options.n_cols = min(max(options.n_cols, 0), 6)
        options.dpi = min(max(options.dpi, 50), 2400)
        return options


@dataclass
class PlotRequest:
    """要画的图：调用哪个 Plotter 方法、传入哪些谱图和参数。出版图和“复制为代码”共用。"""

    method: str                     # 表征方法，如 "XPS"
    function: str                   # Plotter 方法名，如 "plot_element_static"
    records: list[Record]
    keys: list[str]                 # 多条谱时字典的键；单条谱时为 []
    kwargs: dict                    # 除数据和尺寸、字体以外的绘图参数
    panels: int = 1                 # 子图个数（决定默认尺寸）
    interactive: str | None = None  # 对应的交互图（plotly）方法；没有时不能导出 HTML

    @property
    def single(self) -> bool:
        return not self.keys

    def data(self):
        if self.single:
            return self.records[0].to_dataframe()
        return {k: r.to_dataframe() for k, r in zip(self.keys, self.records, strict=True)}


@dataclass
class ProfileRequest(PlotRequest):
    """
    计算工具（如 SRIM）的出版图：数据由工具页算好后直接给出，不在项目中。
    “复制为代码”时，setup 是读取文件、计算数据并赋给 data 的那几行代码。
    """

    frame: object = None                            # 要画的 DataFrame
    setup: list[str] = field(default_factory=list)  # 生成 data 的代码
    stem: str = "figure"                            # 导出文件的默认文件名

    @property
    def single(self) -> bool:
        return True

    def data(self):
        return self.frame


# ============================================================
# 从界面状态生成 PlotRequest
# ============================================================
def uses_fit(record: Record) -> bool:
    """这条谱图用拟合谱图函数画：XPS 元素谱（拟合与否都是），Raman 拟合谱；其余用谱线图函数。"""
    if record.method == "XPS":
        return record.kind == "element"
    return record.fitted and record.method in FIT_FUNCTIONS


def supports_marks(view: str, records: list[Record], options: FigureOptions | None = None) -> bool:
    """这张图用谱线图函数画，可以标峰位（XRD 还可以标参考物相）。"""
    if not records:
        return False
    if view == "overlay":
        return True
    if view == "side" and len(records) > 1:
        return not (records[0].method in FIT_FUNCTIONS and any(uses_fit(r) for r in records))
    return not uses_fit(records[0])


def make_request(view: str, records: list[Record], displays: list[Display], options: FigureOptions,
                 palette=None, *, normalize: bool = False, offset: float = 0.0, peaks: dict | None = None,
                 references: dict | None = None, phase_colors: dict | None = None) -> PlotRequest:
    """
    view：single（当前谱图）、overlay（叠加）、side（并排）。displays 与 records 一一对应。
    peaks（{标签: 位置}）和 XRD 的 references（{物相名: {晶面指数: 2θ}}）、phase_colors 只用于谱线图。
    """
    if not records:
        raise ValueError("No spectrum to plot.")
    method = records[0].method
    style = {"show_legend": options.legend, "legend_loc": options.legend_loc,
             "hide_y_ticks": options.hide_y_ticks}
    marks = {}
    if peaks:
        marks["peaks"] = dict(peaks)
    if references and method == "XRD":
        marks["references"] = {k: dict(v) for k, v in references.items()}
        if phase_colors:
            marks["phase_colors"] = dict(phase_colors)
    line = LINE_FUNCTIONS[method]

    if view == "single" or len(records) == 1 and view != "overlay":
        record, display = records[0], displays[0]
        if uses_fit(record):
            function = FIT_FUNCTIONS[method]
            kwargs = {**element_kwargs(record, display, palette, options), **style}
            return PlotRequest(method, function, [record], [], kwargs, interactive=INTERACTIVE[function])
        kwargs = {**style, **marks}
        if display.color:
            kwargs["palette"] = [display.color]
        return PlotRequest(method, line, [record], [], kwargs, interactive=INTERACTIVE[line])

    keys = overlay_labels(records)
    if view == "overlay":
        colors = overlay_colors(keys, displays, palette)
        kwargs = {"sample_colors": dict(zip(keys, colors, strict=True)), **style, **marks}
        if normalize:
            kwargs["normalize"] = True
        if offset and not options.subplots:
            kwargs["offset"] = float(offset)
        if options.subplots:
            kwargs["subplots"] = True
            kwargs["n_cols"] = n_cols(options, len(records))
        return PlotRequest(method, line, records, keys, kwargs,
                           panels=len(records) if options.subplots else 1,
                           interactive=None if options.subplots else INTERACTIVE[line])

    # 并排：每条谱一个子图。有拟合谱时用拟合谱图函数（分峰），否则用谱线图函数的子图
    if method in FIT_FUNCTIONS and any(uses_fit(r) for r in records):
        merged: dict[str, str] = {}
        for record, display in zip(records, displays, strict=True):
            for name, color in component_colors(record, display, palette).items():
                merged.setdefault(name, color)
        first = displays[0]
        kwargs = {"component_colors": merged, "component_mode": records[0].component_mode,
                  "raw_color": first.raw_color, "fit_color": first.fit_color, "bg_color": first.bg_color,
                  "component_alpha": options.component_alpha, "n_cols": n_cols(options, len(records)), **style}
        return PlotRequest(method, FIT_FUNCTIONS[method], records, keys, kwargs, panels=len(records))
    colors = overlay_colors(keys, displays, palette)
    kwargs = {"sample_colors": dict(zip(keys, colors, strict=True)), "subplots": True,
              "n_cols": n_cols(options, len(records)), **style, **marks}
    return PlotRequest(method, line, records, keys, kwargs, panels=len(records))


def element_kwargs(record: Record, display: Display, palette, options: FigureOptions) -> dict:
    if not record.fitted:
        return {"raw_line_color": display.color} if display.color else {}
    return {"component_colors": component_colors(record, display, palette),
            "component_mode": record.component_mode, "raw_color": display.raw_color,
            "fit_color": display.fit_color, "bg_color": display.bg_color,
            "component_alpha": options.component_alpha}


def n_cols(options: FigureOptions, panels: int) -> int:
    """子图列数：自动时单栏排成一列，双栏和自定义每行最多 3 个。"""
    if options.n_cols:
        return min(options.n_cols, panels)
    return 1 if options.size == "single" else min(3, panels)


def figure_size(options: FigureOptions, panels: int = 1) -> tuple[float, float]:
    """整张图的尺寸（英寸）。单栏、双栏是整张图的宽度；有多行子图时高度按行数增加。"""
    if options.size == "custom":
        return round(options.width, 2), round(options.height, 2)
    width, height = SIZE_PRESETS[options.size]
    rows = math.ceil(panels / n_cols(options, panels)) if panels > 1 else 1
    return width, round(height * rows, 2)


def mixed_modes(records: list[Record]) -> bool:
    """并排的元素谱中，拟合谱的分峰数据模式不一致（出版图只能用一种）。"""
    return len({r.component_mode for r in records if r.fitted}) > 1


# ============================================================
# 字体
# ============================================================
_registered = False


def register_fonts() -> None:
    """把随应用附带的字体登记给 matplotlib（只做一次）。"""
    global _registered
    if _registered:
        return
    for path in sorted(FONT_DIR.glob("*.[ot]tf")):
        try:
            font_manager.fontManager.addfont(str(path))
        except (OSError, RuntimeError, ValueError):
            continue
    _registered = True


def font_available(name: str) -> bool:
    register_fonts()
    try:
        font_manager.findfont(font_manager.FontProperties(family=name), fallback_to_default=False)
    except ValueError:
        return False
    return True


def resolve_font(name: str) -> tuple[str, str | None]:
    """返回 (实际使用的字体, 代替时的说明对象)。说明对象为被代替的字体名，没有代替时为 None。"""
    if font_available(name):
        return name, None
    substitute = SUBSTITUTES.get(name)
    if substitute and font_available(substitute):
        return substitute, name
    return FALLBACK_FONT, name


# ============================================================
# 生成图片
# ============================================================
@dataclass
class RenderResult:
    data: bytes | None          # 没有写文件时的图片内容
    path: Path | None
    font: str                   # 实际使用的字体
    substituted: str | None     # 被代替的字体（系统中没有）
    warnings: list[str]


def _use_agg() -> None:
    if matplotlib.get_backend().lower() != "agg":
        plt.switch_backend("Agg")


def render(request: PlotRequest, options: FigureOptions, *, fmt: str | None = None, dpi: int | None = None,
           path: Path | str | None = None, palette=None, use_latex: bool = False) -> RenderResult:
    """
    生成图片。path 为 None 时返回图片内容（预览），否则写入文件（导出）。
    fmt 为 None 时用 options.format；dpi 为 None 时用 options.dpi。
    """
    fmt = (fmt or options.format).lower()
    dpi = int(dpi or options.dpi)
    if fmt == HTML:
        return _render_html(request, options, path, palette)
    if fmt not in FORMATS:
        raise ValueError(f"Unknown figure format {fmt!r}.")
    _use_agg()
    font, substituted = resolve_font(options.font)
    families = [font, CJK_FONT]  # 所选字体里没有的字（如中文样品名）用 Noto Sans SC
    plotter = PLOTTERS[request.method](font_family=families, font_size=options.font_size,
                                       palette=palette, use_latex=use_latex)
    caught: list[str] = []
    fig = None
    try:
        with warnings.catch_warnings(record=True) as records:
            warnings.simplefilter("always")
            fig, _ = getattr(plotter, request.function)(
                request.data(), figsize=figure_size(options, request.panels), show=False, **request.kwargs)
            target = io.BytesIO() if path is None else Path(path)
            # 在出版图样式中保存，与 GMA 自己保存（save_path）时完全相同
            with mpl_style(families, options.font_size, use_latex):
                fig.savefig(target, format="jpeg" if fmt == "jpg" else fmt, dpi=dpi, bbox_inches="tight")
            caught = list(dict.fromkeys(str(w.message) for w in records))
    finally:
        if fig is not None:
            plt.close(fig)
    if path is None:
        return RenderResult(target.getvalue(), None, font, substituted, caught)
    return RenderResult(None, Path(path), font, substituted, caught)


def _render_html(request: PlotRequest, options: FigureOptions, path, palette) -> RenderResult:
    """交互 HTML（plotly），离线也能打开（附带 plotly.js）。并排和子图没有对应的交互图。"""
    if request.interactive is None:
        raise ValueError("This figure has no interactive (HTML) version.")
    if path is None:
        raise ValueError("HTML export needs a file path.")
    plotter = PLOTTERS[request.method](font_family=options.font, palette=palette)
    allowed = INTERACTIVE_KWARGS[request.interactive]
    kwargs = {k: v for k, v in request.kwargs.items() if k in allowed}
    fig = getattr(plotter, request.interactive)(request.data(), **kwargs)
    fig.write_html(str(path), include_plotlyjs=True)
    return RenderResult(None, Path(path), options.font, None, [])
