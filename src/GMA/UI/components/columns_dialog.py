# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
通用表格导入的第一步（方案 8）：指定其他软件导出的表格中，哪一列是横轴、强度，
拟合谱另外指定拟合曲线、背景和分峰列。之后和仪器文件一样，在导入对话框中确认识别结果和清洗报告。

列名按第一个文件；选了多个文件时，其他文件需要有相同的列名。初始值按列名猜测，只是建议。
"""
from __future__ import annotations

import asyncio
import math
from pathlib import Path

import flet as ft
import pandas as pd

from ...project import ProjectError, TableColumns
from .. import theme as th
from ..services import importing
from ..strings import S
from . import widgets as w
from .dialogs import close, dialog, show

PREVIEW_ROWS = 6
NONE = "__none__"


def cell(value) -> str:
    if not isinstance(value, (int, float)) or not math.isfinite(value):
        return "—"
    return f"{value:.6g}"


class ColumnsDialog:
    def __init__(self, view, table: pd.DataFrame, paths: list[str]):
        self.view = view
        self.table = table
        self.paths = [Path(p) for p in paths]
        self.columns = [str(c) for c in table.columns]
        self.fits = view.spec.method != "XRD"  # XRD 只有横轴和强度
        guess = importing.guess_columns(table, view.spec.method)
        self.x, self.y = guess.x, guess.intensity
        self.fit, self.bg = guess.fit, guess.background
        self.components = set(guess.components)
        self.mapping = ft.Column(spacing=10, tight=True)
        self.message = ft.Text("", size=th.SIZE_SMALL, color=view.p.error)
        self.box: ft.AlertDialog | None = None
        self.future: asyncio.Future | None = None

    @property
    def p(self):
        return self.view.p

    async def show(self) -> TableColumns | None:
        """显示对话框，返回各列的含义；取消时为 None。"""
        p = self.view.p
        self.future = asyncio.get_running_loop().create_future()
        first = self.paths[0].name
        more = S.TABLE_MORE_FILES.format(n=len(self.paths) - 1) if len(self.paths) > 1 else ""
        subtitle = S.TABLE_SUBTITLE.format(file=first, rows=len(self.table), cols=len(self.columns)) + more
        self.refresh(update=False)
        content = ft.Container(width=760, content=ft.Column([
            w.muted(subtitle, p, th.SIZE_SMALL),
            self.preview(),
            self.mapping,
        ], spacing=14, tight=True))
        actions = [ft.Row([self.message, ft.Container(expand=True),
                           ft.TextButton(S.CANCEL, on_click=lambda e: self.finish(None)),
                           ft.FilledButton(S.NEXT, on_click=self.submit)],
                          spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER)]
        self.box = dialog(p, S.TABLE_TITLE, content, actions, width=760)
        self.box.on_dismiss = lambda e: self.finish(None)
        show(self.view.app.page, self.box)
        return await self.future

    def finish(self, value) -> None:
        if self.future is not None and not self.future.done():
            close(self.box)
            self.future.set_result(value)

    # ============================================================
    # 预览和选择
    # ============================================================
    def preview(self) -> ft.Control:
        """表格的前几行，列名就是下面下拉框中的名称。"""
        p = self.p
        head = self.table.head(PREVIEW_ROWS)

        def row(values, header=False):
            return ft.Row([ft.Container(
                width=110, padding=ft.Padding.symmetric(horizontal=8, vertical=5),
                content=ft.Text(v, size=th.SIZE_SMALL, color=p.muted if header else p.text, max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS, tooltip=v if header else None,
                                weight=ft.FontWeight.W_600 if header else None))
                for v in values], spacing=0)

        rows = [ft.Container(content=row(self.columns, True), bgcolor=p.subtle)]
        rows += [row([cell(v) for v in r]) for r in head.itertuples(index=False, name=None)]
        return ft.Container(
            content=ft.Row([ft.Column(rows, spacing=0)], scroll=ft.ScrollMode.AUTO),
            border=ft.Border.all(1, p.border), border_radius=th.RADIUS_CONTROL, clip_behavior=ft.ClipBehavior.HARD_EDGE)

    def dropdown(self, label: str, value: str | None, on_select, *, optional: bool = False) -> ft.Control:
        options = ([ft.DropdownOption(key=NONE, text=S.NONE_COLUMN)] if optional else [])
        options += [ft.DropdownOption(key=c, text=c) for c in self.columns]
        return ft.Dropdown(label=label, value=value or NONE, options=options, width=170, dense=True,
                           text_size=th.SIZE_BODY, on_select=on_select)

    def refresh(self, update: bool = True) -> None:
        p = self.p

        def pick(attr):
            def on_select(e):
                value = None if e.control.value == NONE else e.control.value
                setattr(self, attr, value)
                if value is not None:
                    self.components.discard(value)
                self.refresh()
            return on_select

        controls = [ft.Row([self.dropdown(S.COL_X, self.x, pick("x")),
                            self.dropdown(S.COL_INTENSITY, self.y, pick("y"))], spacing=12)]
        if self.fits:
            controls.append(ft.Row([self.dropdown(S.COL_FIT, self.fit, pick("fit"), optional=True),
                                    self.dropdown(S.COL_BACKGROUND, self.bg, pick("bg"), optional=True),
                                    w.faint(S.FIT_COLUMNS_HINT, p, th.SIZE_SMALL, expand=True)],
                                   spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER))
            fitted = self.fit is not None and self.bg is not None
            used = {self.x, self.y, self.fit, self.bg}
            boxes = []
            for col in self.columns:
                if col in used:
                    continue

                def toggle(e, c=col):
                    (self.components.add if e.control.value else self.components.discard)(c)

                boxes.append(ft.Checkbox(label=col, value=col in self.components and fitted, disabled=not fitted,
                                         on_change=toggle))
            if boxes:
                controls.append(ft.Column([w.text(S.COL_COMPONENT_COLUMNS, p, th.SIZE_BODY, bold=True),
                                           ft.Row(boxes, wrap=True, spacing=6, run_spacing=0)], spacing=4, tight=True))
        self.mapping.controls = controls
        self.message.value = ""
        if update:
            self.mapping.update()
            self.message.update()

    def submit(self, e=None) -> None:
        fitted = self.fits and self.fit is not None and self.bg is not None
        try:
            if self.fits and (self.fit is None) != (self.bg is None):
                raise ProjectError(S.FIT_NEEDS_BOTH)
            columns = TableColumns(self.x, self.y, self.fit if fitted else None, self.bg if fitted else None,
                                   [c for c in self.columns if c in self.components] if fitted else [])
        except ProjectError as exc:
            self.message.value = S.COLUMNS_USED_ONCE if "once" in str(exc) else str(exc)
            self.message.update()
            return
        self.finish(columns)
