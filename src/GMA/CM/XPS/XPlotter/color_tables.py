"""
XPS 绘图色表。

1. 通用色卡（默认使用，初期分析时不用管颜色）
   DEFAULT_PALETTE 对四种图都生效；XPSPlotter(palette=...) 或单次调用的 palette 参数可以覆盖它。
   可以写 matplotlib 自带的色卡名：
   - 离散色卡，按顺序取色、不够时循环："tab10"、"tab20"、"Set1"、"Set2"、"Dark2"、
     "Paired" 等，完整列表见 matplotlib.color_sequences；
   - 连续色卡，按数量均匀取色："viridis"、"plasma"、"cividis" 等；
   也可以直接写颜色列表，如 ["black", "tab:red", "#1f77b4"]。

2. 定制色表（默认不使用，出版绘图时手动传入）
   - COMPONENT_COLORS：元素谱按化学键（分峰名）配色，传给 component_colors；
   - SAMPLE_COLORS：全谱按样品配色，传给 sample_colors，不同样品可以用同一个颜色。
   表里没有的分峰 / 样品仍按通用色卡取色。

颜色可以写颜色名（"tab:blue"、"black"）、十六进制（"#1f77b4"）或 RGB 元组，
matplotlib 能识别的写法都可以。
"""

DEFAULT_PALETTE = "tab10"

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

# ============================================================
# 全谱定制色表：样品名 -> 颜色
# 样品名与传入数据字典的 key 一致。下面是示例，按需修改。
# ============================================================
SAMPLE_COLORS = {
    "As-deposited": "black",
    "Corroded 100 h": "tab:red",
    "Corroded 300 h": "tab:red",  # 不同样品可以用同一个颜色
}