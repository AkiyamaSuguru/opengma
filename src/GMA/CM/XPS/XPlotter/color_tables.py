# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
XPS 定制色表（默认不使用，出版绘图时手动传入）。

- COMPONENT_COLORS：元素谱按化学键（分峰名）配色，传给 component_colors。
  表里没有的分峰仍按通用色卡取色。

通用色卡 DEFAULT_PALETTE 和样品色表 SAMPLE_COLORS 由各表征方法共用，
在 GMA/CM/common/color_tables.py 中设置。

颜色可以写颜色名（"tab:blue"、"black"）、十六进制（"#1f77b4"）或 RGB 元组，
matplotlib 能识别的写法都可以。
"""

# ============================================================
# 元素谱定制色表：分峰名 -> 颜色
# 分峰名要和读取数据时 peaks 参数中的名称完全一致（区分大小写），例如
# loader.read_element("C1s.xlsx", peaks=["C-Si", "C-C", "C-O"])。
# 下面是示例，按自己的命名增删即可。
# ============================================================
COMPONENT_COLORS = {
    # C 1s
    "C-Si": "tab:blue",
    "C-C": "tab:orange",
    "C-O": "tab:green",
    # Si 2p
    "Si-C": "tab:blue",  # 和 C-Si 同属 SiC，用同一个颜色
    "Si-O": "tab:red",
}
