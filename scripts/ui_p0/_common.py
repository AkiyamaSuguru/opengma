# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
P0 验证脚本共用的部分：模拟数据、抽稀、按比例计算窗口尺寸。

这些脚本只用于验证技术方案，不属于 GMA 库，也不会被 GMA.UI 导入。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

RNG = np.random.default_rng(7)


# ============================================================
# 模拟数据
# ============================================================
def _pseudo_voigt(x, center, fwhm, height, eta=0.4):
    gauss = np.exp(-4 * np.log(2) * (x - center) ** 2 / fwhm**2)
    lorentz = 1 / (1 + 4 * (x - center) ** 2 / fwhm**2)
    return height * (eta * lorentz + (1 - eta) * gauss)


def xrd_pattern(step=0.01, scale=1.0, shift=0.0):
    """一条模拟的 XRD 图谱：10–90°，β-SiC 与石墨的尖锐衍射峰，加背景和噪声。"""
    x = np.round(np.arange(10, 90 + step / 2, step), 4)
    peaks = [(26.5, 0.16, 5200), (35.6, 0.12, 9800), (41.4, 0.13, 1900), (54.6, 0.2, 700),
             (60.0, 0.14, 4300), (71.8, 0.15, 3200), (75.5, 0.16, 650)]
    y = 220 + 900 * np.exp(-(x - 10) / 9)
    for center, fwhm, height in peaks:
        y = y + _pseudo_voigt(x, center + shift, fwhm, height * scale)
    y = RNG.poisson(np.clip(y, 1, None)).astype(float)
    return x, y


def xrd_patterns(n=5, step=0.01):
    """n 条强度、峰位略有不同的 XRD 图谱，模拟叠加比较。"""
    return {
        f"样品 {i + 1}": xrd_pattern(step, scale=1 - 0.12 * i, shift=0.03 * i)
        for i in range(n)
    }


def xps_c1s_frame():
    """模拟的 C1s 拟合谱，列名与 GMA 的 XPS 标准数据结构一致（分峰列包含背景）。"""
    be = np.round(np.arange(280, 292, 0.05), 2)[::-1]
    comps = {"C-Si": (283.3, 1.05, 9000), "C-C": (284.8, 1.35, 3800), "C-O": (286.4, 1.6, 900)}
    nets = {k: _pseudo_voigt(be, *v, eta=0) for k, v in comps.items()}
    net = sum(nets.values())
    order = np.argsort(be)
    cumulative = np.cumsum(net[order])
    cumulative /= cumulative[-1]
    bg = np.empty_like(be)
    bg[order] = 600 + 2600 * cumulative
    fit = bg + net
    data = {"Binding Energy (eV)": be, "Intensity": fit + RNG.normal(0, 140, be.size), "Fitting Curve": fit}
    data.update({k: bg + v for k, v in nets.items()})
    data["Background"] = bg
    return pd.DataFrame(data)


# ============================================================
# 抽稀：每个区间保留最小值和最大值，峰顶不会被丢掉
# ============================================================
def decimate_minmax(x, y, max_points):
    """返回保留下来的下标（升序）。点数不超过 max_points 时原样返回。"""
    n = len(x)
    if n <= max_points or max_points < 4:
        return np.arange(n)
    buckets = max_points // 2
    edges = np.linspace(0, n, buckets + 1, dtype=int)
    keep = [0, n - 1]
    for a, b in zip(edges[:-1], edges[1:], strict=True):
        if b <= a:
            continue
        seg = y[a:b]
        keep.append(a + int(np.argmin(seg)))
        keep.append(a + int(np.argmax(seg)))
    return np.unique(keep)


# ============================================================
# 窗口尺寸：按可用屏幕区域的比例计算（可用区域由 p0_window.py 用最大化窗口测得，三个系统同一套做法）
# ============================================================
def window_size(screen_w, screen_h, ratio_w, ratio_h, min_size, max_size=None):
    """按屏幕比例计算窗口尺寸，限制在 [min_size, max_size] 之间，并且不超过屏幕可用区域。"""
    w = max(min_size[0], screen_w * ratio_w)
    h = max(min_size[1], screen_h * ratio_h)
    if max_size:
        w, h = min(w, max_size[0]), min(h, max_size[1])
    return round(min(w, screen_w)), round(min(h, screen_h))
