# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
打开着的项目。

内存中的 Project 是唯一的事实来源（设计原则“数据优先于界面状态”）：界面上的操作先改项目，
再通知各个视图刷新。这个文件不依赖 flet，可以单独测试。
"""
from __future__ import annotations

import uuid
from pathlib import Path

from ..project import Project, load_project, save_project
from .strings import S

UI_STATE_VERSION = 1


class ProjectSession:
    def __init__(self, project: Project | None = None, *, backup_key: str | None = None):
        self.project = project if project is not None else Project(S.UNTITLED)
        self._listeners = []
        self.read_only = False   # 项目已在别的窗口中打开、选择了只读：不保存到原来的文件
        self.backup_key = backup_key or uuid.uuid4().hex[:16]   # 自动备份的文件名（services/autosave.py）
        self.locked_path: Path | None = None   # 这个窗口持有锁的项目文件（services/locks.py）

    # ---------- 通知 ----------
    def subscribe(self, listener) -> None:
        """
        listener(kind, source)：kind 为 "data"（数据或样品变了）、"saved"、"renamed" 等；
        source 是发起修改的标签视图（它自己已经刷新过），其他来源时为 None。
        """
        if listener not in self._listeners:
            self._listeners.append(listener)

    def unsubscribe(self, listener) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)

    def changed(self, kind: str = "data", source=None) -> None:
        for listener in list(self._listeners):
            listener(kind, source)

    # ---------- 状态 ----------
    @property
    def name(self) -> str:
        return self.project.name

    @property
    def path(self) -> Path | None:
        return Path(self.project.file_path) if self.project.file_path else None

    @property
    def dirty(self) -> bool:
        return bool(self.project.dirty)

    def rename(self, name: str) -> None:
        name = name.strip()
        if name and name != self.project.name:
            self.project.name = name
            self.project.dirty = True
            self.changed("renamed")

    # ---------- 打开与保存 ----------
    @classmethod
    def open(cls, path) -> ProjectSession:
        return cls(load_project(path))

    def write(self, path=None, ui_state: dict | None = None) -> Path:
        """
        写入文件（不通知界面，可以在后台线程中调用）：保存到 path（另存为）或原来的文件。
        还没有起名的项目用文件名作项目名。
        """
        if ui_state is not None:
            self.project.ui_state = ui_state
        if path is not None and self.project.name == S.UNTITLED:
            self.project.name = Path(path).stem
        return save_project(self.project, path)

    def save(self, path=None, ui_state: dict | None = None) -> Path:
        saved = self.write(path, ui_state)
        self.changed("saved")
        return saved


# ============================================================
# 界面状态：保存在项目中，重新打开时恢复标签
# ============================================================
def make_ui_state(tabs: list[dict], active: int) -> dict:
    """tabs：[{"module": 模块键, "state": {...}}, ...]（不含固定的“项目”标签）；active：0 为“项目”标签。"""
    return {"version": UI_STATE_VERSION, "tabs": tabs, "active": active}


def read_ui_state(ui_state, known_modules) -> tuple[list[dict], int]:
    """
    读出要恢复的标签，忽略不认识的模块；没有保存过界面状态时返回 ([], 0)。
    返回 (tabs, active)，active 超出范围时退回 0（“项目”标签）。
    """
    if not isinstance(ui_state, dict) or not isinstance(ui_state.get("tabs"), list):
        return [], 0
    tabs = [{"module": t["module"], "state": t.get("state") if isinstance(t.get("state"), dict) else {}}
            for t in ui_state["tabs"] if isinstance(t, dict) and t.get("module") in known_modules]
    active = ui_state.get("active", 0)
    if not isinstance(active, int) or isinstance(active, bool) or not 0 <= active <= len(tabs):
        active = 0
    return tabs, active
