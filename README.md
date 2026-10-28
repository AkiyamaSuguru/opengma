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

推荐在 [marimo](https://marimo.io/) 笔记本中使用，下面的例子也可以直接在脚本或 Jupyter 中运行。在 marimo 中，静态图要传入 `show=False`，并把返回的 `fig` 放在单元格最后一行，详见[显示与保存](#显示与保存)。

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
# 分峰拟合后的数据也可以直接画，fitted 的整理方法见“使用方法”中的“拟合谱图”
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

## 使用方法

所有功能都从两类入口使用：**Loader** 把仪器导出的文件读成[标准数据结构](#标准数据结构)的 DataFrame，**Plotter** 把 DataFrame 画成图。两者只通过 DataFrame 衔接，所以 Plotter 也能画你自己整理的数据。六个入口都可以直接从 `GMA` 导入：`XPSLoader`、`XPSPlotter`、`RamanLoader`、`RamanPlotter`、`XRDLoader`、`XRDPlotter`。

下面的例子沿用[快速上手](#快速上手)中读取的数据。

### 读取数据

创建 Loader 时传入仪器名，之后可以用它读取任意多个文件：

| Loader | 仪器名 | 读取的文件 | 读取方法 | 返回 |
| --- | --- | --- | --- | --- |
| `XPSLoader` | `"Avantage"` | Thermo Fisher Avantage 导出的 Excel（.xls 或 .xlsx） | 全谱 `read_survey(path)`，元素谱 `read_element(path, peaks=None)` | DataFrame |
| `RamanLoader` | `"Horiba HR evolution"` | Horiba LabSpec 导出的 txt | `read(path)` | `(data, metadata)` |
| `XRDLoader` | `"D8 Advance"` | Bruker 衍射仪导出的 txt | `read(path)` | `(data, metadata)` |

- **XPS 元素谱的 `peaks`**：按 Excel 中从左到右的顺序给出分峰名，个数要与分峰数一致。分峰名会显示在图例中，按化学键配色（`component_colors`）时也按它查找颜色。不传时沿用 Avantage 中的分峰名，适合先预览；未拟合的元素谱只有结合能和强度两列，不能传 `peaks`。
- **metadata**：Raman、XRD 文件头中的测试参数，Horiba 为 `{参数名: 值}`，Bruker 为 `{节名: {参数名: 值}}`。`read()` 的返回值可以直接解包，也可以按名字取 `.data`、`.metadata`。
- **检查**：仪器名写错时，报错信息会列出可用的仪器名；读到的数据不符合标准数据结构时，会列出缺少的列。

```python
from GMA import XPSLoader, XRDLoader

preview = XPSLoader("Avantage").read_element("data/C1s.xlsx")  # 不传 peaks，沿用 Avantage 中的分峰名

result = XRDLoader("D8 Advance").read("data/as-deposited.txt")
pattern = result.data  # 等同于 pattern, metadata = XRDLoader("D8 Advance").read(...)
print(result.metadata)
```

#### 接入新的仪器

写一个读取函数，返回标准数据结构即可：

- Raman、XRD：接收文件路径，返回 `(df, metadata)`，没有元数据时返回 `{}`；
- XPS：需要两个函数，读取全谱的 `survey_reader(file_path)` 和读取元素谱的 `element_reader(file_path, peaks=None)`，都只返回 df，以元组 `(survey_reader, element_reader)` 传给 `XPSLoader`。

读取函数可以直接传给 Loader：

```python
import pandas as pd
from GMA import XRDLoader

def reader_my_xrd(file_path):
    raw = pd.read_csv(file_path)
    df = pd.DataFrame({"2Theta (deg)": raw["angle"], "Intensity": raw["counts"]})
    return df, {}

pattern, metadata = XRDLoader(reader_my_xrd).read("my_pattern.csv")
```

想长期使用时，把读取函数放进对应的 `XLoader/`、`RLoader/` 或 `DLoader/` 文件夹，并在该表征方法的 `loader.py` 中把它注册到 `READERS`，之后就能像内置仪器一样用名称创建 Loader。Loader 会检查读取函数的返回值，不符合约定或标准数据结构时报错，并给出缺少的列名。

### 绘图

#### 设置 Plotter

Plotter 只保存各种图共用的设置，数据在调用绘图方法时传入，所以一个 Plotter 可以画任意多张图。三个 Plotter 的设置相同：

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `font_family` | `"Times New Roman"` | 字体，静态图和交互图共用，需要是系统中已安装的字体 |
| `font_size` | `8` | 静态图字号（pt），适合期刊单栏图 |
| `interactive_font_size` | `12` | 交互图字号（px） |
| `palette` | `None`，即 `"tab10"` | 通用色卡，见[配色](#配色) |
| `use_latex` | `False` | 静态图是否用 LaTeX 渲染文字，需要安装 LaTeX |

绘图时传入的同名参数优先，只对这一张图生效：

```python
from GMA import XPSPlotter

plotter = XPSPlotter(font_family="Arial", font_size=7)
plotter.plot_survey_static(survey, font_size=9)  # 这张图用 9 pt
```

#### 绘图方法

| Plotter | 谱线图 | 拟合谱图 |
| --- | --- | --- |
| `XPSPlotter` | 全谱：`plot_survey_static`、`plot_survey_interactive` | 元素谱：`plot_element_static`、`plot_element_interactive` |
| `RamanPlotter` | Raman 谱：`plot_spectrum_static`、`plot_spectrum_interactive` | 拟合谱：`plot_fit_static`、`plot_fit_interactive` |
| `XRDPlotter` | 图谱：`plot_pattern_static`、`plot_pattern_interactive` | — |

`*_static` 画学术出版图（matplotlib）；`*_interactive` 画交互图（plotly），适合初期分析时查看数据，悬停可以读出横轴数值和强度，框选可以放大，双击还原。同一类图的参数相同：

- **谱线图**：画一条或多条谱线，可以标出峰位；XRD 还可以标出参考物相。
- **拟合谱图**：自动判断数据是否拟合过。只有横轴和强度两列时画成谱线；有 `Fitting Curve` 和 `Background` 列时，画出原始数据点、拟合曲线、背景和各分峰。

传入单个 DataFrame 画一条谱，传入 `{名称: DataFrame}` 字典画多条谱，名称显示在图例或子图上：

| 图 | 单条 | 多条画在同一张图 | 多条各占一个子图 |
| --- | :---: | :---: | :---: |
| 谱线静态图 | ✓ | ✓（默认，`offset` 上下错开） | ✓（`subplots=True`） |
| 拟合谱静态图 | ✓ | — | ✓ |
| 谱线交互图 | ✓ | ✓ | — |
| 拟合谱交互图 | ✓ | — | — |

画图前可以用 `plotter.info(data)` 检查数据，它会打印每条谱的类型（`raw` 未拟合 / `fit` 拟合后）、行列数和列名。

#### 谱线图

XPS 全谱、Raman 谱和 XRD 图谱。多条谱可以画在同一张图中，也可以各占一个子图；`peaks` 可以所有谱共用，也可以按样品分别写：

```python
from GMA import XPSLoader, XPSPlotter

survey_corroded = XPSLoader("Avantage").read_survey("data/survey_corroded.xlsx")
surveys = {"As-deposited": survey, "Corroded": survey_corroded}

plotter = XPSPlotter()
# 同一张图：归一化后上下错开，所有谱共用 peaks
plotter.plot_survey_static(surveys, peaks={"C 1s": 284.8, "O 1s": 532.0},
                           normalize=True, offset=1.1, hide_y_ticks=True)
# 每条谱一个子图，上下排列，各自标出自己的峰
plotter.plot_survey_static(surveys, subplots=True, n_cols=1,
                           peaks={"As-deposited": {"Si 2p": 101.0}, "Corroded": {"F 1s": 685.0}})
plotter.plot_survey_interactive(surveys, normalize=True, offset=1.1).show()
```

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `subplots` | `False` | `True` 时每条谱一个子图 |
| `peaks` | `None` | 标出峰位：所有谱共用写 `{标签: 位置}`，按样品分别写 `{样品名: {标签: 位置}}`，画在同一张图时合并标注。峰位很近时标签会重叠，可以合并成一个标签 |
| `normalize` | `False` | 每条谱除以自身最大值 |
| `offset` | `0` | 同一张图中相邻两条谱的上下间距，第一条在最上面；归一化后取 1 左右 |
| `hide_y_ticks` | `False` | 隐藏纵轴刻度，错开显示时建议打开 |
| `linewidth` | 静态图 `0.8`，交互图 `1.2` | 线宽 |
| `show_legend`、`legend_loc` | `True`、`"best"` | 图例及其位置 |
| `n_cols` | `3` | 子图模式下每行最多几个子图 |
| `figsize` | 每个坐标轴 3.2 × 2.4 英寸 | 图的尺寸（英寸） |
| `label_scale` | `1.2` | 子图标签字号相对正文的倍数 |
| `palette`、`sample_colors` | | 见[配色](#配色) |
| `save_path`、`dpi`、`show` | | 见[显示与保存](#显示与保存) |

交互图没有子图模式，可用的参数为 `peaks`、`normalize`、`offset`、`hide_y_ticks`、`linewidth` 和配色参数；错开显示时，悬停读出的仍是原始强度。

XRD 的两个方法还可以标出参考物相：

- `references`：`{物相名: {晶面指数: 2θ}}`，在标准峰位画竖直虚线、在图顶部写晶面指数，每个物相一种颜色，物相名显示在图例中。颜色按通用色卡分配，并避开图谱曲线已经用掉的颜色。
- `phase_colors`：按物相指定颜色，见[配色](#配色)。

`peaks` 画的是灰色虚线，不进图例，适合标普通峰位。

#### 拟合谱图

XPS 元素谱和 Raman 拟合谱。传入字典时每条谱一个子图，拟合后的和未拟合的谱可以画在一起：

```python
from GMA import XPSLoader, XPSPlotter

f1s = XPSLoader("Avantage").read_element("data/F1s.xlsx")  # 未拟合的元素谱
plotter = XPSPlotter()
plotter.plot_element_static({"C 1s": c1s, "Si 2p": si2p, "F 1s": f1s}, raw_line_color="black")
```

其他软件的拟合结果，整理成标准数据结构后也可以直接画，分峰列名就是图例中的名称。如果分峰列是扣除背景后的强度，传入 `component_mode="relative"`：

```python
import pandas as pd
from GMA import RamanPlotter

raw = pd.read_csv("data/raman_fit.csv")  # 其他软件导出的拟合结果
fitted = pd.DataFrame({
    "Raman Shift (cm-1)": raw["shift"],
    "Intensity": raw["counts"],
    "Fitting Curve": raw["fit"],
    "D": raw["peak1"],
    "G": raw["peak2"],
    "Background": raw["baseline"],
})

plotter = RamanPlotter()
plotter.plot_fit_static(fitted, component_mode="relative")
plotter.plot_fit_interactive(fitted, component_mode="relative").show()
```

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `component_mode` | `"absolute"` | `"absolute"`：分峰列已包含背景（Avantage 导出的数据即如此）；`"relative"`：分峰列是扣除背景后的强度，绘图时自动加上背景 |
| `raw_color`、`raw_size` | `"black"`、`4` | 原始数据点的颜色和大小 |
| `fit_color` | `"red"` | 拟合曲线的颜色 |
| `bg_color` | `"gray"` | 背景的颜色 |
| `component_alpha` | 静态图 `0.35`，交互图 `0.28` | 分峰填充的不透明度 |
| `raw_line_color` | 通用色卡的第一个颜色 | 未拟合谱的线条颜色；静态图可以写 `{子图标签: 颜色}`，分别设置 |
| `hide_y_ticks` | `False` | 隐藏纵轴刻度 |
| `show_legend`、`legend_loc` | `True`、`"best"` | 图例及其位置；多个子图时，子图标签作为图例标题 |
| `n_cols`、`figsize`、`label_scale` | 同谱线图 | 子图排列、图的尺寸、子图标签字号 |
| `palette`、`component_colors` | | 见[配色](#配色) |
| `save_path`、`dpi`、`show` | | 见[显示与保存](#显示与保存) |

交互图一次画一条谱，多条谱请分别调用；没有图例和子图相关的参数。每个分峰画成填充区域、轮廓线和峰位标记，点击图例中的分峰名可以同时隐藏这三者，悬停在峰位标记上可以读出峰位。

#### 显示与保存

- **静态图**返回 matplotlib 的 `(fig, ax)` 或 `(fig, axes)`：谱线图画在同一张图时返回 `ax`，子图模式返回 `axes`；拟合谱图总是返回 `axes`。`axes` 是二维数组，单条谱时为 1×1，用 `axes[0, 0]` 取出坐标轴。
- `save_path` 保存图片，格式由扩展名决定（如 `.png`、`.pdf`、`.svg`、`.tif`），`dpi` 默认为 600。
- `show=True`（默认）时画完直接显示，适合脚本和 Jupyter。marimo 显示单元格最后一行的对象，所以在 marimo 中传入 `show=False`，把返回的 `fig` 放在最后一行。
- **交互图**返回 plotly Figure，`.show()` 显示，`.write_html("survey.html")` 保存为可以用浏览器打开的网页；在 marimo 中直接放在单元格最后一行即可。

要用 matplotlib 继续修改静态图（如调整横轴范围）时，传入 `show=False`，并把修改和保存放在 `plotter.style()` 中，保持同样的出版图样式。XPS 的横轴从高到低，范围要写成 `ax.set_xlim(600, 0)` 这样：

```python
from GMA import XRDPlotter

plotter = XRDPlotter()
with plotter.style():
    fig, ax = plotter.plot_pattern_static(patterns, show=False)
    ax.set_xlim(20, 80)
    fig.savefig("pattern.png", dpi=600)
```

### 配色

初期分析时不用管颜色，所有图默认使用通用色卡；出版绘图时再传入定制色表。

- **通用色卡**：默认为 `GMA/CM/common/color_tables.py` 中的 `DEFAULT_PALETTE`（`"tab10"`），对所有图生效；也可以对某个 Plotter 全局设置，如 `XPSPlotter(palette="Set2")`，或在单次调用中传入 `palette`。可以写 matplotlib 的色卡名或颜色列表：离散色卡（`"tab10"`、`"Set2"`、`"Dark2"` 等）按顺序取色，不够时循环；连续色卡（`"viridis"`、`"plasma"` 等）按需要的颜色数均匀取色。
- **定制色表**：`{名称: 颜色}`，表里有的名称用指定颜色，其余仍按通用色卡取色，并避开已经用掉的颜色。名称要与数据中的完全一致（区分大小写）；`component_colors`、`phase_colors` 缺少某个名称时会给出警告，方便发现漏写或写错。

| 参数 | 用于 | 色表位置 |
| --- | --- | --- |
| `sample_colors` | 谱线图，按样品配色（不同样品可以同色） | `common/color_tables.py` 中的 `SAMPLE_COLORS` |
| `component_colors` | XPS 元素谱按化学键、Raman 拟合谱按谱峰配色 | `XPS/XPlotter/color_tables.py`、`Raman/RPlotter/color_tables.py` 中的 `COMPONENT_COLORS` |
| `phase_colors` | XRD 参考物相，按物相配色 | `XRD/DPlotter/color_tables.py` 中的 `PHASE_COLORS` |

色表文件中的颜色是示例，可以按自己的样品和命名修改，也可以直接传入字典。颜色可以写颜色名（`"tab:blue"`、`"black"`）、十六进制（`"#1f77b4"`）等 matplotlib 能识别的写法。

```python
from GMA import XPSPlotter
from GMA.CM.common import SAMPLE_COLORS
from GMA.CM.XPS.XPlotter import COMPONENT_COLORS

plotter = XPSPlotter()
plotter.plot_element_static({"C 1s": c1s, "Si 2p": si2p}, component_colors=COMPONENT_COLORS)
plotter.plot_survey_static(surveys, sample_colors=SAMPLE_COLORS)
plotter.plot_survey_static(surveys, sample_colors={"As-deposited": "black", "Corroded": "tab:red"})
```

### 组合多面板图

各表征方法的 `[X]Plotter` 文件夹中提供 `draw_*` 函数，把一条谱画在指定的坐标轴上并返回这个坐标轴，用来自由组合多面板图，不同表征方法的谱也可以放在同一张图中：

| 导入位置 | 函数 |
| --- | --- |
| `GMA.CM.XPS.XPlotter` | `draw_survey`（全谱）、`draw_element`（元素谱，自动判断是否拟合）、`draw_peak_labels`（标峰） |
| `GMA.CM.Raman.RPlotter` | `draw_spectrum`（Raman 谱）、`draw_fit`（拟合谱，自动判断是否拟合）、`draw_peak_labels` |
| `GMA.CM.XRD.DPlotter` | `draw_pattern`（图谱）、`draw_references`（参考物相）、`draw_peak_labels` |

谱线的常用参数有 `color`、`label`、`offset`、`normalize`、`show_legend`、`hide_y_ticks`，拟合谱的参数同[拟合谱图](#拟合谱图)。把建图、绘图和保存都放在 `plotter.style()` 中，就能使用与 Plotter 相同的出版图样式：

```python
import matplotlib.pyplot as plt
from GMA import XPSPlotter
from GMA.CM.Raman.RPlotter import draw_peak_labels, draw_spectrum
from GMA.CM.XPS.XPlotter import draw_element
from GMA.CM.XRD.DPlotter import draw_pattern, draw_references

plotter = XPSPlotter()  # 字体、字号取自这个 Plotter
with plotter.style():
    fig, (ax_a, ax_b, ax_c) = plt.subplots(1, 3, figsize=(9.6, 2.4))
    draw_pattern(ax_a, deposited, color="black")
    draw_references(ax_a, {"β-SiC": {"(111)": 35.6, "(220)": 60.0, "(311)": 71.8}})
    draw_spectrum(ax_b, sic, color="black")
    draw_peak_labels(ax_b, {"TO": 796, "LO": 972})
    draw_element(ax_c, c1s)
    fig.tight_layout()
    fig.savefig("figure.png", dpi=600, bbox_inches="tight")
```

需要与通用色卡一致的颜色时（如自己补画曲线），可以用 `GMA.CM.common.palette_colors(n, palette)` 从通用色卡取 n 个颜色。

## 标准数据结构

各模块之间传递的数据都是 pandas DataFrame，列名定义在各表征方法的 `schema.py` 中：

| 表征方法 | 数据 | 列 |
| --- | --- | --- |
| XPS | 全谱 | `Binding Energy (eV)`、`Intensity` |
| XPS | 元素谱（拟合后） | `Binding Energy (eV)`、`Intensity`、`Fitting Curve`、分峰列…、`Background` |
| Raman | 谱线 | `Raman Shift (cm-1)`、`Intensity` |
| Raman | 拟合谱 | `Raman Shift (cm-1)`、`Intensity`、`Fitting Curve`、分峰列…、`Background` |
| XRD | 图谱 | `2Theta (deg)`、`Intensity` |

未拟合的元素谱与全谱结构相同。拟合谱中，标准列以外的数值列都视为分峰列，列名就是图例中的分峰名，可以有 0 个或多个。Raman 和 XRD 的 reader 返回 `(df, metadata)`，metadata 保存仪器、测试参数等信息；XPS 的 reader 只返回 df。自己整理数据时，列名也可以从 `schema.py` 导入，如 `from GMA.CM.Raman.schema import SHIFT_COL`。

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
