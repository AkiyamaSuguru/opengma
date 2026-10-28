# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
Raman 拟合谱（分峰，如 D、G 峰）静态出版图，基于 matplotlib。

支持两种数据（列名见 Raman/schema.py）：
1. 未拟合：["Raman Shift (cm-1)", "Intensity"]
2. 已拟合：["Raman Shift (cm-1)", "Intensity", "Fitting Curve", 分峰列..., "Background"]

配色：默认按通用色卡 palette 取色；出版绘图时可传 component_colors（如
RPlotter/color_tables.py 中的 COMPONENT_COLORS），按谱峰固定颜色。

具体实现在 GMA.CM.common.fit_static（XPS 元素谱与 Raman 拟合谱共用），
这里绑定 Raman 的横轴（拉曼位移）。
"""
from ...common import fit_static
from ..schema import AXIS


def draw_fit(ax, df, **kwargs):
    """
    画一条拟合谱：原始数据点、拟合包络线、背景和各分峰；未拟合时画一条谱线。

    参数见 common.fit_static.draw_fit_or_spectrum，常用的有 component_colors、
    component_mode、show_legend、hide_y_ticks。
    """
    return fit_static.draw_fit_or_spectrum(ax, df, AXIS, **kwargs)


def plot_fit_static(data, **kwargs):
    """
    拟合谱静态出版图：传入单个 DataFrame 画一张图，传入字典时每条谱一个子图。

    参数见 common.fit_static.plot_fits_static，常用的有 component_colors、palette、
    n_cols、hide_y_ticks、save_path。返回 (fig, axes)。
    """
    return fit_static.plot_fits_static(data, AXIS, **kwargs)
