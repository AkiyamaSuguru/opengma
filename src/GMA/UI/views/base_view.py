# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
表征方法模块页的三栏模板（方案 6）：左栏数据、中间交互图和数据表、右栏检查器。

XPS、Raman、XRD 的谱图结构很接近，主要区别在横轴，所以三个模块共用这个模板，每个模块只提供
自己的读取器、数据类型、筛选和显示选项（与 GMA 中各方法共用 common 绘图实现的思路一样）。

每个标签各自保存选择和显示设置（方案 4.3），保存项目时写进界面状态；改名、删除、分峰名等修改的是
项目数据，先改项目，再刷新界面（设计原则“数据优先于界面状态”）。
"""
from __future__ import annotations

import asyncio
import traceback
from pathlib import Path

import flet as ft

from ...CM.common.palette import assign_colors
from ...project import (
    GENERIC_READER,
    ProjectError,
    export_csv,
    export_excel,
    read_table,
)
from .. import theme as th
from ..components import widgets as w
from ..components.chart import SpectrumChart
from ..components.columns_dialog import ColumnsDialog
from ..components.data_panel import DataPanel
from ..components.data_table import DataTable
from ..components.dialogs import (
    confirm,
    edit_fields,
    edit_names,
    pick_color,
    prompt_text,
)
from ..components.figure_dialog import FigureDialog
from ..components.import_dialog import ImportDialog
from ..components.inspector import Inspector
from ..components.tables_dialog import PeakTablesDialog, PhasesDialog
from ..services import analysis, codegen, figures, importing
from ..services.figures import FigureOptions
from ..services.spectra import (
    MAX_SIDE,
    PEAK_COLOR,
    VIEWS,
    Display,
    Mark,
    component_colors,
    is_color,
    overlay_colors,
    overlay_labels,
    overlay_series,
    point_counts,
    single_series,
)
from ..services.text import plain_label
from ..strings import S
from .base import TabView
from .registry import ModuleSpec

LEFT_W, RIGHT_W = 282, 332
NARROW_RIGHT, NARROW_LEFT = 1080, 820  # 窗口内容宽度小于这些值时自动收起右栏、左栏


class MethodView(TabView):
    # 子类设置：左栏的类型筛选、可以导入的文件后缀、读取器（第一个为默认）、是否有参考物相（XRD）
    FILTERS: tuple[tuple[str, str], ...] = (("all", S.FILTER_ALL),)
    SUFFIXES: tuple[str, ...] = ()
    READERS: tuple[str, ...] = ()
    PHASES = False

    # ---------- 子类可以改写：类型筛选、左栏标签、标题旁的类型 ----------
    def matches(self, record, key: str) -> bool:
        """左栏的类型筛选：key 为 FILTERS 中的键，"all" 以外默认按数据类型（record.kind）。"""
        return key == "all" or record.kind == key

    def badge(self, record) -> str:
        """左栏条目右侧的小标签。"""
        return S.BADGE_FITTED.format(n=len(record.components)) if record.fitted else S.BADGE_RAW

    def kind_label(self, record) -> str:
        """标题旁的数据类型。"""
        return S.CHIP_FIT if record.fitted else S.CHIP_LINE

    def side_records(self, records):
        """并排视图中显示的谱图（XPS 只并排元素谱）。"""
        return records

    def __init__(self, app, session, workspace, spec: ModuleSpec, state: dict):
        super().__init__(app, session, workspace)
        self.spec = spec
        self.st = self.load_state(state)
        self.displays: dict[str, Display] = {
            rid: Display.from_dict(d) for rid, d in (self.st.pop("display", None) or {}).items()}
        self.panel = DataPanel(self)
        self.inspector = Inspector(self)
        self.table = DataTable(self, self.st["table"])
        self.chart: SpectrumChart | None = None
        self.plot_size: tuple[float, float] | None = None      # 上一张交互图的绘图区尺寸
        self.compact_size: tuple[float, float] | None = None   # 并排小图的绘图区尺寸
        self.center = ft.Container(expand=True)
        self.points_text = ft.Text("", size=th.SIZE_SMALL, color=app.p.faint)
        self.left = ft.Container()
        self.right = ft.Container()
        self.width = 0.0

    # ============================================================
    # 状态
    # ============================================================
    def load_state(self, state: dict) -> dict:
        st = dict(state or {})
        st.setdefault("current", None)
        st["checked"] = [str(r) for r in st.get("checked") or []]
        st["view"] = st.get("view") if st.get("view") in VIEWS else "single"
        keys = [k for k, _ in self.FILTERS]
        st["filter"] = st.get("filter") if st.get("filter") in keys else "all"
        st["search"] = str(st.get("search") or "")
        st["sample"] = st.get("sample") or None
        st["collapsed"] = [str(s) for s in st.get("collapsed") or []]
        overlay = st.get("overlay") if isinstance(st.get("overlay"), dict) else {}
        st["overlay"] = {"normalize": bool(overlay.get("normalize")), "offset": _float(overlay.get("offset"), 0.0),
                         "x_range": overlay.get("x_range")}
        st["inspector"] = st.get("inspector") if st.get("inspector") in ("display", "analysis", "info") else "display"
        st["table"] = st.get("table") if isinstance(st.get("table"), dict) else {}
        st["figure"] = st.get("figure") if isinstance(st.get("figure"), dict) else {}
        st["peak_table"] = st.get("peak_table") if isinstance(st.get("peak_table"), str) else None
        st["hidden_phases"] = [str(x) for x in st.get("hidden_phases") or []]
        colors = st.get("phase_colors") if isinstance(st.get("phase_colors"), dict) else {}
        st["phase_colors"] = {str(k): v for k, v in colors.items() if is_color(v)}
        st["left"] = st.get("left", True) is not False
        st["right"] = st.get("right", True) is not False
        return st

    def state(self) -> dict:
        ids = {r.record_id for r in self.records()}
        out = dict(self.st)
        out["checked"] = [r for r in self.st["checked"] if r in ids]
        out["display"] = {rid: d.to_dict() for rid, d in self.displays.items() if rid in ids and d.to_dict()}
        return out

    def open_with(self, state: dict) -> None:
        """从项目总览跳转过来（如只看某个样品）：更新状态后刷新。"""
        if state.get("sample"):
            self.st["sample"] = state["sample"]
            sample_records = [r for r in self.records() if r.sample == state["sample"]]
            if sample_records and (self.current() is None or self.current().sample != state["sample"]):
                self.st["current"] = sample_records[0].record_id
        self.invalidate()

    @property
    def view_mode(self) -> str:
        return self.st["view"]

    @property
    def palette(self):
        return self.app.settings.color_cycle or None

    def selection(self) -> str:
        """状态栏中的选择：勾选了谱图时显示“已选 n / 总数 条谱图”。"""
        total = len(self.records())
        n = len([r for r in self.st["checked"] if r in self.project.records])
        return S.SELECTED_SPECTRA.format(n=n, total=total) if n else ""

    # ============================================================
    # 数据
    # ============================================================
    def records(self):
        return self.project.records_of(method=self.spec.method)

    def filtered(self):
        st, query = self.st, self.st["search"].casefold()
        out = []
        for r in self.records():
            if not self.matches(r, st["filter"]):
                continue
            if st["sample"] and r.sample != st["sample"]:
                continue
            if query and query not in r.sample.casefold() and query not in r.name.casefold():
                continue
            out.append(r)
        return out

    def grouped(self):
        """[(样品名, [谱图...])]，样品按项目中的顺序。"""
        groups: dict[str, list] = {}
        order = {name: i for i, name in enumerate(self.project.samples)}
        for r in self.filtered():
            groups.setdefault(r.sample, []).append(r)
        return sorted(groups.items(), key=lambda kv: order.get(kv[0], len(order)))

    def current_id(self) -> str | None:
        rid = self.st["current"]
        if rid in self.project.records and self.project.records[rid].method == self.spec.method:
            return rid
        first = next(iter(self.filtered()), None) or next(iter(self.records()), None)
        self.st["current"] = first.record_id if first else None
        return self.st["current"]

    def current(self):
        rid = self.current_id()
        return self.project.records.get(rid) if rid else None

    def checked_records(self):
        """勾选的谱图，按左栏中的顺序。"""
        ids = set(self.st["checked"])
        return [r for _, items in self.grouped() for r in items if r.record_id in ids] or \
               [r for r in self.records() if r.record_id in ids]

    def view_records(self):
        """中间显示的谱图：单谱为当前谱图；叠加、并排为勾选的谱图（没有勾选时为当前谱图）。"""
        current = self.current()
        if self.view_mode == "single":
            return [current] if current else []
        records = self.checked_records() or ([current] if current else [])
        if self.view_mode == "side":
            return self.side_records(records)[:MAX_SIDE]
        return records

    def display(self, rid: str) -> Display:
        if rid not in self.displays:
            self.displays[rid] = Display()
        return self.displays[rid]

    def component_colors(self, record) -> dict[str, str]:
        return component_colors(record, self.display(record.record_id), self.palette)

    def line_color(self, record) -> str:
        if self.view_mode == "overlay":
            records = self.view_records()
            if record in records:
                labels = overlay_labels(records)
                colors = overlay_colors(labels, [self.display(r.record_id) for r in records], self.palette)
                return colors[records.index(record)]
        return self.display(record.record_id).color or (single_series(record, Display(), self.palette)[0].color)

    def same_name_records(self, record):
        """其他样品中同一方法、同名的谱图（如各样品的 C1s）。"""
        return [r for r in self.records() if r.name == record.name and r.sample != record.sample]

    # ============================================================
    # 界面
    # ============================================================
    def build(self) -> ft.Control:
        p = self.p
        # 先生成中间的交互图，检查器中的坐标范围取自交互图
        self.center.content = self.center_content()
        self.left.content = self.panel.build()
        self.right.content = self.inspector.build()
        for box, width in ((self.left, LEFT_W), (self.right, RIGHT_W)):
            box.width = width
            box.bgcolor, box.border = p.panel, ft.Border.all(1, p.border)
            box.border_radius, box.padding = th.RADIUS_PANEL, ft.Padding.all(12) if box is self.left else None
        self.left.visible, self.right.visible = self.st["left"], self.st["right"]
        center = ft.Container(content=self.center, expand=True, bgcolor=p.panel, border=ft.Border.all(1, p.border),
                              border_radius=th.RADIUS_PANEL, clip_behavior=ft.ClipBehavior.ANTI_ALIAS)
        return ft.Container(content=ft.Row([self.left, center, self.right], spacing=12, expand=True,
                                           vertical_alignment=ft.CrossAxisAlignment.STRETCH),
                            padding=12, expand=True, on_size_change=self.on_size, size_change_interval=200)

    def on_size(self, e: ft.LayoutSizeChangeEvent) -> None:
        """窗口较窄时自动收起左右栏（只在变窄的那一刻收起；之后仍然可以手动打开）。"""
        old, self.width = self.width, e.width
        changed = False
        if old >= NARROW_RIGHT > e.width and self.st["right"]:
            self.st["right"], changed = False, True
        if old >= NARROW_LEFT > e.width and self.st["left"]:
            self.st["left"], changed = False, True
        if changed:
            self.apply_panels()

    def apply_panels(self) -> None:
        self.left.visible, self.right.visible = self.st["left"], self.st["right"]
        self.left.update()
        self.right.update()

    def toggle_panel(self, side: str) -> None:
        self.st[side] = not self.st[side]
        self.apply_panels()

    def refresh_center(self) -> None:
        self.center.content = self.center_content()
        self.center.update()

    def refresh_all(self) -> None:
        """数据变了（导入、改名、删除）：重画三栏。"""
        self.panel.refresh()
        self.refresh_center()
        self.inspector.refresh()
        self.workspace.set_status()

    # ---------- 中间 ----------
    def center_content(self) -> ft.Control:
        p = self.p
        records = self.view_records()
        if not self.records():
            return self.empty_state()
        if not records:
            return ft.Container(content=w.faint(S.SELECT_A_SPECTRUM, p, th.SIZE_BODY), alignment=ft.Alignment.CENTER,
                                expand=True)
        current = self.current()
        self.table.set_frame(current.to_dataframe() if current else None,
                             current.spec.x_column if current else "")
        return ft.Column([
            ft.Container(content=self.header(records), padding=ft.Padding.only(left=18, right=14, top=12)),
            ft.Container(content=self.toolbar(), padding=ft.Padding.only(left=14, right=14, top=6, bottom=4)),
            w.hsep(p),
            ft.Container(content=self.chart_area(records), expand=True,
                         padding=ft.Padding.only(left=6, right=18, top=12, bottom=8)),
            w.hsep(p),
            self.table.control,
        ], spacing=0, expand=True)

    def header(self, records) -> ft.Control:
        p = self.p
        mode = self.view_mode
        if mode == "single":
            r = records[0]
            chips = [self.kind_chip(r)]
            if r.fitted:
                chips.append(w.chip(S.CHIP_PEAKS.format(n=len(r.components)), p))
            chips.append(w.chip(S.CHIP_POINTS.format(n=f"{r.point_count:,}".replace(",", " ")), p))
            title = [ft.Text(r.name, size=18, weight=ft.FontWeight.W_700, color=p.text, max_lines=1,
                             overflow=ft.TextOverflow.ELLIPSIS),
                     ft.Text(r.sample, size=th.SIZE_BODY, color=p.muted, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                     *chips]
        else:
            text = S.OVERLAY_TITLE if mode == "overlay" else S.SIDE_TITLE
            title = [ft.Text(text.format(n=len(records)), size=16, weight=ft.FontWeight.W_700, color=p.text)]
            hint = S.VIEW_HINT_OVERLAY if mode == "overlay" else S.VIEW_HINT_SIDE.format(n=MAX_SIDE)
            if mode == "side" and len(self.checked_records()) > MAX_SIDE:
                hint = S.SIDE_LIMIT.format(n=MAX_SIDE)
            title.append(w.faint(hint, p, th.SIZE_SMALL))
        views = ft.SegmentedButton(
            selected=[mode], show_selected_icon=False, on_change=self.on_view,
            segments=[ft.Segment(value="single", label=S.VIEW_SINGLE), ft.Segment(value="overlay", label=S.VIEW_OVERLAY),
                      ft.Segment(value="side", label=S.VIEW_SIDE)])
        return ft.Row([ft.Row(title, spacing=10, expand=True, vertical_alignment=ft.CrossAxisAlignment.CENTER,
                              wrap=True), views], vertical_alignment=ft.CrossAxisAlignment.CENTER)

    def kind_chip(self, record) -> ft.Control:
        return w.chip(self.kind_label(record), self.p)

    def toolbar(self) -> ft.Control:
        p, page = self.p, self.app.page

        def button(text, icon, on_click, tooltip=None):
            return ft.OutlinedButton(text, icon=icon, on_click=on_click, tooltip=tooltip,
                                     style=ft.ButtonStyle(padding=ft.Padding.symmetric(horizontal=12)))

        export = ft.PopupMenuButton(
            content=ft.Container(content=ft.Row([ft.Icon(ft.Icons.TABLE_VIEW_OUTLINED, size=16, color=p.primary),
                                                 ft.Text(S.EXPORT_DATA_MENU, size=th.SIZE_SMALL, color=p.primary,
                                                         weight=ft.FontWeight.W_600),
                                                 ft.Icon(ft.Icons.EXPAND_MORE_ROUNDED, size=16, color=p.primary)],
                                                spacing=6, tight=True),
                                 border=ft.Border.all(1, p.border), border_radius=20,
                                 padding=ft.Padding.symmetric(horizontal=12, vertical=7)),
            menu_position=ft.PopupMenuPosition.UNDER,
            items=[ft.PopupMenuItem(content=label, on_click=lambda e, s=scope, f=fmt: page.run_task(
                self.export_data, s, f)) for label, scope, fmt in self.export_choices(data=True)])
        return ft.Row([
            button(S.FIGURE, ft.Icons.IMAGE_OUTLINED, lambda e: self.open_figure(),
                   S.SHORTCUT_HINT.format(action=S.FIGURE_TITLE, keys="Ctrl+E")),
            export,
            button(S.COPY_CODE, ft.Icons.CODE_ROUNDED, lambda e: page.run_task(self.copy_code)),
            ft.Container(expand=True),
            self.points_text,
            w.icon_button(ft.Icons.VIEW_SIDEBAR_OUTLINED, S.TOGGLE_LEFT, lambda e: self.toggle_panel("left"), p,
                          size=17),
            w.icon_button(ft.Icons.TUNE_ROUNDED, S.TOGGLE_RIGHT, lambda e: self.toggle_panel("right"), p, size=17),
        ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER)

    def empty_state(self) -> ft.Control:
        p, page = self.p, self.app.page
        return ft.Container(expand=True, alignment=ft.Alignment.CENTER, content=ft.Column([
            w.module_tile(self.spec, p.dark, 64, 36),
            w.text(S.MODULE_EMPTY.format(title=self.spec.title), p, th.SIZE_TITLE, bold=True),
            ft.Container(width=420, content=ft.Text(S.MODULE_EMPTY_HINT.format(title=self.spec.title),
                                                    size=th.SIZE_BODY, color=p.muted, text_align=ft.TextAlign.CENTER)),
            w.faint(S.MODULE_FORMATS.format(formats=self.spec.formats), p, th.SIZE_SMALL),
            ft.Row([ft.FilledButton(S.IMPORT_FILES, icon=ft.Icons.UPLOAD_FILE_OUTLINED,
                                    on_click=lambda e: page.run_task(self.import_files)),
                    ft.OutlinedButton(S.IMPORT_FOLDER, icon=ft.Icons.FOLDER_OPEN_OUTLINED,
                                      on_click=lambda e: page.run_task(self.import_folder))],
                   spacing=10, tight=True),
        ], spacing=12, tight=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER))

    # ---------- 交互图 ----------
    def max_points(self) -> int:
        s = self.app.settings
        return int(s.decimate_points) if s.decimate else 0

    def chart_area(self, records) -> ft.Control:
        p = self.p
        axis = records[0].spec.axis
        if self.view_mode == "side" and len(records) > 1:
            self.chart = None
            charts = []
            colors = self.curve_colors(records)
            marks = self.chart_marks(records, colors)
            for r, color in zip(records, colors, strict=True):
                d = self.display(r.record_id)
                if not r.fitted:  # 未拟合的谱用叠加时的颜色，与出版图的子图一致
                    d = d.copy()
                    d.color = color
                chart = SpectrumChart(p, compact=True, title=f"{r.name} · {r.sample}", max_points=self.max_points(),
                                      on_hover=self.on_hover, on_range=lambda lo, hi, rid=r.record_id:
                                      self.remember_range(rid, lo, hi), size=self.compact_size,
                                      on_resize=lambda w, h: setattr(self, "compact_size", (w, h)))
                chart.set_data(single_series(r, d, self.palette), x_label=plain_label(axis.label),
                               reversed=axis.reversed, x_range=d.x_range, y_fixed=d.y_range if d.y_mode == "fixed" else None,
                               hidden=d.hidden, x_unit=r.spec.x_unit, marks=marks)
                charts.append(ft.Container(content=chart.control, col={"xs": 12, "md": 6, "xl": 4}, height=300))
            self.points_text.value = ""
            return ft.Column([ft.ResponsiveRow(charts, spacing=12, run_spacing=12)], scroll=ft.ScrollMode.AUTO,
                             expand=True)
        chart = SpectrumChart(p, max_points=self.max_points(), on_range=self.on_chart_range, on_hover=self.on_hover,
                              on_toggle=self.on_toggle, size=self.plot_size,
                              on_resize=lambda w, h: setattr(self, "plot_size", (w, h)))
        if self.view_mode == "overlay":
            o = self.st["overlay"]
            series = overlay_series(records, [self.display(r.record_id) for r in records], self.palette,
                                    normalize=o["normalize"], offset=o["offset"])
            hidden = [r.record_id for r in records if r.record_id in o.get("hidden", [])]
            chart.set_data(series, x_label=plain_label(axis.label), reversed=axis.reversed, x_range=o.get("x_range"),
                           hidden=hidden, x_unit=records[0].spec.x_unit,  # 纵轴标题与出版图相同，归一化时也不变
                           marks=self.chart_marks(records, [s.color for s in series]))
        else:
            r = records[0]
            d = self.display(r.record_id)
            series = single_series(r, d, self.palette)
            chart.set_data(series, x_label=plain_label(axis.label), reversed=axis.reversed,
                           x_range=d.x_range, y_fixed=d.y_range if d.y_mode == "fixed" else None, hidden=d.hidden,
                           x_unit=r.spec.x_unit, marks=self.chart_marks(records, [s.color for s in series]))
        self.chart = chart
        self.update_points(chart.lo, chart.hi, update=False)
        return chart.control

    def update_points(self, lo: float, hi: float, update: bool = True) -> None:
        if self.chart is None:
            return
        visible, total = point_counts(self.chart.series, lo, hi)
        self.points_text.value = S.SHOWN_POINTS.format(visible=f"{visible:,}".replace(",", " "),
                                                       total=f"{total:,}".replace(",", " "))
        if update:
            self.points_text.update()

    def on_chart_range(self, lo: float, hi: float) -> None:
        chart = self.chart
        full = chart is not None and lo <= chart.xmin and hi >= chart.xmax
        rng = None if full else [lo, hi]
        if self.view_mode == "overlay":
            self.st["overlay"]["x_range"] = rng
        else:
            record = self.current()
            if record is not None:
                self.display(record.record_id).x_range = rng
        self.update_points(lo, hi)
        record = self.current()
        if record is not None:
            self.inspector.set_range_fields(lo, hi, record.spec.axis.reversed)

    def remember_range(self, rid: str, lo: float, hi: float) -> None:
        self.display(rid).x_range = [lo, hi]

    def on_hover(self, text: str) -> None:
        self.workspace.set_readout(text)

    def on_toggle(self, key: str) -> None:
        if self.view_mode == "overlay":
            hidden = self.st["overlay"].setdefault("hidden", [])
        else:
            record = self.current()
            if record is None:
                return
            hidden = self.display(record.record_id).hidden
        if key in hidden:
            hidden.remove(key)
        else:
            hidden.append(key)

    # ============================================================
    # 选择与视图
    # ============================================================
    def select(self, rid: str) -> None:
        if rid == self.st["current"] and self.view_mode == "single":
            return
        self.st["current"] = rid
        self.panel.refresh()
        if self.view_mode == "single" or not self.st["checked"]:
            self.refresh_center()
        else:  # 叠加、并排显示的是勾选的谱图，只换下方的数据表
            self.table.set_frame(self.current().to_dataframe(), self.current().spec.x_column)
            self.table.control.update()
        self.inspector.refresh()

    def set_checked(self, rid: str, value: bool) -> None:
        checked = self.st["checked"]
        if value and rid not in checked:
            checked.append(rid)
        elif not value and rid in checked:
            checked.remove(rid)
        self.panel.refresh()
        self.workspace.set_status()
        if self.view_mode != "single":
            self.refresh_center()
            self.inspector.refresh()

    def clear_checked(self) -> None:
        self.st["checked"] = []
        self.panel.refresh()
        self.workspace.set_status()
        if self.view_mode != "single":
            self.refresh_center()
            self.inspector.refresh()

    def on_view(self, e) -> None:
        self.st["view"] = (e.control.selected or ["single"])[0]
        self.refresh_center()
        self.inspector.refresh()

    # ============================================================
    # 峰位表与参考物相：标在谱线图上（交互图和出版图相同）
    # ============================================================
    def marks_supported(self) -> bool:
        return figures.supports_marks(self.view_mode, self.view_records())

    def peak_marks(self) -> dict[str, float]:
        name = self.st["peak_table"]
        if not name or name not in self.project.peak_tables:
            return {}
        return self.project.peaks(name)

    def shown_phases(self) -> list[str]:
        if not self.PHASES:
            return []
        hidden = set(self.st["hidden_phases"])
        return [ph for ph in self.project.phase_names() if ph not in hidden]

    def curve_colors(self, records=None) -> list[str]:
        """当前视图中各条谱的颜色（未拟合的谱线）：叠加、并排时按通用色卡依次取色。"""
        records = self.view_records() if records is None else records
        if self.view_mode in ("overlay", "side") and len(records) > 1:
            return overlay_colors(overlay_labels(records), [self.display(r.record_id) for r in records], self.palette)
        return [self.line_color(r) for r in records]

    def phase_colors(self, avoid=()) -> dict[str, str]:
        """各物相的颜色：指定的优先，其余按通用色卡取色，并避开谱线的颜色（与 GMA 出版图相同）。"""
        phases = self.project.phase_names()
        if not phases:
            return {}
        colors = assign_colors(phases, self.palette, {k: v for k, v in self.st["phase_colors"].items()
                                                      if k in phases}, avoid=list(avoid))
        return dict(zip(phases, colors, strict=True))

    def chart_marks(self, records, curve_colors) -> list[Mark]:
        if not figures.supports_marks(self.view_mode, records):
            return []
        marks = [Mark(position, label, PEAK_COLOR) for label, position in self.peak_marks().items()]
        phases = self.shown_phases()
        if phases:
            colors = self.phase_colors(curve_colors)
            for row in self.project.reference_phases:
                if row["phase"] in phases:
                    marks.append(Mark(float(row["two_theta"]), row["hkl"], colors[row["phase"]], dashed=True))
        return marks

    def set_peak_table(self, name: str | None) -> None:
        self.st["peak_table"] = name or None
        self.redraw_marks()

    def set_phase_shown(self, phase: str, shown: bool) -> None:
        hidden = self.st["hidden_phases"]
        if shown and phase in hidden:
            hidden.remove(phase)
        elif not shown and phase not in hidden:
            hidden.append(phase)
        self.redraw_marks()

    async def choose_phase_color(self, phase: str) -> None:
        current = self.phase_colors(self.curve_colors()).get(phase, PEAK_COLOR)
        color = await pick_color(self.app.page, self.p, f"{S.CHOOSE_COLOR} · {phase}", current)
        if color is None or color == current:
            return
        # 其他物相的颜色一起记下，不随这个物相换色而变
        self.st["phase_colors"] = {**self.phase_colors(self.curve_colors()), phase: color}
        self.redraw_marks()

    def redraw_marks(self) -> None:
        """峰位表、参考物相变了：交互图只重画标注，不重新发送数据点。"""
        if self.chart is not None and self.view_mode != "side":
            self.chart.set_marks(self.chart_marks(self.view_records(), [s.color for s in self.chart.series]))
        else:
            self.refresh_center()
        self.inspector.refresh()

    async def edit_peak_tables(self) -> None:
        """编辑峰位表；点“确定”后标出对话框中选中的表。"""
        name = await PeakTablesDialog(self).show()
        if name is None:
            return
        self.st["peak_table"] = name or None
        self.session.changed("data", source=self)
        self.redraw_marks()

    async def edit_phases(self) -> None:
        if await PhasesDialog(self).show():
            self.session.changed("data", source=self)
            self.redraw_marks()

    # ============================================================
    # 显示设置
    # ============================================================
    def redraw_chart(self) -> None:
        """显示设置变了，需要重新整理曲线（颜色、分峰模式、归一化等）。"""
        self.refresh_center()

    def x_range_shown(self) -> tuple[float, float]:
        if self.chart is not None:
            return self.chart.lo, self.chart.hi
        record = self.current()
        if record is None:
            return 0.0, 1.0
        x = record.x
        return float(x.min()), float(x.max())

    def set_x_bound(self, which: int, value: float) -> None:
        if self.chart is None:
            return
        record = self.current()
        lo, hi = self.chart.lo, self.chart.hi
        # 输入框按显示的方向排列：XPS 左边是高结合能
        if record is not None and record.spec.axis.reversed:
            which = 1 - which
        if which == 0:
            lo = value
        else:
            hi = value
        if lo > hi:
            lo, hi = hi, lo
        self.chart.set_range(lo, hi)

    def set_y_mode(self, mode: str) -> None:
        record = self.current()
        if record is None or self.chart is None:
            return
        d = self.display(record.record_id)
        if mode == "fixed":
            d.y_mode, d.y_range = "fixed", [self.chart.ylo, self.chart.yhi]
        else:
            d.y_mode, d.y_range = "auto", None
        self.chart.set_y(d.y_range if d.y_mode == "fixed" else None)
        self.inspector.refresh()

    def set_y_bound(self, which: int, value: float) -> None:
        record = self.current()
        if record is None or self.chart is None:
            return
        d = self.display(record.record_id)
        lo, hi = d.y_range or [self.chart.ylo, self.chart.yhi]
        lo, hi = (value, hi) if which == 0 else (lo, value)
        if lo == hi:
            return
        d.y_mode, d.y_range = "fixed", [min(lo, hi), max(lo, hi)]
        self.chart.set_y(d.y_range)

    def set_overlay(self, **values) -> None:
        self.st["overlay"].update(values)
        if self.view_mode == "overlay":
            self.redraw_chart()

    async def choose_component_color(self, record, name: str) -> None:
        colors = self.component_colors(record)
        current = colors[name]
        color = await pick_color(self.app.page, self.p, f"{S.CHOOSE_COLOR} · {name}", current)
        if color is None or color == current:
            return
        # 其他分峰的颜色一起记下：只按色卡顺序取色时，换掉一个分峰的颜色会让后面的分峰跟着换色
        colors[name] = color
        self.display(record.record_id).component_colors = colors
        if self.chart is not None and self.view_mode == "single":
            self.chart.recolor({f"c:{n}": c for n, c in colors.items()})
        else:
            self.redraw_chart()
        self.inspector.refresh()

    async def choose_curve_color(self, record, attr: str) -> None:
        d = self.display(record.record_id)
        current = getattr(d, attr) or self.line_color(record)
        color = await pick_color(self.app.page, self.p, S.CHOOSE_COLOR, current)
        if color is None or color == current:
            return
        if attr == "color" and self.view_mode == "overlay":
            # 叠加中其他谱的颜色一起记下，不随这条谱换色而变
            for other in self.view_records():
                od = self.display(other.record_id)
                od.color = od.color or self.line_color(other)
        setattr(d, attr, color)
        key = {"raw_color": "raw", "fit_color": "fit", "bg_color": "bg"}.get(attr)
        if self.chart is not None and self.view_mode == "single" and key:
            self.chart.recolor({key: color})
        else:
            self.redraw_chart()
        self.inspector.refresh()

    def apply_to_others(self, record) -> None:
        """把当前谱图的显示设置（颜色、坐标范围、纵轴）复制给其他样品的同名谱图。"""
        others = self.same_name_records(record)
        if not others:
            self.app.toast(S.NOTHING_TO_APPLY.format(name=record.name))
            return
        source = self.display(record.record_id)
        for other in others:
            self.displays[other.record_id] = source.copy()
        self.app.toast(S.APPLIED_TO.format(n=len(others)))

    # ============================================================
    # 修改项目数据
    # ============================================================
    def data_changed(self) -> None:
        """改了项目数据：通知其他标签（项目总览等），自己只刷新需要的部分。"""
        self.session.changed("data", source=self)
        self.refresh_all()

    async def rename_components(self, record) -> None:
        labels = [S.COMPONENT_NAME_N.format(n=i + 1, old=n) for i, n in enumerate(record.components)]
        names = await edit_names(self.app.page, self.p, S.RENAME_COMPONENTS, record.components, labels)
        if names is None or names == record.components:
            return
        old = record.components
        try:
            record.rename_components(names)
        except ProjectError as exc:
            self.app.show_error(S.RENAME_COMPONENTS, str(exc))
            return
        self.project.dirty = True
        d = self.display(record.record_id)  # 颜色、隐藏的曲线跟着改名
        d.component_colors = {dict(zip(old, names, strict=True)).get(k, k): v for k, v in d.component_colors.items()}
        d.hidden = [f"c:{dict(zip(old, names, strict=True))[k[2:]]}" if k.startswith("c:") and k[2:] in old else k
                    for k in d.hidden]
        self.data_changed()

    def unify_component_names(self, record) -> None:
        """把当前谱图的分峰名统一到其他样品的同名谱图（分峰数相同的才改）。"""
        changed = skipped = 0
        for other in self.same_name_records(record):
            if len(other.components) != len(record.components):
                skipped += 1
                continue
            if other.components != record.components:
                other.rename_components(record.components)
                changed += 1
        if changed:
            self.project.dirty = True
            self.data_changed()
        message = S.UNIFIED.format(n=changed) + (S.UNIFY_SKIPPED.format(n=skipped) if skipped else "")
        self.app.toast(message)

    def set_component_mode(self, record, mode: str) -> None:
        if mode == record.component_mode:
            return
        record.component_mode = mode
        self.project.dirty = True
        self.session.changed("data", source=self)
        self.redraw_chart()
        self.inspector.refresh()

    async def rename_record(self, rid: str) -> None:
        record = self.project.records.get(rid)
        if record is None:
            return

        def validate(text):
            other = self.project.find_by_name(record.sample, record.method, text)
            return S.NAME_EXISTS if other is not None and other is not record else None

        name = await prompt_text(self.app.page, self.p, S.RENAME_SPECTRUM, S.SPECTRUM_NAME, record.name,
                                 validate=validate)
        if not name or name == record.name:
            return
        self.project.rename_record(rid, name)
        self.data_changed()

    async def move_record(self, rid: str) -> None:
        record = self.project.records.get(rid)
        if record is None:
            return
        sample = await prompt_text(self.app.page, self.p, S.MOVE_TO_SAMPLE.rstrip("…"), S.TARGET_SAMPLE, record.sample)
        if not sample or sample == record.sample:
            return
        self.project.move_record(rid, sample)
        self.data_changed()

    async def remove_records(self, ids: list[str]) -> None:
        records = [self.project.records[r] for r in ids if r in self.project.records]
        if not records:
            return
        if len(records) == 1:
            body = S.REMOVE_SPECTRUM_BODY.format(name=f"{records[0].sample} / {records[0].name}")
        else:
            body = S.REMOVE_CHECKED_BODY.format(n=len(records))
        if not await confirm(self.app.page, self.p, S.REMOVE_SPECTRUM, body, S.DELETE, danger=True):
            return
        for r in records:
            self.project.remove_record(r.record_id)
            self.displays.pop(r.record_id, None)
            if r.record_id in self.st["checked"]:
                self.st["checked"].remove(r.record_id)
        self.data_changed()

    async def edit_sample_info(self, sample: str) -> None:
        info = self.project.samples[sample].info if sample in self.project.samples else {}
        values = await edit_fields(self.app.page, self.p, f"{S.EDIT_SAMPLE_INFO} · {sample}",
                                   self.project.sample_fields, info)
        if values is None:
            return
        changed = False
        for field, value in values.items():
            if info.get(field, "") != value:
                self.project.set_sample_info(sample, field, value)
                changed = True
        if changed:
            self.data_changed()

    async def open_source(self, rid: str) -> None:
        record = self.project.records.get(rid)
        path = Path(record.source.get("path") or "") if record else None
        if not path or not str(path) or not path.exists():
            self.app.toast(S.SOURCE_MISSING.format(path=path or "—"))
            return
        await self.app.open_url(path.parent.as_uri())

    # ============================================================
    # 导入
    # ============================================================
    async def import_files(self) -> None:
        files = await self.app.file_picker.pick_files(
            dialog_title=S.IMPORT_TITLE.format(title=self.spec.title), allow_multiple=True,
            file_type=ft.FilePickerFileType.CUSTOM, allowed_extensions=[s.lstrip(".") for s in self.SUFFIXES])
        paths = [f.path for f in files or [] if f.path]
        if paths:
            await self.inspect_and_import(paths=paths)

    async def import_folder(self) -> None:
        folder = await self.app.file_picker.get_directory_path(dialog_title=S.IMPORT_FOLDER.rstrip("…"))
        if folder:
            await self.inspect_and_import(folder=folder)

    async def import_table(self) -> None:
        """其他软件导出的表格：先选文件，再指定各列的含义（方案 8“通用 CSV 导入”）。"""
        files = await self.app.file_picker.pick_files(
            dialog_title=S.IMPORT_TABLE_TITLE, allow_multiple=True, file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=[s.lstrip(".") for s in importing.TABLE_SUFFIXES])
        paths = [f.path for f in files or [] if f.path]
        if paths:
            await self.import_table_files(paths)

    async def import_table_files(self, paths: list[str]) -> None:
        try:
            table = await asyncio.to_thread(read_table, paths[0])
        except Exception as exc:  # noqa: BLE001 - 读取出错的原因显示给用户
            self.app.show_error(S.IMPORT_FAILED, S.FILE_ERROR.format(name=Path(paths[0]).name, error=exc))
            return
        columns = await ColumnsDialog(self, table, paths).show()
        if columns is not None:
            await self.inspect_and_import(paths=paths, reader=GENERIC_READER, columns=columns)

    async def inspect_and_import(self, *, paths=None, folder=None, reader: str | None = None, columns=None) -> None:
        reader = reader or self.app.settings.readers.get(self.spec.method) or self.READERS[0]
        self.workspace.set_status(S.IMPORTING.format(n=len(paths) if paths else "…"))
        try:
            items = await asyncio.to_thread(importing.inspect, paths, folder, method=self.spec.method, reader=reader,
                                            columns=columns)
        except ProjectError as exc:
            self.workspace.set_status(S.READY)
            self.app.show_error(S.IMPORT_FAILED, str(exc))
            return
        except Exception as exc:  # noqa: BLE001 - 读取出错的原因显示给用户
            self.workspace.set_status(S.READY)
            self.app.show_error(S.IMPORT_FAILED, str(exc), traceback.format_exc())
            return
        self.workspace.set_status(S.READY)
        if not items:
            self.app.toast(S.IMPORT_NOTHING)
            return
        readers = [GENERIC_READER] if reader == GENERIC_READER else self.READERS
        added = await ImportDialog(self, items, folder=folder, readers=readers).show()
        if not added:
            return
        first = added[0]
        self.st["current"] = first.record_id
        self.st["sample"] = None if self.st["sample"] and self.st["sample"] != first.sample else self.st["sample"]
        if self.st["filter"] != "all" and first.kind != self.st["filter"]:
            self.st["filter"] = "all"
        self.session.changed("data", source=self)
        self.redraw()
        self.workspace.set_status()
        self.app.toast(S.IMPORTED.format(n=len(added)))

    # ============================================================
    # 导出、复制、出版图
    # ============================================================
    def export_choices(self, data: bool = False):
        """导出菜单的项：(文字, 范围, 格式)。"""
        out = [(S.EXPORT_CURRENT_CSV, "current", "csv"), (S.EXPORT_CURRENT_EXCEL, "current", "xlsx")]
        if self.st["checked"]:
            out += [(S.EXPORT_CHECKED_CSV, "checked", "csv"), (S.EXPORT_CHECKED_EXCEL, "checked", "xlsx")]
        return out

    def scope_records(self, scope: str):
        if scope == "checked":
            return self.checked_records()
        current = self.current()
        return [current] if current else []

    async def export_data(self, scope: str, fmt: str) -> None:
        records = self.scope_records(scope)
        if not records:
            self.app.toast(S.NOTHING_TO_EXPORT)
            return
        try:
            if fmt == "xlsx":
                name = records[0].name if len(records) == 1 else self.session.name
                path = await self.app.file_picker.save_file(
                    dialog_title=S.EXPORT_DATA, file_name=f"{name}.xlsx", file_type=ft.FilePickerFileType.CUSTOM,
                    allowed_extensions=["xlsx"])
                if not path:
                    return
                path = Path(path).with_suffix(".xlsx")
                await asyncio.to_thread(export_excel, records, path, project=self.project)
                self.app.toast(S.EXPORTED_EXCEL.format(path=path))
            else:
                folder = await self.app.file_picker.get_directory_path(dialog_title=S.EXPORT_DATA)
                if not folder:
                    return
                files = await asyncio.to_thread(export_csv, records, folder)
                self.app.toast(S.EXPORTED_CSV.format(n=len(files), path=folder))
        except Exception as exc:  # noqa: BLE001
            self.app.show_error(S.EXPORT_FAILED, str(exc), traceback.format_exc())

    async def export_analysis(self, scope: str, fmt: str) -> None:
        records = self.scope_records(scope)
        if not records:
            return
        name = f"{records[0].name}_analysis" if len(records) == 1 else f"{self.session.name}_analysis"
        path = await self.app.file_picker.save_file(dialog_title=S.EXPORT, file_name=f"{name}.{fmt}",
                                                    file_type=ft.FilePickerFileType.CUSTOM, allowed_extensions=[fmt])
        if not path:
            return
        try:
            saved = await asyncio.to_thread(analysis.export, records, path, fmt)
        except Exception as exc:  # noqa: BLE001
            self.app.show_error(S.EXPORT_FAILED, str(exc), traceback.format_exc())
            return
        self.app.toast(S.EXPORTED_EXCEL.format(path=saved))

    async def copy_analysis(self, record) -> None:
        try:
            text = analysis.table_text(record, analysis.metrics_for(record))
        except (ValueError, TypeError) as exc:
            self.app.show_error(S.EXPORT_FAILED, str(exc))
            return
        await self.app.clipboard.set(text)
        self.app.toast(S.TABLE_COPIED)

    def figure_options(self) -> FigureOptions:
        s = self.app.settings
        return FigureOptions.from_dict(self.st["figure"], font=s.figure_font, font_size=float(s.figure_font_size),
                                       dpi=int(s.dpi), format=s.figure_format)

    def save_figure_options(self, options: FigureOptions) -> None:
        self.st["figure"] = options.to_dict()

    def figure_request(self, options: FigureOptions):
        records = self.view_records()
        o = self.st["overlay"]
        marks = {}
        if figures.supports_marks(self.view_mode, records):
            peaks = self.peak_marks()
            if peaks:
                marks["peaks"] = peaks
            phases = self.shown_phases()
            if phases:
                colors = self.phase_colors(self.curve_colors(records))
                marks["references"] = self.project.references(phases)
                marks["phase_colors"] = {k: colors[k] for k in phases}
        return figures.make_request(self.view_mode, records, [self.display(r.record_id) for r in records], options,
                                    self.palette, normalize=o["normalize"], offset=o["offset"], **marks)

    def describe(self) -> str:
        records = self.view_records()
        if len(records) == 1:
            return f"{records[0].name} · {records[0].sample}"
        title = S.OVERLAY_TITLE if self.view_mode == "overlay" else S.SIDE_TITLE
        return title.format(n=len(records))

    def open_figure(self) -> None:
        if not self.view_records():
            self.app.toast(S.SELECT_A_SPECTRUM)
            return
        FigureDialog(self, self.describe()).show()

    async def copy_code(self) -> None:
        if not self.view_records():
            self.app.toast(S.SELECT_A_SPECTRUM)
            return
        options = self.figure_options()
        request = self.figure_request(options)
        _, substituted = figures.resolve_font(options.font)
        code = codegen.figure_code(request, options, project_path=self.session.path, dirty=self.session.dirty,
                                   palette=self.palette, use_latex=self.app.settings.latex, substituted=substituted)
        await self.app.clipboard.set(code)
        self.app.toast(S.CODE_COPIED)

    # ============================================================
    # 快捷键
    # ============================================================
    async def on_shortcut(self, key: str, shift: bool) -> bool:
        if key == "i":
            await self.import_files()
            return True
        if key == "e":
            self.open_figure()
            return True
        return False


def _float(value, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
