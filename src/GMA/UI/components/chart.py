# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
交互图：Flet 原生 LineChart（Q5），做法来自 P0 的验证（scripts/ui_p0/RESULTS.md）：

- 数据点只在打开时发送一次；缩放、平移只改坐标范围，图表区域外的部分由外层容器裁掉；
- LineChart 不裁剪范围外的曲线，刻度也只能落在间隔的整数倍上，所以坐标轴和网格线自己画在图表外面；
- 曲线数据标记为 isolated：改坐标范围、颜色时 Flet 不再逐个比较曲线上的点；
- 鼠标滚轮缩放；触控板捏合、双指上下滑缩放，双指左右滑平移；按住鼠标拖动平移；双击复位。
  Flutter 把触控板手势当作缩放手势，三个系统用同一套处理；
- 悬停读数由这里根据指针位置计算（离指针最近的数据点），画竖线、圆点和提示框，并交给状态栏；
- XPS 横轴从高到低：图表内部用 −x 作横坐标，刻度标签显示原来的数值。

默认显示全部数据点，不抽稀；设置中打开“抽稀显示”后只影响显示，悬停读数仍然用全部数据。
"""
from __future__ import annotations

import math
import time

import flet as ft
import flet_charts as fch
import numpy as np

from .. import theme as th
from ..services.spectra import (
    Series,
    data_range,
    decimate,
    format_value,
    nearest,
    ticks,
    y_range,
)
from ..strings import S
from ..theme import Palette

AXIS_W, AXIS_H, TITLE_W = 58, 20, 18
TRANSPARENT = "#00000000"
ZOOM_STEP = 0.85
THROTTLE = 0.04  # 两次缩放、平移之间至少间隔的秒数


class _Series(fch.LineChartData):
    """曲线数据标记为 isolated：更新图表时 Flet 不再逐个比较曲线上的点（P0）。"""

    def is_isolated(self):
        return True


def luminance(color: str) -> float:
    try:
        r, g, b = (int(color[i:i + 2], 16) / 255 for i in (1, 3, 5))
    except (ValueError, IndexError):
        return 0.5
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


class SpectrumChart:
    """
    一张交互图。on_range(lo, hi) 在坐标范围改变后调用；on_hover(text) 给出状态栏中的读数（离开时为 ""）；
    on_toggle(key) 在点击图例隐藏 / 显示曲线后调用。compact=True 时（并排视图的小图）不显示图例和范围滑块。
    """

    def __init__(self, p: Palette, *, compact: bool = False, on_range=None, on_hover=None, on_toggle=None,
                 max_points: int = 0, title: str = ""):
        self.p = p
        self.compact = compact
        self.on_range = on_range
        self.on_hover = on_hover
        self.on_toggle = on_toggle
        self.max_points = max_points
        self.title = title
        self.series: list[Series] = []
        self.hidden: set[str] = set()
        self.reversed = False
        self.x_label = ""
        self.y_label = ""
        self.xmin, self.xmax = 0.0, 1.0
        self.lo, self.hi = 0.0, 1.0
        self.ylo, self.yhi = 0.0, 1.0
        self.y_fixed: tuple[float, float] | None = None
        self.w, self.h = 600.0, 360.0
        self._last = 0.0
        self._pinch = 1.0
        self._acc = [0.0, 0.0, 1.0]  # 触控板手势累积的 dx、dy、缩放
        self.chart: fch.LineChart | None = None

        font = 10 if compact else 10.5
        self.font = font
        self.grid = ft.Stack(expand=True)
        self.overlay = ft.Stack(expand=True)
        self.holder = ft.Container(expand=True)
        self.y_axis = ft.Stack(width=AXIS_W, clip_behavior=ft.ClipBehavior.NONE)
        self.x_axis = ft.Stack(height=AXIS_H, expand=True, clip_behavior=ft.ClipBehavior.NONE)
        self.x_title = ft.Text("", size=font + 0.5, color=p.muted)
        self.y_title = ft.Text("", size=font + 0.5, color=p.muted, no_wrap=True)
        self.legend = ft.Row(wrap=True, spacing=6, run_spacing=6, alignment=ft.MainAxisAlignment.CENTER)
        self.slider = ft.RangeSlider(min=0, max=1, start_value=0, end_value=1, expand=True,
                                     on_change_end=self._on_slider, active_color=p.primary,
                                     inactive_color=th.mix(p.border, p.panel, 0.2))
        self.lo_text = ft.Text("", size=th.SIZE_SMALL, color=p.text, width=58, text_align=ft.TextAlign.RIGHT)
        self.hi_text = ft.Text("", size=th.SIZE_SMALL, color=p.text, width=58)
        self.plot = ft.GestureDetector(
            on_scroll=self._on_scroll, on_scale_start=self._on_scale_start, on_scale_update=self._on_scale_update,
            on_hover=self._on_hover_move, on_exit=self._on_exit, on_double_tap=lambda e: self.reset(),
            hover_interval=30, expand=True, mouse_cursor=ft.MouseCursor.PRECISE,
            content=ft.Container(
                content=ft.Stack([self.grid, self.holder, self.overlay], expand=True),
                clip_behavior=ft.ClipBehavior.HARD_EDGE, expand=True, bgcolor=p.panel,
                border=ft.Border.all(1, self.axis_color), on_size_change=self._on_size, size_change_interval=60))
        self.control = self._layout()

    # ============================================================
    # 外观
    # ============================================================
    @property
    def axis_color(self) -> str:
        return th.mix(self.p.border, self.p.text, 0.25)

    @property
    def grid_color(self) -> str:
        return th.mix(self.p.border, self.p.panel, 0.45)

    def shown_color(self, color: str) -> str:
        """深色模式下把接近黑色的曲线（如原始数据的 black）显示为浅色，否则看不见；导出的图不受影响。"""
        if self.p.dark and luminance(color) < 0.18:
            return self.p.text
        return color

    def _layout(self) -> ft.Control:
        p = self.p
        # RotatedBox 在布局前旋转，竖排的标题按旋转后的尺寸排版，不会被截断
        y_title = ft.Container(content=ft.RotatedBox(quarter_turns=3, content=self.y_title), width=TITLE_W,
                               alignment=ft.Alignment.CENTER)
        rows = [
            ft.Row([y_title, self.y_axis, self.plot], expand=True, spacing=0,
                   vertical_alignment=ft.CrossAxisAlignment.STRETCH),
            ft.Row([ft.Container(width=TITLE_W + AXIS_W), self.x_axis], spacing=0),
            ft.Row([ft.Container(width=TITLE_W + AXIS_W),
                    ft.Container(content=self.x_title, expand=True, alignment=ft.Alignment.CENTER)], spacing=0),
        ]
        if self.title:
            rows.insert(0, ft.Text(self.title, size=th.SIZE_SMALL, weight=ft.FontWeight.W_600, color=p.text,
                                   max_lines=1, overflow=ft.TextOverflow.ELLIPSIS))
        if not self.compact:
            rows.append(ft.Container(content=self.legend, padding=ft.Padding.only(top=6, left=TITLE_W + AXIS_W)))
            rows.append(ft.Row([
                ft.Text(S.X_RANGE, size=th.SIZE_SMALL, color=p.muted, weight=ft.FontWeight.W_600),
                self.lo_text, self.slider, self.hi_text,
                ft.OutlinedButton(S.RESET, icon=ft.Icons.RESTART_ALT_ROUNDED, on_click=lambda e: self.reset(),
                                  tooltip=S.CHART_HELP,
                                  style=ft.ButtonStyle(padding=ft.Padding.symmetric(horizontal=12))),
            ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER))
        return ft.Column(rows, spacing=2, expand=True)

    # ============================================================
    # 数据
    # ============================================================
    def cx(self, x):
        return -x if self.reversed else x

    def set_data(self, series: list[Series], *, x_label: str, y_label: str = "Intensity (a.u.)",
                 reversed: bool = False, x_range=None, y_fixed=None, hidden=()) -> None:
        """换一组曲线：所有数据点只在这里发送一次。"""
        self.series = series
        self.reversed = reversed
        self.x_label, self.y_label = x_label, y_label
        self.x_title.value, self.y_title.value = x_label, y_label
        self.hidden = {k for k in hidden if any(s.key == k for s in series)}
        self.xmin, self.xmax = data_range(series)
        self.lo, self.hi = self._clamp(x_range) if x_range else (self.xmin, self.xmax)
        self.y_fixed = tuple(y_fixed) if y_fixed else None
        self._update_y()
        data_series = []
        for s in series:
            idx = decimate(s.x, s.y, self.max_points) if self.max_points else np.arange(len(s.x))
            xs, ys = s.x[idx], s.y[idx]
            ok = np.isfinite(xs) & np.isfinite(ys)
            xs, ys = xs[ok], ys[ok]
            if self.reversed:
                xs, ys = xs[::-1], ys[::-1]
            points = [fch.LineChartDataPoint(x=float(self.cx(a)), y=float(b)) for a, b in zip(xs, ys, strict=True)]
            data_series.append(_Series(
                points=points, color=TRANSPARENT if s.key in self.hidden else self.shown_color(s.color),
                stroke_width=s.width, dash_pattern=s.dash, point=False, curved=False))
        none = fch.ChartAxis(show_labels=False, label_size=0, title_size=0)
        cmin, cmax = self._chart_range()
        self.chart = fch.LineChart(
            data_series=data_series, interactive=False, animation=0, bgcolor=TRANSPARENT,
            min_x=cmin, max_x=cmax, min_y=self.ylo, max_y=self.yhi,
            left_axis=none, bottom_axis=none, top_axis=fch.ChartAxis(show_labels=False, label_size=0, title_size=0),
            right_axis=fch.ChartAxis(show_labels=False, label_size=0, title_size=0), expand=True)
        self.holder.content = self.chart
        self.overlay.controls = []
        self.slider.min, self.slider.max = self.xmin, self.xmax
        self.slider.rtl = self.reversed  # XPS：左边是高结合能，与图一致
        self._sync_slider()
        self._draw_axes()
        self._draw_legend()

    def _clamp(self, rng) -> tuple[float, float]:
        lo, hi = max(min(rng), self.xmin), min(max(rng), self.xmax)
        if hi - lo <= (self.xmax - self.xmin) * 1e-6:
            return self.xmin, self.xmax
        return lo, hi

    def _chart_range(self) -> tuple[float, float]:
        a, b = self.cx(self.lo), self.cx(self.hi)
        return min(a, b), max(a, b)

    def _update_y(self) -> None:
        if self.y_fixed:
            self.ylo, self.yhi = self.y_fixed
        else:
            self.ylo, self.yhi = y_range(self.series, self.lo, self.hi, self.hidden)

    # ============================================================
    # 坐标轴、网格、图例
    # ============================================================
    def _px(self, x: float) -> float:
        cmin, cmax = self._chart_range()
        return (self.cx(x) - cmin) / (cmax - cmin) * self.w if cmax > cmin else 0.0

    def _py(self, y: float) -> float:
        return self.h - (y - self.ylo) / (self.yhi - self.ylo) * self.h if self.yhi > self.ylo else 0.0

    def _draw_axes(self) -> None:
        p, grid, xl, yl = self.p, [], [], []
        xs, xd = ticks(self.lo, self.hi, max(3, int(self.w / 90)))
        for v in xs:
            px = self._px(v)
            grid.append(ft.Container(left=px, top=0, bottom=0, width=1, bgcolor=self.grid_color))
            xl.append(ft.Container(left=px - 30, top=3, width=60, alignment=ft.Alignment.TOP_CENTER,
                                   content=ft.Text(f"{v:.{xd}f}", size=self.font, color=p.muted)))
        ys, yd = ticks(self.ylo, self.yhi, max(3, int(self.h / 60)))
        for v in ys:
            py = self._py(v)
            grid.append(ft.Container(top=py, left=0, right=0, height=1, bgcolor=self.grid_color))
            yl.append(ft.Container(top=py - 8, right=6, content=ft.Text(
                format_value(v, yd if yd else 0), size=self.font, color=p.muted)))
        self.grid.controls, self.x_axis.controls, self.y_axis.controls = grid, xl, yl

    def _draw_legend(self) -> None:
        if self.compact:
            return
        p = self.p
        chips = []
        for s in self.series:
            hidden = s.key in self.hidden
            chips.append(ft.Container(
                content=ft.Row([ft.Container(width=9, height=9, bgcolor=self.shown_color(s.color), border_radius=99),
                                ft.Text(s.label, size=11.5, color=p.text)], spacing=6, tight=True),
                padding=ft.Padding.symmetric(horizontal=10, vertical=4), border_radius=99,
                bgcolor=p.subtle, border=ft.Border.all(1, p.border), opacity=0.4 if hidden else 1,
                on_click=lambda e, k=s.key: self.toggle(k), tooltip=S.TOGGLE_SERIES))
        self.legend.controls = chips

    def _sync_slider(self) -> None:
        self.slider.start_value, self.slider.end_value = self.lo, self.hi
        self.lo_text.value, self.hi_text.value = self._fmt_x(self.lo), self._fmt_x(self.hi)
        if self.reversed:  # 左边写大的数值
            self.lo_text.value, self.hi_text.value = self.hi_text.value, self.lo_text.value

    def _fmt_x(self, v: float) -> str:
        _, d = ticks(self.lo, self.hi, 7)
        return f"{v:.{max(d, 1)}f}"

    # ============================================================
    # 更新
    # ============================================================
    def apply(self) -> None:
        """坐标范围改了之后：只改图表的范围和坐标轴，不重新发送数据点。"""
        if self.chart is None:
            return
        self._update_y()
        cmin, cmax = self._chart_range()
        self.chart.min_x, self.chart.max_x, self.chart.min_y, self.chart.max_y = cmin, cmax, self.ylo, self.yhi
        self._draw_axes()
        self._sync_slider()
        self.overlay.controls = []
        for c in (self.grid, self.x_axis, self.y_axis, self.overlay, self.chart):
            c.update()
        if not self.compact:
            for c in (self.slider, self.lo_text, self.hi_text):
                c.update()
        if self.on_range:
            self.on_range(self.lo, self.hi)

    def set_range(self, lo: float, hi: float) -> None:
        self.lo, self.hi = self._clamp((lo, hi))
        self.apply()

    def reset(self) -> None:
        self.set_range(self.xmin, self.xmax)

    def set_y(self, fixed) -> None:
        self.y_fixed = tuple(fixed) if fixed else None
        self.apply()

    def toggle(self, key: str) -> None:
        self.hidden.symmetric_difference_update({key})
        self.recolor()
        if self.on_toggle:
            self.on_toggle(key)

    def recolor(self, colors: dict[str, str] | None = None) -> None:
        """只改颜色（图例开关、换颜色），不重新发送数据点。"""
        if self.chart is None:
            return
        for s, data in zip(self.series, self.chart.data_series, strict=True):
            if colors and s.key in colors:
                s.color = colors[s.key]
            data.color = TRANSPARENT if s.key in self.hidden else self.shown_color(s.color)
        self._draw_legend()
        self._update_y()
        self.apply()
        if not self.compact:
            self.legend.update()

    # ============================================================
    # 输入
    # ============================================================
    def _on_size(self, e: ft.LayoutSizeChangeEvent) -> None:
        self.w, self.h = max(e.width, 50), max(e.height, 50)
        self._draw_axes()
        for c in (self.grid, self.x_axis, self.y_axis):
            c.update()

    def _throttled(self) -> bool:
        now = time.perf_counter()
        if now - self._last < THROTTLE:
            return True
        self._last = now
        return False

    def _anchor(self, px: float) -> float:
        frac = min(max(px / self.w, 0.0), 1.0)
        span = self.hi - self.lo
        return self.hi - frac * span if self.reversed else self.lo + frac * span

    def _zoom(self, anchor: float, factor: float, shift: float = 0.0) -> None:
        lo, hi = self.lo + shift, self.hi + shift
        anchor += shift
        new_lo = anchor - (anchor - lo) * factor
        new_hi = anchor + (hi - anchor) * factor
        if new_hi - new_lo < (self.xmax - self.xmin) * 1e-4:
            return
        self.lo, self.hi = max(new_lo, self.xmin), min(new_hi, self.xmax)
        self.apply()

    def _pan(self, dx_px: float) -> None:
        """内容跟着指针走，到头就停。"""
        span = self.hi - self.lo
        shift = -dx_px / self.w * span * (-1 if self.reversed else 1)
        shift = max(min(shift, self.xmax - self.hi), self.xmin - self.lo)
        if shift:
            self.lo, self.hi = self.lo + shift, self.hi + shift
            self.apply()

    def _on_scroll(self, e: ft.ScrollEvent) -> None:
        if self.chart is None or self._throttled():
            return
        dx = e.scroll_delta.x if e.scroll_delta else 0
        dy = e.scroll_delta.y if e.scroll_delta else 0
        if abs(dx) > abs(dy):  # 触控板左右滑动（部分系统送来的是滚动事件）：平移
            self._pan(-dx)
        elif dy:
            self._zoom(self._anchor(e.local_position.x), ZOOM_STEP if dy < 0 else 1 / ZOOM_STEP)

    def _on_scale_start(self, e: ft.ScaleStartEvent) -> None:
        self._pinch = 1.0
        self._acc = [0.0, 0.0, 1.0]

    def _on_scale_update(self, e: ft.ScaleUpdateEvent) -> None:
        if self.chart is None:
            return
        dx, dy = e.focal_point_delta.x, e.focal_point_delta.y
        self._acc[0] += dx
        self._acc[1] += dy
        if e.scale > 0:
            self._acc[2] *= self._pinch / e.scale
            self._pinch = e.scale
        if self._throttled():
            return
        acc_dx, acc_dy, zoom = self._acc
        self._acc = [0.0, 0.0, 1.0]
        if e.pointer_count < 2:  # 按住鼠标拖动：平移
            self._pan(acc_dx)
            return
        if abs(acc_dy) > abs(acc_dx) and abs(zoom - 1) < 1e-3:  # 双指上下滑：和滚轮一样缩放
            zoom *= math.exp(acc_dy / 300)
            self._zoom(self._anchor(e.local_focal_point.x), zoom)
        elif abs(zoom - 1) >= 1e-3:  # 捏合
            self._zoom(self._anchor(e.local_focal_point.x), zoom)
        else:  # 双指左右滑：平移
            self._pan(acc_dx)

    def _on_slider(self, e) -> None:
        a, b = float(self.slider.start_value), float(self.slider.end_value)
        self.set_range(min(a, b), max(a, b))

    # ---------- 悬停读数 ----------
    def _on_hover_move(self, e: ft.HoverEvent) -> None:
        if self.chart is None or not self.series:
            return
        px, py = e.local_position.x, e.local_position.y
        if not (0 <= px <= self.w and 0 <= py <= self.h):
            return
        span = self.hi - self.lo
        frac = px / self.w
        x = self.hi - frac * span if self.reversed else self.lo + frac * span
        rows, marks = [], []
        x_shown = None
        for s in self.series:
            if s.key in self.hidden:
                continue
            i = nearest(s, x)
            if i is None:
                continue
            xv, yv = float(s.x[i]), float(s.y[i])
            if x_shown is None:
                x_shown = xv
            rows.append((s.label, self.shown_color(s.color), yv))
            if self.ylo <= yv <= self.yhi:
                marks.append((self._px(xv), self._py(yv), self.shown_color(s.color)))
        if x_shown is None:
            return
        self._draw_readout(self._px(x_shown), x_shown, rows, marks, py)
        if self.on_hover:
            text = " · ".join([f"{self._fmt_readout_x(x_shown)}"] +
                              [f"{label} {format_value(v)}" for label, _, v in rows[:4]])
            self.on_hover(text)

    def _fmt_readout_x(self, x: float) -> str:
        unit = self.x_label.rsplit("(", 1)[-1].rstrip(")") if "(" in self.x_label else ""
        return f"{x:.2f} {unit}".strip()

    def _draw_readout(self, px, x, rows, marks, py) -> None:
        p = self.p
        bg = "#1B3037" if not p.dark else "#E3E9EE"
        fg = "#FFFFFF" if not p.dark else "#1B2730"
        controls = [ft.Container(left=px, top=0, bottom=0, width=1, bgcolor=th.mix(p.muted, p.panel, 0.2))]
        for mx, my, color in marks:
            controls.append(ft.Container(left=mx - 4, top=my - 4, width=8, height=8, border_radius=99, bgcolor=color,
                                         border=ft.Border.all(1.5, p.panel)))
        if not self.compact or len(rows) <= 3:
            lines = [ft.Text(self._fmt_readout_x(x), size=11.5, weight=ft.FontWeight.W_600, color=fg)]
            for label, color, v in rows:
                lines.append(ft.Row([ft.Container(width=8, height=8, border_radius=99, bgcolor=color),
                                     ft.Text(label, size=11, color=fg, expand=True, max_lines=1,
                                             overflow=ft.TextOverflow.ELLIPSIS),
                                     ft.Text(format_value(v), size=11, color=fg)], spacing=6, width=150))
            box_w, box_h = 168, 26 + 17 * len(rows)
            left = px + 12 if px + 12 + box_w < self.w else px - 12 - box_w
            top = min(max(py - box_h / 2, 4), max(self.h - box_h - 4, 4))
            controls.append(ft.Container(left=max(left, 2), top=top, width=box_w, bgcolor=bg, opacity=0.94,
                                         border_radius=8, padding=ft.Padding.symmetric(horizontal=9, vertical=7),
                                         content=ft.Column(lines, spacing=3, tight=True)))
        self.overlay.controls = controls
        self.overlay.update()

    def _on_exit(self, e) -> None:
        if self.overlay.controls:
            self.overlay.controls = []
            self.overlay.update()
        if self.on_hover:
            self.on_hover("")
