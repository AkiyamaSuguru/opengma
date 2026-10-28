# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
读取 Horiba Jobin Yvon 仪器（LabSpec 软件）导出的 txt 数据。

返回 (df, metadata)：
- df 符合 Raman 标准数据结构 ["Raman Shift (cm-1)", "Intensity"]（见 Raman/schema.py）；
- metadata 为文件头中 "#键=值" 形式的信息。
"""
import pandas as pd

from ..schema import INTENSITY_COL, SHIFT_COL


# 型号：LabRAM HR Evolution
def reader_horiba_hr_evolution(file_path):
    metadata = {}
    data = []

    with open(file_path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()

            # 文件头：#键=值
            if line.startswith("#"):
                key, sep, value = line[1:].partition("=")
                if sep:
                    metadata[key.strip()] = value.strip()
                continue

            # 数据：拉曼位移  强度
            parts = line.split()
            if len(parts) == 2:
                try:
                    data.append((float(parts[0]), float(parts[1])))
                except ValueError:
                    continue

    df = pd.DataFrame(data, columns=[SHIFT_COL, INTENSITY_COL])
    return df, metadata
