# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
读取 Thermo Fisher Scientific 仪器经 Avantage 软件处理后导出的 Excel 数据。

reader 接收文件路径，返回符合 XPS 标准数据结构（见 XPS/schema.py）的 pandas.DataFrame：
- 全谱：["Binding Energy (eV)", "Intensity"]
- 元素谱：未拟合时同全谱；拟合后为
  ["Binding Energy (eV)", "Intensity", "Fitting Curve", 分峰列..., "Background"]

测试仪器：ESCALAB Xi+
"""
import pandas as pd

from ..schema import BE_COL, BG_COL, FIT_COL, INTENSITY_COL

HEADER_ROWS = 15  # Avantage 导出文件中数据表之前的说明行数


def _read_avantage_excel(file_path) -> pd.DataFrame:
    """读取 Avantage 导出的 Excel，去掉整列为空的列（导出文件中常有空列）。"""
    df = pd.read_excel(file_path, skiprows=HEADER_ROWS, engine="calamine")
    return df.dropna(axis=1, how="all")


def survey_reader(file_path):
    """读取全谱，返回 ["Binding Energy (eV)", "Intensity"] 两列。"""
    df_survey = _read_avantage_excel(file_path).iloc[:, :2]
    df_survey.columns = [BE_COL, INTENSITY_COL]
    return df_survey


def element_reader(file_path, peaks=None):
    """
    读取元素谱。

    导出文件只有两列数据时视为未拟合谱，返回 ["Binding Energy (eV)", "Intensity"]；
    拟合后的数据依次为结合能、强度、拟合曲线、各分峰、背景。

    peaks 参数传入分峰名（化学键）的列表，例如：["C-Si", "C-O"]。需要特别注意传入的顺序
    必须和 Excel 原始数据中从左到右的分峰顺序一致。本函数已经自动处理了其他数据列名，
    只需要传入分峰对应的列名即可。如果只是数据预览，也可不传入，函数会自动使用 Excel
    文件中的分峰名称。
    """
    df_element = _read_avantage_excel(file_path)
    n_columns = df_element.shape[1]

    # 未拟合的元素谱：只有结合能和强度
    if n_columns == 2:
        if peaks:
            raise ValueError("This spectrum has no fitted components, so peaks cannot be set.")
        df_element.columns = [BE_COL, INTENSITY_COL]
        return df_element

    if n_columns < 4:
        raise ValueError(
            f"Expected 2 columns (unfitted) or at least 4 columns (fitted), got {n_columns}: "
            f"{list(df_element.columns)}"
        )

    names = df_element.columns.to_list()
    names[0] = BE_COL
    names[1] = INTENSITY_COL
    names[2] = FIT_COL
    names[-1] = BG_COL
    if peaks:
        if len(peaks) != n_columns - 4:
            raise ValueError(
                f"输入峰值数量错误。期望 {n_columns - 4} 个，实际传入 {len(peaks)} 个。"
            )
        names[3:-1] = peaks

    df_element.columns = names
    return df_element
