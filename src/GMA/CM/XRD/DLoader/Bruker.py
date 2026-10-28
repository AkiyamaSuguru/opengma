# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
读取布鲁克（Bruker）X 射线衍射仪导出的 txt 数据。

返回 (df, metadata)：
- df 符合 XRD 标准数据结构 ["2Theta (deg)", "Intensity"]（见 XRD/schema.py）；
- metadata 为 {节名: {键: 值}}，来自文件中 [节名] 下的 "键=值" 行。
"""
import re

import pandas as pd

from ..schema import INTENSITY_COL, TWO_THETA_COL

COMMENT_RE = re.compile(r";.*")  # 分号后面是注释
SKIPPED_SECTIONS = ("VarInfo", "Drive")  # 这些节会多次出现，不放入 metadata


# 型号：D8 Advance
def reader_d8advance(file_path):
    metadata = {}
    data_points = []
    current_section = None
    is_data_section = False

    with open(file_path, encoding="utf-8-sig", errors="replace") as f:
        for line in f:
            # 1. 清洗行：去掉注释和首尾空白
            line = COMMENT_RE.sub("", line).strip()
            if not line:
                continue

            # 2. 识别节点 (Section)
            if line.startswith("[") and line.endswith("]"):
                current_section = line[1:-1].strip()
                is_data_section = current_section == "Data"
                continue

            # 3. 提取元数据 (Metadata)
            if not is_data_section:
                if "=" in line and current_section not in SKIPPED_SECTIONS:
                    key, value = line.split("=", 1)
                    metadata.setdefault(current_section, {})[key.strip()] = value.strip()
                continue

            # 4. 提取衍射数据 (Data)：跳过列标题行，数据以逗号分隔（如: 10.1639, 253,）
            if "Angle" in line:
                continue
            parts = [p.strip() for p in line.split(",") if p.strip()]
            if len(parts) >= 2:
                try:
                    data_points.append((float(parts[0]), float(parts[1])))
                except ValueError:
                    continue

    df = pd.DataFrame(data_points, columns=[TWO_THETA_COL, INTENSITY_COL])
    return df, metadata
