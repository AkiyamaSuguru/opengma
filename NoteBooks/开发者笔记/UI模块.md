# UI 模块开发者笔记

UI 模块的作用是开发 UI 界面，来方便不熟悉 Python 代码的同学或者人员使用。这里采用的框架为 Flet（现在用的是 Flet 1.0.5），这也是我们另外一个开源项目使用的框架。但是需要注意的是 UI 界面的功能可能无法包含所有的代码功能。如果可以，将本项目当做 Python 库调用会更加适合。我们推荐使用 marimo 笔记本使用本项目。

界面只是 GMA 的外壳：读取、分析、绘图、计算都调用 GMA 的接口，界面中的“复制为代码”生成的就是这些调用。设计原则和代码注释中引用的“方案 x.y”“Qn”见[开发者手册首页](README.md#设计方案中的约定)。

## 入口

```
uv run opengma / python -m GMA.UI / src/main.py（打包）
  → GMA.UI.run()：读取设置，strings.use(界面语言)
  → GMA.UI.app.run()：ft.run(main, assets_dir=GMA/UI/assets)
  → App.start()：主题、窗口、可用屏幕区域、自动备份 → 启动器或上次的项目
```

先选界面语言、再导入界面模块，是因为界面模块在导入时就会读取界面文字（如模块注册表），见[界面文字与翻译](#界面文字与翻译)。

## 目录结构

| 位置 | 内容 |
| --- | --- |
| `app.py` | `App`：启动、换窗、主题、设置、打开与保存项目、自动备份与项目锁、新建窗口、重新启动、快捷键、自检 |
| `launcher.py` | 启动器：模块卡片、全部模块、最近项目 |
| `workspace.py` | 工作区：标签栏、项目菜单、状态栏、快捷键分发；`VIEW_CLASSES`（模块 → 页面类） |
| `session.py` | `ProjectSession`：打开着的项目，修改后通知各个页面；界面状态的读写 |
| `settings.py` | 设置（`~/.opengma/settings.json`） |
| `strings.py`、`strings_en.py` | 界面上的全部文字（中文、英文） |
| `theme.py` | 颜色、字号、浅色 / 深色、主题色、附带的字体 |
| `screen.py` | 可用屏幕区域、默认窗口尺寸 |
| `views/` | 标签页：`base.py`（共同接口）、`overview_view.py`（项目总览）、`base_view.py`（表征方法的三栏模板）、`xps_view.py` 等、`tool_view.py`（计算工具的共同部分）、`srim_view.py`、`salt_view.py`、`module_view.py`（占位页）、`registry.py`（模块注册表） |
| `components/` | 界面部件：交互图 `chart.py`、数据栏、数据表、检查器、导入、出版图、峰位表与物相表、设置、关于、恢复备份等对话框，通用小部件 `widgets.py` |
| `services/` | 适配层，**不依赖 flet**：曲线整理、出版图、复制为代码、分析、导入、文字格式、计算工具、自动备份、项目锁、新建窗口、自检 |
| `assets/` | 图标（SVG）、应用图标、随应用附带的字体 |

`services/` 不导入 flet，所以可以直接用 pytest 测试；页面和部件尽量只负责显示和收集输入，计算和整理放进 services 或 GMA 中。

## 窗口与换窗

Flet 一个进程只有一个窗口。启动器和工作区是同一个窗口（Q3）：换窗时把透明度设为 0，改尺寸、换内容并居中，再把透明度设回 1。不隐藏窗口，因为 macOS 上隐藏唯一的窗口会让程序退出。两种窗口共用一个最小尺寸，只在启动时设一次。

- **可用屏幕区域**：Flet 没有读取屏幕尺寸的接口，第一次启动时在窗口透明时最大化一次，读出可用区域再还原（`screen.py`），结果保存在设置中。
- **关闭**：窗口的关闭按钮被拦下（`prevent_close`），工作区按设置回到启动器或退出（Q4），有未保存的修改时先询问。
- **快捷键**：`App.on_key` 接受 Ctrl 和 ⌘，工作区的快捷键交给 `Workspace.on_shortcut`，导入（I）、出版图（E）再交给当前页面的 `on_shortcut`。

这些做法在三个系统上相同，不按系统分别处理。

## 项目、会话与界面状态

内存中的 `Project` 是唯一的事实来源（设计原则 2）。界面上的修改先改项目，再调用 `session.changed(kind, source)` 通知各个页面：

| kind | 什么时候 | 谁要刷新 |
| --- | --- | --- |
| `data` | 导入、改名、删除、改分峰名等 | 所有标签 |
| `renamed`、`saved` | 项目改名、保存 | 项目总览和标签栏 |
| `state` | 计算工具的输入改了（项目标记为有未保存的修改） | 标签栏 |

发起修改的页面（`source`）自己已经刷新过，不再重画。页面只在切换到它时重新生成（`invalidate()` 后下次 `control()` 重建）。

每个标签保存自己的状态（选择、显示设置、出版图选项，计算工具的输入）。保存项目时工作区收集各标签的 `state()`，写成 `{"version": 1, "tabs": [{"module": 键, "state": {...}}], "active": 序号}` 存进 `project.ui_state`（Q10）；打开项目时按它恢复标签，不认识的模块忽略。

## 模块注册表

`views/registry.py` 中每个模块登记一次（`ModuleSpec`）：键、名称、图标、浅色 / 深色的模块色和图标底色、类别（`METHOD` 表征方法 / `TOOL` 计算工具）、状态（`AVAILABLE` / `PLANNED`）、卡片上的说明、对应的项目方法、支持的文件。启动器的模块区、“全部模块”、工作区的“+”菜单和标签图标都从这里读取。说明、支持的文件和计算工具的名称写在界面文字中（`S.MODULE_*`），表征方法的名称（XPS 等）不翻译。

`workspace.py` 的 `VIEW_CLASSES` 把模块键对应到页面类；没有页面类的模块用占位页 `ModuleView`，规划中的模块显示为灰色（Q21）。

## 页面

所有标签页都继承 `views/base.py` 的 `TabView`：`build()` 生成界面，`control()` 按需重建，`invalidate()` 标记过期，`redraw()` 立即重画，`state()` 返回要保存的状态。

### 表征方法：三栏模板

XPS、Raman、XRD 共用 `base_view.py` 的 `MethodView`：

- **左栏** `components/data_panel.py`：按样品分组的谱图，可以搜索、按类型筛选，勾选后叠加或并排；
- **中间**：交互图 `components/chart.py` 和数据表 `components/data_table.py`；
- **右栏** `components/inspector.py`：显示、分析、信息三页。

子类只提供自己的设置：`FILTERS`（左栏的类型筛选）、`SUFFIXES`（可以导入的文件）、`READERS`（读取器，取自 CM 的 `READERS`）、`PHASES`（是否有参考物相，XRD），必要时改写 `matches()`、`badge()` 等。

**交互图**用 Flet 的 LineChart（Q5），做法来自 P0 的验证（`scripts/ui_p0/RESULTS.md`）：数据点只在打开时发送一次，缩放、平移只改坐标范围；曲线数据标记为 isolated，改范围时 Flet 不再逐点比较；坐标轴、网格、峰位标注自己画在图表外面；滚轮、触控板、拖动缩放平移；悬停读数显示在状态栏。曲线的整理（归一化、错开、分峰曲线、颜色）在 `services/spectra.py` 中，调用 GMA 的整理函数和通用色卡，所以交互图和出版图的数值、颜色一致。这些显示设置不修改项目中的数据。

**出版图**：`components/figure_dialog.py` 向页面要一个 `PlotRequest`（`figure_request(options)`），由 `services/figures.py` 调用 GMA 的 Plotter 生成图片；预览就是导出的图片（不用 MatplotlibChart，它会拉伸图片）。`services/codegen.py` 按同一个请求生成“复制为代码”。字体：系统中没有所选字体时用附带的、字宽相同的 Liberation 字体代替，中文用附带的 Noto Sans SC。出版图选项（`FigureOptions`）保存在标签状态中。

**导入**：`components/import_dialog.py` 在后台线程中调用 `GMA.project` 的 `inspect_files` / `inspect_folder`，显示识别结果、分峰名和清洗报告，确认后 `commit`。其他软件导出的表格先在 `components/columns_dialog.py` 中指定各列的含义。

### 项目总览

`overview_view.py` 是工作区第一个固定标签（Q18）：样品表（字段由用户定义）、数据检查（`services/checks.py`：清洗记录、分峰名不一致，只提示、不自动修改）、数据导出。

### 计算工具

`tool_view.py` 的 `ToolView` 是计算工具页的共同部分：卡片、数字输入框、结果行。计算工具不读写项目中的谱图，输入保存在标签状态中，随项目保存；输入改了会通过 `touch()` 把项目标记为有未保存的修改。

- `srim_view.py`：读取的 SRIM 文件**内容**也保存在标签状态中，换一台电脑打开项目也能重新计算。计算调用 `GMA.SC.SRIM`，出版图用 `figures.ProfileRequest`（数据来自页面，不来自项目），导出、复制为代码在 `services/tools.py` 中。
- `salt_view.py`：组成表、实时计算的称量表。预设保存在设置的 `salt_presets` 中（为 `None` 时用 `GMA.SC.Salts.PRESETS`），可以修改、另存、恢复内置的。

## 界面文字与翻译

界面上的文字全部写在 `strings.py` 的 `S` 中（中文），英文写在 `strings_en.py` 的 `EN` 中，名字和模板参数一一对应，`tests/test_ui_p5.py` 检查两边是否一致。

- 启动时 `strings.use(language)` 把 `S` 中的文字换成所选语言；界面模块在导入时就读取 `S`，所以换语言要重新启动（设置中可以直接重新启动）。
- 带参数的句子写成 `str.format` 模板：`S.SELECTED_SAMPLES.format(n=1, total=3)`。中文和英文的标点、语序不同，拼接文字也用模板（`S.LABELED`、`S.LIST_SEP`、`S.WITH_NOTE` 等），代码中不写标点。
- 英文的单复数写成 `{n:file|files}`，n 为 1 时用前一个词（`strings.Text`）。
- 日期中的月份、主题色的名称、模块的名称和说明、“复制为代码”中的注释也都在这里。
- 库中的异常信息是英文的；需要在界面上解释时（如峰位表的检查结果），在界面中按情况换成界面文字。

**增加一段文字**：在 `S` 中加一个名字，在 `EN` 中加同名的英文（参数相同），代码中用 `S.名字`。英文用美式拼写，按界面的长度检查一遍（按钮、分段按钮、下拉框中放不下时用更短的说法）。

**增加一种语言**：写一个 `strings_xx.py`，在 `strings.LANGUAGES` 和 `use()` 中登记，`settings.py` 的 `CHOICES["language"]` 中加上它，再仿照现有的测试检查名字和参数。

## 外观

- `theme.py`：界面中自己画的部分（面板、边框、标签栏）用 `Palette` 中的颜色；Flet 自带的控件用 `make_theme()` 由主题色生成的主题。两者都随主题色和浅色 / 深色变化（Q12）。模块色固定，不随主题色变化。
- 字体：界面用附带的 Noto Sans SC（SIL OFL 1.1），三个系统显示一致；出版图的代替字体是附带的 Liberation Serif / Sans。字体文件和许可证在 `assets/fonts/`。
- 图标是 `assets/icons/` 中的 SVG，24 px 网格、圆头线条（Q14）。应用图标 `assets/icon.png`、`icon_macos.png` 由 Logo 生成，打包时使用。

## 设置

`settings.py` 中的 `Settings` 保存在 `~/.opengma/settings.json`（`OPENGMA_HOME` 可以改到别处）：外观、窗口、绘图和数据的默认值、启动与关闭、界面语言、最近项目、熔盐预设。读取时忽略不认识的键，值不合法时用默认值，所以新旧版本的设置文件都能读；保存时先写临时文件再替换。增加一项设置时：在 `Settings` 中加字段和默认值，需要限定取值时加进 `CHOICES` 或在 `from_dict` 中检查，再在 `components/settings_dialog.py` 中加控件。

## 自动备份、项目锁、新建窗口

这三项都只用文件和时间判断，三个系统做法相同，代码在 `services/` 中，不依赖 flet：

- **自动备份**（`autosave.py`）：有未保存的修改时，每 5 分钟把项目写一份到 `~/.opengma/autosave`（`<key>.nc` 是项目，`<key>.json` 记录项目名、原来的文件、备份时间）。程序运行期间每分钟更新一次 `alive_at`（心跳）。启动时，超过 3 分钟没有心跳的备份说明上次没有正常关闭，启动器中提示打开或删除（`components/recovery_dialog.py`）；另一个窗口正在用的备份有心跳，不会被当成需要恢复的。保存项目、正常关闭时删除备份。
- **项目锁**（`locks.py`）：打开项目时在项目文件旁边写 `.项目名.nc.lock`（JSON：窗口标识、用户、电脑名、进程号、打开时间、心跳时间），每分钟更新心跳。另一个窗口（或另一台电脑通过共享文件夹）打开同一个项目时，发现有心跳的锁就提示只读打开、仍然编辑或取消；超过 3 分钟没有心跳的锁视为失效。只读打开的项目只能另存为新文件。写不了锁文件时不影响打开项目。
- **新建窗口**（`launch.py`）：再启动一个 OpenGMA 进程。从源码运行时用当前的 Python 运行 `python -m GMA.UI`；打包的程序（环境变量 `FLET_PLATFORM`）再运行程序本身。新进程从启动器开始（`OPENGMA_NEW_WINDOW`）。换界面语言后的“重新启动”也用它。

## 增加一个表征方法模块

在 CM 和 project 中加好新方法以后（见 [CM 模块](CM模块.md#增加表征方法)、[project 模块](project模块.md#增加表征方法)）：

1. 画一个模块图标放进 `assets/icons/`；
2. `registry.py` 中加 `ModuleSpec`（类别 `METHOD`，`method` 写项目中的方法名），说明和支持的文件写进 `S` 和 `EN`；
3. 新建 `views/ftir_view.py`，继承 `MethodView`，设置 `FILTERS`、`SUFFIXES`、`READERS`（照 `raman_view.py` 写，只有十几行），在 `workspace.py` 的 `VIEW_CLASSES` 中登记；
4. `services/figures.py` 中把新方法加进 `PLOTTERS`、`LINE_FUNCTIONS`（谱线图）、`FIT_FUNCTIONS`（拟合谱图，没有可以不加），以及导出交互 HTML 用的 `INTERACTIVE`、`INTERACTIVE_KWARGS`。“复制为代码”按 `{方法名}Plotter` 写类名（`services/codegen.py`），所以 Plotter 要这样命名并从 `GMA` 导出；
5. 按方法区分的文字：`S.AXIS_NAMES`（分析中的“范围”），导入对话框中“识别为”的类型名（`services/importing.py` 的 `kind_options` 和 `S.KIND_*`）；
6. 测试：仿照 `tests/test_ui_p4.py`，检查各视图选用的绘图函数、复制的代码能运行。

界面中的交互图按项目中 `MethodSpec` 的 `AXIS` 定方向和坐标轴标题，分析按 `spectrum_metrics` 计算，这两处不需要修改。

## 增加一个计算工具

1. 先在 `GMA.SC` 中写好计算函数和测试（见 [SC 模块 · 增加计算](SC模块.md#增加计算)）；
2. `registry.py` 中加 `ModuleSpec`（类别 `TOOL`，`method` 为 `None`），文字写进 `S` 和 `EN`；
3. 新建页面类，继承 `ToolView`：输入放在 `self.st` 中（随项目保存），改动后调用 `touch()`；计算只调用 `GMA.SC`；
4. 在 `VIEW_CLASSES` 中登记；导出、复制为代码等不依赖界面的部分放进 `services/tools.py`；
5. 测试：仿照 `tests/test_ui_p5.py`，用只有设置和配色的替身对象检查页面的状态、计算和生成的代码。

## 测试与检查

- `uv run pytest` 中的界面测试都不打开窗口，见[开发流程 · 测试](开发流程.md#测试)。
- 界面的样子用网页模式检查：按[开发流程 · 运行](开发流程.md#运行)中的方法运行，在浏览器中操作或用 Playwright 截图；中文、英文，浅色、深色，宽窗口、窄窗口都看一遍。
- 桌面版：`uv run opengma`；需要自动检查时设置 `OPENGMA_SMOKE_TEST`，程序打开启动器、完成自检后自动退出（`services/smoke.py`）。打包后的程序用同样的自检，见[开发流程 · 打包](开发流程.md#打包)。
