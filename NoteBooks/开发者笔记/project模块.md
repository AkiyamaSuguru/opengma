# project 模块开发者笔记

`GMA.project` 把多个样品、多种表征方法的数据整理成一个项目，保存为一个 NetCDF 文件（`.nc`）。它是 CM 和图形界面之间的一层：读取仍然用 CM 的 Loader，这里负责识别数据类型、清洗并记录、保存来源、存成文件、导出。这个模块不依赖 flet，在 marimo 中也可以直接使用，用法见仓库 README 的“项目文件”一节。

| 文件 | 内容 |
| --- | --- |
| `model.py` | `Record`（一条谱图）、`Sample`（样品）、`Project`（项目）；表征方法表 `METHODS`；清洗 `clean_frame` 和清洗记录 `CleanNote` |
| `storage.py` | `Project` ⇄ `xarray.DataTree`，`save_project`、`load_project` |
| `importers.py` | 导入：`inspect_file`、`inspect_files`、`inspect_folder` 生成导入项 `ImportItem`，确认后 `commit`；通用表格 `GENERIC_READER` 和 `TableColumns` |
| `tables.py` | `read_table` 读取其他软件导出的表格；峰位表、参考物相表与 CSV 的读写 |
| `exporters.py` | `export_csv`、`export_excel`，Excel 中的“信息”表 `info_frame` |

## 数据模型

**表征方法**：`METHODS` 中每种方法一个 `MethodSpec`，写明标准 DataFrame 中的横轴列名、Dataset 中的横轴坐标名、单位、这种方法的数据类型（第一个是默认值）和横轴 `AXIS`：

| 方法 | 横轴坐标 | 单位 | 数据类型 |
| --- | --- | --- | --- |
| XPS | `binding_energy` | eV | `element`（元素谱）、`survey`（全谱） |
| Raman | `raman_shift` | cm-1 | `spectrum` |
| XRD | `two_theta` | deg | `pattern` |

**Record**：一条谱图，内部是一个 `xarray.Dataset`。横轴是 `point` 维度上的坐标；`intensity` 是强度；拟合谱另有 `fitting_curve`、`background`，以及 `component_intensity`（维度 `component` × `point`，`component` 坐标是分峰名）。属性中保存：`record_id`（uuid）、方法、类型、名称、样品、是否拟合、分峰数据模式、来源（路径、文件名、SHA-256、读取器、导入时间）、GMA 版本、清洗记录和仪器元数据（JSON 字符串）、备注、派生来源。

- `Record.from_dataframe(df, method, name, sample, ...)` 把标准 DataFrame 存进来（先经过 `clean_frame`），`to_dataframe()` 原样取出，可以直接交给 Plotter；
- 名称、样品、分峰名都可以改（`rename_components` 只改名字，不改数据），改动直接写在 Dataset 上。

**Project**：项目名、样品（`Sample`：名称和样品信息字典）、谱图（按 `record_id`）、样品信息的字段、峰位表、参考物相表、界面状态 `ui_state`。修改项目的方法都会把 `dirty` 设为 True，保存后清除：

- 谱图：`add_record`（同名时 `copy` 另存副本、`replace` 替换、`skip` 跳过）、`get`、`find_by_name`、`records_of`、`rename_record`、`move_record`、`remove_record`；
- 样品：`add_sample`、`rename_sample`、`remove_sample`、`add_field`、`set_sample_info`；
- 峰位表和参考物相：`set_peak_table`、`peaks(名称)`、`set_reference_phases`、`references()`。行的内容会检查（标签不能为空或重复、位置必须是有限的数值），不符合时抛出 `ProjectError`。GMA 不内置任何峰位或物相（Q7）。

`ProjectError` 是这个模块的异常，信息用英文，说明哪条数据、哪一步、为什么；界面把它们显示给用户。

## 清洗

`clean_frame(df, method)` 只做不改变科学含义的整理（Q19），每一步写进清洗记录：

| 记录 | 什么时候 |
| --- | --- |
| `dropped_rows` | 必需列为空或不是数值的行，去掉，记下行号（从 1 开始，按原始顺序） |
| `empty_component` | 分峰列整列没有数值，忽略这一列 |
| `duplicate_x` | 横轴有重复的值，只提示，不删除 |
| `sorted` | 横轴不单调，按横轴从小到大排列（从大到小时直接倒序，不记录） |

`CleanNote` 中 `code` 供程序判断，`detail` 保存具体数字；`text()` 给出中文说明。界面按界面语言另外生成说明（`GMA/UI/services/importing.py` 的 `note_text`），所以增加一种记录时两边都要加。截取范围这类会改变数据的操作不在清洗中做，以后要做时生成新的派生谱图，并在 `derived_from` 中记下原来的谱图。

## 项目文件

一个项目就是一个 NetCDF-4/HDF5 文件，内部是 `xarray.DataTree`，层级为 `/样品/方法/谱图`（Q8）：

```
/                       根：schema、项目名、时间、样品字段、样品和谱图的顺序、峰位表、物相表、界面状态
/{样品}                 node_type = sample，样品名和样品信息
/{样品}/{方法}          node_type = method
/{样品}/{方法}/{名称}   node_type = record，就是 Record 的 Dataset
```

- 节点名不能含 `/`，`_node_name` 把 `/`、`\` 换成 `_`，重名时加序号；原名保存在属性中，读回时用原名。
- 根节点的表格类内容（样品字段、峰位表、物相表、界面状态等）存成 JSON 字符串属性。
- 根节点的 `schema_name`、`schema_version`（现在是 `1.0`）用来识别文件和以后迁移旧版本：改变文件结构时提高版本号，并在 `datatree_to_project` 中把旧版本转换过来。
- 保存时先写同一文件夹中的临时文件 `.{文件名}.saving`，再用 `os.replace` 替换，保存中断时原文件不受影响。
- 打开时用 `xr.load_datatree` 把全部数据读进内存并关闭文件。Windows 上打开着的文件不能被替换，所以不能改成懒加载。
- `save_copy` 写一份副本而不改变项目的路径和“未保存”状态，自动备份用的就是它；`write_tree` 可以在主线程中生成 DataTree、在后台线程中写文件。

不用 GMA 也能读：`xarray.open_datatree("项目.nc", engine="h5netcdf")`。

## 导入

导入分两步：先读取、生成可以检查和修改的导入项，确认后再加入项目。

1. `inspect_file` / `inspect_files` / `inspect_folder` 读取文件，生成 `ImportItem`（样品名默认取文件夹名，谱图名取文件名；XPS 按文件名识别全谱，其余为元素谱）。读取或清洗出错时 `item.error` 记下原因，不抛出异常，界面据此在导入对话框中显示。
2. 用户在对话框中改样品名、谱图名、分峰名、类型（`set_kind` 按新类型重新读取）。
3. `commit(project, items, on_conflict=...)` 把读取成功的导入项加入项目，记下来源路径、SHA-256、读取器、导入时间。

读取在 `_read` 中按方法调用 CM 的 Loader。**通用表格**（`GENERIC_READER`）用于其他软件导出的 CSV、TSV、文本：`read_table` 自动识别编码（UTF-8、GBK 等）、分隔符、表头和开头的说明行（如 Origin 的“名称、单位、注释”三行），`TableColumns` 指定哪一列是横轴、强度，拟合谱另外指定拟合曲线、背景和分峰列；各列的含义记在谱图的元数据中。

## 导出

- `export_csv`：每条谱图一个 CSV（UTF-8 带 BOM，Excel 打开不乱码），按 `样品/方法` 分文件夹；
- `export_excel`：每条谱图一个工作表，最后是“信息”表（Q20），记录样品、方法、类型、点数、分峰、来源、清洗记录和样品信息。工作表名会去掉 Excel 不允许的字符、截到 31 个字符并避免重名。表名和列名默认是中文，界面用英文时传入 `labels` 和 `note_text`。

导出的列名就是标准数据结构的列名，可以用 GMA 读回来作图。

## 增加表征方法

在 CM 中增加了新方法（见 [CM 模块 · 增加表征方法](CM模块.md#增加表征方法)）之后，这里要做两件事：

1. 在 `model.py` 的 `METHODS` 中加一个 `MethodSpec`：横轴列名、横轴坐标名（小写英文，如 `wavenumber`）、单位、数据类型、`AXIS`；
2. 在 `importers.py` 的 `_read` 中按方法调用新的 Loader，在 `DEFAULT_READERS` 中写默认读取器；需要按文件名识别类型时参考 `guess_xps_kind`。

项目文件的结构不变，不需要提高 schema 版本。
