# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
导入对话框（方案 7.1）：导入前确认识别结果和清洗报告。

- 读取器、样品名（可以应用到全部）、分峰数据模式、已有同名谱图时的处理；
- 每个文件一行：是否导入、识别为（XPS 为全谱 / 元素谱，改了会重新读取）、谱图名、分峰名、检查结果；
- 分峰名取自文件中的列名（黄色），可以当场改，也可以导入后再改；读取失败的文件写明原因，默认不导入。

读取在后台线程中进行；确认后用 GMA.project.commit 加入项目，来源路径、哈希、读取器、导入时间都会记下。
"""
from __future__ import annotations

import asyncio

import flet as ft

from ...project import ImportItem, ProjectError, commit
from .. import theme as th
from ..services import importing
from ..strings import S
from . import widgets as w
from .dialogs import close, dialog, edit_names, show

CONFLICTS = [("copy", S.CONFLICT_COPY), ("replace", S.CONFLICT_REPLACE), ("skip", S.CONFLICT_SKIP)]
YELLOW, YELLOW_DARK = ("#FEF3C7", "#92400E"), ("#3A2D14", "#FBBF24")
BLUE, BLUE_DARK = ("#E5EEFE", "#1D4ED8"), ("#1B2A44", "#93C5FD")
COLS = (36, 190, 170, 120, 250)  # 勾选、文件、识别为、谱图名、分峰名；检查一列占剩下的宽度


class ImportDialog:
    def __init__(self, view, items: list[ImportItem], *, folder=None, readers):
        self.view = view
        self.items = items
        self.folder = folder
        self.readers = readers
        self.reader = items[0].reader if items else readers[0]
        self.mode = view.app.settings.component_mode
        self.conflict = "copy"
        self.busy = False
        self.rows = ft.Column(spacing=0, scroll=ft.ScrollMode.AUTO, expand=True)
        self.sample = ft.TextField(value=importing.common_sample(items), dense=True, text_size=th.SIZE_BODY,
                                   width=230, label=S.SAMPLE_NAME)
        self.import_button = ft.FilledButton(on_click=self.on_import)
        self.progress = ft.ProgressRing(width=16, height=16, stroke_width=2, visible=False)
        # 对话框中的提示（如名称不能为空）显示在按钮旁边，不用底部提示条（会被对话框挡住）
        self.message = ft.Text("", size=th.SIZE_SMALL, color=view.p.error, max_lines=2,
                               overflow=ft.TextOverflow.ELLIPSIS)
        self.future: asyncio.Future | None = None
        self.box: ft.AlertDialog | None = None

    @property
    def p(self):
        return self.view.p

    @property
    def page(self):
        return self.view.app.page

    # ============================================================
    # 对话框
    # ============================================================
    async def show(self) -> list:
        """显示对话框，返回加入项目的谱图（取消时为空列表）。"""
        p = self.p
        self.future = asyncio.get_running_loop().create_future()
        title = S.IMPORT_TITLE.format(title=self.view.spec.title)
        subtitle = (S.IMPORT_FROM_FOLDER.format(folder=self.folder, n=len(self.items)) if self.folder
                    else S.IMPORT_FROM_FILES.format(n=len(self.items)))
        apply_all = ft.TextButton(S.APPLY_TO_ALL, on_click=self.apply_sample)
        reader = ft.Dropdown(value=self.reader, dense=True, text_size=th.SIZE_BODY, width=220, label=S.READER,
                             options=[ft.DropdownOption(key=r, text=r) for r in self.readers],
                             on_select=self.on_reader)
        mode = ft.SegmentedButton(
            selected=[self.mode], show_selected_icon=False, on_change=self.on_mode,
            segments=[ft.Segment(value="absolute", label=S.COMPONENT_ABSOLUTE),
                      ft.Segment(value="relative", label=S.COMPONENT_RELATIVE_SHORT)])
        conflict = ft.Dropdown(value=self.conflict, dense=True, text_size=th.SIZE_BODY, width=150,
                               label=S.ON_CONFLICT, options=[ft.DropdownOption(key=k, text=t) for k, t in CONFLICTS],
                               on_select=self.on_conflict)
        settings_row = ft.Row([reader, ft.Row([self.sample, apply_all], spacing=4, tight=True),
                               ft.Column([w.faint(S.COMPONENT_MODE_TITLE, p, th.SIZE_TINY), mode], spacing=2,
                                         tight=True),
                               ft.Container(expand=True), conflict], spacing=16,
                              vertical_alignment=ft.CrossAxisAlignment.END)
        header = self.table_row([ft.Container(), *(w.label(t, p) for t in (S.COL_FILE, S.COL_KIND, S.COL_NAME,
                                                                           S.COL_COMPONENTS, S.COL_CHECK))],
                                head=True)
        self.refresh_rows(update=False)
        self.update_button(update=False)
        height = max(min(self.view.app.page.height or 800, 900) * 0.62, 320)
        content = ft.Container(width=1040, height=height, content=ft.Column([
            w.muted(subtitle, p, th.SIZE_SMALL),
            settings_row,
            ft.Container(height=4),
            ft.Container(content=ft.Column([header, self.rows], spacing=0, expand=True), expand=True,
                         border=ft.Border.all(1, p.border), border_radius=th.RADIUS_CONTROL),
        ], spacing=10, expand=True))
        actions = [ft.Row([ft.Icon(ft.Icons.INFO_OUTLINE, size=15, color=p.faint), w.faint(S.IMPORT_HINT, p),
                           ft.Container(expand=True), self.message, self.progress,
                           ft.TextButton(S.CANCEL, on_click=lambda e: self.finish([])), self.import_button],
                          spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER)]
        self.box = dialog(p, title, content, actions, width=1040)
        self.box.on_dismiss = lambda e: self.finish([])
        show(self.page, self.box)
        return await self.future

    def finish(self, added: list) -> None:
        if self.future is not None and not self.future.done():
            close(self.box)
            self.future.set_result(added)

    # ============================================================
    # 表格
    # ============================================================
    def table_row(self, cells: list[ft.Control], *, head: bool = False, faded: bool = False) -> ft.Control:
        p = self.p
        boxes = [ft.Container(content=c, width=width, padding=ft.Padding.only(right=8))
                 for c, width in zip(cells[:5], COLS, strict=True)]
        boxes.append(ft.Container(content=cells[5], expand=True))
        return ft.Container(
            content=ft.Row(boxes, spacing=0, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.Padding.symmetric(horizontal=10, vertical=6 if head else 4),
            bgcolor=p.subtle if head else (th.mix(p.subtle, p.panel, 0.5) if faded else None),
            border=ft.Border.only(bottom=ft.BorderSide(1, p.border)))

    def refresh_rows(self, update: bool = True) -> None:
        self.rows.controls = [self.item_row(i, item) for i, item in enumerate(self.items)]
        if update:
            self.rows.update()

    def item_row(self, index: int, item: ImportItem) -> ft.Control:
        p = self.p
        ok, check = importing.check_text(item)

        def toggle(e):
            item.selected = bool(e.control.value)
            self.update_button()

        def rename(e):
            item.name = (e.control.value or "").strip()
            self.update_button()

        box = ft.Checkbox(value=item.selected and ok, disabled=not ok, on_change=toggle)
        file = ft.Row([ft.Icon(ft.Icons.DESCRIPTION_OUTLINED, size=16, color=p.muted if ok else p.faint),
                       ft.Text(item.path.name, size=th.SIZE_BODY, color=p.text if ok else p.faint, expand=True,
                               max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, tooltip=str(item.path))],
                      spacing=6)
        options = importing.kind_options(item)
        kind = ft.Dropdown(value=item.kind, dense=True, text_size=th.SIZE_SMALL, width=162,
                           options=[ft.DropdownOption(key=k, text=t) for k, t in options],
                           on_select=lambda e, i=index: self.page.run_task(self.change_kind, i, e.control.value),
                           disabled=len(options) < 2)
        name = ft.TextField(value=item.name, dense=True, text_size=th.SIZE_BODY, on_change=rename,
                            disabled=not ok, content_padding=ft.Padding.symmetric(horizontal=8, vertical=6))
        components = self.component_chips(index, item)
        color = p.success if ok else p.error
        check_cell = ft.Row([ft.Icon(ft.Icons.CHECK_ROUNDED if ok else ft.Icons.WARNING_AMBER_ROUNDED, size=16,
                                     color=color),
                             ft.Text(check, size=th.SIZE_SMALL, color=color, expand=True, max_lines=2,
                                     overflow=ft.TextOverflow.ELLIPSIS, tooltip=check)], spacing=6)
        return self.table_row([box, file, kind, name, components, check_cell], faded=not ok)

    def component_chips(self, index: int, item: ImportItem) -> ft.Control:
        p = self.p
        if not item.fitted or not item.file_components:
            return w.faint("—", p)
        original = not item.renamed
        bg, fg = (YELLOW_DARK if p.dark else YELLOW) if original else (BLUE_DARK if p.dark else BLUE)
        chips = [ft.Container(content=ft.Text(n, size=11.5, color=fg, max_lines=1), bgcolor=bg, border_radius=6,
                              padding=ft.Padding.symmetric(horizontal=7, vertical=2)) for n in item.components]
        edit = w.icon_button(ft.Icons.EDIT_OUTLINED, S.RENAME_COMPONENTS,
                             lambda e: self.page.run_task(self.edit_components, index), p, size=15)
        return ft.Row([*chips, edit], spacing=4, wrap=True, run_spacing=4)

    def update_button(self, update: bool = True) -> None:
        n = sum(1 for i in self.items if i.selected and i.ok)
        self.import_button.content = S.IMPORT_N.format(n=n)
        self.import_button.disabled = n == 0 or self.busy
        if update:
            self.import_button.update()

    def set_busy(self, busy: bool) -> None:
        self.busy = busy
        self.progress.visible = busy
        self.progress.update()
        self.update_button()

    # ============================================================
    # 修改
    # ============================================================
    def apply_sample(self, e=None) -> None:
        sample = (self.sample.value or "").strip()
        if not sample:
            self.sample.error = S.REQUIRED
            self.sample.update()
            return
        self.sample.error = None
        self.sample.update()
        for item in self.items:
            item.sample = sample

    async def change_kind(self, index: int, kind: str) -> None:
        item = self.items[index]
        if kind == item.kind:
            return
        self.set_busy(True)
        try:
            self.items[index] = await asyncio.to_thread(importing.change_kind, item, kind)
        finally:
            self.set_busy(False)
        self.refresh_rows()
        self.update_button()

    async def on_reader(self, e) -> None:
        reader = e.control.value
        if reader == self.reader:
            return
        self.reader = reader
        self.set_busy(True)
        try:
            self.items = await asyncio.to_thread(importing.reread, self.items, reader=reader)
        finally:
            self.set_busy(False)
        self.refresh_rows()
        self.update_button()

    def on_mode(self, e) -> None:
        self.mode = (e.control.selected or [self.mode])[0]

    def on_conflict(self, e) -> None:
        self.conflict = e.control.value or "copy"

    async def edit_components(self, index: int) -> None:
        item = self.items[index]
        labels = [S.COMPONENT_NAME_N.format(n=i + 1, old=old) for i, old in enumerate(item.file_components)]
        names = await edit_names(self.page, self.p, S.RENAME_COMPONENTS, item.components, labels)
        if names is None:
            return
        try:
            item.components = names
        except ProjectError as exc:
            self.say(str(exc))
            return
        self.rows.controls[index] = self.item_row(index, item)
        self.rows.update()

    # ============================================================
    # 导入
    # ============================================================
    def on_import(self, e=None) -> None:
        sample = (self.sample.value or "").strip()
        if sample and importing.common_sample(self.items) != sample and len({i.sample for i in self.items}) <= 1:
            for item in self.items:  # 只有一个样品名时，改了名称框直接生效，不必再点“应用到全部”
                item.sample = sample
        chosen = [i for i in self.items if i.selected and i.ok]
        if any(not i.name.strip() or not i.sample.strip() for i in chosen):
            self.say(S.NAME_REQUIRED)
            return
        try:
            added = commit(self.view.project, chosen, on_conflict=self.conflict, component_mode=self.mode)
        except ProjectError as exc:
            self.say(str(exc))
            return
        self.finish(added)

    def say(self, message: str) -> None:
        self.message.value = message
        self.message.tooltip = message
        self.message.update()
