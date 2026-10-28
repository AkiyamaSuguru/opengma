# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
XPS 各仪器 / 数据处理软件的 reader，返回的数据结构见 XPS/schema.py。
"""
from .Avantage import element_reader, survey_reader

__all__ = ["element_reader", "survey_reader"]
