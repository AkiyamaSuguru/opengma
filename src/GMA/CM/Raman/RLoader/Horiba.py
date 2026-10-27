"""
本模块用于读取 Horiba Jobin Yvon 仪器的数据，数据导出的格式为txt格式。
"""
import pandas as pd
from matplotlib import pyplot as plt

# 型号：Horiba HR evolution
def reader_horiba_hr_evolution(filepath):
    metadata = {}
    data = []

    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()

            # metadata
            if line.startswith("#"):
                line = line[1:]
                if "=" in line:
                    key, value = line.split("=", 1)
                    metadata[key.strip()] = value.strip()

            # data
            else:
                parts = line.split()
                if len(parts) == 2:
                    try:
                        shift = float(parts[0])
                        intensity = float(parts[1])
                        data.append([shift, intensity])
                    except:
                        pass

    df = pd.DataFrame(data, columns=["Raman_shift", "Intensity"])

    return df, metadata