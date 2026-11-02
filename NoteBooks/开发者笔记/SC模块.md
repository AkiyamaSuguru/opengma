# SC 模块开发者笔记

SC 模块主要为模拟和计算的模块，为 Simulation 和 Calculation 的缩写。这里目前主要包含的是离子辐照中使用 SRIM 计算得到数据的处理，也就是 dpa 等计算。关于 SRIM 模拟等代码封装在 SRIM 模块下。另外在进行熔盐腐蚀实验时需要计算 LiF 等各种盐的称量质量，这里也提供了 Salts 模块供熔盐相关的计算。

关于其他部分的计算和模拟代码根据后续开发者的经验补充。

```
src/GMA/SC/
├── SRIM/
│   ├── reader.py    # 读取 VACANCY.txt、RANGE.txt：VacancyTable、RangeTable、Layer
│   ├── damage.py    # depth_profile（dpa、注入离子浓度），peak、average、centroid
│   └── plotter.py   # SRIMPlotter：dpa 和离子浓度两条纵轴的出版图
└── Salts/
    ├── elements.py  # 相对原子质量 ATOMIC_WEIGHTS
    └── mixture.py   # 化学式解析、摩尔质量、salt_masses、内置组成 PRESETS
```

SC 和 CM 一样不依赖 flet。图形界面中的计算工具页（`GMA/UI/views/srim_view.py`、`salt_view.py`）只负责输入和显示，计算都调用这里的函数，“复制为代码”生成的也是这些调用。用法见仓库 README 的“计算”一节。

## SRIM

### 文件格式

TRIM 每次计算在 `SRIM Outputs` 中写出 VACANCY.txt（空位）和 RANGE.txt（离子和反冲原子停留位置的分布）。两种计算方式的输出列不同，读取时按表头区分：

| 计算方式 | VACANCY.txt 的列 | RANGE.txt 的列 |
| --- | --- | --- |
| Quick K-P（Ion Distribution and Quick Calculation of Damage） | 深度、离子产生的空位、反冲产生的空位 | 深度、离子分布、反冲分布（全为 0） |
| Full Cascade（Detailed Calculation with full Damage Cascades） | 深度、离子撞出的初级撞出原子数（Knock-Ons）、各元素的空位 | 深度、离子分布、各元素反冲原子的分布 |

- 深度是每个深度区间的右端，单位 Å，一般是把靶的总厚度等分成 100 个区间；数据点之间的间隔就是区间宽度。读取后原样保存，`frame()` 可以看到原始表格。
- 文件头中读出离子、能量（keV）、计算的离子数、Total Target Vacancies，以及各层的名称、厚度、原子密度（atoms/cm³）、质量密度和组成。RANGE.txt 还有平均射程和歧离。
- 多层靶的 Full Cascade 文件中，元素的列按层依次排列（如 W | Si O | Si）。`_element_layers` 按文件头中各层的元素把列对应到层，对不上时只按元素名处理。
- 某些系统区域设置下 SRIM 写出的是小数逗号（`1,5E-04`），读取时按小数点处理。
- 读不出表格、表头或文件头中缺少原子密度时抛出 `SRIMFileError`，信息说明缺的是什么。

测试数据：`tests/data/srim` 中是一组真实的 Quick K-P 结果（Xe 5.4 MeV 打石墨）。Full Cascade、多层靶等格式在 `tests/test_sc.py` 中按 TRIM 的格式合成。

### 计算

`depth_profile(vacancy, ions, fluence=..., densities=None)` 返回深度分布的 DataFrame：

```
dpa(x) = V(x) × 10⁸ × Φ ÷ N(x)
C(x)   = R(x) × Φ，  at.% = C ÷ (C + N) × 100
```

- V：每个离子在每 Å 深度上产生的空位（vacancies/(Å·ion)）。Quick K-P 为离子产生的加反冲产生的；Full Cascade 为各元素空位之和，**不加 Knock-Ons 列**：各元素的空位已经包含离子直接撞出的原子留下的空位。用 pysrim 带的 5 个真实 SRIM 结果核对过，这样得到的总数与文件头的 Total Target Vacancies 一致（`vacancies_per_ion()` 可以核对）。
- 10⁸：Å 换算成 cm；Φ：注量（ions/cm²）。按束流和时间时 Φ = 束流（ions/(cm²·s)）× 时间（s）。
- N：深度 x 所在层的原子密度（atoms/cm³），默认取文件头中的值；`densities` 可以是一个数（所有层）或按层的列表（`None` 的层用文件头中的值）。
- R：RANGE.txt 的离子分布（(atoms/cm³)/(atoms/cm²)）。at.% 用 C ÷ (C + N)，与原来的参考脚本一致。

这两个公式与项目最初的参考脚本（`Damage.get_dpa`、`Concentration`）相同，`tests/test_sc.py` 中有对比。同时给出两个文件时，`check_same_run` 检查它们来自同一次计算（离子、能量、深度区间相同）。

返回的列：`Depth (nm)`、`Atomic density (atoms/cm3)`，有 VACANCY.txt 时有 `Vacancies (1/(A*ion))`、`dpa`（Full Cascade 另有各元素的 `dpa (元素)`，加起来就是总的 dpa），有 RANGE.txt 时有 `Ions (atoms/cm3)`、`Ions (at.%)`。`attrs` 中记录离子、能量、注量、各层名称和界面深度，画图时用。

读数：

- `peak(profile, column)`：最大值和所在深度；
- `average(profile, column, start, end)`：深度范围内的平均值。每个区间内的值看作常数，范围只覆盖区间的一部分时按覆盖的长度计入，所以结果不受端点是否落在区间边界上的影响；
- `centroid(profile)`：分布的平均深度（按区间中点），如注入离子的平均射程。

`SRIMPlotter.plot_profile_static` 把 dpa 画在左纵轴、离子浓度画在右纵轴，多层靶的界面画成点线，样式与 CM 的出版图相同；深度单位可以是 nm、µm 或 Å。

## Salts

`salt_masses(组成, 总质量, molar_masses=None)` 按摩尔分数和混合盐的总质量计算每种盐的质量：

```
m_i = M_total × x_i·M_i ÷ Σ x_j·M_j
```

- 组成写成 `{化学式: 摩尔比例}`，比例可以是 mol%，也可以是任意比例（如 2 : 1），按总和归一化；
- 摩尔质量由 `parse_formula` 解析化学式后按 `ATOMIC_WEIGHTS` 计算。化学式支持括号（`Ca(NO3)2`）、下标数字（`BeF₂`）和结晶水（`MgCl2·6H2O`，也可以写 `MgCl2*6H2O`）；不接受以数字开头的写法（如表示同位素的 `7LiF`），同位素富集的盐用 `molar_masses` 直接给出摩尔质量；
- 原子量用 IUPAC 标准原子量，有范围的元素（Li、B、C、Cl 等）用约定值，没有稳定同位素的元素用最长寿命同位素的质量数。FLiNaK 的质量比与原来的参考脚本 `FLiNaKs` 一致（0.29211 : 0.11694 : 0.59095），有测试；
- 返回的列：`Salt`、`Mole fraction (mol%)`、`Molar mass (g/mol)`、`Mass fraction (wt%)`、`Mass (g)`。

`PRESETS` 中是几种常见组成：FLiNaK（LiF-NaF-KF 46.5-11.5-42）、FLiBe（LiF-BeF2 67-33）、NaCl-KCl、LiCl-KCl、NaCl-MgCl2、KCl-MgCl2。这些只是起点：图形界面中可以修改、另存为自己的预设（保存在设置中），也可以恢复内置的。

## 增加计算

1. 在 `SC/` 下新建子模块（如 `SC/Diffusion/`），写成不依赖界面的函数：输入是数值或文件路径，输出是数值或 DataFrame，单位写在列名中；
2. 公式、单位、适用范围写在模块的 docstring 中，并在这份笔记中补一节；
3. 有参考脚本或文献数值时写成测试，在 `tests/test_sc.py` 中对比；
4. 需要界面时，见 [UI 模块 · 增加一个计算工具](UI模块.md#增加一个计算工具)。
