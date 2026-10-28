# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
XRD 各仪器的 reader。

reader 接收文件路径，返回元组 (df, metadata)：
- df 为两列的 DataFrame，列名见 XRD/schema.py：["2Theta (deg)", "Intensity"]；
- metadata 存储仪器、测试参数等信息。通常来说 metadata 并不是很重要，但有些计算中可能会用到，
  这里保留 metadata，方便对处理的数据有更加全面的认识。
"""
from .Bruker import reader_d8advance

__all__ = ["reader_d8advance"]
