# OPEN GMA

> **本项目正在开发中**，接口可能还会调整。

OPEN GMA（Open General Material Analyzer）是 Jay 开发的材料表征数据分析工具集。它把科研中表征数据的读取、分析、绘图等环节整理成一个可以复用的 Python 库，目前已支持 **XPS、Raman、XRD** 的数据读取和绘图。

## 功能

| 模块 | 内容 | 状态 |
| --- | --- | --- |
| 数据读取 | 读取不同仪器导出的数据，统一转换为标准数据结构 | XPS、Raman、XRD 已完成 |
| 绘图 | 学术出版图（matplotlib）和交互图（plotly） | XPS、Raman、XRD 已完成 |
| 数据分析 | 常用表征方法的数据分析，如分峰拟合 | 规划中 |
| 计算 | 通用以及专用的物理量计算 | 规划中 |
| 结构化存储 | 用数据库等形式结构化存储数据，方便复用 | 规划中 |
| UI | 基于 Flet 的图形界面，方便不熟悉 Python 的使用者 | 规划中 |

## 设计哲学

我们希望这个项目可以像 Python 库一样使用。科研中表征数据的处理被划分为读取、分析、绘图等几个环节，各环节之间通过**标准数据结构**衔接、互相解耦。比如你的数据来自本项目还不支持的仪器，只要自己写一个读取函数，把数据整理成本项目规定的数据结构，就可以直接使用分析、绘图等其他模块。尽可能提高代码的可复用性，是本项目最重要的设计哲学。

项目按表征方法组织代码，因为同一种表征方法的处理通常有共性，最终使用的数据结构相同或相似，这让数据输入的标准化成为可能。不同表征方法的谱图结构也很接近，主要区别在横轴，所以它们共用 `common` 中的一套绘图实现，每种表征方法只规定自己的数据结构和横轴。

目前支持的表征方法主要是作者用过的表征手段，也期待有新的开发者加入，一起完善本项目。由于项目还未开发完成，目前以具有传染性的开源协议发布，后续可能会考虑改用 MIT 等协议，取消强制开源的传递性，方便使用。

## 目录结构

```
src/GMA/
├── CM/                      # 表征方法（Characterization Methods）
│   ├── common/              # 各表征方法共用：数据检查、配色、样式和绘图实现
│   │   └── color_tables.py  # 通用色卡 DEFAULT_PALETTE、样品色表 SAMPLE_COLORS
│   ├── XPS/
│   │   ├── schema.py        # 标准数据结构（列名）
│   │   ├── loader.py        # 读取入口 XPSLoader
│   │   ├── plotter.py       # 绘图入口 XPSPlotter
│   │   ├── XLoader/         # 各仪器 / 软件的 reader
│   │   └── XPlotter/        # 各种图的实现，以及 XPS 定制色表
│   ├── Raman/               # 结构同上：RamanLoader、RamanPlotter、RLoader/、RPlotter/
│   └── XRD/                 # 结构同上：XRDLoader、XRDPlotter、DLoader/、DPlotter/
└── utils/
tests/                       # 测试
```

每种表征方法下设读取（loader）、分析（analyzer）、绘图（plotter）入口，具体实现放在以表征方法首字母命名的 `[X]Loader`、`[X]Analyzer`、`[X]Plotter` 子文件夹中（XRD 取 Diffraction 的 D）。

## 安装

需要 Python 3.14 及以上，推荐使用 [uv](https://docs.astral.sh/uv/)：

```bash
git clone https://github.com/AkiyamaSuguru/opengma.git
cd opengma
uv sync
```

`uv sync` 会安装所有依赖，并以可编辑模式安装 `GMA`，之后在任何位置都可以 `import GMA`。运行测试：

```bash
uv run pytest
```

## 快速上手

推荐在 [marimo](https://marimo.io/) 笔记本中使用。marimo 会显示单元格最后一行的对象：静态图传入 `show=False`，把返回的 `fig` 放在最后一行；交互图直接把返回的 plotly Figure 放在最后一行。在脚本或 Jupyter 中，静态图默认直接显示，交互图用 `.show()` 显示。

### XPS

```python
from GMA import XPSLoader, XPSPlotter

loader = XPSLoader("Avantage")
survey = loader.read_survey("data/survey.xlsx")
# 分峰名按 Excel 中从左到右的顺序给出；只是预览时可以不传，使用 Avantage 中的名称
c1s = loader.read_element("data/C1s.xlsx", peaks=["C-Si", "C-C", "C-O"])
si2p = loader.read_element("data/Si2p.xlsx", peaks=["Si-C", "Si-O"])

plotter = XPSPlotter()
plotter.plot_element_interactive(c1s).show()  # 悬停查看结合能、强度和分峰峰位
plotter.plot_element_static({"C 1s": c1s, "Si 2p": si2p}, save_path="element.png")
plotter.plot_survey_static(survey, peaks={"Si 2p": 101.0, "C 1s": 284.8, "O 1s": 532.0})
```

### Raman

```python
from GMA import RamanLoader, RamanPlotter

loader = RamanLoader("Horiba HR evolution")
sic, metadata = loader.read("data/SiC.txt")  # 返回 (数据, 元数据)
pyc, _ = loader.read("data/PyC.txt")

plotter = RamanPlotter()
plotter.plot_spectrum_static(
    {"CVD-SiC": sic, "PyC": pyc},
    peaks={"TO": 796, "LO": 972, "D": 1350, "G": 1585},
    normalize=True,
    offset=1.1,
    hide_y_ticks=True,
)
# 分峰拟合后的数据（列结构见“标准数据结构”）也可以直接画
plotter.plot_fit_static(fitted)
```

### XRD

```python
from GMA import XRDLoader, XRDPlotter

loader = XRDLoader("D8 Advance")
deposited, metadata = loader.read("data/as-deposited.txt")  # 返回 (数据, 元数据)
corroded, _ = loader.read("data/corroded.txt")
patterns = {"As-deposited": deposited, "Corroded": corroded}

# 参考物相：{物相名: {晶面指数: 2θ}}，峰位以所用射线对应的 PDF 卡片为准（下例为 Cu Kα）
references = {
    "β-SiC": {"(111)": 35.6, "(200)": 41.4, "(220)": 60.0, "(311)": 71.8},
    "Graphite": {"(002)": 26.5},
}

plotter = XRDPlotter()
plotter.plot_pattern_static(patterns, references=references,
                            normalize=True, offset=1.1, hide_y_ticks=True)
plotter.plot_pattern_static(patterns, references=references, subplots=True)
plotter.plot_pattern_interactive(patterns, references=references).show()
```

### 支持的画法

传入单个 DataFrame 画一条谱，传入 `{名称: DataFrame}` 字典画多条谱。

| 图 | 单条 | 多条画在同一张图 | 多条各占一个子图 |
| --- | :---: | :---: | :---: |
| 谱线静态图：XPS 全谱、Raman 谱、XRD 图谱 | ✓ | ✓（默认，`offset` 上下错开） | ✓（`subplots=True`） |
| 拟合谱静态图：XPS 元素谱、Raman 拟合谱 | ✓ | — | ✓ |
| 谱线交互图 | ✓ | ✓ | — |
| 拟合谱交互图 | ✓ | — | — |

- 谱线图可用 `peaks` 标出峰位，所有谱共用 `{标签: 位置}`，或按样品分别写 `{样品名: {标签: 位置}}`；XRD 另有 `references` 标出参考物相。
- 静态图返回 `(fig, ax)` 或 `(fig, axes)`，传入 `save_path` 时保存（默认 600 dpi）；交互图返回 plotly Figure，`.show()` 显示，`.write_html()` 保存为网页。
- 拟合谱的分峰默认包含背景（Avantage 导出的数据即如此）；如果分峰列是扣除背景后的强度，传入 `component_mode="relative"`。

### 配色

初期分析时不用管颜色，所有图默认使用通用色卡；出版绘图时再传入定制色表。

- **通用色卡**：默认为 `GMA/CM/common/color_tables.py` 中的 `DEFAULT_PALETTE`（`"tab10"`），对所有图生效；也可以对某个 Plotter 全局设置，如 `XPSPlotter(palette="Set2")`，或在单次调用中传入 `palette`。可以写 matplotlib 的色卡名（`"tab10"`、`"Set2"`、`"viridis"` 等）或颜色列表。
- **定制色表**：表里有的名称用指定颜色，其余仍按通用色卡取色，并避开已经用掉的颜色。

| 参数 | 用于 | 色表位置 |
| --- | --- | --- |
| `sample_colors` | 谱线图，按样品配色（不同样品可以同色） | `common/color_tables.py` 中的 `SAMPLE_COLORS` |
| `component_colors` | XPS 元素谱按化学键、Raman 拟合谱按谱峰配色 | `XPS/XPlotter/color_tables.py`、`Raman/RPlotter/color_tables.py` 中的 `COMPONENT_COLORS` |
| `phase_colors` | XRD 参考物相，按物相配色 | `XRD/DPlotter/color_tables.py` 中的 `PHASE_COLORS` |

```python
from GMA import XPSPlotter
from GMA.CM.common import SAMPLE_COLORS
from GMA.CM.XPS.XPlotter import COMPONENT_COLORS

plotter = XPSPlotter()
plotter.plot_element_static({"C 1s": c1s, "Si 2p": si2p}, component_colors=COMPONENT_COLORS)
plotter.plot_survey_static({"As-deposited": s1, "Corroded": s2}, sample_colors=SAMPLE_COLORS)
```

### 组合多面板图

各表征方法的 `[X]Plotter` 中提供 `draw_*` 函数，可以画在自己建的坐标轴上。把建图、绘图和保存放在 `plotter.style()` 中，就能使用统一的出版图样式：

```python
import matplotlib.pyplot as plt
from GMA import XPSPlotter
from GMA.CM.XPS.XPlotter import draw_element, draw_peak_labels, draw_survey

plotter = XPSPlotter()
with plotter.style():
    fig, (ax_a, ax_b) = plt.subplots(1, 2, figsize=(6.4, 2.4))
    draw_survey(ax_a, survey)
    draw_peak_labels(ax_a, {"C 1s": 284.8, "O 1s": 532.0})
    draw_element(ax_b, c1s)
    fig.tight_layout()
    fig.savefig("figure.png", dpi=600, bbox_inches="tight")
```

## 标准数据结构

各模块之间传递的数据都是 pandas DataFrame，列名定义在各表征方法的 `schema.py` 中：

| 表征方法 | 数据 | 列 |
| --- | --- | --- |
| XPS | 全谱 | `Binding Energy (eV)`、`Intensity` |
| XPS | 元素谱（拟合后） | `Binding Energy (eV)`、`Intensity`、`Fitting Curve`、分峰列…、`Background` |
| Raman | 谱线 | `Raman Shift (cm-1)`、`Intensity` |
| Raman | 拟合谱 | `Raman Shift (cm-1)`、`Intensity`、`Fitting Curve`、分峰列…、`Background` |
| XRD | 图谱 | `2Theta (deg)`、`Intensity` |

未拟合的元素谱与全谱结构相同。Raman 和 XRD 的 reader 返回 `(df, metadata)`，metadata 保存仪器、测试参数等信息；XPS 的 reader 只返回 df。

## 接入新的仪器

写一个读取函数，返回标准数据结构即可。它可以直接传给 Loader，也可以注册到对应 `loader.py` 的 `READERS` 中：

```python
import pandas as pd
from GMA import XRDLoader

def reader_my_xrd(file_path):
    raw = pd.read_csv(file_path)
    df = pd.DataFrame({"2Theta (deg)": raw["angle"], "Intensity": raw["counts"]})
    return df, {}

pattern, metadata = XRDLoader(reader_my_xrd).read("my_pattern.csv")
```

Loader 会检查返回的数据是否符合标准数据结构，不符合时给出缺少的列名。

## 开发进度

- **XPS**：读取（Thermo Fisher Avantage 导出的 Excel，测试仪器 ESCALAB Xi+）和绘图已完成。
- **Raman**：读取（Horiba LabRAM HR Evolution 导出的 txt）和绘图已完成。
- **XRD**：读取（Bruker D8 Advance 导出的 txt）和绘图已完成。
- **数据分析、计算、结构化存储、UI**：规划中。

## License

**Only the code is open source.** Everything else (the author's name and personal information, the design and the content) is reserved.

- **Code: [GNU AGPL-3.0](LICENSE) (`AGPL-3.0-only`), a strong copyleft license.** The Python package in `src/`, `main.py`, the notebooks in `NoteBooks/` and the project files. You may use, study, change and share it. If you share a changed version, or run one as a network service (a web app or an online analysis tool, for example), you must offer its full source code under the same license to everyone who receives it or uses it over the network, keep the copyright and license notices, and mark your changes. It comes with no warranty.
- **Reserved: the author's name and personal information.** Jay Ma (AkiyamaSuguru) and any details about the author.
- **Reserved: design.** The author's emblem in every form, all icons, and every logo, ornament, illustration and other design element, in whatever form and wherever it appears, including any added to this repository later.
- **Reserved: content.** The text of this README and any other content that is not code, such as documents, images and data.

© 2026 Jay Ma. Everything the AGPL does not cover is reserved: **no use in any form** without written permission, commercial or not, including text and data mining and AI training. Fair use that the law allows (personal study, research, or a brief quotation that names its source) needs no permission; please keep within it. Keeping the copyright and license notices in the code, as the AGPL requires, needs none either.

If you build on the code, replace everything reserved with your own. To ask for permission, write to the author at the address on the letter page of the author's homepage (https://akiyamasuguru.github.io/#letter), or through GitHub ([@AkiyamaSuguru](https://github.com/AkiyamaSuguru)).

### 许可说明

**本项目只开源代码**。除代码以外的一切（作者的姓名与个人信息、设计与内容）均保留所有权利。

- **代码：[GNU AGPL-3.0](LICENSE)（`AGPL-3.0-only`），强 Copyleft 许可证**。包括 `src/` 中的 Python 包、`main.py`、`NoteBooks/` 中的笔记本以及项目文件。可以使用、研究、修改与分享；分享修改后的版本，或将其作为网络服务（例如网页应用或在线分析工具）运行时，必须以同一许可证向获得它或通过网络使用它的所有人提供全部源代码，保留版权与许可声明，并注明所作的修改。本软件不提供任何担保。
- **保留**：作者的姓名与个人信息；作者徽标的一切形式、所有图标及其他一切设计元素（包括今后加入本仓库的）；本说明的文字以及其他非代码内容，如文档、图片与数据。

© 2026 Jay Ma。AGPL 不涵盖的一切均保留所有权利：未经书面许可，**禁止以任何形式使用**，无论商业或非商业用途，包括文本与数据挖掘及 AI 训练。法律允许的合理使用（个人学习、研究，或注明出处的适当引用）无需许可，请遵守这一界限；按 AGPL 的要求保留代码中的版权与许可声明，同样无需许可。如需许可，请通过[主页书信页](https://akiyamasuguru.github.io/?lang=zh#letter)上的地址或 GitHub（[@AkiyamaSuguru](https://github.com/AkiyamaSuguru)）联系作者。
