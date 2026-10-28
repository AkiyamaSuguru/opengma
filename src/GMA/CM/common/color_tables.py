# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
各表征方法共用的色表。

1. 通用色卡 DEFAULT_PALETTE（默认使用，初期分析时不用管颜色）
   对 XPS、Raman、XRD 的所有图都生效；XPSPlotter(palette=...) 等 Plotter 的设置，
   或单次调用的 palette 参数可以覆盖它。可以写 matplotlib 自带的色卡名：
   - 离散色卡，按顺序取色、不够时循环："tab10"、"tab20"、"Set1"、"Set2"、"Dark2"、
     "Paired" 等，完整列表见 matplotlib.color_sequences；
   - 连续色卡，按数量均匀取色："viridis"、"plasma"、"cividis" 等；
   也可以直接写颜色列表，如 ["black", "tab:red", "#1f77b4"]。

2. 样品色表 SAMPLE_COLORS（默认不使用，出版绘图时传给 sample_colors）
   样品名 -> 颜色。XPS 全谱、Raman 谱、XRD 图谱共用，同一个样品在所有图中颜色一致；
   不同样品可以用同一个颜色。表里没有的样品按通用色卡取色。

各表征方法自己的定制色表放在各自的 [X]Plotter/color_tables.py 中：
- XPS：COMPONENT_COLORS，元素谱按化学键（分峰名）配色；
- Raman：COMPONENT_COLORS，拟合谱按谱峰（分峰名）配色；
- XRD：PHASE_COLORS，参考物相标记按物相配色。

颜色可以写颜色名（"tab:blue"、"black"）、十六进制（"#1f77b4"）或 RGB 元组，
matplotlib 能识别的写法都可以。
"""

DEFAULT_PALETTE = "tab10"

# ============================================================
# 样品色表：样品名 -> 颜色
# 样品名与传入数据字典的 key 一致。下面是示例，按需修改。
# ============================================================
SAMPLE_COLORS = {
    "As-deposited": "black",
    "Corroded 100 h": "tab:red",
    "Corroded 300 h": "tab:red",  # 不同样品可以用同一个颜色
}
