# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
OpenGMA 的图形界面（Flet）。

启动：
    uv run opengma
    uv run python -m GMA.UI

界面只是 GMA 的外壳：读取、分析、绘图都调用 GMA 的接口；GMA 的核心不依赖 flet。
"""


def run() -> None:
    """启动图形界面：先按设置选好界面语言，再导入界面模块（它们在导入时就会读取界面文字）。"""
    from . import strings
    from .settings import load_settings

    strings.use(load_settings().language)
    from .app import run as _run

    _run()


__all__ = ["run"]
