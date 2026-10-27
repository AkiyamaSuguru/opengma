"""
本模块用于读取 ThermoFisher Scientific 仪器 数据，reader 如下规定：
接收文件路径，返回一个 pandas.DataFrame。

element 数据的 df 结构规定为：
第一列：结合能列，
第二列：强度列，
第三列：拟合曲线列，
最后一列：背景列，
中间列：拟合峰数据。

survey 数据只有前两列（结合能、强度）。

df 结构必须标准化才能进行后续处理。
"""

#型号 ： ESCALAB Xi+

import pandas as pd

def survey_reader(file_path):
    """Survey 数据读取，注意传入 Avantage 软件处理好后的 Excel 数据。"""
    df_survey_raw = pd.read_excel(file_path, skiprows=15).dropna(axis=1, how="all")
    # 提取所有行，以及前两列
    df_survey = df_survey_raw.iloc[:, :2]
    # 重命名列
    df_survey.columns = ["Binding Energy (eV)", "Intensity"]
    return df_survey


def element_reader(file_path, peaks=None):
    """Element 数据读取，注意传入 Avantage 软件处理好后的 Excel 数据。
    peaks 参数传入峰名（化学键）的列表，例如：["C-Si","C-O"]。需要特别注意传入的顺序
    必须和 Excel 原始数据中从左到右的拟合峰值顺序一致。本函数已经自动处理了其他数据列名，
    只需要传入拟合峰值对应的列名即可。如果只是数据预览，也可不传入，函数会自动使用 Excel
    文件中的拟合峰值名称。
    """
    df_element = pd.read_excel(file_path, skiprows=15).dropna(axis=1, how="all")
    names = df_element.columns.to_list()
    names[0] = "Binding Energy (eV)"
    names[1] = "Intensity"
    names[2] = "Fitting Curve"
    names[-1] = "Background"
    if peaks:
        if len(peaks) != len(df_element.columns) - 4:
            raise ValueError(
                f"输入峰值数量错误。期望 {len(df_element.columns) - 4} 个，实际传入 {len(peaks)} 个。")
        names[3:-1] = peaks

    df_element.columns = names
    return df_element