# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
结构化存储：把多个样品、多种表征方法的数据整理成一个项目，保存为一个 NetCDF 文件。

- model：Record（一条谱图）、Sample（样品）、Project（项目），以及数据清洗 clean_frame
- storage：save_project / load_project，项目文件为 NetCDF-4/HDF5（.nc）
- importers：读取仪器导出的文件，生成可检查、可修改的导入项，确认后加入项目
- exporters：导出提取的数据，CSV 或 Excel

用法：
    from GMA.project import Project, inspect_folder, commit, save_project, load_project

    project = Project("SiC-FLiNaK 腐蚀")
    items = inspect_folder("data/B1_SiC_1100℃", "XPS")   # 文件夹名作样品名
    commit(project, items)
    save_project(project, "SiC-FLiNaK 腐蚀.nc")

    project = load_project("SiC-FLiNaK 腐蚀.nc")
    c1s = project.get("B1_SiC_1100℃", "XPS", "C1s").to_dataframe()   # 标准 DataFrame
"""
from .exporters import export_csv, export_excel, info_frame
from .importers import (
    DEFAULT_READERS,
    ImportItem,
    commit,
    file_sha256,
    guess_xps_kind,
    inspect_file,
    inspect_files,
    inspect_folder,
    item_to_record,
    set_kind,
)
from .model import (
    METHODS,
    CleanNote,
    MethodSpec,
    Project,
    ProjectError,
    Record,
    Sample,
    clean_frame,
    method_spec,
)
from .storage import SCHEMA_NAME, SCHEMA_VERSION, load_project, project_to_datatree, save_project

__all__ = [
    "DEFAULT_READERS",
    "METHODS",
    "SCHEMA_NAME",
    "SCHEMA_VERSION",
    "CleanNote",
    "ImportItem",
    "MethodSpec",
    "Project",
    "ProjectError",
    "Record",
    "Sample",
    "clean_frame",
    "commit",
    "export_csv",
    "export_excel",
    "file_sha256",
    "guess_xps_kind",
    "info_frame",
    "inspect_file",
    "inspect_files",
    "inspect_folder",
    "item_to_record",
    "load_project",
    "method_spec",
    "project_to_datatree",
    "save_project",
    "set_kind",
]
