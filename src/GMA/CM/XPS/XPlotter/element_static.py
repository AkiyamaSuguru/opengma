# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
XPS 元素谱（高分辨谱）静态出版图，基于 matplotlib。

支持三种数据（列名见 XPS/schema.py）：
1. 未拟合：["Binding Energy (eV)", "Intensity"]
2. 已拟合、无分峰列：["Binding Energy (eV)", "Intensity", "Fitting Curve", "Background"]
3. 已拟合、有分峰列：在 2 的基础上增加若干分峰列

配色：默认按通用色卡 palette 取色；出版绘图时可传 component_colors（如
XPlotter/color_tables.py 中的 COMPONENT_COLORS），按化学键（分峰名）固定颜色。

函数分两层：
- draw_*：画在传入的 ax 上并返回 ax，可以自己组合多面板图；
- plot_element_static：生成整张图（单个元素，或多个元素按子图排列）。

具体实现在 GMA.CM.common.fit_static（XPS 元素谱与 Raman 拟合谱共用），
这里绑定 XPS 的横轴（结合能，从高到低）。
"""
from ...common import fit_static, spectra_static
from ...common.data import detect_fit_type
from ..schema import AXIS


def detect_element_type(df):
    """判断元素谱类型："raw"（未拟合）或 "fit"（拟合后）。"""
    return detect_fit_type(df, AXIS)


def draw_element_raw(ax, df, **kwargs):
    """
    画未拟合的元素谱。

    参数见 common.spectra_static.draw_spectrum，常用的有 color（None 时用通用色卡的
    第一个颜色）、linewidth、show_legend、hide_y_ticks。
    """
    options = {"linewidth": 1.0, "label": "Raw data", **kwargs}
    return spectra_static.draw_spectrum(ax, df, AXIS, **options)


def draw_element_fit(ax, df, **kwargs):
    """
    画拟合后的元素谱：原始数据点、拟合包络线、背景和各分峰。

    参数见 common.fit_static.draw_fit，常用的有 component_colors、component_mode、
    show_legend、hide_y_ticks。
    """
    return fit_static.draw_fit(ax, df, AXIS, **kwargs)


def draw_element(ax, df, **kwargs):
    """
    自动判断 df 是未拟合谱还是拟合谱，并调用对应的 draw 函数。

    参数见 common.fit_static.draw_fit_or_spectrum。
    """
    return fit_static.draw_fit_or_spectrum(ax, df, AXIS, **kwargs)


def plot_element_static(data, **kwargs):
    """
    元素谱静态出版图：传入单个 DataFrame 画一张图，传入字典时每个元素一个子图。

    参数见 common.fit_static.plot_fits_static，常用的有 component_colors、palette、
    n_cols、hide_y_ticks、save_path。返回 (fig, axes)。
    """
    return fit_static.plot_fits_static(data, AXIS, **kwargs)
