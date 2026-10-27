"""
Raman 数据读取入口：用一个类统一管理不同厂商、型号仪器的数据读取。

reader 约定：接收文件路径，返回元组 (df, metadata)，
其中 df 为 pandas.DataFrame，metadata 为元数据（建议用 dict）。
"""
from __future__ import annotations

from collections.abc import Callable
from typing import NamedTuple

import pandas as pd

from .RLoader.Horiba import reader_horiba_hr_evolution

# 仪器型号 -> reader 函数；新增仪器时在这里注册
READERS: dict[str, Callable] = {
    "Horiba HR evolution": reader_horiba_hr_evolution,
}

class RamanResult(NamedTuple):
    """read() 的返回值：本身就是 (data, metadata) 元组，也可以按名字取字段。"""

    data: pd.DataFrame
    metadata: dict

class RamanLoader:
    """传入仪器型号名或自定义 reader 函数，之后统一用 read() 读取文件。"""

    def __init__(self, reader: str | Callable):
        if isinstance(reader, str):
            if reader not in READERS:
                raise ValueError(
                    f"Unknown reader {reader!r}. Available readers: {list(READERS)}"
                )
            self.reader = READERS[reader]
        elif callable(reader):
            self.reader = reader
        else:
            raise TypeError(
                f"reader must be a str or a callable, got {type(reader).__name__}"
            )

    def read(self, file_path) -> RamanResult:
        """读取文件，并检查 reader 的返回值是否符合约定。"""
        result = self.reader(file_path)
        if not (isinstance(result, tuple) and len(result) == 2):
            raise TypeError("reader must return a tuple: (df, metadata)")
        df, metadata = result
        if not isinstance(df, pd.DataFrame):
            raise TypeError(
                f"df must be a pandas DataFrame, got {type(df).__name__}"
            )
        return RamanResult(df, metadata)