"""
XPS 数据读取入口：用一个类统一管理不同厂商、型号仪器的数据读取。

每种仪器注册两个 reader，组成元组 (survey_reader, element_reader)：
- survey_reader(file_path)：读取 survey 数据，返回 pandas.DataFrame；
- element_reader(file_path, peaks=None)：读取 element 数据，返回 pandas.DataFrame。
"""
from __future__ import annotations

from collections.abc import Callable

import pandas as pd

from .XLoader.Avantage import element_reader, survey_reader

# 仪器型号/数据处理软件 -> (survey_reader, element_reader)；新增时在这里注册
READERS: dict[str, tuple[Callable, Callable]] = {
    "Avantage": (survey_reader, element_reader),
}


class XPSLoader:
    """传入仪器型号名，或自定义的 (survey_reader, element_reader) 元组，
    之后用 read_survey() / read_element() 读取文件。
    """

    def __init__(self, reader: str | tuple[Callable, Callable]):
        if isinstance(reader, str):
            if reader not in READERS:
                raise ValueError(
                    f"Unknown reader {reader!r}. Available readers: {list(READERS)}"
                )
            self.survey_reader, self.element_reader = READERS[reader]
        elif (
            isinstance(reader, tuple)
            and len(reader) == 2
            and all(callable(func) for func in reader)
        ):
            self.survey_reader, self.element_reader = reader
        else:
            raise TypeError(
                "reader must be a str or a tuple of two callables: "
                "(survey_reader, element_reader)"
            )

    def read_survey(self, file_path) -> pd.DataFrame:
        """读取 survey 数据。"""
        return self._check(self.survey_reader(file_path))

    def read_element(self, file_path, peaks=None) -> pd.DataFrame:
        """读取 element 数据，peaks 的用法见 element_reader 的说明。"""
        return self._check(self.element_reader(file_path, peaks=peaks))

    @staticmethod
    def _check(df) -> pd.DataFrame:
        """检查 reader 的返回值是否符合约定。"""
        if not isinstance(df, pd.DataFrame):
            raise TypeError(
                f"reader must return a pandas DataFrame, got {type(df).__name__}"
            )
        return df