# CM 模块开发者笔记

CM 模块（Characterization Methods）是 GMA 中最主要的模块，所有的表征方法处理都会集成到这个模块中，目前正在开发的表征方法处理子模块包括 XRD、Raman、XPS 等。

大部分表征方法的代码块包含读取、分析、绘图模块，分别标记为 `[X]Loader`、`[X]Analyzer`、`[X]Plotter`。其中在具体表征方法的子模块下，分别设有 loader、analyzer、plotter 入口，具体的代码模块则放入以 `[X]Loader`、`[X]Analyzer`、`[X]Plotter` 命名的子文件夹下面（X 取表征方法的首字母，XRD 取 Diffraction 的 D）。

## 目录结构

```
src/GMA/CM/
├── common/                 # 各表征方法共用
│   ├── axis.py             # SpectrumAxis：横轴的列名、标题、单位、方向
│   ├── data.py             # 标准数据结构的检查与整理（require_columns、detect_fit_type、prepare_spectrum…）
│   ├── metrics.py          # 数值指标：数据范围、拟合质量、分峰峰位 / 峰高 / 面积
│   ├── color_tables.py     # 通用色卡 DEFAULT_PALETTE、样品色表 SAMPLE_COLORS
│   ├── palette.py          # 取色：palette_colors、按定制色表分配并避开已用颜色 assign_colors
│   ├── style.py            # 出版图样式 PUBLICATION_STYLE、mpl_style()，交互图布局
│   ├── spectra_static.py   # 谱线出版图：draw_spectrum、draw_peak_labels、plot_spectra_static
│   ├── spectra_interactive.py
│   ├── fit_static.py       # 拟合谱（分峰）出版图：draw_fit、plot_fits_static
│   ├── fit_interactive.py
│   └── plotter.py          # BasePlotter：各 Plotter 的基类
├── XPS/
│   ├── schema.py           # 标准数据结构（列名）和横轴 AXIS
│   ├── loader.py           # XPSLoader 和 READERS（仪器名 → 读取函数）
│   ├── analyzer.py         # XPSAnalyzer
│   ├── plotter.py          # XPSPlotter
│   ├── XLoader/            # 各仪器 / 软件的读取函数，如 Avantage.py
│   ├── XAnalyzer/          # 分析的实现
│   └── XPlotter/           # 各种图的实现，color_tables.py 中是定制色表 COMPONENT_COLORS
├── Raman/                  # 同上：RamanLoader、RamanPlotter、RLoader/、RPlotter/
└── XRD/                    # 同上：XRDLoader、XRDPlotter、DLoader/、DPlotter/（另有参考物相 references.py）
```

## 标准数据结构

各环节之间只通过 pandas DataFrame 衔接，列名规定在各方法的 `schema.py` 中：

| 数据 | 列 |
| --- | --- |
| 谱线 | `[横轴列, "Intensity"]` |
| 拟合谱 | `[横轴列, "Intensity", "Fitting Curve", 分峰列…, "Background"]`，分峰列可以有 0 个或多个 |

| 方法 | 横轴列 | 方向 |
| --- | --- | --- |
| XPS | `Binding Energy (eV)` | 从高到低 |
| Raman | `Raman Shift (cm-1)` | 从低到高 |
| XRD | `2Theta (deg)` | 从低到高 |

标准列以外的数值列都视为分峰列，列名就是图例中的分峰名。分峰列有两种含义，由 `component_mode` 区分：`"absolute"` 表示已包含背景（Avantage 导出的数据），`"relative"` 表示已扣除背景，画图和计算指标时再加上背景。

`schema.py` 中的 `AXIS`（`SpectrumAxis`）描述横轴：列名、出版图和交互图中的标题、悬停时的名称、单位、是否从高到低。共用的绘图代码只按 `AXIS` 取数据、写标题、定方向，所以三种方法能共用一套绘图实现。

## 读取

每种方法有一个 Loader 类和一个读取函数表 `READERS`（仪器名 → 读取函数）。创建 Loader 时传入仪器名或读取函数，`read()` 调用读取函数，再检查返回值：

| 方法 | 读取函数的约定 | Loader 的方法 |
| --- | --- | --- |
| XPS | 两个函数 `(survey_reader, element_reader)`：`survey_reader(path)`、`element_reader(path, peaks=None)`，都只返回 DataFrame | `read_survey`、`read_element` |
| Raman、XRD | `reader(path)` 返回 `(df, metadata)`，没有元数据时 metadata 为 `{}` | `read`，返回的元组也可以按 `.data`、`.metadata` 取 |

Loader 用 `common/data.py` 中的 `require_columns` 检查列名，缺少的列写在报错信息中。读取函数只负责把文件变成标准数据结构，不做清洗；清洗（去掉无效行、排序等）在 `GMA.project` 导入时进行，并写进清洗记录。

### 接入新的仪器

1. 在对应的 `[X]Loader/` 中新建一个文件，如 `DLoader/Rigaku.py`，写读取函数，返回标准数据结构。文件编码、小数逗号、说明行等格式问题都在这里处理。
2. 在该方法的 `loader.py` 中把它登记到 `READERS`，之后就能用 `XRDLoader("Rigaku SmartLab")` 这样按名称创建。
3. 在 `tests/conftest.py` 中按仪器的格式生成一个小文件（不要提交真实数据，除非作者同意），在 `tests/test_loaders.py` 中测试读取结果和出错提示。

图形界面不需要另外修改：导入对话框和设置中的“默认读取器”都直接列出 `READERS` 中的仪器名，`GMA.project` 的导入函数也是按名称调用 Loader。

## 分析

分析只处理已经拟合好的结果，不做扣背景和峰拟合（Q1），只用标准数据结构中已有的列。计算在 `common/metrics.py` 中：

- `spectrum_metrics(df, axis, component_mode)` 返回 `SpectrumMetrics`：数据范围、点数、最大强度位置，拟合谱还有拟合质量（RMSE、MAE、R²）和每个分峰的 `ComponentMetrics`（峰位、峰高、面积、面积占比）；
- `component_table(metrics)` 把分峰指标整理成表格。

`XPSAnalyzer` 是 XPS 的入口，其他方法需要分析时，照着写一个 `[X]Analyzer`，调用 `spectrum_metrics` 并传入自己的 `AXIS`。面积占比是面积之比，不是原子百分比，文档和界面中都要这样写清楚。

## 绘图

`BasePlotter` 保存各种图共用的设置（字体、字号、交互图字号、通用色卡、是否用 LaTeX），数据在调用绘图方法时传入；调用时传入的同名参数优先（`_options()` 合并）。各方法的 Plotter 只设置自己的 `AXIS`，再把绘图方法转给 `common` 中的实现。

绘图函数分两层：

- `draw_*`：画在传入的坐标轴上并返回它，用来自由组合多面板图；
- `plot_*_static`：生成整张图，负责样式、尺寸、图例、保存和显示，返回 `(fig, ax)` 或 `(fig, axes)`。

出版图样式写在 `style.py` 的 `PUBLICATION_STYLE` 中，不依赖 scienceplots；`plotter.style()` 返回样式上下文，自己组合图时把建图和保存都放在里面。交互图用 plotly，布局也在 `style.py`。

配色分两层：通用色卡（`DEFAULT_PALETTE`，默认 `"tab10"`）和定制色表（`{名称: 颜色}`，如 `SAMPLE_COLORS`、`COMPONENT_COLORS`、`PHASE_COLORS`）。表里没有的名称按通用色卡取色，并避开已经用掉的颜色（`assign_colors`）；色表缺少某个名称时给出警告。

图形界面的出版图和“复制为代码”调用的就是这些 Plotter 方法，所以修改绘图函数的参数时，要同时看 `GMA/UI/services/figures.py` 和 `codegen.py`。

## 增加表征方法

以增加 FTIR 为例，核心库中：

1. 新建 `CM/FTIR/`，`schema.py` 中写横轴列名（如 `"Wavenumber (cm-1)"`）和 `AXIS`；
2. `loader.py`：`READERS` 和 `FTIRLoader`（照 `XRDLoader` 写），读取函数放在 `[X]Loader/` 中；
3. `plotter.py`：`FTIRPlotter(BasePlotter)`，设置 `AXIS`，谱线图转给 `spectra_static` / `spectra_interactive`，有拟合谱时转给 `fit_static` / `fit_interactive`；
4. 在 `CM/__init__.py` 和 `GMA/__init__.py` 中导出；
5. 测试：`tests/conftest.py` 中合成数据，测试读取和绘图。

要在项目文件和图形界面中使用，还要做两步，见 [project 模块 · 增加表征方法](project模块.md#增加表征方法) 和 [UI 模块 · 增加一个表征方法模块](UI模块.md#增加一个表征方法模块)。
