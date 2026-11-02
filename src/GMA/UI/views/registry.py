# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
模块注册表。

每个模块在这里登记一次：名称、图标、颜色、类别（表征方法 / 计算工具）、状态（可用 / 规划中）。
启动器的模块区、“全部模块”、工作区的“+”菜单和标签图标都从这里读取，新增表征方法或计算模块时
不改框架代码。模块色固定，不随主题色变化（方案 11.1）。
"""
from __future__ import annotations

from dataclasses import dataclass

from ..strings import S

METHOD, TOOL = "method", "tool"
AVAILABLE, PLANNED = "available", "planned"
CATEGORY_TITLES = {METHOD: S.CATEGORY_METHOD, TOOL: S.CATEGORY_TOOL}


@dataclass(frozen=True)
class ModuleSpec:
    key: str
    title: str
    icon: str            # assets/icons/ 中的 SVG 文件名（不含扩展名）
    color: str           # 浅色模式下的模块色
    color_dark: str      # 深色模式下的模块色
    tint: str            # 浅色模式下图标的底色
    tint_dark: str
    category: str        # METHOD / TOOL
    status: str          # AVAILABLE / PLANNED
    description: str     # 卡片上的一两行说明，用 \n 分行
    method: str | None = None   # 对应项目中的方法（XPS、Raman、XRD）；计算工具为 None
    formats: str = ""           # 支持的文件，显示在空模块页上

    @property
    def planned(self) -> bool:
        return self.status == PLANNED

    def color_for(self, dark: bool) -> str:
        return self.color_dark if dark else self.color

    def tint_for(self, dark: bool) -> str:
        return self.tint_dark if dark else self.tint

    @property
    def icon_src(self) -> str:
        return f"icons/{self.icon}.svg"


MODULES: tuple[ModuleSpec, ...] = (
    ModuleSpec("xps", "XPS", "xps", "#2563EB", "#60A5FA", "#E5EEFE", "#1B2A44", METHOD, AVAILABLE,
               "Avantage 导出数据\n全谱 · 元素谱", method="XPS", formats="Avantage 导出的 .xlsx / .xls，其他软件导出的表格"),
    ModuleSpec("raman", "Raman", "raman", "#7C3AED", "#A78BFA", "#F0E9FE", "#2A2142", METHOD, AVAILABLE,
               "Horiba LabSpec\n谱线 · 拟合谱", method="Raman", formats="LabSpec 导出的 .txt，其他软件导出的表格"),
    ModuleSpec("xrd", "XRD", "xrd", "#D97706", "#FBBF24", "#FDF1DE", "#3A2D14", METHOD, AVAILABLE,
               "Bruker D8 Advance\n图谱 · 参考物相", method="XRD", formats="D8 Advance 导出的 .txt，其他软件导出的表格"),
    ModuleSpec("srim", "SRIM · dpa", "calc", "#64748B", "#94A3B8", "#EDF0F4", "#252C35", TOOL, PLANNED,
               "离子辐照\n损伤计算"),
    ModuleSpec("salt", "熔盐配比", "calc", "#64748B", "#94A3B8", "#EDF0F4", "#252C35", TOOL, PLANNED,
               "LiF-NaF-KF 等\n质量配比"),
)
_BY_KEY = {m.key: m for m in MODULES}
_BY_METHOD = {m.method: m for m in MODULES if m.method}


def get(key: str) -> ModuleSpec | None:
    return _BY_KEY.get(key)


def for_method(method: str) -> ModuleSpec | None:
    """项目中的方法（XPS、Raman、XRD）对应的模块。"""
    return _BY_METHOD.get(method)


def by_category() -> dict[str, list[ModuleSpec]]:
    """{类别: [模块, ...]}，按注册顺序。"""
    out = {METHOD: [], TOOL: []}
    for m in MODULES:
        out.setdefault(m.category, []).append(m)
    return out


def available() -> list[ModuleSpec]:
    return [m for m in MODULES if not m.planned]
