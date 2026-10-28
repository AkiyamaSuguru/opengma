# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
XPS 元素谱交互图，基于 plotly，适合在 Notebook 或浏览器中查看数据。

自动判断未拟合 / 拟合谱。拟合谱会画出各分峰的填充区域、轮廓线和峰值位置标记，
点击图例中的分峰名，可以同时隐藏这三个图层。

具体实现在 GMA.CM.common.fit_interactive，这里绑定 XPS 的横轴（结合能，从高到低）。
"""
from ...common import fit_interactive
from ..schema import AXIS


def plot_element_interactive(df, **kwargs):
    """
    绘制一条元素谱的交互图，返回 plotly Figure（.show() 显示，.write_html() 保存）。

    参数见 common.fit_interactive.plot_fit_interactive，常用的有 component_colors、
    palette、component_mode。
    """
    return fit_interactive.plot_fit_interactive(df, AXIS, **kwargs)
