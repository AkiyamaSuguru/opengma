# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""界面中显示的时间、路径、版本等文字。"""
from __future__ import annotations

import importlib.metadata as md
import platform
import re
import sys
from datetime import datetime
from pathlib import Path

from ..strings import S

PACKAGES = ("flet", "flet-charts", "numpy", "pandas", "matplotlib", "xarray", "h5netcdf", "h5py", "openpyxl")


def local_time(iso: str | None) -> datetime | None:
    """把 ISO 时间换成本地时间：带时区的（如项目文件中的 UTC 时间）按时区换算，不带的视为本地时间。无法解析时返回 None。"""
    try:
        return datetime.fromisoformat(iso).astimezone()
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def when(iso: str, now: datetime | None = None) -> str:
    """最近项目的打开时间：今天 21:14 / 昨天 21:14 / 10月28日 / 2025年10月28日。"""
    t = local_time(iso)
    if t is None:
        return ""
    now = now.astimezone() if now else datetime.now().astimezone()
    days = (now.date() - t.date()).days
    if days == 0:
        return S.TODAY.format(time=t.strftime("%H:%M"))
    if days == 1:
        return S.YESTERDAY.format(time=t.strftime("%H:%M"))
    if t.year == now.year:
        return S.DATE_MONTH_DAY.format(m=t.month, d=t.day)
    return S.DATE_FULL.format(y=t.year, m=t.month, d=t.day)


def short_path(path, home: Path | None = None) -> str:
    """把用户目录写成 ~，路径更短。"""
    path, home = Path(path), home or Path.home()
    try:
        return str(Path("~") / path.relative_to(home))
    except ValueError:
        return str(path)


def app_version() -> str:
    try:
        return md.version("opengma")
    except md.PackageNotFoundError:
        return "0.1.0"


def environment() -> str:
    """关于对话框中的运行环境，可以一键复制，方便反馈问题。"""
    lines = [f"OpenGMA {app_version()}", f"Python {sys.version.split()[0]}",
             f"{platform.system()} {platform.release()} ({platform.machine()})"]
    for name in PACKAGES:
        try:
            lines.append(f"{name} {md.version(name)}")
        except md.PackageNotFoundError:
            continue
    return "\n".join(lines)


# 上标负号 ⁻ 不在附带的界面字体中，cm-1 保持原样，避免有的系统上显示成方框
UNITS = {"deg": "°"}


def unit(value: str) -> str:
    """横轴单位的显示写法：deg → °，其余不变。"""
    return UNITS.get(value, value)


def plain_label(label: str) -> str:
    """
    坐标轴标题的纯文字写法：GMA 给出版图用的标题含 matplotlib 的公式写法（如 cm$^{-1}$、2$\\theta$），
    交互图中写成 cm-1、2θ。
    """
    text = label.replace(r"$\theta$", "θ")
    text = re.sub(r"\$\^\{([^}]*)\}\$", r"\1", text)
    return text.replace("$", "")
