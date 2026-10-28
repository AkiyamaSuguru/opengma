# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
XRD 定制色表（默认不使用，出版绘图时手动传入）。

- PHASE_COLORS：参考物相标记按物相配色，传给 phase_colors。
  表里没有的物相按通用色卡取色，并避开图谱曲线已经用掉的颜色。

通用色卡 DEFAULT_PALETTE 和样品色表 SAMPLE_COLORS 由各表征方法共用，
在 GMA/CM/common/color_tables.py 中设置。

颜色可以写颜色名（"tab:blue"、"black"）、十六进制（"#1f77b4"）或 RGB 元组，
matplotlib 能识别的写法都可以。
"""

# ============================================================
# 物相定制色表：物相名 -> 颜色
# 物相名与 references 参数中的物相名完全一致（区分大小写）。
# 下面是示例，按自己的命名增删即可。
# ============================================================
PHASE_COLORS = {
    "β-SiC": "tab:purple",
    "Graphite": "tab:brown",
    "Si": "tab:pink",
}
