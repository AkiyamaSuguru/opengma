# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
颜色、字号、间距；浅色 / 深色；主题色。

界面中自己画的部分（面板、边框、标签栏等）用 Palette 中的颜色；Flet 自带的控件（按钮、输入框、
开关等）用 make_theme() 生成的主题，由主题色生成整套配色。两者都随主题色和浅色 / 深色变化。
"""
from __future__ import annotations

import colorsys
import re
from dataclasses import dataclass
from pathlib import Path

import flet as ft

DEFAULT_PRIMARY = "#146C7E"
PRESETS = [("青蓝", "#146C7E"), ("墨蓝", "#2C4F8C"), ("松绿", "#2F7A55"), ("赭石", "#A2552B"), ("石墨", "#4B5563")]
HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")

# 方案 11.1 中的颜色
LIGHT = {"bg": "#F4F6F8", "panel": "#FFFFFF", "subtle": "#EEF2F5", "border": "#DDE3E8", "strip": "#E8EDF1",
         "text": "#1B2730", "muted": "#5F6F7A", "faint": "#8C99A4",
         "success": "#15803D", "warning": "#B45309", "error": "#B42318"}
DARK = {"bg": "#0F1418", "panel": "#161C21", "subtle": "#1D252B", "border": "#2A343C", "strip": "#12181C",
        "text": "#E3E9EE", "muted": "#93A2AD", "faint": "#66757F",
        "success": "#4ADE80", "warning": "#FBBF24", "error": "#F87171"}
# 默认主题色在深色模式下的颜色与浅底，取方案中的值；自定义主题色按同样的规律计算
DEFAULT_DARK_PRIMARY, DEFAULT_LIGHT_WEAK, DEFAULT_DARK_WEAK = "#4FB3C4", "#E2F0F3", "#12343B"

# 字号（方案 11.2）与形状（11.3）
SIZE_TITLE, SIZE_PANEL_TITLE, SIZE_BODY, SIZE_SMALL, SIZE_TINY = 17, 13.5, 13, 12, 11.5
RADIUS_PANEL, RADIUS_CONTROL = 12, 8

FONT_DIR = Path(__file__).parent / "assets" / "fonts"
UI_FONT = "Noto Sans SC"


# ============================================================
# 颜色计算
# ============================================================
def is_hex(value) -> bool:
    return isinstance(value, str) and bool(HEX.match(value.strip()))


def _rgb(color: str) -> tuple[float, float, float]:
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) / 255 for i in (0, 2, 4))


def _hex(rgb) -> str:
    return "#" + "".join(f"{round(max(0.0, min(1.0, c)) * 255):02X}" for c in rgb)


def mix(a: str, b: str, t: float) -> str:
    """a 与 b 按 t 混合：t=0 为 a，t=1 为 b。"""
    ra, rb = _rgb(a), _rgb(b)
    return _hex(x + (y - x) * t for x, y in zip(ra, rb, strict=True))


def _with_lightness(color: str, lightness: float) -> str:
    h, _, s = colorsys.rgb_to_hls(*_rgb(color))
    return _hex(colorsys.hls_to_rgb(h, lightness, s))


def dark_primary(primary: str) -> str:
    """深色模式下的主题色：提亮，保证在深色背景上看得清。"""
    if primary.upper() == DEFAULT_PRIMARY:
        return DEFAULT_DARK_PRIMARY
    _, lightness, _ = colorsys.rgb_to_hls(*_rgb(primary))
    return _with_lightness(primary, max(lightness, 0.55))


def weak(primary: str, dark: bool) -> str:
    """主色浅底：选中行、悬停卡片等的底色。"""
    if primary.upper() == DEFAULT_PRIMARY:
        return DEFAULT_DARK_WEAK if dark else DEFAULT_LIGHT_WEAK
    return mix(primary, DARK["panel"], 0.72) if dark else mix(primary, "#FFFFFF", 0.88)


def on_color(color: str) -> str:
    """在该颜色上写字用黑色还是白色。"""
    r, g, b = _rgb(color)
    return "#FFFFFF" if 0.2126 * r + 0.7152 * g + 0.0722 * b < 0.6 else "#1B2730"


# ============================================================
# 调色板
# ============================================================
@dataclass(frozen=True)
class Palette:
    dark: bool
    primary: str        # 当前模式下的主题色
    primary_weak: str   # 主色浅底
    on_primary: str     # 主题色上的文字
    bg: str             # 页面背景
    panel: str          # 面板、卡片
    subtle: str         # 次级背景（悬停、输入框底色）
    border: str
    strip: str          # 工作区标签栏
    text: str
    muted: str          # 次要文字
    faint: str          # 更弱的文字、占位
    success: str
    warning: str
    error: str


def palette(primary: str = DEFAULT_PRIMARY, dark: bool = False) -> Palette:
    primary = primary if is_hex(primary) else DEFAULT_PRIMARY
    base = DARK if dark else LIGHT
    main = dark_primary(primary) if dark else primary.upper()
    return Palette(dark=dark, primary=main, primary_weak=weak(primary, dark), on_primary=on_color(main), **base)


def available_font() -> str | None:
    """assets/fonts 中有界面字体时返回字体族名，否则返回 None（用系统默认字体）。"""
    return UI_FONT if any(FONT_DIR.glob("NotoSansSC*.[ot]tf")) else None


def font_files() -> dict[str, str]:
    """注册给 page.fonts 的字体：{字体族名: assets 中的相对路径}。"""
    files = sorted(FONT_DIR.glob("NotoSansSC*.[ot]tf"))
    if not files:
        return {}
    regular = next((f for f in files if "Regular" in f.name or "VF" in f.name or "Variable" in f.name), files[0])
    return {UI_FONT: f"fonts/{regular.name}"}


def make_theme(p: Palette, font: str | None = None) -> ft.Theme:
    """Flet 控件用的主题：由主题色生成配色，并统一字体、分隔线和滚动条颜色。"""
    return ft.Theme(
        color_scheme_seed=p.primary,
        font_family=font,
        use_material3=True,
        divider_theme=ft.DividerTheme(color=p.border, thickness=1, space=1),
        scrollbar_theme=ft.ScrollbarTheme(thickness=6, radius=3,
                                          thumb_color=ft.Colors.with_opacity(0.35, p.muted)),
        tooltip_theme=ft.TooltipTheme(wait_duration=500),
        visual_density=ft.VisualDensity.COMPACT,
    )
