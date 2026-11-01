# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
P0-1：Flet 原生 LineChart 的交互与流畅度验证。

运行（在仓库根目录）：
    uv run --with flet-charts==1.0.5 python scripts/ui_p0/p0_linechart.py

要验证的内容见同目录 README.md。

默认显示全部数据点（不抽稀）。缩放有两种做法可以对比：
- 只改范围：所有点只发送一次，缩放时只改坐标范围，图表区域外的部分裁掉。
  LineChart 本身不裁剪范围外的曲线，所以坐标轴和网格线由本脚本自己画在图表外面。
- 重新筛选点：每次缩放只发送范围内的点。
抽稀只是可选项，打开后会自动改用“重新筛选点”，抽稀结果随缩放范围重新计算。

自动测速：用环境变量 P0_BENCH=1 运行（run_mac.sh 就是这样运行的），或者点窗口中的“自动测速”。
依次测量各组数据的首次显示、缩放、平移、图例开关，以及几种对比设置，结果写入
results/linechart_bench.txt；测完后窗口回到默认设置，可以继续手动操作。
窗口看不见时（在别的桌面、被最小化或被完全挡住）macOS 不刷新它，测速会等它显示出来再继续。
每一步记两种时间：Python 端（准备数据并发出更新）用时；以及界面完成第 1、第 3 帧布局的时间
（发出更新后连续改变一个 1 像素控件的宽度，等界面回报尺寸变化，第 3 帧包含了前面的绘制）。
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import math
import os
import platform
import statistics
import sys
import time
import unicodedata
from pathlib import Path

import flet as ft
import flet_charts as fch
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from _common import decimate_minmax, xps_c1s_frame, xrd_patterns  # noqa: E402

PALETTE = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2", "#7f7f7f"]
XPS_COLORS = {"Raw data": "#2B3A42", "Fit": "#D1495B", "Background": "#8A979E",
              "C-Si": "#2563EB", "C-C": "#F59E0B", "C-O": "#10B981"}
AXIS_W, AXIS_H = 64, 22          # 左侧、下方坐标轴区域的尺寸（像素）
GRID, LABEL = "#E7EEF0", "#50656B"
TRANSPARENT = "#00000000"
RESULTS = Path(__file__).parent / "results"
BENCH = os.environ.get("P0_BENCH") == "1"


async def bring_to_front(page):
    """把窗口拿到最前面；网页模式等不支持时忽略。"""
    with contextlib.suppress(Exception):
        await asyncio.wait_for(page.window.to_front(), 3)


class IsolatedSeries(fch.LineChartData):
    """曲线数据标记为 isolated：更新图表的坐标范围时，Flet 不再逐个比较曲线上的点。"""

    def is_isolated(self):
        return True


# ============================================================
# 数据与刻度
# ============================================================
def load_dataset(key, step):
    """返回 (曲线列表, 横轴标题, 横轴是否反向)。曲线为 [名称, 颜色, x, y, 虚线]。"""
    if key == "xps":
        df = xps_c1s_frame()
        x = df["Binding Energy (eV)"].to_numpy()
        cols = [("Raw data", "Intensity"), ("Fit", "Fitting Curve"), ("Background", "Background"),
                ("C-Si", "C-Si"), ("C-C", "C-C"), ("C-O", "C-O")]
        return [[n, XPS_COLORS[n], x, df[c].to_numpy(), [6, 4] if n == "Background" else None] for n, c in cols], \
            "Binding Energy (eV)", True
    n = 1 if key == "xrd1" else 5
    patterns = xrd_patterns(n, step)
    return [[name, PALETTE[i % len(PALETTE)], x, y, None] for i, (name, (x, y)) in enumerate(patterns.items())], \
        "2θ (°)", False


def nice_step(span, target=7):
    raw = span / max(target, 1)
    mag = 10 ** math.floor(math.log10(raw)) if raw > 0 else 1
    r = raw / mag
    return (1 if r < 1.5 else 2 if r < 3 else 5 if r < 7 else 10) * mag


def ticks(lo, hi, target=7):
    step = nice_step(hi - lo, target)
    start = math.ceil(lo / step) * step
    values = np.arange(start, hi + step * 1e-9, step)
    decimals = max(0, -int(math.floor(math.log10(step)))) if step < 1 else 0
    return values, decimals


def fmt_y(v):
    if abs(v) >= 1e5:
        return f"{v:.2g}"
    return f"{v:,.0f}".replace(",", " ")


# ============================================================
# 界面
# ============================================================
def main(page: ft.Page):
    page.title = "P0-1 · LineChart 验证"
    page.window.width, page.window.height = 1280, 840
    page.padding = 16

    st = {
        "key": "xrd5", "step": 0.01, "zoom_mode": "clip", "density": "all", "max_points": 4000,
        "custom_tip": False, "isolate": True, "hidden": set(), "series": [], "reversed": False, "origin": 0.0,
        "xmin": 0.0, "xmax": 1.0, "lo": 0.0, "hi": 1.0, "ylo": 0.0, "yhi": 1.0,
        "w": 900.0, "h": 480.0, "shown": [], "last_wheel": 0.0, "chart": None, "data": [],
        "last": {}, "probe_w": 1, "probe_event": None,
    }

    status = ft.Text("把鼠标移到曲线上，读数显示在这里", size=12, color=ft.Colors.BLUE_GREY_700, selectable=True)
    timing = ft.Text("", size=12, color=ft.Colors.BLUE_GREY_500)
    legend = ft.Row(wrap=True, spacing=6, run_spacing=6)
    grid_layer = ft.Stack(expand=True)
    chart_holder = ft.Container(expand=True)
    y_axis = ft.Stack(width=AXIS_W, clip_behavior=ft.ClipBehavior.NONE)
    x_axis = ft.Stack(height=AXIS_H, expand=True, clip_behavior=ft.ClipBehavior.NONE)
    x_title = ft.Text("", size=11)
    slider = ft.RangeSlider(min=0, max=1, start_value=0, end_value=1, expand=True)
    range_text = ft.Text("", size=12, width=200)
    fast_note = ft.Text("", size=11, color=ft.Colors.BLUE_GREY_400)

    def cx(x):  # 数据横轴 → 图表横轴（XPS 反向）
        return st["origin"] - x if st["reversed"] else x

    def chart_range():
        a, b = cx(st["lo"]), cx(st["hi"])
        return min(a, b), max(a, b)

    def fast_mode():
        return st["zoom_mode"] == "clip" and st["density"] == "all"

    # ---------- 纵轴范围：按当前横轴范围内可见的曲线计算 ----------
    def update_y_range():
        lo, hi = st["lo"], st["hi"]
        ymin, ymax = np.inf, -np.inf
        for name, _, x, y, _ in st["series"]:
            if name in st["hidden"]:
                continue
            m = (x >= lo) & (x <= hi)
            if m.any():
                ymin, ymax = min(ymin, float(y[m].min())), max(ymax, float(y[m].max()))
        if not np.isfinite(ymin):
            ymin, ymax = 0.0, 1.0
        pad = (ymax - ymin) * 0.06 or 1.0
        st["ylo"], st["yhi"] = ymin - pad, ymax + pad

    # ---------- 自己画的坐标轴和网格线 ----------
    def draw_axes():
        w, h = st["w"], st["h"]
        cmin, cmax = chart_range()
        grid, xl, yl = [], [], []
        xs, xd = ticks(st["lo"], st["hi"])
        for v in xs:
            px = (cx(v) - cmin) / (cmax - cmin) * w
            grid.append(ft.Container(left=px, top=0, bottom=0, width=1, bgcolor=GRID))
            xl.append(ft.Container(left=px - 30, top=3, width=60, alignment=ft.Alignment.TOP_CENTER,
                                   content=ft.Text(f"{v:.{xd}f}", size=10, color=LABEL)))
        ys, _ = ticks(st["ylo"], st["yhi"], 6)
        for v in ys:
            py = h - (v - st["ylo"]) / (st["yhi"] - st["ylo"]) * h
            grid.append(ft.Container(top=py, left=0, right=0, height=1, bgcolor=GRID))
            yl.append(ft.Container(top=py - 8, right=6, content=ft.Text(fmt_y(v), size=10, color=LABEL)))
        grid_layer.controls, x_axis.controls, y_axis.controls = grid, xl, yl

    # ---------- 生成曲线 ----------
    def make_points(name, x, y):
        lo, hi = st["lo"], st["hi"]
        ids = np.arange(len(x))
        if not fast_mode():
            m = np.flatnonzero((x >= lo) & (x <= hi))
            if m.size == 0:
                return np.array([]), np.array([]), []
            ids = np.unique(np.clip(np.concatenate([[m[0] - 1], m, [m[-1] + 1]]), 0, len(x) - 1))
            if st["density"] == "max":
                ids = ids[decimate_minmax(x[ids], y[ids], st["max_points"])]
            elif st["density"] == "pixel":
                ids = ids[decimate_minmax(x[ids], y[ids], int(2 * st["w"]))]
        xs, ys = x[ids], y[ids]
        order = np.argsort(cx(xs))
        xs, ys = xs[order], ys[order]
        if st["custom_tip"]:
            pts = [fch.LineChartDataPoint(x=float(cx(a)), y=float(b), tooltip=f"{name}  {a:.3f} · {b:.0f}")
                   for a, b in zip(xs, ys, strict=True)]
        else:
            pts = [fch.LineChartDataPoint(x=float(cx(a)), y=float(b)) for a, b in zip(xs, ys, strict=True)]
        return xs, ys, pts

    def full_rebuild():
        t0 = time.perf_counter()
        update_y_range()
        series_controls, shown, total = [], [], 0
        SeriesClass = IsolatedSeries if st["isolate"] else fch.LineChartData
        for name, color, x, y, dash in st["series"]:
            hidden = name in st["hidden"]
            if hidden and not fast_mode():
                continue
            xs, ys, pts = make_points(name, x, y)
            if not pts:
                continue
            series_controls.append(SeriesClass(points=pts, color=TRANSPARENT if hidden else color,
                                                     stroke_width=1.4, dash_pattern=dash, point=False))
            shown.append((name, xs, ys))
            total += len(pts)
        st["shown"] = shown
        t1 = time.perf_counter()
        cmin, cmax = chart_range()
        chart = fch.LineChart(
            data_series=series_controls, interactive=True, animation=0,
            min_x=cmin, max_x=cmax, min_y=st["ylo"], max_y=st["yhi"],
            left_axis=fch.ChartAxis(show_labels=False, label_size=0, title_size=0),
            bottom_axis=fch.ChartAxis(show_labels=False, label_size=0, title_size=0),
            bgcolor=TRANSPARENT,
            tooltip=fch.LineChartTooltip(bgcolor="#E61B3037", border_radius=8,
                                         fit_inside_horizontally=True, fit_inside_vertically=True),
            on_event=on_chart_event, expand=True,
        )
        st["chart"] = chart
        chart_holder.content = chart
        draw_axes()
        t2 = time.perf_counter()
        page.update()
        t3 = time.perf_counter()
        report("重建图表", total, t1 - t0, t2 - t1, t3 - t2)

    def fast_range():
        t0 = time.perf_counter()
        update_y_range()
        chart = st["chart"]
        cmin, cmax = chart_range()
        chart.min_x, chart.max_x, chart.min_y, chart.max_y = cmin, cmax, st["ylo"], st["yhi"]
        draw_axes()
        t1 = time.perf_counter()
        for c in (grid_layer, x_axis, y_axis):
            c.update()
        t2 = time.perf_counter()
        chart.update()
        t3 = time.perf_counter()
        report("只改范围", sum(len(s[1]) for s in st["shown"]), t1 - t0, 0, t3 - t1,
               extra=f"（坐标轴 {1000 * (t2 - t1):.0f} ms，图表 {1000 * (t3 - t2):.0f} ms）")

    def report(kind, total, prep, build, send, extra=""):
        mode = {"all": "全部点", "max": f"抽稀到每条 {st['max_points']} 点", "pixel": "按屏幕像素抽稀"}[st["density"]]
        timing.value = (f"{kind}：显示 {total:,} 个点（{mode}）· 准备 {1000 * prep:.0f} ms · "
                        f"构建 {1000 * build:.0f} ms · 发送 {1000 * send:.0f} ms{extra}")
        range_text.value = f"范围 {st['lo']:.3f} – {st['hi']:.3f}"
        fast_note.value = "当前：缩放只改坐标范围" if fast_mode() else "当前：缩放时重新筛选点"
        st["last"] = {"kind": kind, "total": total}
        print(f"[linechart] {timing.value}", flush=True)
        page.update()

    def apply_range():
        slider.start_value, slider.end_value = st["lo"], st["hi"]
        fast_range() if fast_mode() and st["chart"] is not None else full_rebuild()

    # ---------- 事件 ----------
    def on_chart_event(e: fch.LineChartEvent):
        if e.type != fch.ChartEventType.POINTER_HOVER or not e.spots:
            return
        parts = []
        for spot in e.spots:
            if spot.bar_index < len(st["shown"]):
                name, xs, ys = st["shown"][spot.bar_index]
                if name not in st["hidden"] and 0 <= spot.spot_index < len(xs):
                    parts.append(f"{name}: {xs[spot.spot_index]:.3f} · {ys[spot.spot_index]:.0f}")
        if parts:
            status.value = "   ".join(parts)
            status.update()

    def on_plot_size(e: ft.LayoutSizeChangeEvent):
        st["w"], st["h"] = max(e.width, 50), max(e.height, 50)
        draw_axes()
        page.update()

    def on_wheel(e: ft.ScrollEvent):
        now = time.perf_counter()
        if now - st["last_wheel"] < (0.04 if fast_mode() else 0.12):
            return
        st["last_wheel"] = now
        dx = e.scroll_delta.x if e.scroll_delta else 0
        dy = e.scroll_delta.y if e.scroll_delta else 0
        log_input("scroll", f"dx={dx:.1f} dy={dy:.1f}")
        lo, hi = st["lo"], st["hi"]
        span = hi - lo
        if abs(dx) > abs(dy):  # 触控板左右滑动：平移
            shift = dx / st["w"] * span * (-1 if st["reversed"] else 1)
            shift = max(min(shift, st["xmax"] - hi), st["xmin"] - lo)
            st["lo"], st["hi"] = lo + shift, hi + shift
        elif dy:  # 上下滚动：以鼠标位置为中心缩放
            frac = min(max(e.local_position.x / st["w"], 0), 1)
            anchor = hi - frac * span if st["reversed"] else lo + frac * span
            factor = 0.85 if dy < 0 else 1 / 0.85
            st["lo"] = max(anchor - (anchor - lo) * factor, st["xmin"])
            st["hi"] = min(anchor + (hi - anchor) * factor, st["xmax"])
        else:
            return
        apply_range()

    input_logged = {"scroll": 0, "scale": 0}

    def log_input(kind, text):
        if input_logged[kind] < 8:  # 只记前几次，看 macOS 送来的是哪种事件
            input_logged[kind] += 1
            print(f"[linechart] 输入 {kind}：{text}", flush=True)

    def on_scale_start(e: ft.ScaleStartEvent):
        st["pinch"] = 1.0
        log_input("scale", f"开始，手指 {e.pointer_count}")

    def on_scale_update(e: ft.ScaleUpdateEvent):
        dx, dy = e.focal_point_delta.x, e.focal_point_delta.y
        log_input("scale", f"scale={e.scale:.3f} 手指={e.pointer_count} 位移=({dx:.1f}, {dy:.1f})")
        if e.pointer_count < 2:  # 鼠标拖动不处理，留给图表自己的悬停
            return
        st["acc_dx"] = st.get("acc_dx", 0.0) + dx
        st["acc_dy"] = st.get("acc_dy", 0.0) + dy
        zoom_by = st.get("pinch", 1.0) / e.scale if e.scale > 0 else 1.0
        st["pinch"] = e.scale
        st["acc_zoom"] = st.get("acc_zoom", 1.0) * zoom_by
        now = time.perf_counter()
        if now - st["last_wheel"] < (0.04 if fast_mode() else 0.12):
            return
        st["last_wheel"] = now
        lo, hi = st["lo"], st["hi"]
        span = hi - lo
        frac = min(max(e.local_focal_point.x / st["w"], 0), 1)
        anchor = hi - frac * span if st["reversed"] else lo + frac * span
        factor = st["acc_zoom"]
        if abs(st["acc_dy"]) > abs(st["acc_dx"]):  # 双指上下滑：和滚轮一样缩放
            factor *= math.exp(st["acc_dy"] / 300)
        else:  # 双指左右滑：平移（内容跟着手指走），到头就停
            shift = -st["acc_dx"] / st["w"] * span * (-1 if st["reversed"] else 1)
            shift = max(min(shift, st["xmax"] - hi), st["xmin"] - lo)
            anchor += shift
            lo, hi = lo + shift, hi + shift
        st["acc_dx"] = st["acc_dy"] = 0.0
        st["acc_zoom"] = 1.0
        new_lo = anchor - (anchor - lo) * factor
        new_hi = anchor + (hi - anchor) * factor
        if new_hi - new_lo < 1e-6:
            return
        st["lo"], st["hi"] = max(new_lo, st["xmin"]), min(new_hi, st["xmax"])
        apply_range()

    def on_slider_end(e):
        st["lo"], st["hi"] = float(slider.start_value), float(slider.end_value)
        apply_range()

    def reset(e=None):
        st["lo"], st["hi"] = st["xmin"], st["xmax"]
        apply_range()

    def toggle(name):
        st["hidden"].symmetric_difference_update({name})
        rebuild_legend()
        if fast_mode() and st["chart"] is not None:  # 只改颜色，不重新发送点
            for i, (n, color, *_rest) in enumerate([s for s in st["series"]]):
                st["chart"].data_series[i].color = TRANSPARENT if n in st["hidden"] else color
            fast_range()
        else:
            full_rebuild()

    def rebuild_legend():
        legend.controls = [ft.Container(
            content=ft.Row([ft.Container(width=9, height=9, bgcolor=color, border_radius=99),
                            ft.Text(name, size=11, color="#40565D")], spacing=5, tight=True),
            padding=ft.Padding.symmetric(horizontal=9, vertical=4), border_radius=99,
            bgcolor="#F2F7F8", border=ft.Border.all(1, "#D8E4E7"), opacity=0.35 if name in st["hidden"] else 1,
            on_click=lambda e, n=name: toggle(n), ink=True, tooltip="点击隐藏 / 显示")
            for name, color, *_ in st["series"]]

    def load(e=None):
        series, title, rev = load_dataset(st["key"], st["step"])
        xs = np.concatenate([s[2] for s in series])
        xmin, xmax = float(xs.min()), float(xs.max())
        mag = 10 ** math.ceil(math.log10(max(xmax - xmin, 1e-9)))
        st.update(series=series, reversed=rev, hidden=set(), xmin=xmin, xmax=xmax, lo=xmin, hi=xmax,
                  origin=math.ceil(xmax / mag) * mag)  # 反向坐标的原点取整，刻度和网格才对齐
        x_title.value = title
        slider.min, slider.max = xmin, xmax
        slider.start_value, slider.end_value = xmin, xmax
        rebuild_legend()
        full_rebuild()

    # ---------- 控件 ----------
    def set_and(key, value, then):
        st[key] = value
        then()

    slider.on_change_end = on_slider_end
    dd_data = ft.Dropdown(label="数据", value="xrd5", width=230, dense=True, text_size=13,
                          on_select=lambda e: set_and("key", e.control.value, load), options=[
                              ft.DropdownOption(key="xrd1", text="XRD · 1 条"),
                              ft.DropdownOption(key="xrd5", text="XRD · 5 条叠加"),
                              ft.DropdownOption(key="xps", text="XPS C1s（横轴反向）")])
    dd_step = ft.Dropdown(label="XRD 步长", value="0.01", width=130, dense=True, text_size=13,
                          on_select=lambda e: set_and("step", float(e.control.value), load), options=[
                              ft.DropdownOption(key="0.02", text="0.02°"), ft.DropdownOption(key="0.01", text="0.01°"),
                              ft.DropdownOption(key="0.005", text="0.005°")])
    dd_zoom = ft.Dropdown(label="缩放方式", value="clip", width=170, dense=True, text_size=13,
                          on_select=lambda e: set_and("zoom_mode", e.control.value, full_rebuild), options=[
                              ft.DropdownOption(key="clip", text="只改范围"),
                              ft.DropdownOption(key="filter", text="重新筛选点")])
    dd_density = ft.Dropdown(label="显示点数", value="all", width=200, dense=True, text_size=13,
                             on_select=lambda e: set_and("density", e.control.value, full_rebuild), options=[
                                 ft.DropdownOption(key="all", text="全部（不抽稀）"),
                                 ft.DropdownOption(key="max", text="抽稀到每条 N 点"),
                                 ft.DropdownOption(key="pixel", text="按屏幕像素抽稀")])
    tf_n = ft.TextField(label="N", value="4000", width=90, dense=True, text_size=13,
                        on_submit=lambda e: set_and("max_points", max(100, int(e.control.value or 4000)), full_rebuild))
    sw_tip = ft.Switch(label="悬停提示带横轴值", value=False,
                       on_change=lambda e: set_and("custom_tip", bool(e.control.value), full_rebuild))
    sw_iso = ft.Switch(label="曲线数据隔离更新", value=True,
                       on_change=lambda e: set_and("isolate", bool(e.control.value), full_rebuild))
    controls = ft.Row([dd_data, dd_step, dd_zoom, dd_density, tf_n, sw_tip, sw_iso], spacing=12, wrap=True)

    # ---------- 自动测速（P0_BENCH=1） ----------
    # 用“探针”判断界面什么时候处理完一次更新：改变几个 1 像素控件的宽度（在 1、2、3 之间轮换，
    # 迟到的回报对不上当前宽度，不会被误认），等界面回报。哪种先回应就用哪种，并统计各自回应了多少次：
    #   size0：尺寸变化立即回报（size_change_interval=0）
    #   size10：用默认的 10 ms 采样（图表区域的尺寸回报在 Mac 上正常，用的就是默认值）
    #   anim：带 1 ms 隐式动画，动画结束时回报。这个事件不带宽度，只计数，不用来计时
    # 处理函数写成普通函数，用 call_soon_threadsafe 通知等待中的协程。
    probe_stats = {"size0": 0, "size10": 0, "anim": 0}
    probe_logged = dict.fromkeys(probe_stats, 0)

    def probe_hit(kind, width=None):
        if probe_logged[kind] < 3:
            probe_logged[kind] += 1
            print(f"[linechart] 探针 {kind} 回报：宽 {width}，应为 {st['probe_w']}", flush=True)
        ev, loop = st["probe_event"], st.get("loop")
        if width is None:  # 动画结束：只计数
            probe_stats[kind] += 1
            return
        if ev is not None and loop is not None and abs(width - st["probe_w"]) < 0.5:
            probe_stats[kind] += 1
            loop.call_soon_threadsafe(ev.set)

    probes = [
        ft.Container(width=1, height=1, size_change_interval=0,
                     on_size_change=lambda e: probe_hit("size0", e.width)),
        ft.Container(width=1, height=1, on_size_change=lambda e: probe_hit("size10", e.width)),
        ft.Container(width=1, height=1, animate=ft.Animation(1), on_animation_end=lambda e: probe_hit("anim")),
    ]
    probe_row = ft.Row(probes, spacing=1, tight=True)

    async def frames(t0, n=3, timeout=10):
        """连续改变探针的宽度 n 次，返回界面每次回应时距 t0 的毫秒数；没有回应的记为 NaN。"""
        if st.get("no_probe"):
            return [math.nan] * n
        st["loop"] = asyncio.get_running_loop()
        marks = []
        for _ in range(n):
            st["probe_w"] = st["probe_w"] % 3 + 1
            for p in probes:
                p.width = st["probe_w"]
            st["probe_event"] = ev = asyncio.Event()
            probe_row.update()
            try:
                await asyncio.wait_for(ev.wait(), timeout)
            except TimeoutError:
                break
            marks.append(1000 * (time.perf_counter() - t0))
        return marks + [math.nan] * (n - len(marks))

    def sync_controls():
        dd_data.value, dd_step.value = st["key"], f"{st['step']:g}"
        dd_zoom.value, dd_density.value, tf_n.value = st["zoom_mode"], st["density"], str(st["max_points"])
        sw_tip.value, sw_iso.value = st["custom_tip"], st["isolate"]

    def zoom(factor, frac=0.4):
        lo, hi = st["lo"], st["hi"]
        anchor = hi - frac * (hi - lo) if st["reversed"] else lo + frac * (hi - lo)
        st["lo"] = max(anchor - (anchor - lo) * factor, st["xmin"])
        st["hi"] = min(anchor + (hi - anchor) * factor, st["xmax"])
        apply_range()

    def pan(fraction):
        lo, hi = st["lo"], st["hi"]
        shift = max(min(fraction * (hi - lo), st["xmax"] - hi), st["xmin"] - lo)
        st["lo"], st["hi"] = lo + shift, hi + shift
        apply_range()

    wait_text = "等界面回应：窗口在别的桌面、被最小化或被完全挡住时，macOS 不刷新它"

    async def wait_visible(limit=60):
        """
        等到界面重新回应探针（窗口可见、在刷新）为止。等了 limit 秒还没有回应时，
        不再测界面用时，只记 Python 端用时，免得一直卡在这里。
        """
        told, start = False, time.perf_counter()
        while math.isnan((await frames(time.perf_counter(), n=1))[0]):
            await bring_to_front(page)
            if not told:
                timing.value = wait_text
                page.update()
                print(f"[linechart] {wait_text}", flush=True)
                told = True
            if time.perf_counter() - start > limit:
                st["no_probe"] = True
                text = f"界面 {limit} 秒没有回应探针，改为只记 Python 端用时（各探针回应次数：{probe_stats}）"
                timing.value = text
                page.update()
                print(f"[linechart] {text}", flush=True)
                return
        if told:
            print("[linechart] 界面有回应了，继续测速", flush=True)

    async def bench(e=None):
        if st.get("benching"):
            return
        st["benching"] = True
        bench_btn.disabled = True
        page.window.always_on_top = True  # 测速时置顶：被别的窗口挡住时 macOS 不刷新
        page.update()
        await bring_to_front(page)
        rows = []

        async def measure(case, action=None):
            t0 = time.perf_counter()
            if action is not None:
                action()
            py = 1000 * (time.perf_counter() - t0)
            f = await frames(t0)
            if math.isnan(f[2]) and not st.get("no_probe"):  # 中途窗口看不见了：等它重新显示
                await wait_visible()
                if not st.get("no_probe"):  # 窗口回来了，这一次不算
                    await asyncio.sleep(0.15)
                    return
            rows.append({"case": case, "points": st["last"].get("total") if action else None,
                         "python_ms": round(py, 1), "frame1_ms": round(f[0], 1), "frame3_ms": round(f[2], 1)})
            await asyncio.sleep(0.15)

        def configure(**kw):
            st.update(kw)
            sync_controls()

        defaults = {"key": "xrd5", "step": 0.01, "zoom_mode": "clip", "density": "all", "max_points": 4000,
                    "custom_tip": False, "isolate": True}
        print("[linechart] 自动测速开始", flush=True)
        await asyncio.sleep(1.5)
        await wait_visible()
        for _ in range(5):
            await measure("空闲（基准）")
        for key, step, label in [("xrd5", 0.01, "XRD 5 条 · 0.01°"), ("xrd5", 0.005, "XRD 5 条 · 0.005°"),
                                 ("xrd1", 0.01, "XRD 1 条 · 0.01°"), ("xps", 0.01, "XPS C1s")]:
            configure(**{**defaults, "key": key, "step": step})
            await measure(f"{label} · 首次显示", load)
            await asyncio.sleep(0.8)
            for _ in range(4):
                await measure(f"{label} · 缩放", lambda: zoom(0.85))
            for _ in range(4):
                await measure(f"{label} · 平移", lambda: pan(0.1))
            for _ in range(4):
                await measure(f"{label} · 缩放", lambda: zoom(1 / 0.85))
            first = st["series"][0][0]
            for _ in range(2):
                await measure(f"{label} · 图例开关", lambda name=first: toggle(name))
        for label, kw in [("关闭隔离更新", {"isolate": False}), ("悬停提示带横轴值", {"custom_tip": True}),
                          ("重新筛选点 · 全部点", {"zoom_mode": "filter"}),
                          ("重新筛选点 · 抽稀到每条 4000 点", {"zoom_mode": "filter", "density": "max"}),
                          ("重新筛选点 · 按屏幕像素抽稀", {"zoom_mode": "filter", "density": "pixel"})]:
            configure(**{**defaults, **kw})
            await measure(f"XRD 5 条 · 0.01° · {label} · 首次显示", load)
            await asyncio.sleep(0.8)
            for _ in range(3):
                await measure(f"XRD 5 条 · 0.01° · {label} · 缩放", lambda: zoom(0.85))
        configure(**defaults)
        load()
        write_bench(rows)
        timing.value = f"自动测速完成，结果在 {RESULTS / 'linechart_bench.txt'}；现在可以手动操作"
        st["benching"] = False
        bench_btn.disabled = False
        page.window.always_on_top = False
        page.update()

    def write_bench(rows, note=""):
        groups = {}
        for r in rows:
            groups.setdefault(r["case"], []).append(r)

        def ms(v):
            return "-" if math.isnan(v) else f"{v:.0f}"

        def med(values):
            values = [v for v in values if not math.isnan(v)]  # 去掉超时
            return statistics.median(values) if values else math.nan

        def cell(text, width, right=True):  # 中文按两个字符宽对齐
            pad = " " * max(0, width - sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in text))
            return pad + text if right else text + pad

        head = ["次数", "点数", "Python", "界面第1帧", "界面第3帧", "最慢第3帧"]
        widths = [5, 9, 9, 11, 11, 11]
        lines = [f"P0-1 LineChart 自动测速 · {time.strftime('%Y-%m-%d %H:%M')}",
                 f"{platform.platform()} · Python {platform.python_version()} · flet {ft.__version__}",
                 f"图表区域 {st['w']:.0f} × {st['h']:.0f}",
                 "单位 ms，取中位数。“界面第 3 帧”减去“空闲（基准）”的同项，约等于界面处理这次更新所用的时间。",
                 f"各探针回应次数：{probe_stats}" + ("（探针没有回应，只记了 Python 端用时）" if st.get("no_probe") else ""),
                 *([note] if note else []), "",
                 "".join(cell(h, w) for h, w in zip(head, widths, strict=True)) + "   项目"]
        for case, rs in groups.items():
            pts = rs[-1]["points"]
            slowest = [r["frame3_ms"] for r in rs if not math.isnan(r["frame3_ms"])]
            values = [str(len(rs)), f"{pts:,}" if pts else "-", ms(med([r["python_ms"] for r in rs])),
                      ms(med([r["frame1_ms"] for r in rs])), ms(med([r["frame3_ms"] for r in rs])),
                      ms(max(slowest) if slowest else math.nan)]
            lines.append("".join(cell(v, w) for v, w in zip(values, widths, strict=True)) + "   " + case)
        text = "\n".join(lines)
        RESULTS.mkdir(exist_ok=True)
        (RESULTS / "linechart_bench.txt").write_text(text + "\n", encoding="utf-8")
        (RESULTS / "linechart_bench.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
        print(text, flush=True)

    bench_btn = ft.Button("自动测速", icon=ft.Icons.SPEED, on_click=bench, tooltip="依次测量各组数据和设置，约 1–3 分钟")
    plot = ft.GestureDetector(
        on_scroll=on_wheel, on_scale_start=on_scale_start, on_scale_update=on_scale_update, expand=True,
        content=ft.Container(content=ft.Stack([grid_layer, chart_holder], expand=True),
                             clip_behavior=ft.ClipBehavior.HARD_EDGE, expand=True, bgcolor=ft.Colors.WHITE,
                             border=ft.Border.all(1, "#CAD9DD"), on_size_change=on_plot_size))
    chart_block = ft.Column([
        ft.Row([y_axis, plot], expand=True, spacing=0, vertical_alignment=ft.CrossAxisAlignment.STRETCH),
        ft.Row([ft.Container(width=AXIS_W), x_axis], spacing=0),
        ft.Row([ft.Container(width=AXIS_W), ft.Container(content=x_title, expand=True, alignment=ft.Alignment.CENTER)],
               spacing=0),
    ], expand=True, spacing=0)

    page.add(ft.Column([
        ft.Text("P0-1 · Flet 原生 LineChart", size=18, weight=ft.FontWeight.BOLD),
        controls,
        ft.Container(content=chart_block, expand=True, bgcolor=ft.Colors.WHITE, border_radius=10,
                     border=ft.Border.all(1, "#D5E1E4"), padding=ft.Padding.only(left=4, right=16, top=12, bottom=6)),
        legend,
        ft.Row([ft.Text("横轴范围", size=12), slider, range_text,
                ft.Button("复位", icon=ft.Icons.RESTART_ALT, on_click=reset), bench_btn]),
        ft.Row([status]), ft.Row([timing, fast_note, probe_row], spacing=16),
        ft.Text("滚轮或双指上下滑：以指针位置缩放 · 捏合：缩放 · 双指左右滑：平移 · 点击图例：隐藏 / 显示曲线", size=11,
                color=ft.Colors.BLUE_GREY_400),
    ], expand=True, spacing=8))
    load()
    if BENCH:
        page.run_task(bench)


if __name__ == "__main__":
    try:
        ft.run(main)
        print("[linechart] 窗口已关闭", flush=True)
    except KeyboardInterrupt:
        print("[linechart] 被 Ctrl+C 中断", flush=True)
