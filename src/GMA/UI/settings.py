# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
设置：保存在用户目录下的 .opengma/settings.json，界面和 marimo 都能读取。

这个文件不依赖 flet。读取时忽略不认识的键，值不合法时用默认值，所以旧版本、新版本的设置文件
都能读；保存时先写临时文件再替换，中断时原文件不受影响。设置文件所在的文件夹可以用环境变量
OPENGMA_HOME 改到别处（测试中用到）。
"""
from __future__ import annotations

import json
import math
import os
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime
from pathlib import Path

DEFAULT_READERS = {"XPS": "Avantage", "Raman": "Horiba HR evolution", "XRD": "D8 Advance"}
CHOICES = {
    "theme_mode": ("system", "light", "dark"),
    "density": ("standard", "compact"),
    "figure_format": ("png", "svg", "pdf", "tiff", "jpg"),
    "component_mode": ("absolute", "relative"),
    "export_format": ("xlsx", "csv"),
    "close_workspace": ("launcher", "quit"),
    "startup": ("launcher", "last_project"),
    "language": ("zh",),
}


def settings_dir() -> Path:
    return Path(os.environ.get("OPENGMA_HOME") or Path.home() / ".opengma").expanduser()


def settings_path() -> Path:
    return settings_dir() / "settings.json"


@dataclass
class RecentProject:
    """最近打开的项目：路径、项目中打开过的模块（按标签顺序）、上次停留的模块、打开时间。"""

    path: str
    modules: list[str] = field(default_factory=list)
    active: str | None = None
    opened_at: str = ""

    @classmethod
    def from_dict(cls, data) -> RecentProject | None:
        if not isinstance(data, dict) or not isinstance(data.get("path"), str) or not data["path"]:
            return None
        modules = [m for m in data.get("modules", []) if isinstance(m, str)]
        active = data.get("active") if isinstance(data.get("active"), str) else None
        opened_at = data.get("opened_at") if isinstance(data.get("opened_at"), str) else ""
        return cls(data["path"], modules, active, opened_at)

    @property
    def exists(self) -> bool:
        return Path(self.path).is_file()


@dataclass
class Settings:
    # 外观
    theme_mode: str = "system"
    primary: str = "#146C7E"
    density: str = "standard"
    # 窗口：默认尺寸占可用屏幕区域的比例；记住的尺寸；测得的可用区域
    launcher_ratio: list[float] = field(default_factory=lambda: [0.42, 0.52])
    workspace_ratio: list[float] = field(default_factory=lambda: [0.85, 0.90])
    remember_size: bool = True
    launcher_size: list[int] | None = None
    workspace_size: list[int] | None = None
    work_area: list[float] | None = None
    # 绘图
    figure_font: str = "Times New Roman"
    figure_font_size: float = 8.0
    color_cycle: str = "tab10"
    latex: bool = False
    dpi: int = 600
    figure_format: str = "png"
    decimate: bool = False
    decimate_points: int = 4000
    # 数据
    readers: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_READERS))
    component_mode: str = "absolute"
    export_format: str = "xlsx"
    # 常规
    close_workspace: str = "launcher"
    startup: str = "launcher"
    recent_limit: int = 5
    language: str = "zh"
    recent: list[RecentProject] = field(default_factory=list)
    # 计算工具：熔盐配比的预设组成，None 表示使用内置预设（见 GMA.SC.Salts.PRESETS）
    salt_presets: list[dict] | None = None

    # ---------- 读写 ----------
    @classmethod
    def from_dict(cls, data) -> Settings:
        """从 JSON 数据生成设置；不认识的键忽略，类型不对或取值不在范围内的用默认值。"""
        settings = cls()
        if not isinstance(data, dict):
            return settings
        for f in fields(cls):
            if f.name not in data or f.name == "recent":
                continue
            value, default = data[f.name], getattr(settings, f.name)
            if f.name in CHOICES:
                if value in CHOICES[f.name]:
                    setattr(settings, f.name, value)
            elif f.name in ("launcher_ratio", "workspace_ratio"):
                if _pair(value) and all(0.1 <= v <= 1.0 for v in value):
                    setattr(settings, f.name, [float(v) for v in value])
            elif f.name in ("launcher_size", "workspace_size", "work_area"):
                if value is None or (_pair(value) and all(v > 0 for v in value)):
                    setattr(settings, f.name, None if value is None else [float(v) for v in value])
            elif f.name == "salt_presets":
                settings.salt_presets = clean_presets(value)
            elif f.name == "readers":
                if isinstance(value, dict):
                    settings.readers.update({k: v for k, v in value.items() if isinstance(v, str)})
            elif f.name == "primary":
                if isinstance(value, str) and len(value) == 7 and value.startswith("#"):
                    try:
                        int(value[1:], 16)
                        settings.primary = value.upper()
                    except ValueError:
                        pass
            elif isinstance(default, bool):
                if isinstance(value, bool):
                    setattr(settings, f.name, value)
            elif isinstance(default, (int, float)) and not isinstance(value, bool) and isinstance(value, (int, float)):
                if value > 0:
                    setattr(settings, f.name, type(default)(value))
            elif isinstance(default, str) and isinstance(value, str):
                setattr(settings, f.name, value)
        recent = data.get("recent", [])
        if isinstance(recent, list):
            settings.recent = [r for r in (RecentProject.from_dict(x) for x in recent) if r is not None]
        settings.recent = settings.recent[: settings.recent_limit]
        return settings

    def to_dict(self) -> dict:
        return asdict(self)

    # ---------- 最近项目 ----------
    def add_recent(self, path, modules=(), active=None) -> None:
        """把项目放到最近项目的最前面；同一个文件只保留一条。"""
        path = str(Path(path).expanduser())
        self.recent = [r for r in self.recent if r.path != path]
        self.recent.insert(0, RecentProject(path, list(modules), active, datetime.now().astimezone().isoformat(timespec="seconds")))
        del self.recent[self.recent_limit:]

    def remove_recent(self, path) -> None:
        path = str(path)
        self.recent = [r for r in self.recent if r.path != path]


def clean_presets(value) -> list[dict] | None:
    """
    熔盐配比的预设：[{"name": 名称, "salts": [[化学式, 摩尔比例, 摩尔质量或 None], ...]}, ...]。
    格式不对的条目跳过；整个值不是列表时为 None（使用内置预设）。
    """
    if not isinstance(value, list):
        return None
    out, names = [], set()
    for item in value:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str) or not item["name"].strip():
            continue
        name = item["name"].strip()
        salts = []
        for row in item.get("salts") or []:
            if (isinstance(row, (list, tuple)) and len(row) == 3 and isinstance(row[0], str) and row[0].strip()
                    and _number(row[1]) and (row[2] is None or _number(row[2]))):
                salts.append([row[0].strip(), float(row[1]), None if row[2] is None else float(row[2])])
        if salts and name not in names:
            names.add(name)
            out.append({"name": name, "salts": salts})
    return out


def _number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def _pair(value) -> bool:
    return (isinstance(value, (list, tuple)) and len(value) == 2
            and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in value))


def load_settings(path=None) -> Settings:
    """读取设置；文件不存在或内容损坏时返回默认设置。"""
    path = Path(path) if path is not None else settings_path()
    try:
        return Settings.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return Settings()


def save_settings(settings: Settings, path=None) -> Path:
    path = Path(path) if path is not None else settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.saving")
    temporary.write_text(json.dumps(settings.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)
    return path
