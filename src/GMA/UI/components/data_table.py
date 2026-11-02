# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
模块页下方的数据表（方案 6.4）：前 30 行 / 后 30 行 / 全部（每页 50 行，避免大文件卡顿）。
列名就是标准数据结构的列名；可以收起，可以导出 CSV 或 Excel。
"""
from __future__ import annotations

import math

import flet as ft
import pandas as pd

from .. import theme as th
from ..strings import S
from . import widgets as w

HEAD, TAIL, ALL = "head", "tail", "all"
N_ROWS, PAGE = 30, 50
VISIBLE_ROWS = 5  # 表格区域的高度（行），更多的行可以滚动
ROW_H = 26


def cell_text(value, x_column: bool) -> str:
    if not isinstance(value, (int, float)) or not math.isfinite(value):
        return "—"
    if x_column:
        return f"{value:.4f}".rstrip("0").rstrip(".")
    if abs(value) >= 100:
        return f"{value:,.0f}".replace(",", " ")
    return f"{value:.4g}"


class DataTable:
    """state 是模块标签状态中的一个字典：mode、page、open。"""

    def __init__(self, view, state: dict):
        self.view = view
        self.state = state
        self.state.setdefault("mode", HEAD)
        self.state.setdefault("page", 0)
        self.state.setdefault("open", True)
        self.frame: pd.DataFrame | None = None
        self.x_column = ""
        self.control = ft.Container()

    @property
    def p(self):
        return self.view.p

    def set_frame(self, frame: pd.DataFrame | None, x_column: str) -> None:
        self.frame, self.x_column = frame, x_column
        self.state["page"] = 0
        self.control.content = self.build()

    def refresh(self) -> None:
        self.control.content = self.build()
        self.control.update()

    def _set(self, **kw) -> None:
        self.state.update(kw)
        self.refresh()

    def build(self) -> ft.Control:
        p, df = self.p, self.frame
        is_open = self.state["open"]
        header = [ft.Icon(ft.Icons.TABLE_CHART_OUTLINED, size=17, color=p.muted),
                  w.text(S.TABLE, p, th.SIZE_PANEL_TITLE, bold=True)]
        if df is not None:
            header.append(ft.SegmentedButton(
                selected=[self.state["mode"]], show_selected_icon=False,
                on_change=lambda e: self._set(mode=(e.control.selected or [HEAD])[0], page=0),
                segments=[ft.Segment(value=HEAD, label=S.TABLE_HEAD), ft.Segment(value=TAIL, label=S.TABLE_TAIL),
                          ft.Segment(value=ALL, label=S.TABLE_ALL)],
                style=ft.ButtonStyle(padding=ft.Padding.symmetric(horizontal=10))))
            header.append(w.faint(S.TABLE_SIZE.format(rows=f"{len(df):,}".replace(",", " "), cols=len(df.columns)),
                                  p, th.SIZE_SMALL))
        header.append(ft.Container(expand=True))
        if df is not None and is_open and self.state["mode"] == ALL:
            pages = max(1, math.ceil(len(df) / PAGE))
            page = min(self.state["page"], pages - 1)
            header += [
                w.icon_button(ft.Icons.CHEVRON_LEFT_ROUNDED, S.PREV_PAGE, lambda e: self._set(page=max(page - 1, 0)),
                              p, disabled=page == 0),
                w.faint(S.TABLE_PAGE.format(page=page + 1, pages=pages), p, th.SIZE_SMALL),
                w.icon_button(ft.Icons.CHEVRON_RIGHT_ROUNDED, S.NEXT_PAGE,
                              lambda e: self._set(page=min(page + 1, pages - 1)), p, disabled=page >= pages - 1),
            ]
        header.append(w.icon_button(ft.Icons.EXPAND_MORE_ROUNDED if is_open else ft.Icons.EXPAND_LESS_ROUNDED,
                                    S.COLLAPSE if is_open else S.EXPAND,
                                    lambda e: self._set(open=not self.state["open"]), p))
        parts = [ft.Container(content=ft.Row(header, spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                              padding=ft.Padding.only(left=14, right=6, top=4, bottom=4))]
        if is_open and df is not None:
            parts.append(self.grid(df))
        return ft.Column(parts, spacing=0)

    def rows(self, df: pd.DataFrame) -> pd.DataFrame:
        mode = self.state["mode"]
        if mode == TAIL:
            return df.tail(N_ROWS)
        if mode == ALL:
            start = self.state["page"] * PAGE
            return df.iloc[start:start + PAGE]
        return df.head(N_ROWS)

    def grid(self, df: pd.DataFrame) -> ft.Control:
        p = self.p
        columns = list(df.columns)

        def row(values, *, head=False):
            cells = []
            for col, v in zip(columns, values, strict=True):
                value = v if head else cell_text(v, col == self.x_column)
                cells.append(ft.Container(
                    expand=True, alignment=ft.Alignment.CENTER_RIGHT, padding=ft.Padding.symmetric(horizontal=10),
                    content=ft.Text(value, size=th.SIZE_SMALL, color=p.muted if head else p.text, max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS, weight=ft.FontWeight.W_600 if head else None,
                                    tooltip=value if head else None)))
            return ft.Container(content=ft.Row(cells, spacing=0), height=ROW_H + (4 if head else 0),
                                border=ft.Border.only(bottom=ft.BorderSide(1, p.border)),
                                bgcolor=p.subtle if head else None)

        body = [row(r) for r in self.rows(df).itertuples(index=False, name=None)]
        return ft.Column([row(columns, head=True),
                          ft.Column(body, spacing=0, scroll=ft.ScrollMode.AUTO, height=min(len(body), VISIBLE_ROWS) * ROW_H)],
                         spacing=0)
