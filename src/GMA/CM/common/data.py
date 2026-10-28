# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
谱图数据的检查与整理，各表征方法共用。

标准数据结构（DataFrame 的列名）：
- 谱线：[横轴列, "Intensity"]，横轴列由各表征方法的 schema.py 规定；
- 拟合谱：[横轴列, "Intensity", "Fitting Curve", 分峰列..., "Background"]，
  分峰列可以为 0 个。
"""
from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd

INTENSITY_COL = "Intensity"
FIT_COL = "Fitting Curve"
BG_COL = "Background"

COMPONENT_MODES = ("absolute", "relative")


# ============================================================
# 输入与列检查
# ============================================================
def as_mapping(data) -> dict:
    """把输入统一成 {标签: DataFrame}；传入单个 DataFrame 时标签为空字符串。"""
    if isinstance(data, pd.DataFrame):
        return {"": data}
    if not isinstance(data, Mapping):
        raise TypeError(
            "data must be a pandas DataFrame or a mapping such as "
            "dict[str, pd.DataFrame]."
        )
    if not data:
        raise ValueError("data cannot be empty.")

    invalid = {
        key: type(df).__name__
        for key, df in data.items()
        if not isinstance(df, pd.DataFrame)
    }
    if invalid:
        raise TypeError(
            "All values in data must be pandas.DataFrame objects. "
            f"Invalid entries: {invalid}"
        )
    return dict(data)


def require_columns(df: pd.DataFrame, columns) -> None:
    """检查 df 是否包含所有必需列，缺少时报错并列出缺少的列。"""
    missing = [col for col in columns if col not in df.columns]
    if missing:
        raise ValueError(
            f"Missing required columns: {missing}\n"
            f"Required columns are: {list(columns)}\n"
            f"Current columns are: {list(df.columns)}"
        )


def line_columns(axis) -> list:
    """谱线的必需列：[横轴列, "Intensity"]。"""
    return [axis.column, INTENSITY_COL]


def fit_columns(axis) -> list:
    """拟合谱的必需列：[横轴列, "Intensity", "Fitting Curve", "Background"]。"""
    return [axis.column, INTENSITY_COL, FIT_COL, BG_COL]


def detect_fit_type(df: pd.DataFrame, axis) -> str:
    """
    判断谱图类型。

    Returns
    -------
    "raw" : 只有谱线，未拟合；
    "fit" : 有 Fitting Curve 和 Background，可包含或不包含分峰列。
    """
    require_columns(df, line_columns(axis))

    has_fit = FIT_COL in df.columns
    has_bg = BG_COL in df.columns
    if has_fit and has_bg:
        return "fit"
    if not has_fit and not has_bg:
        return "raw"

    missing = [col for col in (FIT_COL, BG_COL) if col not in df.columns]
    raise ValueError(
        "Incomplete fitted-spectrum data. "
        f"Missing columns: {missing}. "
        f"'{FIT_COL}' and '{BG_COL}' must appear together."
    )


# ============================================================
# 整理数据
# ============================================================
def clean_spectrum(df: pd.DataFrame, axis, fitted: bool = False) -> pd.DataFrame:
    """检查必需列，转成数值，去掉必需列为空的行，并按横轴升序排列。"""
    columns = fit_columns(axis) if fitted else line_columns(axis)
    require_columns(df, columns)
    df = df.apply(pd.to_numeric, errors="coerce")
    df = df.dropna(subset=columns).sort_values(axis.column, ignore_index=True)
    if df.empty:
        raise ValueError("No valid numeric data to plot.")
    return df


def prepare_spectrum(df: pd.DataFrame, axis, normalize: bool = False):
    """整理谱线，返回 (横轴, 强度) 两个数组；normalize=True 时强度除以最大值。"""
    df = clean_spectrum(df, axis)
    x = df[axis.column].to_numpy(dtype=float)
    intensity = df[INTENSITY_COL].to_numpy(dtype=float)
    if normalize:
        intensity = intensity / intensity.max()
    return x, intensity


def component_columns(df: pd.DataFrame, axis) -> list:
    """标准列以外、含有数值的列都视为分峰列（df 需先经过 clean_spectrum）。"""
    standard = fit_columns(axis)
    return [
        col for col in df.columns
        if col not in standard and df[col].notna().any()
    ]


def check_component_mode(component_mode: str) -> None:
    if component_mode not in COMPONENT_MODES:
        raise ValueError(
            f"component_mode must be one of {COMPONENT_MODES}, "
            f"got {component_mode!r}."
        )


def component_curve(df: pd.DataFrame, col, component_mode: str) -> np.ndarray:
    """
    返回分峰在图上的强度曲线。

    "absolute"：分峰列本身已经包含背景；
    "relative"：分峰列为扣背景后的峰强度，绘图时加上 Background。
    """
    values = df[col].to_numpy(dtype=float)
    if component_mode == "relative":
        return values + df[BG_COL].to_numpy(dtype=float)
    return values


# ============================================================
# 标峰参数
# ============================================================
def check_peaks(peaks) -> None:
    if not isinstance(peaks, Mapping):
        raise TypeError(
            "peaks must be a dict such as {'C 1s': 284.8, 'O 1s': 532.0}."
        )


def peaks_by_spectrum(peaks, keys) -> dict:
    """
    把要标注的峰统一成 {样品名: {标签: 位置}}。

    peaks 可以是：
    - 所有谱共用：{"C 1s": 284.8, "O 1s": 532.0}；
    - 按样品分别写：{"As-deposited": {"C 1s": 284.8}, "Corroded": {"F 1s": 685.0}}，
      没写到的样品不标注。
    """
    keys = list(keys)
    if not peaks:
        return {key: {} for key in keys}
    check_peaks(peaks)

    nested = [isinstance(value, Mapping) for value in peaks.values()]
    if not any(nested):
        return {key: dict(peaks) for key in keys}
    if not all(nested):
        raise ValueError(
            "peaks must be either {label: position} shared by all spectra, "
            "or {sample: {label: position}} for each spectrum."
        )

    unknown = [key for key in peaks if key not in keys]
    if unknown:
        raise ValueError(f"peaks has unknown samples: {unknown}. Samples are: {keys}")
    return {key: dict(peaks.get(key, {})) for key in keys}


def merge_peaks(peaks_per_key: dict) -> dict:
    """多条谱画在同一张图时，把各样品要标注的峰合并在一起。"""
    merged = {}
    for key_peaks in peaks_per_key.values():
        merged.update(key_peaks)
    return merged
