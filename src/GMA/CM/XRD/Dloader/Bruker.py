# 本模块用于布鲁克（Bruker）品牌的 X 射线衍射仪测得的数据
import re
import pandas as pd

## 型号：D8 Advance
def reader_d8advance(file_path):
    """
        解析 txt 格式文件
        返回: (df, metadata)
        """
    metadata = {}
    data_points = []
    current_section = None
    is_data_section = False

    # 用于清洗 标签和分号注释的正则
    tag_re = re.compile(r'\s*')
    comment_re = re.compile(r';.*')

    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            # 1. 清洗行：去除系统标签、注释、首尾空格
            line = tag_re.sub('', line)
            line = comment_re.sub('', line).strip()
            if not line:
                continue

            # 2. 识别节点 (Section)
            if line.startswith('[') and line.endswith(']'):
                current_section = line[1:-1]
                if current_section == 'Data':
                    is_data_section = True
                else:
                    is_data_section = False
                continue

            # 3. 提取元数据 (Metadata)
            if not is_data_section and '=' in line:
                key, val = line.split('=', 1)
                key, val = key.strip(), val.strip()

                # 特殊处理多次出现的 VarInfo
                if current_section == 'VarInfo' or current_section == 'Drive':
                    continue
                else:
                    if current_section not in metadata:
                        metadata[current_section] = {}
                    metadata[current_section][key] = val

            # 4. 提取衍射数据 (Data)
            elif is_data_section:
                # 跳过数据列标题行
                if 'Angle' in line:
                    continue
                # 处理以逗号分隔的数据（如: 10.1639, 253,）
                parts = [p.strip() for p in line.split(',') if p.strip()]
                if len(parts) >= 2:
                    try:
                        angle = float(parts[0])
                        psd = float(parts[1])
                        data_points.append({'Angle': angle, 'PSD': psd})
                    except ValueError:
                        continue

    # 转换为 DataFrame
    df = pd.DataFrame(data_points)

    return df,metadata