# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
自动备份（方案 9.5）：有未保存的修改时，每 5 分钟把打开的项目写一份到用户目录下的 .opengma/autosave。

- 每个打开的项目一个备份：<key>.nc 是项目（含界面状态），<key>.json 记录项目名、原来的文件、备份时间；
- 程序运行期间每分钟更新 .json 中的 alive_at（“心跳”）。启动时，超过 3 分钟没有心跳的备份说明上次没有
  正常关闭（崩溃、断电、强制退出），提示恢复；另一个窗口正在使用的备份有心跳，不会被当成需要恢复的；
- 保存项目、正常关闭时删除备份。

只用文件和时间判断，Windows、macOS、Linux 做法相同。这个文件不依赖 flet。
"""
from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from ...project import Project, load_project, write_tree
from ..settings import settings_dir

INTERVAL = 300    # 自动备份的间隔（秒）
HEARTBEAT = 60    # 心跳的间隔（秒）
STALE = 180       # 超过这么久没有心跳，认为写备份的程序已经不在运行（秒）


def autosave_dir() -> Path:
    return settings_dir() / "autosave"


def new_key() -> str:
    return uuid.uuid4().hex[:16]


def now() -> datetime:
    return datetime.now(UTC)


@dataclass
class Backup:
    key: str
    meta: dict

    @property
    def path(self) -> Path:
        return autosave_dir() / f"{self.key}.nc"

    @property
    def name(self) -> str:
        return str(self.meta.get("name") or self.key)

    @property
    def source(self) -> str | None:
        """原来的项目文件；还没有保存过的项目为 None。"""
        return self.meta.get("source") or None

    @property
    def saved_at(self) -> str:
        return str(self.meta.get("saved_at") or "")

    def alive_since(self) -> datetime | None:
        try:
            return datetime.fromisoformat(self.meta.get("alive_at"))
        except (TypeError, ValueError):
            return None

    def orphaned(self, at: datetime | None = None) -> bool:
        """写这个备份的程序已经不在运行（超过 STALE 秒没有心跳）。"""
        alive = self.alive_since()
        return alive is None or (at or now()) - alive > timedelta(seconds=STALE)


def _meta_path(key: str) -> Path:
    return autosave_dir() / f"{key}.json"


def _write_meta(key: str, meta: dict) -> None:
    path = _meta_path(key)
    temporary = path.with_name(f".{path.name}.saving")
    temporary.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(temporary, path)


def write_backup(key: str, tree, *, name: str, source) -> Path:
    """
    写备份：tree 是 project_to_datatree() 的结果（在主线程中生成），这里可以在后台线程中调用。
    source 是原来的项目文件（没有时为 None）。
    """
    folder = autosave_dir()
    folder.mkdir(parents=True, exist_ok=True)
    path = write_tree(tree, folder / f"{key}.nc")
    stamp = now().isoformat(timespec="seconds")
    _write_meta(key, {"key": key, "name": name, "source": str(source) if source else None,
                      "saved_at": stamp, "alive_at": stamp, "pid": os.getpid()})
    return path


def heartbeat(key: str) -> None:
    """程序还在运行：更新备份的 alive_at（还没有写过备份时什么也不做）。"""
    path = _meta_path(key)
    try:
        meta = json.loads(path.read_text(encoding="utf-8"))
        meta["alive_at"] = now().isoformat(timespec="seconds")
        _write_meta(key, meta)
    except (OSError, ValueError):
        pass


def remove_backup(key: str) -> None:
    for path in (autosave_dir() / f"{key}.nc", _meta_path(key)):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass


def list_backups(*, orphaned_only: bool = True) -> list[Backup]:
    """自动备份，最新的在前。orphaned_only 时只列出上次没有正常关闭留下的（没有心跳的）。"""
    folder = autosave_dir()
    if not folder.is_dir():
        return []
    out = []
    for meta_path in folder.glob("*.json"):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        backup = Backup(meta_path.stem, meta if isinstance(meta, dict) else {})
        if backup.path.is_file() and (not orphaned_only or backup.orphaned()):
            out.append(backup)
    return sorted(out, key=lambda b: b.saved_at, reverse=True)


def open_backup(backup: Backup) -> Project:
    """
    打开备份：项目的文件路径设为原来的文件（还没有保存过的项目为 None），并标记为有未保存的修改，
    用户确认后保存才会写回原来的文件。
    """
    project = load_project(backup.path)
    project.file_path = Path(backup.source) if backup.source else None
    project.dirty = True
    return project
