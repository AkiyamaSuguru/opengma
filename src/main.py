# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
flet build 打包时的程序入口（pyproject.toml 的 [tool.flet.app]：path = "src"，module = "main"）。

与 uv run opengma、python -m GMA.UI 相同：先按设置选好界面语言，再启动图形界面。
打包见 scripts/build_app.py；平时开发不需要这个文件。
"""
from GMA.UI import run

run()
