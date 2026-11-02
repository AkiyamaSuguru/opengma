# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
SRIM 深度分布的出版图：损伤（dpa）画在左纵轴，注入离子浓度（at.%）画在右纵轴，样式与 CM 中的出版图相同。

    from GMA.SC.SRIM import SRIMPlotter, depth_profile, read_range, read_vacancy

    profile = depth_profile(read_vacancy("VACANCY.txt"), read_range("RANGE.txt"), fluence=1e16)
    SRIMPlotter().plot_profile_static(profile, depth_unit="nm", save_path="dpa.png")
"""
from __future__ import annotations

import matplotlib.pyplot as plt

from ...CM.common.palette import palette_colors
from ...CM.common.plotter import BasePlotter
from ...CM.common.style import (
    DEFAULT_FONT_FAMILY,
    DEFAULT_FONT_SIZE,
    PANEL_SIZE,
    finish_figure,
    mpl_style,
)
from .damage import DEPTH, DPA, IONS_PERCENT, element_column

DEPTH_UNITS = {"nm": (1.0, "nm"), "um": (1e-3, "μm"), "μm": (1e-3, "μm"), "µm": (1e-3, "μm"),
               "A": (10.0, "Å"), "Å": (10.0, "Å"), "angstrom": (10.0, "Å")}


def depth_unit(unit: str) -> tuple[float, str]:
    """深度单位：返回（从 nm 换算的倍数，坐标轴上的写法）。"""
    try:
        return DEPTH_UNITS[unit]
    except KeyError:
        raise ValueError(f"Unknown depth unit {unit!r}; use 'nm', 'um' or 'A'.") from None


def plot_profile_static(
        profile,
        *,
        depth_unit_name="nm",
        damage=True,
        concentration=True,
        elements=False,
        interfaces=None,
        color=None,
        ions_color=None,
        linewidth=1.0,
        show_legend=True,
        legend_loc="best",
        hide_y_ticks=False,
        figsize=None,
        save_path=None,
        dpi=600,
        show=True,
        palette=None,
        font_family=DEFAULT_FONT_FAMILY,
        font_size=DEFAULT_FONT_SIZE,
        use_latex=False,
):
    """见 SRIMPlotter.plot_profile_static。"""
    factor, unit_label = depth_unit(depth_unit_name)
    has_dpa = damage and DPA in profile
    has_ions = concentration and IONS_PERCENT in profile
    if not has_dpa and not has_ions:
        raise ValueError("Nothing to plot: the profile has neither dpa nor ion concentration, "
                         "or both are turned off.")
    ion = profile.attrs.get("ion") or "Ion"
    symbols = [c[len("dpa ("):-1] for c in profile.columns if c.startswith("dpa (")] if elements and has_dpa else []
    colors = palette_colors(2 + len(symbols), palette)
    color = color or colors[0]
    ions_color = ions_color or (colors[1] if has_dpa else colors[0])
    depth = profile[DEPTH].to_numpy(dtype=float) * factor
    if interfaces is None:
        interfaces = profile.attrs.get("interfaces", [])

    with mpl_style(font_family, font_size, use_latex):
        fig, ax = plt.subplots(figsize=figsize or PANEL_SIZE)
        handles = []
        if has_dpa:
            handles += ax.plot(depth, profile[DPA], color=color, linewidth=linewidth, label="dpa")
            for symbol, c in zip(symbols, colors[2:], strict=False):
                handles += ax.plot(depth, profile[element_column(symbol)], color=c, linewidth=0.8 * linewidth,
                                   linestyle="--", label=symbol)
            ax.set_ylabel("Damage (dpa)")
        second = None
        if has_ions:
            target = ax
            if has_dpa:
                second = target = ax.twinx()
                ax.tick_params(axis="y", which="both", right=False)
                second.tick_params(axis="y", which="both", left=False, right=True, direction="in")
            handles += target.plot(depth, profile[IONS_PERCENT], color=ions_color, linewidth=linewidth,
                                   linestyle="-." if has_dpa else "-", label=f"{ion} (at.%)")
            target.set_ylabel(f"{ion} concentration (at.%)")
            target.set_ylim(bottom=0)
            if has_dpa:
                ax.yaxis.label.set_color(color)
                second.yaxis.label.set_color(ions_color)
        for x in interfaces:
            ax.axvline(float(x) * factor, color="#808080", linewidth=0.6, linestyle=":", zorder=0)
        ax.set_xlabel(f"Depth ({unit_label})")
        ax.set_xlim(0, depth[-1])
        ax.set_ylim(bottom=0)
        ax.xaxis.set_ticks_position("bottom")
        if second is not None:
            second.xaxis.set_ticks_position("bottom")
        if hide_y_ticks:
            for a in (ax, second):
                if a is not None:
                    a.set_yticks([])
        if show_legend and len(handles) > 1:
            base = plt.rcParams["font.size"]
            (second or ax).legend(handles, [h.get_label() for h in handles], fontsize=0.75 * base, frameon=False,
                                  loc=legend_loc)
        finish_figure(fig, save_path, dpi, show)
    return fig, (ax if second is None else (ax, second))


class SRIMPlotter(BasePlotter):
    """
    SRIM 深度分布的绘图入口：保存字体、通用色卡等设置，数据在调用时传入。
    构造参数（font_family、font_size、palette、use_latex）见 GMA.CM.common.plotter.BasePlotter。
    """

    def plot_profile_static(self, profile, *, depth_unit="nm", **kwargs):
        """
        depth_profile() 的结果画成一张图：dpa 在左纵轴（实线），注入离子浓度在右纵轴（点划线）；
        只有其中一种时只画一条纵轴。

        depth_unit : "nm"（默认）、"um" 或 "A"。
        damage : 是否画 dpa（profile 中有时）。
        concentration : 是否画注入离子浓度（profile 中有时）。
        elements : True 时另画 Full Cascade 中各元素的 dpa（虚线）。
        interfaces : 多层靶界面的深度（nm），画成灰色点线；None 时取 profile.attrs 中的值。
        color、ions_color : dpa、离子浓度曲线的颜色，None 时按通用色卡取色。
        show_legend、legend_loc、hide_y_ticks、figsize、save_path、dpi、show 与 CM 中的出版图相同。

        返回 (fig, ax)；同时画两条纵轴时返回 (fig, (ax, ax_ions))。
        """
        return plot_profile_static(profile, depth_unit_name=depth_unit, **self._options(kwargs))

    @staticmethod
    def info(profile) -> None:
        """打印深度分布的列名、行数和计算条件。"""
        print(f"Shape: {profile.shape}")
        print(f"Columns: {list(profile.columns)}")
        for key, value in profile.attrs.items():
            print(f"{key}: {value}")
