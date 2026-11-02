# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
计算工具：SRIM 损伤（dpa）和注入离子浓度。

左栏：读取的 SRIM 文件、注量（直接给出，或束流 × 时间）、各层的原子密度；中间：深度分布的交互图
（损伤 / 注入离子，可以按元素显示）；右栏：峰值、平均值等结果，导出数据、复制为代码、出版图。
计算都调用 GMA.SC.SRIM；读取的文件内容保存在标签状态中（随项目保存），换了电脑也能重新计算。
"""
from __future__ import annotations

import asyncio
import traceback
from pathlib import Path
from typing import ClassVar

import flet as ft

from ...CM.common.palette import palette_colors
from ...SC.SRIM import (
    DPA,
    IONS_PERCENT,
    SRIMFileError,
    average,
    centroid,
    depth_profile,
    element_column,
    parse_range,
    parse_vacancy,
    peak,
)
from ...SC.SRIM.damage import check_same_run
from ...SC.SRIM.reader import read_text
from .. import theme as th
from ..components import widgets as w
from ..components.chart import SpectrumChart
from ..components.figure_dialog import FigureDialog
from ..services import tools
from ..services.figures import FigureOptions, ProfileRequest
from ..services.spectra import PEAK_COLOR, Mark, Series
from ..services.text import sci
from ..strings import S
from .tool_view import ToolView

SIDE_W = 296
NARROW = 1040   # 内容宽度小于这个值时上下排列
# 改了这些输入时标记项目有未保存的修改；显示方式（单位、显示哪条曲线等）不算
INPUTS = {"vacancy", "range", "mode", "fluence", "flux", "hours", "densities"}


class SRIMView(ToolView):
    DEFAULTS: ClassVar[dict] = {
        "vacancy": None,        # {"name", "path", "text"}：读取的 VACANCY.txt
        "range": None,          # 同上：RANGE.txt
        "mode": "fluence",      # fluence：直接给出注量；flux：束流 × 时间
        "fluence": 1e16,        # ions/cm²
        "flux": 1e12,           # ions/(cm²·s)
        "hours": 1.0,
        "densities": [],        # 各层的原子密度，None 为文件中的值
        "unit": "nm",           # 深度单位：A / nm / um
        "show": "dpa",          # 交互图：dpa / ions
        "elements": False,      # Full Cascade：按元素显示 dpa
        "window": [None, None],  # 平均 dpa 的深度范围（nm）
        "figure": {},
        "figure_parts": {"damage": True, "ions": True, "elements": False},
    }

    def __init__(self, app, session, workspace, spec, state):
        super().__init__(app, session, workspace, spec, state)
        self.vacancy = self._restore("vacancy", parse_vacancy)
        self.ions = self._restore("range", parse_range)
        if self.st["unit"] not in tools.DEPTH_UNITS:
            self.st["unit"] = "nm"
        self.profile = None
        self.used_ions = None          # 参与计算的 RANGE.txt（与 VACANCY.txt 不是同一次计算时为 None）
        self.warning = ""
        self.plot_size = None
        self.width = None
        self.chart: SpectrumChart | None = None
        self.chart_box = ft.Container(expand=True)
        self.results = ft.Column(spacing=10)
        self.avg_text = ft.Text("")
        self.fluence_text = ft.Text("")
        self.warning_box = ft.Container()

    def _restore(self, key: str, parse):
        entry = self.st.get(key)
        if not isinstance(entry, dict) or not isinstance(entry.get("text"), str):
            self.st[key] = None
            return None
        try:
            return parse(entry["text"], entry.get("name", ""))
        except (SRIMFileError, ValueError):
            self.st[key] = None
            return None

    # ============================================================
    # 计算
    # ============================================================
    @property
    def base(self):
        return self.vacancy if self.vacancy is not None else self.ions

    def inputs(self) -> tools.SRIMInputs:
        return tools.SRIMInputs(
            vacancy_path=(self.st["vacancy"] or {}).get("path") if self.vacancy is not None else None,
            range_path=(self.st["range"] or {}).get("path") if self.used_ions is not None else None,
            mode=self.st["mode"], fluence=float(self.st["fluence"]), flux=float(self.st["flux"]),
            hours=float(self.st["hours"]), densities=self.densities())

    def densities(self) -> list:
        n = len(self.base.layers) if self.base is not None else 0
        values = list(self.st["densities"])[:n] + [None] * max(0, n - len(self.st["densities"]))
        return [v if isinstance(v, (int, float)) and v > 0 else None for v in values]

    def compute(self) -> None:
        self.profile, self.used_ions, self.warning = None, self.ions, ""
        if self.base is None:
            return
        if self.vacancy is not None and self.ions is not None:
            try:
                check_same_run(self.vacancy, self.ions)
            except ValueError:
                self.used_ions, self.warning = None, S.SRIM_MISMATCH
        try:
            self.profile = depth_profile(self.vacancy, self.used_ions, fluence=self.inputs().total_fluence,
                                         densities=self.densities())
        except ValueError as exc:
            self.warning = str(exc)

    # ============================================================
    # 界面
    # ============================================================
    def build(self) -> ft.Control:
        self.compute()
        p = self.p
        if self.base is None:
            return self.empty(S.SRIM_EMPTY_TITLE, S.SRIM_EMPTY_HINT, ft.FilledButton(
                S.SRIM_CHOOSE, icon=ft.Icons.FILE_OPEN_OUTLINED, tooltip=S.SRIM_CHOOSE_TIP,
                on_click=lambda e: self.app.page.run_task(self.choose_files)))
        width = self.width or (self.app.page.width or 1400) - 24
        narrow = width < NARROW
        self.avg_text = ft.Text("", size=15, weight=ft.FontWeight.W_600, color=p.text, selectable=True)
        self.fluence_text = ft.Text("", size=th.SIZE_SMALL, color=p.muted)
        compact = ft.ButtonStyle(padding=ft.Padding.symmetric(horizontal=10))
        footer = ft.Row([
            ft.OutlinedButton(S.COPY_CODE, icon=ft.Icons.CODE_ROUNDED, on_click=self.copy_code, expand=True,
                              style=compact),
            ft.FilledButton(S.EXPORT_PROFILE, icon=ft.Icons.DOWNLOAD_ROUNDED, on_click=self.export, expand=True,
                            style=compact),
        ], spacing=8)
        left = self.card(S.CONDITIONS, self.input_controls(), width=None if narrow else SIDE_W, fill=not narrow)
        right = self.card(S.RESULTS, [self.warning_box, self.results], width=None if narrow else SIDE_W,
                          footer=footer, fill=not narrow)
        center = self.card(self.title(), [self.toolbar(), self.chart_box], scroll=False, expand=True)
        self.fill(update=False)
        if narrow:
            body = ft.Column([ft.Container(content=center, height=460), left, right], spacing=12,
                             scroll=ft.ScrollMode.AUTO, expand=True)
        else:
            body = ft.Row([left, center, right], spacing=12, expand=True,
                          vertical_alignment=ft.CrossAxisAlignment.STRETCH)
        return ft.Container(content=body, padding=12, expand=True, on_size_change=self.on_size,
                            size_change_interval=200)

    def on_size(self, e: ft.LayoutSizeChangeEvent) -> None:
        old, self.width = self.width, e.width
        if old is not None and (old < NARROW) != (e.width < NARROW):
            self.redraw()

    def title(self) -> str:
        base = self.base
        return f"{base.ion} {base.energy:g} keV → {' / '.join(layer.name for layer in base.layers)}"

    # ---------- 左栏 ----------
    def input_controls(self) -> list[ft.Control]:
        p = self.p
        controls = [self.section(S.SRIM_FILES, w.ghost_button(S.SRIM_CHOOSE, ft.Icons.FILE_OPEN_OUTLINED,
                                                              lambda e: self.app.page.run_task(self.choose_files), p,
                                                              tooltip=S.SRIM_CHOOSE_TIP)),
                    self.file_row("vacancy", "VACANCY.txt", self.vacancy),
                    self.file_row("range", S.SRIM_RANGE_OPTIONAL, self.ions)]
        # 注量
        mode = ft.SegmentedButton(
            selected=[self.st["mode"]], show_selected_icon=False,
            segments=[ft.Segment(value="fluence", label=S.FLUENCE_DIRECT), ft.Segment(value="flux", label=S.FLUENCE_FLUX)],
            on_change=lambda e: self.set("mode", (e.control.selected or ["fluence"])[0], rebuild=True))
        controls += [self.section(S.FLUENCE), mode]
        if self.st["mode"] == "flux":
            controls += [
                self.number_field(self.st["flux"], lambda v: self.set("flux", v), label=S.FLUX, suffix="ions/(cm²·s)"),
                self.number_field(self.st["hours"], lambda v: self.set("hours", v), label=S.IRRADIATION_TIME,
                                  suffix="h"),
                self.fluence_text,
            ]
        else:
            controls.append(self.number_field(self.st["fluence"], lambda v: self.set("fluence", v), label=S.FLUENCE,
                                              suffix="ions/cm²"))
        # 各层的原子密度
        controls.append(self.section(S.ATOMIC_DENSITY))
        overrides = self.densities()
        for i, layer in enumerate(self.base.layers):
            def changed(v, i=i):
                self.set_density(i, v)

            elements = "·".join(layer.elements)
            restore = w.icon_button(ft.Icons.RESTART_ALT_ROUNDED, S.RESTORE_FILE_VALUE.format(value=sci(layer.density)),
                                    lambda e, i=i: self.set_density(i, None, rebuild=True), p, size=16,
                                    disabled=overrides[i] is None)
            controls.append(ft.Row([
                self.number_field(overrides[i] if overrides[i] is not None else layer.density, changed,
                                  label=f"{layer.name}（{elements}）" if elements else layer.name,
                                  suffix="atoms/cm³", expand=True),
                restore], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER))
        controls.append(w.faint(S.DENSITY_HINT, p, th.SIZE_TINY))
        formula = S.SRIM_FORMULA + ("\n" + S.SRIM_FORMULA_FULL if self.vacancy is not None and not self.vacancy.quick
                                    else "")
        controls += [w.hsep(p), w.faint(formula, p, th.SIZE_TINY, selectable=True)]
        return controls

    def file_row(self, key: str, title: str, table) -> ft.Control:
        p = self.p
        entry = self.st[key] or {}
        if table is None:
            return ft.Row([ft.Icon(ft.Icons.DESCRIPTION_OUTLINED, size=18, color=p.faint),
                           ft.Column([w.text(title, p, th.SIZE_BODY), w.faint(S.SRIM_NOT_LOADED, p)],
                                     spacing=1, tight=True, expand=True)],
                          spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER)
        mode = S.SRIM_MODE_QUICK if table.quick else S.SRIM_MODE_FULL
        ions = f"{table.ions_calculated:,.0f}".replace(",", " ") if table.ions_calculated else "—"
        summary = S.SRIM_SUMMARY.format(ion=table.ion, energy=f"{table.energy:g}",
                                        target=" / ".join(layer.name for layer in table.layers), mode=mode, ions=ions)
        return ft.Row([
            ft.Icon(ft.Icons.DESCRIPTION_OUTLINED, size=18, color=p.primary),
            ft.Column([w.text(entry.get("name") or title, p, th.SIZE_BODY, bold=True, max_lines=1,
                              tooltip=entry.get("path")),
                       w.muted(f"{table.ion} {table.energy:g} keV · {mode}", p, th.SIZE_TINY, max_lines=1,
                               tooltip=summary)], spacing=1, tight=True, expand=True),
            w.icon_button(ft.Icons.CLOSE_ROUNDED, S.SRIM_REMOVE, lambda e: self.remove(key), p, size=16),
        ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER)

    # ---------- 中间 ----------
    def toolbar(self) -> ft.Control:
        p = self.p
        has_dpa, has_ions = tools.has_columns(self.profile)
        show = self.shown()
        segments = [ft.Segment(value="dpa", label=S.SHOW_DAMAGE, disabled=not has_dpa),
                    ft.Segment(value="ions", label=S.SHOW_IONS, disabled=not has_ions)]
        parts: list[ft.Control] = [ft.SegmentedButton(
            selected=[show], show_selected_icon=False, segments=segments,
            on_change=lambda e: self.set("show", (e.control.selected or ["dpa"])[0], rebuild=True))]
        if self.vacancy is not None and not self.vacancy.quick and show == "dpa":
            parts.append(ft.Row([ft.Switch(value=self.st["elements"], scale=0.85,
                                           on_change=lambda e: self.set("elements", bool(e.control.value))),
                                 w.text(S.BY_ELEMENT, p, th.SIZE_SMALL)], spacing=2, tight=True,
                                tooltip=S.BY_ELEMENT_TIP))
        parts += [
            ft.Container(expand=True),
            ft.SegmentedButton(
                selected=[self.st["unit"]], show_selected_icon=False, tooltip=S.DEPTH_UNIT,
                segments=[ft.Segment(value=k, label=v[0]) for k, v in tools.DEPTH_UNITS.items()],
                on_change=lambda e: self.set("unit", (e.control.selected or ["nm"])[0], rebuild=True)),
            ft.OutlinedButton(S.FIGURE, icon=ft.Icons.IMAGE_OUTLINED, on_click=lambda e: self.open_figure(),
                              disabled=self.profile is None),
        ]
        return ft.Row(parts, spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER)

    def shown(self) -> str:
        has_dpa, has_ions = tools.has_columns(self.profile)
        if self.st["show"] == "ions" and has_ions or not has_dpa:
            return "ions"
        return "dpa"

    def series(self) -> tuple[list[Series], str]:
        profile, factor = self.profile, tools.unit_factor(self.st["unit"])
        x = profile["Depth (nm)"].to_numpy(dtype=float) * factor
        if self.shown() == "ions":
            color = palette_colors(2, self.palette)[1]
            return [Series("ions", f"{self.base.ion} (at.%)", color,
                           x, profile[IONS_PERCENT].to_numpy(dtype=float))], f"{self.base.ion} (at.%)"
        symbols = list(self.vacancy.element_vacancies()) if self.st["elements"] and self.vacancy is not None else []
        colors = palette_colors(2 + len(symbols), self.palette)
        out = [Series("dpa", "dpa", colors[0], x, profile[DPA].to_numpy(dtype=float), width=1.8)]
        for symbol, color in zip(symbols, colors[2:], strict=False):
            out.append(Series(symbol, symbol, color, x, profile[element_column(symbol)].to_numpy(dtype=float),
                              dash=[5, 4], width=1.2))
        return out, "Damage (dpa)"

    def marks(self) -> list[Mark]:
        """多层靶：各层之间的界面画成竖线，标签是下面一层的名称。"""
        factor, layers = tools.unit_factor(self.st["unit"]), self.base.layers
        return [Mark(x * factor, layers[i + 1].name if i + 1 < len(layers) else "", PEAK_COLOR)
                for i, x in enumerate(self.profile.attrs.get("interfaces", []))]

    def fill(self, update: bool = True) -> None:
        """重新计算后：交互图、结果、提示。"""
        p = self.p
        if self.profile is None:
            self.chart = None
            self.chart_box.content = ft.Container(content=w.muted(self.warning, p, th.SIZE_BODY), expand=True,
                                                  alignment=ft.Alignment.CENTER)
        else:
            chart = SpectrumChart(p, on_hover=self.workspace.set_readout, size=self.plot_size,
                                  on_resize=lambda w_, h: setattr(self, "plot_size", (w_, h)))
            series, y_label = self.series()
            unit = tools.unit_label(self.st["unit"])
            chart.set_data(series, x_label=f"Depth ({unit})", y_label=y_label, x_unit=unit, marks=self.marks())
            self.chart = chart
            self.chart_box.content = chart.control
        self.warning_box.content = self.note(self.warning, p.warning, ft.Icons.WARNING_AMBER_ROUNDED) \
            if self.warning and self.profile is not None else None
        self.results.controls = self.result_controls()
        if self.st["mode"] == "flux":
            self.fluence_text.value = S.FLUENCE_RESULT.format(value=sci(self.inputs().total_fluence))
        if update:
            for c in (self.chart_box, self.warning_box, self.results, self.fluence_text):
                if c.page is not None:
                    c.update()

    # ---------- 右栏 ----------
    def depth(self, nm: float) -> str:
        unit, factor = tools.unit_label(self.st["unit"]), tools.unit_factor(self.st["unit"])
        value = nm * factor
        text = f"{value:.0f}" if abs(value) >= 100 else f"{value:.3g}"
        return f"{text} {unit}"

    def result_controls(self) -> list[ft.Control]:
        p, profile = self.p, self.profile
        if profile is None:
            return []
        has_dpa, has_ions = tools.has_columns(profile)
        out: list[ft.Control] = [self.section(S.DAMAGE)]
        if has_dpa:
            value, depth = peak(profile)
            out += [self.value_row(S.PEAK_VALUE, f"{value:.4g} dpa", strong=True),
                    self.value_row(S.AT_DEPTH, self.depth(depth))]
            if self.st["mode"] == "flux":
                seconds = self.st["hours"] * 3600
                out.append(self.value_row(S.DPA_RATE, f"{sci(value / seconds)} dpa/s"))
            out.append(self.average_controls())
            reported = self.vacancy.reported_vacancies
            check = f"{self.vacancy.vacancies_per_ion():,.0f}".replace(",", " ")
            if reported:
                check = S.VACANCIES_CHECK.format(value=check, reported=f"{reported:,.0f}".replace(",", " "))
            out.append(self.value_row(S.VACANCIES_PER_ION, check, stacked=True))
        else:
            out.append(w.faint(S.NEED_VACANCY, p, th.SIZE_SMALL))
        out.append(self.section(S.IMPLANTED))
        if has_ions:
            value, depth = peak(profile, IONS_PERCENT)
            out += [self.value_row(S.PEAK_VALUE, S.CONCENTRATION_VALUE.format(
                        percent=f"{value:.3g}", appm=f"{value * 1e4:,.0f}".replace(",", " ")), strong=True),
                    self.value_row(S.AT_DEPTH, self.depth(depth))]
            ions = self.used_ions
            if ions.mean_range:
                rng = S.RANGE_VALUE.format(value=self.depth(ions.mean_range / 10),
                                           straggling=self.depth(ions.straggling / 10)) if ions.straggling \
                    else self.depth(ions.mean_range / 10)
            else:
                rng = self.depth(centroid(profile))
            out += [self.value_row(S.MEAN_RANGE, rng, stacked=bool(ions.straggling)),
                    self.value_row(S.STOPPED, f"{ions.stopped_fraction() * 100:.1f} %")]
        else:
            out.append(w.faint(S.NEED_RANGE, p, th.SIZE_SMALL))
        out += [self.section(S.CONDITIONS), w.muted(self.conditions_text(), p, th.SIZE_SMALL, selectable=True)]
        return out

    def average_controls(self) -> ft.Control:
        """平均 dpa：深度范围的两个输入框（当前单位，留空为整个范围）和结果。"""
        p = self.p
        unit, factor = self.st["unit"], tools.unit_factor(self.st["unit"])
        start, end = self.st["window"]

        def setter(index):
            def on_value(v):
                window = list(self.st["window"])
                window[index] = None if v is None else v / factor
                self.st["window"] = window
                self.update_average()
            return on_value

        def field(value, index, hint):
            return self.number_field(None if value is None else round(value * factor, 6), setter(index), width=92,
                                     hint=hint, allow_empty=True, positive=False)

        self.update_average(update=False)
        return ft.Column([
            ft.Row([ft.Text(S.AVERAGE, size=th.SIZE_BODY, color=p.muted, expand=True), self.avg_text]),
            ft.Row([field(start, 0, "0"), ft.Text("–", color=p.muted), field(end, 1, S.AVERAGE_END_HINT),
                    w.faint(tools.unit_label(unit), p, th.SIZE_SMALL)],
                   spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER, tooltip=S.AVERAGE_RANGE_TIP),
        ], spacing=4, tight=True)

    def update_average(self, update: bool = True) -> None:
        start, end = self.st["window"]
        try:
            self.avg_text.value = f"{average(self.profile, DPA, start, end):.4g} dpa"
            self.avg_text.color = self.p.text
        except (ValueError, KeyError):
            self.avg_text.value = "—"
            self.avg_text.color = self.p.faint
        if update and self.avg_text.page is not None:
            self.avg_text.update()

    def conditions_text(self) -> str:
        base = self.base
        lines = [f"{base.ion} {base.energy:g} keV · {S.FLUENCE} {sci(self.inputs().total_fluence)} ions/cm²"]
        for layer, override in zip(base.layers, self.densities(), strict=True):
            lines.append(f"{layer.name}：{sci(override or layer.density)} atoms/cm³")
        return "\n".join(lines)

    # ============================================================
    # 修改
    # ============================================================
    def set(self, key: str, value, *, rebuild: bool = False) -> None:
        if self.st[key] != value and key in INPUTS:
            self.touch()
        self.st[key] = value
        if rebuild:
            self.redraw()
        else:
            self.compute()
            self.fill()

    def set_density(self, index: int, value, *, rebuild: bool = False) -> None:
        densities = self.densities()
        densities[index] = value
        self.set("densities", densities, rebuild=rebuild)

    def remove(self, key: str) -> None:
        self.touch()
        self.st[key] = None
        if key == "vacancy":
            self.vacancy = None
        else:
            self.ions = None
        if self.base is None:
            self.st["densities"] = []
        self.redraw()

    async def choose_files(self) -> None:
        files = await self.app.file_picker.pick_files(
            dialog_title=S.SRIM_CHOOSE.rstrip("…"), allow_multiple=True, file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["txt", "TXT"])
        paths = [Path(f.path) for f in files or [] if f.path]
        if paths:
            await self.load(paths)

    async def load(self, paths: list[Path]) -> None:
        """读取选择的文件，按内容判断是 VACANCY.txt 还是 RANGE.txt；同一文件夹中的另一个文件一起读取。"""
        loaded: dict[str, tuple] = {}
        errors = []
        for path in paths:
            result = await asyncio.to_thread(read_srim, path)
            if isinstance(result, Exception):
                errors.append(S.FILE_ERROR.format(name=path.name, error=S.SRIM_NOT_SRIM.format(name=path.name)))
                continue
            loaded[result[0]] = (path, *result[1:])
        also = []
        for kind, partner in (("vacancy", "range"), ("range", "vacancy")):
            if kind in loaded and partner not in loaded:
                sibling = find_sibling(loaded[kind][0], "RANGE.txt" if partner == "range" else "VACANCY.txt")
                if sibling is not None:
                    result = await asyncio.to_thread(read_srim, sibling)
                    if not isinstance(result, Exception) and result[0] == partner:
                        loaded[partner] = (sibling, *result[1:])
                        also.append(sibling.name)
        old_layers = [layer.name for layer in self.base.layers] if self.base is not None else None
        if loaded:
            self.touch()
        for kind, (path, text, table) in loaded.items():
            self.st[kind] = {"name": path.name, "path": str(path), "text": text}
            if kind == "vacancy":
                self.vacancy = table
            else:
                self.ions = table
        if self.base is not None and [layer.name for layer in self.base.layers] != old_layers:
            self.st["densities"] = []
            self.st["window"] = [None, None]
        if "range" in loaded and "vacancy" not in loaded and self.vacancy is None:
            self.st["show"] = "ions"
        self.redraw()
        if errors:
            self.app.show_error(S.SRIM_READ_FAILED, "\n".join(errors))
        elif also:
            self.app.toast(S.SRIM_ALSO_READ.format(name="、".join(also)))

    # ============================================================
    # 导出、代码、出版图
    # ============================================================
    def info_rows(self) -> list[tuple[str, str]]:
        base, inputs = self.base, self.inputs()
        rows = [("VACANCY.txt", inputs.vacancy_path or "—"), ("RANGE.txt", inputs.range_path or "—"),
                ("Ion", base.ion), ("Energy (keV)", f"{base.energy:g}"),
                ("Calculation", S.SRIM_MODE_QUICK if base.quick else S.SRIM_MODE_FULL),
                ("Fluence (ions/cm2)", f"{inputs.total_fluence:.6g}")]
        if inputs.mode == "flux":
            rows += [("Flux (ions/(cm2*s))", f"{inputs.flux:.6g}"), ("Time (h)", f"{inputs.hours:g}")]
        for layer, override in zip(base.layers, self.densities(), strict=True):
            rows.append((f"Atomic density, {layer.name} (atoms/cm3)", f"{override or layer.density:.6g}"))
        rows.append(("Formula", S.SRIM_FORMULA.replace("\n", "; ")))
        return rows

    async def export(self, e=None) -> None:
        if self.profile is None:
            self.app.toast(S.NOTHING_TO_EXPORT)
            return
        fmt = "csv" if self.app.settings.export_format == "csv" else "xlsx"
        name = tools.safe_name(f"SRIM_{self.base.ion}_{self.base.energy:g}keV")
        path = await self.app.file_picker.save_file(dialog_title=S.EXPORT_PROFILE.rstrip("…"),
                                                    file_name=f"{name}.{fmt}", file_type=ft.FilePickerFileType.CUSTOM,
                                                    allowed_extensions=["xlsx", "csv"])
        if not path:
            return
        path = Path(path)
        if path.suffix.lower() not in (".xlsx", ".csv"):
            path = path.with_name(f"{path.name}.{fmt}")
        try:
            await asyncio.to_thread(tools.export_profile, self.profile, path, self.st["unit"], self.info_rows())
        except Exception as exc:  # noqa: BLE001
            self.app.show_error(S.EXPORT_FAILED, str(exc), traceback.format_exc())
            return
        self.app.toast(S.EXPORTED_TO.format(path=path))

    async def copy_code(self, e=None) -> None:
        if self.profile is None:
            return
        await self.app.clipboard.set(tools.srim_code(self.inputs(), tuple(self.st["window"])))
        self.app.toast(S.CODE_COPIED)

    async def on_shortcut(self, key: str, shift: bool) -> bool:
        if key == "i":
            await self.choose_files()
            return True
        if key == "e" and self.profile is not None:
            self.open_figure()
            return True
        return False

    def figure_options(self) -> FigureOptions:
        s = self.app.settings
        return FigureOptions.from_dict(self.st["figure"], font=s.figure_font, font_size=float(s.figure_font_size),
                                       dpi=int(s.dpi), format=s.figure_format)

    def save_figure_options(self, options: FigureOptions) -> None:
        self.st["figure"] = options.to_dict()

    def figure_parts(self) -> dict:
        parts = {"damage": True, "ions": True, "elements": False, **self.st["figure_parts"]}
        has_dpa, has_ions = tools.has_columns(self.profile)
        if not (has_dpa and parts["damage"]) and not (has_ions and parts["ions"]):
            parts["damage"], parts["ions"] = has_dpa, has_ions   # 至少画一种
        return parts

    def figure_request(self, options: FigureOptions) -> ProfileRequest:
        parts = self.figure_parts()
        kwargs = {"depth_unit": self.st["unit"], "damage": parts["damage"], "concentration": parts["ions"]}
        if parts["elements"] and self.vacancy is not None and not self.vacancy.quick:
            kwargs["elements"] = True
        kwargs.update({"show_legend": options.legend, "legend_loc": options.legend_loc,
                       "hide_y_ticks": options.hide_y_ticks})
        return ProfileRequest("SRIM", "plot_profile_static", [], [], kwargs, frame=self.profile,
                              setup=tools.srim_setup(self.inputs(), imports={"SRIMPlotter"}),
                              stem=tools.safe_name(f"SRIM_{self.base.ion}_{self.base.energy:g}keV"))

    def figure_controls(self, dialog, section, row) -> list[ft.Control]:
        """出版图对话框中 SRIM 自己的选项：画哪些曲线。"""
        has_dpa, has_ions = tools.has_columns(self.profile)
        parts = self.figure_parts()

        def toggle(key):
            def on_change(e):
                self.st["figure_parts"] = {**parts, key: bool(e.control.value)}
                dialog.refresh()
            return on_change

        controls = [section(S.FIGURE_PARTS),
                    row(S.FIGURE_DAMAGE, ft.Switch(value=parts["damage"] and has_dpa, disabled=not has_dpa,
                                                   on_change=toggle("damage"))),
                    row(S.FIGURE_IONS, ft.Switch(value=parts["ions"] and has_ions, disabled=not has_ions,
                                                 on_change=toggle("ions")))]
        if self.vacancy is not None and not self.vacancy.quick:
            controls.append(row(S.FIGURE_ELEMENT_DPA, ft.Switch(value=parts["elements"], disabled=not parts["damage"],
                                                             on_change=toggle("elements"))))
        return controls

    def open_figure(self) -> None:
        if self.profile is None:
            return
        FigureDialog(self, self.title()).show()


# ============================================================
# 读取文件（在线程中运行）
# ============================================================
def read_srim(path: Path):
    """读取一个 SRIM 文件：返回 (类型, 文件内容, 表) 或读取时的异常。"""
    try:
        text = read_text(path)
    except OSError as exc:
        return exc
    for kind, parse in (("vacancy", parse_vacancy), ("range", parse_range)):
        try:
            return kind, text, parse(text, path.name)
        except (SRIMFileError, ValueError) as exc:
            error = exc
    return error


def find_sibling(path: Path, name: str) -> Path | None:
    """同一文件夹中名为 name 的文件（不区分大小写）。"""
    try:
        for candidate in path.parent.iterdir():
            if candidate.name.lower() == name.lower() and candidate.is_file():
                return candidate
    except OSError:
        return None
    return None
