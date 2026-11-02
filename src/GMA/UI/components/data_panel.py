# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
模块页左栏：数据（方案 6.1）。

- 按样品分组的树，可以搜索、按类型筛选（XPS 为全谱 / 元素谱）；从总览跳转过来时只显示对应样品；
- 单击条目在中间查看；勾选条目用于叠加或并排；
- 条目菜单：重命名、移到其他样品、打开来源文件所在的文件夹、从项目中移除（不删除原文件）；
- 下方是当前样品的信息卡。
"""
from __future__ import annotations

import flet as ft

from .. import theme as th
from ..strings import S
from . import widgets as w

ROW_H = 34


class DataPanel:
    def __init__(self, view):
        self.view = view
        self.list = ft.Column(spacing=1, scroll=ft.ScrollMode.AUTO, expand=True)
        self.info = ft.Container()
        self.header_count = ft.Container()
        self.search = ft.TextField(
            value=view.st["search"], hint_text=S.SEARCH, dense=True, text_size=th.SIZE_BODY,
            prefix_icon=ft.Icons.SEARCH_ROUNDED, on_change=self.on_search, border_radius=th.RADIUS_CONTROL,
            content_padding=ft.Padding.symmetric(horizontal=10, vertical=8))
        self.sample_chip = ft.Container()
        self.control = ft.Container()

    @property
    def p(self):
        return self.view.p

    def build(self) -> ft.Control:
        p, view = self.p, self.view
        import_menu = ft.PopupMenuButton(
            content=ft.Container(
                content=ft.Row([ft.Icon(ft.Icons.UPLOAD_ROUNDED, size=16, color=p.on_primary),
                                ft.Text(S.IMPORT, size=th.SIZE_SMALL, weight=ft.FontWeight.W_600, color=p.on_primary)],
                               spacing=6, tight=True),
                bgcolor=p.primary, border_radius=th.RADIUS_CONTROL,
                padding=ft.Padding.symmetric(horizontal=12, vertical=7)),
            tooltip=S.SHORTCUT_HINT.format(action=S.IMPORT, keys="Ctrl+I"), menu_position=ft.PopupMenuPosition.UNDER,
            items=[ft.PopupMenuItem(content=S.IMPORT_FILES, icon=ft.Icons.DESCRIPTION_OUTLINED,
                                    on_click=lambda e: view.app.page.run_task(view.import_files)),
                   ft.PopupMenuItem(content=S.IMPORT_FOLDER, icon=ft.Icons.FOLDER_OPEN_OUTLINED,
                                    on_click=lambda e: view.app.page.run_task(view.import_folder)),
                   ft.PopupMenuItem(),
                   ft.PopupMenuItem(content=S.IMPORT_TABLE, icon=ft.Icons.TABLE_VIEW_OUTLINED,
                                    on_click=lambda e: view.app.page.run_task(view.import_table))])
        filters = ft.SegmentedButton(
            selected=[view.st["filter"]], show_selected_icon=False, on_change=self.on_filter,
            segments=[ft.Segment(value=k, label=t) for k, t in view.FILTERS],
            style=ft.ButtonStyle(padding=ft.Padding.symmetric(horizontal=10)))
        self.refresh(update=False)
        top = ft.Column([
            ft.Row([w.text(S.DATA_TITLE.format(title=view.spec.title), p, th.SIZE_PANEL_TITLE, bold=True),
                    self.header_count, ft.Container(expand=True), import_menu],
                   spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            self.search,
            ft.Row([filters], scroll=ft.ScrollMode.HIDDEN) if len(view.FILTERS) > 1 else ft.Container(),
            self.sample_chip,
        ], spacing=10)
        self.control.content = ft.Column([top, ft.Container(content=self.list, expand=True), self.info],
                                         spacing=10, expand=True)
        return self.control

    # ============================================================
    # 刷新
    # ============================================================
    def refresh(self, update: bool = True) -> None:
        p, view = self.p, self.view
        records = view.records()
        checked = [r for r in records if r.record_id in view.st["checked"]]
        self.header_count.content = w.chip(str(len(records)), p)
        sample = view.st.get("sample")
        if sample:
            self.sample_chip.content = ft.Container(
                content=ft.Row([ft.Icon(ft.Icons.FILTER_ALT_OUTLINED, size=14, color=p.primary),
                                ft.Text(S.ONLY_SAMPLE.format(sample=sample), size=th.SIZE_SMALL, color=p.primary,
                                        expand=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                w.icon_button(ft.Icons.CLOSE_ROUNDED, S.SHOW_ALL_SAMPLES, self.clear_sample, p,
                                              size=14, color=p.primary)], spacing=6),
                bgcolor=p.primary_weak, border_radius=th.RADIUS_CONTROL, padding=ft.Padding.only(left=10, right=2))
        else:
            self.sample_chip.content = None
        rows: list[ft.Control] = []
        groups = view.grouped()
        if records:
            # 勾选说明一直占一行：勾选第一条时下面的条目不会移动，不会点错
            actions = []
            if checked:
                actions = [
                    w.icon_button(ft.Icons.CLEAR_ALL_ROUNDED, S.CLEAR_CHECKED, lambda e: view.clear_checked(), p,
                                  size=16),
                    w.icon_button(ft.Icons.DELETE_OUTLINE, S.REMOVE_CHECKED.format(n=len(checked)),
                                  lambda e: view.app.page.run_task(view.remove_records,
                                                                   [r.record_id for r in checked]),
                                  p, size=16, color=p.error)]
            text = S.CHECKED_N.format(n=len(checked)) if checked else S.CHECK_HINT
            rows.append(ft.Container(
                content=ft.Row([w.text(text, p, th.SIZE_TINY, color=p.primary if checked else p.faint, expand=True,
                                       max_lines=1), *actions], spacing=0,
                               vertical_alignment=ft.CrossAxisAlignment.CENTER),
                height=32, padding=ft.Padding.only(left=6)))
        if not groups:
            rows.append(ft.Container(content=w.faint(S.NO_MATCH if records else S.MODULE_EMPTY_HINT.format(
                title=view.spec.title), p, th.SIZE_SMALL), padding=ft.Padding.all(8)))
        collapsed = set(view.st["collapsed"])
        for sample_name, items in groups:
            is_open = sample_name not in collapsed or bool(view.st["search"])
            rows.append(self.sample_row(sample_name, len(items), is_open))
            if is_open:
                rows += [self.record_row(r) for r in items]
        self.list.controls = rows
        self.info.content = self.sample_card()
        if update:
            for c in (self.list, self.info, self.header_count, self.sample_chip):
                c.update()

    def sample_row(self, name: str, n: int, is_open: bool) -> ft.Control:
        p = self.p

        def toggle(e):
            collapsed = self.view.st["collapsed"]
            if name in collapsed:
                collapsed.remove(name)
            else:
                collapsed.append(name)
            self.refresh()

        return w.hoverable(ft.Row([
            ft.Icon(ft.Icons.EXPAND_MORE_ROUNDED if is_open else ft.Icons.CHEVRON_RIGHT_ROUNDED, size=18,
                    color=p.muted),
            ft.Icon(ft.Icons.FOLDER_OUTLINED, size=17, color=p.muted),
            ft.Text(name, size=th.SIZE_BODY, weight=ft.FontWeight.W_600, color=p.text, expand=True, max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS, tooltip=name),
            w.faint(str(n), p, th.SIZE_SMALL),
        ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER), p, on_click=toggle, height=ROW_H,
            padding=ft.Padding.only(left=4, right=10))

    def record_row(self, record) -> ft.Control:
        p, view = self.p, self.view
        rid = record.record_id
        current = rid == view.current_id()

        def check(e):
            view.set_checked(rid, bool(e.control.value))

        menu = ft.PopupMenuButton(
            icon=ft.Icons.MORE_HORIZ_ROUNDED, icon_size=16, icon_color=p.faint, tooltip="",
            menu_position=ft.PopupMenuPosition.UNDER,
            items=[
                ft.PopupMenuItem(content=S.RENAME_SPECTRUM, icon=ft.Icons.EDIT_OUTLINED,
                                 on_click=lambda e: view.app.page.run_task(view.rename_record, rid)),
                ft.PopupMenuItem(content=S.MOVE_TO_SAMPLE, icon=ft.Icons.DRIVE_FILE_MOVE_OUTLINE,
                                 on_click=lambda e: view.app.page.run_task(view.move_record, rid)),
                ft.PopupMenuItem(content=S.OPEN_SOURCE_FOLDER, icon=ft.Icons.FOLDER_OPEN_OUTLINED,
                                 on_click=lambda e: view.app.page.run_task(view.open_source, rid)),
                ft.PopupMenuItem(),
                ft.PopupMenuItem(content=S.REMOVE_SPECTRUM, icon=ft.Icons.DELETE_OUTLINE,
                                 on_click=lambda e: view.app.page.run_task(view.remove_records, [rid])),
            ])
        badge = ft.Container(content=ft.Text(view.badge(record), size=10.5, color=p.muted, max_lines=1),
                             bgcolor=p.subtle, border_radius=99, padding=ft.Padding.symmetric(horizontal=8, vertical=1))
        row = ft.Row([
            ft.Checkbox(value=rid in view.st["checked"], on_change=check, width=28, height=28),
            ft.Text(record.name, size=th.SIZE_BODY, color=p.text, expand=True, max_lines=1,
                    weight=ft.FontWeight.W_600 if current else None, overflow=ft.TextOverflow.ELLIPSIS,
                    tooltip=record.name),
            badge, menu,
        ], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER)
        box = w.hoverable(row, p, on_click=lambda e: view.select(rid), height=ROW_H,
                          base_color=p.primary_weak if current else None,
                          hover_color=p.primary_weak if current else None,
                          padding=ft.Padding.only(left=16, right=0))
        if current:
            box.border = ft.Border.only(left=ft.BorderSide(3, p.primary))
        return box

    def sample_card(self) -> ft.Control | None:
        p, view = self.p, self.view
        record = view.current()
        if record is None:
            return None
        sample = view.project.samples.get(record.sample)
        fields = view.project.sample_fields
        lines = []
        for f in fields:
            value = (sample.info.get(f, "") if sample else "") or "—"
            lines.append(ft.Row([ft.Text(f, size=th.SIZE_SMALL, color=p.muted, width=72, max_lines=1,
                                         overflow=ft.TextOverflow.ELLIPSIS, tooltip=f),
                                 ft.Text(value, size=th.SIZE_SMALL, color=p.text, expand=True, max_lines=2,
                                         overflow=ft.TextOverflow.ELLIPSIS, tooltip=value)], spacing=8))
        if not lines:
            lines.append(w.faint(S.NO_SAMPLE_INFO, p, th.SIZE_TINY))
        title = ft.Row([ft.Text(f"{S.SAMPLE_INFO} · {record.sample}", size=th.SIZE_SMALL, weight=ft.FontWeight.W_600,
                                color=p.muted, expand=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                        w.icon_button(ft.Icons.EDIT_OUTLINED, S.EDIT_SAMPLE_INFO,
                                      lambda e: view.app.page.run_task(view.edit_sample_info, record.sample), p,
                                      size=15, disabled=not fields)], spacing=4)
        return ft.Container(content=ft.Column([title, *lines], spacing=4, tight=True), bgcolor=p.subtle,
                            border_radius=th.RADIUS_CONTROL, padding=ft.Padding.only(left=12, right=4, top=6, bottom=10))

    # ============================================================
    # 事件
    # ============================================================
    def on_search(self, e) -> None:
        self.view.st["search"] = (e.control.value or "").strip()
        self.refresh()

    def on_filter(self, e) -> None:
        self.view.st["filter"] = (e.control.selected or ["all"])[0]
        self.refresh()

    def clear_sample(self, e=None) -> None:
        self.view.st["sample"] = None
        self.refresh()
