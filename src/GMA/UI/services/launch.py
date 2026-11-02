# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
新建窗口：Flet 一个进程只有一个窗口，所以新窗口是再启动一个 OpenGMA 进程（方案 3：启动新进程的做法
只用于“新建窗口”）。

- 从源码或安装的包运行时：用当前的 Python 运行 python -m GMA.UI；
- flet build 打包的程序：再运行一次程序本身（sys.executable 指向程序时；Linux 上也可以从 /proc/self/exe 得到）。

新进程从启动器开始（环境变量 OPENGMA_NEW_WINDOW），不自动打开上次的项目。三个系统做法相同；
CREATE_NO_WINDOW 只在 Windows 上有，其他系统上为 0（不起作用），避免 Windows 上弹出命令行窗口。
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

NEW_WINDOW_ENV = "OPENGMA_NEW_WINDOW"


def packaged() -> bool:
    """flet build 打包的程序（Flet 在其中设置 FLET_PLATFORM）。"""
    return os.environ.get("FLET_PLATFORM") is not None


def _program(path) -> str | None:
    try:
        path = Path(path).resolve()
    except (OSError, TypeError, ValueError):
        return None
    if path.is_file() and not path.name.lower().startswith("python"):
        return str(path)
    return None


def new_window_command() -> list[str] | None:
    """启动新窗口的命令；打包的程序中找不到程序本身时为 None（这时不提供“新建窗口”）。"""
    if not packaged():
        return [sys.executable, "-m", "GMA.UI"] if sys.executable else None
    for candidate in (sys.executable, "/proc/self/exe"):
        program = _program(candidate) if candidate else None
        if program is not None:
            return [program]
    return None


def open_new_window() -> bool:
    """启动新窗口；不能启动时返回 False。"""
    command = new_window_command()
    if command is None:
        return False
    env = dict(os.environ)
    env[NEW_WINDOW_ENV] = "1"
    try:
        subprocess.Popen(command, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, close_fds=True, start_new_session=True,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except OSError:
        return False
    return True


def is_new_window() -> bool:
    """这个进程是“新建窗口”启动的：从启动器开始。读过之后清除，这个进程再启动的新窗口另外设置。"""
    return os.environ.pop(NEW_WINDOW_ENV, None) == "1"
