# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
项目锁（方案风险表“两个窗口打开同一个项目”）：打开项目时在项目文件旁边写一个锁文件
（.项目名.nc.lock），记录是谁、在哪台电脑上打开的；程序运行期间每分钟更新一次时间（心跳）。

另一个窗口（或另一台电脑通过共享文件夹）再打开同一个项目时，发现有心跳的锁就提示以只读方式打开。
程序崩溃留下的锁超过 3 分钟没有心跳，视为失效，直接忽略。只用文件和时间判断，三个系统做法相同。
写不了锁文件（如只读的文件夹）时不影响打开项目。这个文件不依赖 flet。
"""
from __future__ import annotations

import getpass
import json
import os
import platform
from datetime import UTC, datetime, timedelta
from pathlib import Path

STALE = 180   # 超过这么久没有心跳的锁视为失效（秒）


def lock_path(project_path) -> Path:
    path = Path(project_path)
    return path.with_name(f".{path.name}.lock")


def _now() -> datetime:
    return datetime.now(UTC)


def _user() -> str:
    try:
        return getpass.getuser()
    except Exception:  # noqa: BLE001 - 取不到用户名时不影响加锁
        return ""


def read_lock(project_path, token: str | None = None) -> dict | None:
    """
    别人持有的、还有心跳的锁：返回锁的内容（user、host、opened_at 等）；没有锁、锁已失效、
    或者是自己（token 相同）的锁时返回 None。
    """
    try:
        info = json.loads(lock_path(project_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(info, dict) or (token is not None and info.get("token") == token):
        return None
    try:
        alive = datetime.fromisoformat(info.get("alive_at"))
    except (TypeError, ValueError):
        return None
    if _now() - alive > timedelta(seconds=STALE):
        return None
    return info


def acquire(project_path, token: str) -> bool:
    """写锁文件（已有别人的锁时覆盖，调用前应先用 read_lock 询问用户）。写不了时返回 False。"""
    stamp = _now().isoformat(timespec="seconds")
    info = {"token": token, "user": _user(), "host": platform.node(), "pid": os.getpid(),
            "opened_at": stamp, "alive_at": stamp}
    return _write(project_path, info)


def heartbeat(project_path, token: str) -> None:
    """还开着这个项目：更新锁的时间；锁已经被别人接管时不动它。"""
    try:
        info = json.loads(lock_path(project_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        info = None
    if isinstance(info, dict) and info.get("token") not in (None, token):
        return
    if not isinstance(info, dict):
        acquire(project_path, token)
        return
    info["alive_at"] = _now().isoformat(timespec="seconds")
    _write(project_path, info)


def release(project_path, token: str) -> None:
    """关闭项目：删除自己的锁（别人的锁不动）。"""
    path = lock_path(project_path)
    try:
        info = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    if isinstance(info, dict) and info.get("token") == token:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass


def _write(project_path, info: dict) -> bool:
    path = lock_path(project_path)
    temporary = path.with_name(f"{path.name}.writing")
    try:
        temporary.write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
        os.replace(temporary, path)
    except OSError:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        return False
    return True
