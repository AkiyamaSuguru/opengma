# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
模块页右栏：检查器（方案 6.5、7.3、7.4）。

- 显示：分峰名（取自数据列，可以重命名）和颜色、分峰数据模式、曲线颜色、坐标范围、叠加设置；
  底部按钮把这些设置应用到其他样品的同名谱图；
- 分析：拟合质量、谱图范围、分峰指标（只用标准数据结构中已有的列计算），可以复制表格、导出；
- 信息：来源文件、读取器、导入时间、文件哈希、清洗报告、仪器元数据。
"""
from __future__ import annotations

import flet as ft

from .. import theme as th
from ..services import analysis
from ..services.importing import note_text
from ..services.text import local_time, unit
from ..strings import S
from . import widgets as w

TABS = [("display", S.TAB_DISPLAY), ("analysis", S.TAB_ANALYSIS), ("info", S.TAB_INFO)]


class Inspector:
    def __init__(self, view):
        self.view = view
        self.body = ft.Container(expand=True)
        self.tabs = ft.Container()
        self.footer = ft.Container()
        self.control = ft.Container()
        # 横轴范围的两个输入框：缩放、平移时只改它们的值，不重建检查器
        self.lo_field: ft.TextField | None = None
        self.hi_field: ft.TextField | None = None

    @property
    def p(self):
        return self.view.p

    @property
    def tab(self) -> str:
        return self.view.st["inspector"]

    def build(self) -> ft.Control:
        self.refresh(update=False)
        self.control.content = ft.Column([self.tabs, ft.Container(content=self.body, expand=True), self.footer],
                                         spacing=0, expand=True)
        return self.control

    def refresh(self, update: bool = True) -> None:
        p = self.p
        tabs = []
        for key, title in TABS:
            selected = key == self.tab
            tabs.append(ft.Container(
                content=ft.Text(title, size=th.SIZE_BODY, color=p.primary if selected else p.muted,
                                weight=ft.FontWeight.W_600 if selected else None),
                padding=ft.Padding.only(left=12, right=12, top=10, bottom=8),
                border=ft.Border.only(bottom=ft.BorderSide(2, p.primary if selected else "#00000000")),
                on_click=lambda e, k=key: self.select(k)))
        self.tabs.content = ft.Container(content=ft.Row(tabs, spacing=4),
                                         border=ft.Border.only(bottom=ft.BorderSide(1, p.border)),
                                         padding=ft.Padding.only(left=6))
        record = self.view.current()
        self.lo_field = self.hi_field = None
        footer = None
        if record is None:
            content = [w.faint(S.SELECT_A_SPECTRUM, p, th.SIZE_SMALL)]
        elif self.tab == "analysis":
            content, footer = self.analysis_page(record)
        elif self.tab == "info":
            content = self.info_page(record)
        else:
            content, footer = self.display_page(record)
        self.body.content = ft.Column(content, spacing=12, scroll=ft.ScrollMode.AUTO, expand=True)
        self.body.padding = ft.Padding.only(left=16, right=14, top=14, bottom=10)
        self.footer.content = footer
        self.footer.padding = ft.Padding.all(12) if footer else None
        self.footer.border = ft.Border.only(top=ft.BorderSide(1, p.border)) if footer else None
        if update:
            for c in (self.tabs, self.body, self.footer):
                c.update()

    def select(self, key: str) -> None:
        self.view.st["inspector"] = key
        self.refresh()

    # ============================================================
    # 小部件
    # ============================================================
    def section(self, title: str, right: ft.Control | None = None) -> ft.Control:
        p = self.p
        parts = [ft.Text(title, size=th.SIZE_SMALL, weight=ft.FontWeight.W_600, color=p.muted)]
        if right is not None:
            parts += [ft.Container(expand=True), right]
        return ft.Row(parts, vertical_alignment=ft.CrossAxisAlignment.CENTER)

    def swatch(self, color: str, tooltip: str, on_click, size: float = 20) -> ft.Control:
        """色块：点击选颜色（方案 7.2）。"""
        return ft.Container(width=size, height=size, border_radius=5, bgcolor=color, tooltip=tooltip,
                            border=ft.Border.all(1, self.p.border), on_click=on_click)

    def number(self, value, on_done, width: float = 86) -> ft.TextField:
        def done(e):
            try:
                on_done(float(e.control.value))
                e.control.error = None
            except ValueError:
                e.control.error = S.NUMBER_REQUIRED
            e.control.update()
        return ft.TextField(value="" if value is None else f"{value:.4g}", width=width, dense=True,
                            text_size=th.SIZE_BODY, on_submit=done, on_blur=done,
                            keyboard_type=ft.KeyboardType.NUMBER,
                            content_padding=ft.Padding.symmetric(horizontal=8, vertical=7))

    def kv(self, key: str, value: str, *, selectable: bool = False) -> ft.Control:
        p = self.p
        return ft.Column([ft.Text(key, size=th.SIZE_TINY, color=p.muted),
                          ft.Text(value or "—", size=th.SIZE_SMALL, color=p.text, selectable=selectable)],
                         spacing=1, tight=True)

    # ============================================================
    # 显示
    # ============================================================
    def display_page(self, record):
        p, view = self.p, self.view
        display = view.display(record.record_id)
        page = view.app.page
        parts: list[ft.Control] = []
        if record.fitted:
            colors = view.component_colors(record)
            items = []
            for name in record.components:
                items.append(ft.Container(
                    content=ft.Row([
                        self.swatch(colors[name], S.CHOOSE_COLOR,
                                    lambda e, n=name: page.run_task(view.choose_component_color, record, n)),
                        ft.Text(name, size=th.SIZE_BODY, color=p.text, expand=True, max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS),
                        w.icon_button(ft.Icons.EDIT_OUTLINED, S.RENAME_COMPONENTS,
                                      lambda e: page.run_task(view.rename_components, record), p, size=15),
                    ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    border=ft.Border.all(1, p.border), border_radius=th.RADIUS_CONTROL,
                    padding=ft.Padding.only(left=10, right=2, top=2, bottom=2)))
            if not items:
                items.append(w.faint(S.NO_COMPONENTS, p))
            parts += [self.section(S.COMPONENTS, w.faint(S.COMPONENT_NAMES_FROM, p)), *items]
            if record.components and view.same_name_records(record):
                parts.append(ft.TextButton(S.UNIFY_NAMES.format(name=record.name), icon=ft.Icons.SYNC_ALT_ROUNDED,
                                           on_click=lambda e: view.unify_component_names(record)))
            mode = ft.SegmentedButton(
                selected=[record.component_mode], show_selected_icon=False,
                on_change=lambda e: view.set_component_mode(record, (e.control.selected or ["absolute"])[0]),
                segments=[ft.Segment(value="absolute", label=S.COMPONENT_ABSOLUTE),
                          ft.Segment(value="relative", label=S.COMPONENT_RELATIVE_SHORT)])
            parts += [self.section(S.COMPONENT_MODE_TITLE), mode, w.faint(S.COMPONENT_MODE_HINT, p)]
            curves = ft.Row([
                ft.Row([self.swatch(c, S.CHOOSE_COLOR,
                                    lambda e, a=attr: page.run_task(view.choose_curve_color, record, a)),
                        w.text(label, p, th.SIZE_SMALL)], spacing=6, tight=True)
                for attr, label, c in (("raw_color", S.RAW_DATA, display.raw_color),
                                       ("fit_color", S.FIT_CURVE, display.fit_color),
                                       ("bg_color", S.BACKGROUND, display.bg_color))], spacing=14, wrap=True)
            parts += [self.section(S.CURVES), curves]
        else:
            color = view.line_color(record)
            parts += [self.section(S.SPECTRUM_COLOR), ft.Row([
                self.swatch(color, S.CHOOSE_COLOR, lambda e: page.run_task(view.choose_curve_color, record, "color")),
                w.text(color.upper(), p, th.SIZE_SMALL)], spacing=8)]

        lo, hi = view.x_range_shown()
        x_unit = unit(record.spec.x_unit)
        self.lo_field = self.number(hi if record.spec.axis.reversed else lo, lambda v: view.set_x_bound(0, v))
        self.hi_field = self.number(lo if record.spec.axis.reversed else hi, lambda v: view.set_x_bound(1, v))
        y_fixed = display.y_mode == "fixed" and display.y_range
        y_mode = ft.SegmentedButton(
            selected=["fixed" if y_fixed else "auto"], show_selected_icon=False,
            on_change=lambda e: view.set_y_mode((e.control.selected or ["auto"])[0]),
            segments=[ft.Segment(value="auto", label=S.Y_AUTO), ft.Segment(value="fixed", label=S.Y_FIXED)])
        parts += [self.section(S.AXES),
                  ft.Row([w.text(S.X_RANGE_UNIT.format(unit=x_unit), p, th.SIZE_BODY, expand=True), self.lo_field,
                          ft.Text("–", color=p.muted), self.hi_field], spacing=6,
                         vertical_alignment=ft.CrossAxisAlignment.CENTER),
                  ft.Row([w.text(S.Y_AXIS, p, th.SIZE_BODY, expand=True), y_mode],
                         vertical_alignment=ft.CrossAxisAlignment.CENTER)]
        if y_fixed:
            ylo, yhi = display.y_range
            parts.append(ft.Row([ft.Container(expand=True), self.number(ylo, lambda v: view.set_y_bound(0, v), 96),
                                 ft.Text("–", color=p.muted), self.number(yhi, lambda v: view.set_y_bound(1, v), 96)],
                                spacing=6))

        if view.marks_supported():
            parts += self.marks_section()

        overlay = view.view_mode == "overlay"
        o = view.st["overlay"]
        parts += [
            ft.Text(S.OVERLAY, size=th.SIZE_SMALL, weight=ft.FontWeight.W_600, color=p.muted if overlay else p.faint),
            ft.Row([w.text(S.NORMALIZE, p, th.SIZE_BODY, color=None if overlay else p.faint, expand=True),
                    ft.Switch(value=bool(o.get("normalize")), disabled=not overlay,
                              on_change=lambda e: view.set_overlay(normalize=bool(e.control.value)))],
                   vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Row([w.text(S.OFFSET, p, th.SIZE_BODY, color=None if overlay else p.faint, expand=True),
                    ft.TextField(value=f"{float(o.get('offset', 0)):g}", width=86, dense=True, disabled=not overlay,
                                 text_size=th.SIZE_BODY, keyboard_type=ft.KeyboardType.NUMBER,
                                 content_padding=ft.Padding.symmetric(horizontal=8, vertical=7),
                                 on_submit=self._offset, on_blur=self._offset)],
                   vertical_alignment=ft.CrossAxisAlignment.CENTER),
        ]
        footer = None
        if view.same_name_records(record):
            footer = ft.OutlinedButton(S.APPLY_TO_OTHERS.format(name=record.name), icon=ft.Icons.LAYERS_OUTLINED,
                                       on_click=lambda e: view.apply_to_others(record), expand=True)
            footer = ft.Row([footer])
        return parts, footer

    def marks_section(self) -> list[ft.Control]:
        """峰位表（所有方法的谱线图）和参考物相（XRD）：选择要标出的，编辑的内容保存在项目中。"""
        p, view = self.p, self.view
        page = view.app.page
        tables = list(view.project.peak_tables)
        current = view.st["peak_table"] if view.st["peak_table"] in tables else ""
        edit_peaks = ft.TextButton(S.EDIT, icon=ft.Icons.EDIT_NOTE_ROUNDED,
                                   on_click=lambda e: page.run_task(view.edit_peak_tables))
        parts: list[ft.Control] = [self.section(S.PEAK_TABLE, edit_peaks)]
        if tables:
            parts.append(ft.Dropdown(
                value=current, dense=True, text_size=th.SIZE_BODY, expand=True,
                options=[ft.DropdownOption(key="", text=S.NO_MARKS)] + [ft.DropdownOption(key=n, text=n) for n in tables],
                on_select=lambda e: view.set_peak_table(e.control.value or None)))
        else:
            parts.append(w.faint(S.NO_PEAK_TABLES, p, th.SIZE_SMALL))
        if view.PHASES:
            edit_phases = ft.TextButton(S.EDIT, icon=ft.Icons.EDIT_NOTE_ROUNDED,
                                        on_click=lambda e: page.run_task(view.edit_phases))
            parts.append(self.section(S.REFERENCE_PHASES, edit_phases))
            phases = view.project.phase_names()
            if not phases:
                parts.append(w.faint(S.NO_PHASES, p, th.SIZE_SMALL))
            colors = view.phase_colors(view.curve_colors()) if phases else {}
            shown = set(view.shown_phases())
            counts = {ph: sum(1 for r in view.project.reference_phases if r["phase"] == ph) for ph in phases}
            for phase in phases:
                parts.append(ft.Row([
                    ft.Checkbox(value=phase in shown, on_change=lambda e, ph=phase: view.set_phase_shown(
                        ph, bool(e.control.value)), width=28, height=28),
                    self.swatch(colors[phase], S.CHOOSE_COLOR, lambda e, ph=phase: page.run_task(
                        view.choose_phase_color, ph), size=16),
                    ft.Text(phase, size=th.SIZE_BODY, color=p.text, expand=True, max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS, tooltip=phase),
                    w.faint(S.N_PLANES.format(n=counts[phase]), p, th.SIZE_SMALL),
                ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER))
        return parts

    def _offset(self, e) -> None:
        try:
            value = float(e.control.value)
            e.control.error = None
        except ValueError:
            e.control.error = S.NUMBER_REQUIRED
            e.control.update()
            return
        e.control.update()
        self.view.set_overlay(offset=value)

    def set_range_fields(self, lo: float, hi: float, reversed_axis: bool) -> None:
        """缩放、平移时更新横轴范围的输入框。"""
        if self.lo_field is None or self.hi_field is None:
            return
        a, b = (hi, lo) if reversed_axis else (lo, hi)
        self.lo_field.value, self.hi_field.value = f"{a:.4g}", f"{b:.4g}"
        self.lo_field.error = self.hi_field.error = None
        self.lo_field.update()
        self.hi_field.update()

    # ============================================================
    # 分析
    # ============================================================
    def analysis_page(self, record):
        p, view = self.p, self.view
        try:
            m = analysis.metrics_for(record)
        except (ValueError, TypeError) as exc:
            return [ft.Text(str(exc), color=p.error, size=th.SIZE_SMALL)], None
        parts: list[ft.Control] = []
        quality = analysis.quality_rows(m)
        if quality:
            tiles = [ft.Container(expand=True, bgcolor=p.subtle, border=ft.Border.all(1, p.border),
                                  border_radius=th.RADIUS_CONTROL, padding=ft.Padding.symmetric(horizontal=10, vertical=8),
                                  content=ft.Column([w.muted(k, p, th.SIZE_TINY),
                                                     ft.Text(v, size=15, weight=ft.FontWeight.W_600, color=p.text)],
                                                    spacing=2, tight=True))
                     for k, v in quality]
            parts += [self.section(S.FIT_QUALITY), ft.Row(tiles, spacing=8)]
        rows = [ft.Row([w.text(k, p, th.SIZE_BODY, expand=True), w.text(v, p, th.SIZE_BODY)])
                for k, v in analysis.spectrum_rows(m, record)]
        parts += [self.section(S.SPECTRUM), *rows]
        components = analysis.component_rows(m)
        if components:
            colors = view.component_colors(record)
            x_unit = unit(record.spec.x_unit)
            widths = (None, 60, 50, 54, 48)  # 分峰名占剩下的宽度

            def cells(values, *, head=False, color=None, bold_last=False):
                out = []
                for i, (value, width) in enumerate(zip(values, widths, strict=True)):
                    text = ft.Text(value, size=th.SIZE_SMALL if head else th.SIZE_BODY,
                                   color=p.muted if head else p.text, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
                                   weight=ft.FontWeight.W_600 if head or (bold_last and i == 4) else None,
                                   text_align=ft.TextAlign.LEFT if i == 0 else ft.TextAlign.RIGHT)
                    if i == 0 and color:
                        text = ft.Row([w.dot(color, 8), ft.Container(content=text, expand=True)], spacing=6)
                    out.append(ft.Container(content=text, width=width, expand=width is None))
                return ft.Container(content=ft.Row(out, spacing=4), padding=ft.Padding.symmetric(vertical=6),
                                    border=ft.Border.only(bottom=ft.BorderSide(1, p.border)))

            table = [cells([S.COL_COMPONENT, S.COL_POSITION.format(unit=x_unit), S.COL_HEIGHT, S.COL_AREA,
                            S.COL_FRACTION], head=True)]
            table += [cells([c["name"], c["position"], c["height"], c["area"], c["fraction"]],
                            color=colors.get(c["name"]), bold_last=True) for c in components]
            total = sum(c["fraction_value"] for c in components) or 1
            bar = ft.Row([ft.Container(expand=max(round(1000 * c["fraction_value"] / total), 1), height=10,
                                       bgcolor=colors.get(c["name"], p.muted)) for c in components if c["fraction_value"] > 0],
                         spacing=0)
            parts += [self.section(S.COMPONENTS), ft.Column(table, spacing=0),
                      ft.Container(content=bar, border_radius=99, clip_behavior=ft.ClipBehavior.ANTI_ALIAS),
                      w.faint(S.ANALYSIS_NOTE, p)]
        elif not m.fitted:
            parts.append(w.faint(S.ANALYSIS_UNFITTED, p))
        page = view.app.page
        export = ft.PopupMenuButton(
            content=ft.Container(content=ft.Row([ft.Icon(ft.Icons.DOWNLOAD_ROUNDED, size=16, color=p.primary),
                                                 ft.Text(S.EXPORT, size=th.SIZE_SMALL, color=p.primary,
                                                         weight=ft.FontWeight.W_600),
                                                 ft.Icon(ft.Icons.EXPAND_MORE_ROUNDED, size=16, color=p.primary)],
                                                spacing=6, tight=True),
                                 border=ft.Border.all(1, p.border), border_radius=th.RADIUS_CONTROL,
                                 padding=ft.Padding.symmetric(horizontal=12, vertical=8)),
            menu_position=ft.PopupMenuPosition.UNDER,
            items=[ft.PopupMenuItem(content=label, on_click=lambda e, s=scope, f=fmt: page.run_task(
                view.export_analysis, s, f)) for label, scope, fmt in view.export_choices()])
        footer = ft.Row([ft.OutlinedButton(S.COPY_TABLE, icon=ft.Icons.CONTENT_COPY_ROUNDED, expand=True,
                                           on_click=lambda e: page.run_task(view.copy_analysis, record)), export],
                        spacing=8)
        return parts, footer

    # ============================================================
    # 信息
    # ============================================================
    def info_page(self, record):
        p, view = self.p, self.view
        src = record.source
        imported = local_time(src.get("imported_at"))
        parts: list[ft.Control] = []
        path = src.get("path") or ""
        parts.append(ft.Row([ft.Container(content=self.kv(S.INFO_SOURCE, path or src.get("file", ""), selectable=True),
                                          expand=True),
                             w.icon_button(ft.Icons.FOLDER_OPEN_OUTLINED, S.OPEN_FOLDER,
                                           lambda e: view.app.page.run_task(view.open_source, record.record_id), p,
                                           disabled=not path)], vertical_alignment=ft.CrossAxisAlignment.START))
        parts += [
            self.kv(S.INFO_READER, src.get("reader", "")),
            self.kv(S.INFO_IMPORTED, imported.strftime("%Y-%m-%d %H:%M:%S") if imported else ""),
            self.kv(S.INFO_HASH, src.get("sha256", ""), selectable=True),
            self.kv(S.INFO_GMA, src.get("gma_version", "")),
            self.kv(S.INFO_SAMPLE, record.sample),
            self.kv(S.INFO_POINTS, f"{record.point_count:,}".replace(",", " ")),
        ]
        if record.fitted:
            parts += [self.kv(S.INFO_COMPONENTS, str(len(record.components))),
                      self.kv(S.INFO_MODE, S.COMPONENT_ABSOLUTE if record.component_mode == "absolute"
                              else S.COMPONENT_RELATIVE)]
        if src.get("derived_from"):
            parts.append(self.kv(S.INFO_DERIVED, src["derived_from"]))
        notes = [note_text(n) for n in record.clean_notes]
        parts.append(self.section(S.INFO_CLEAN))
        if notes:
            parts += [ft.Row([ft.Icon(ft.Icons.INFO_OUTLINE, size=15, color=p.primary),
                              ft.Text(t, size=th.SIZE_SMALL, color=p.text, expand=True, selectable=True)],
                             spacing=6, vertical_alignment=ft.CrossAxisAlignment.START) for t in notes]
        else:
            parts.append(w.faint(S.INFO_NO_CLEAN, p))
        metadata = record.metadata
        if metadata:
            parts.append(self.section(S.INFO_METADATA))
            parts += self.metadata_rows(metadata)
        return parts

    def metadata_rows(self, metadata: dict, limit: int = 120) -> list[ft.Control]:
        """仪器元数据：Raman 是“键 = 值”，XRD 按 [节] 分组（每节一个小标题）。"""
        p, rows = self.p, []
        for key, value in metadata.items():
            if len(rows) >= limit:
                break
            if isinstance(value, dict):
                rows.append(ft.Text(str(key), size=th.SIZE_SMALL, weight=ft.FontWeight.W_600, color=p.text))
                rows += [ft.Container(content=self.kv(str(k), str(v), selectable=True), padding=ft.Padding.only(left=10))
                         for k, v in list(value.items())[:limit]]
            else:
                rows.append(self.kv(str(key), str(value), selectable=True))
        return rows
