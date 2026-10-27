"""
Raman 数据的标准结构规定为一个元组，(df, metadata)
df 为一个两列的df表格，metadata用于存储与仪器信息等相关的源数据。通常来说metadata并不是很重要，但是在有些计算中可能会用到，这里我们保留了
metadata，方便对处理的数据有更加全面的认识。
"""
from .Horiba import reader_horiba_hr_evolution

__all__ = ["reader_horiba_hr_evolution"]
