# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
Raman 定制色表（默认不使用，出版绘图时手动传入）。

- COMPONENT_COLORS：拟合谱按谱峰（分峰名）配色，传给 component_colors。
  表里没有的分峰仍按通用色卡取色。

通用色卡 DEFAULT_PALETTE 和样品色表 SAMPLE_COLORS 由各表征方法共用，
在 GMA/CM/common/color_tables.py 中设置。

颜色可以写颜色名（"tab:blue"、"black"）、十六进制（"#1f77b4"）或 RGB 元组，
matplotlib 能识别的写法都可以。
"""

# ============================================================
# 拟合谱定制色表：分峰名 -> 颜色
# 分峰名与拟合谱 DataFrame 中的分峰列名完全一致（区分大小写）。
# 下面是示例，按自己的命名增删即可。
# ============================================================
COMPONENT_COLORS = {
    # 碳材料（如热解碳）的 D、G 峰及其他常用分峰
    "D": "tab:blue",
    "G": "tab:red",
    "D'": "tab:green",
    "D3": "tab:purple",
    "D4": "tab:orange",
    # SiC
    "TO": "tab:cyan",
    "LO": "tab:olive",
}
