# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
颜色分配：从通用色卡取色，以及按定制色表（{名称: 颜色}）指定颜色。
"""
from __future__ import annotations

import warnings
from collections.abc import Mapping, Sequence

import matplotlib as mpl
import numpy as np
from matplotlib.colors import to_hex, to_rgb

from . import color_tables


def palette_colors(n: int, palette=None) -> list:
    """
    从通用色卡取 n 个颜色，返回十六进制颜色字符串（matplotlib 和 plotly 通用）。

    palette 可以是：
    - None：使用 common/color_tables.py 中的 DEFAULT_PALETTE；
    - matplotlib 离散色卡名（如 "tab10"、"Set2"，见 matplotlib.color_sequences）：
      按顺序取色，不够时循环；
    - matplotlib 连续色卡名（如 "viridis"）：按数量均匀取色；
    - 颜色列表：按顺序取色，不够时循环。
    """
    if palette is None:
        palette = color_tables.DEFAULT_PALETTE
    if n == 0:
        return []

    if isinstance(palette, str):
        if palette in mpl.color_sequences:
            return _cycle(mpl.color_sequences[palette], n)
        if palette in mpl.colormaps:
            cmap = mpl.colormaps[palette]
            if n == 1:
                return [to_hex(cmap(0.5))]
            return [to_hex(cmap(i / (n - 1))) for i in range(n)]
        raise ValueError(
            f"Unknown palette: {palette!r}\n"
            f"Discrete palettes: {list(mpl.color_sequences)}\n"
            "A matplotlib colormap name (e.g. 'viridis') or a list of colors "
            "also works."
        )

    if isinstance(palette, Mapping):
        raise TypeError(
            "palette must be a palette name or a list of colors. "
            "For {name: color} mappings, use the custom color table parameter "
            "(component_colors, sample_colors or phase_colors)."
        )

    if isinstance(palette, (Sequence, np.ndarray)):
        color_list = list(palette)
        if not color_list:
            raise ValueError("palette color list cannot be empty.")
        return _cycle(color_list, n)

    raise TypeError("palette must be a palette name or a list of colors.")


def _cycle(color_list, n: int) -> list:
    return [to_hex(color_list[i % len(color_list)]) for i in range(n)]


def assign_colors(
        names,
        palette=None,
        custom=None,
        *,
        avoid=(),
        warn_missing=False,
        custom_name="custom",
) -> list:
    """
    给每个名称分配颜色。

    custom 为定制色表 {名称: 颜色}：表里有的名称用指定颜色（不同名称可以同色）；
    其余名称按通用色卡 palette 依次取色，并跳过定制色表已经用掉的颜色和 avoid 中的颜色，
    避免撞色。custom 为 None 或 {} 时全部按 palette 取色（同样跳过 avoid 中的颜色）。

    warn_missing=True 时，有名称不在定制色表中就给出警告，便于发现漏写或名称写错。
    """
    names = list(names)
    custom = custom or {}
    if not isinstance(custom, Mapping):
        raise TypeError(
            f"{custom_name} must be a dict such as {{'C-Si': 'tab:blue'}}."
        )

    fixed = {name: to_hex(custom[name]) for name in names if name in custom}
    rest = [name for name in names if name not in fixed]
    if not rest:
        return [fixed[name] for name in names]

    if warn_missing and custom:
        warnings.warn(
            f"{custom_name} has no color for {rest}; using palette colors instead.",
            stacklevel=3,
        )

    used = set(fixed.values()) | {to_hex(color) for color in avoid}
    if not used:
        rest_colors = iter(palette_colors(len(rest), palette))
    else:
        pool = palette_colors(len(rest) + len(used), palette)
        free = [color for color in pool if color not in used] or pool
        rest_colors = iter([free[i % len(free)] for i in range(len(rest))])
    return [fixed[name] if name in fixed else next(rest_colors) for name in names]


def to_rgba_string(color, alpha: float) -> str:
    """把颜色转成 plotly 用的 "rgba(r, g, b, a)" 字符串。"""
    r, g, b = (round(255 * c) for c in to_rgb(color))
    return f"rgba({r}, {g}, {b}, {alpha})"
