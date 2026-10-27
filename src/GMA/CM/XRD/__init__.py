"""
本模块用于处理XRD数据，因为XRD数据通常需要包含两列数据，所以数据的标准接口为一个两列的df表格。数据提取与数据处理解耦，本模块也包含XRD数据可视化的
代码。
"""
from .Dloader.Bruker import reader_d8advance

__all__ = ["reader_d8advance"]