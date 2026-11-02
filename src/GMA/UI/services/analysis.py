# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
分析：调用 GMA 的分析接口，整理成检查器“分析”页上的表格，以及复制、导出用的文字和文件（方案 7.3）。

只用标准数据结构中已有的列计算；未拟合的谱只有“谱图”一项。面积占比是面积之比，不是原子百分比。
"""
from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

from ...CM.common.metrics import SpectrumMetrics, spectrum_metrics
from ...CM.XPS import XPSAnalyzer
from ...project import Record
from ..strings import S


def metrics_for(record: Record) -> SpectrumMetrics:
    df = record.to_dataframe()
    if record.method == "XPS":
        analyzer = XPSAnalyzer()
        if record.kind == "survey":
            return analyzer.survey_metrics(df)
        return analyzer.metrics(df, component_mode=record.component_mode)
    return spectrum_metrics(df, record.spec.axis, record.component_mode)


def fmt(value, decimals: int = 2) -> str:
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        return "—"
    return f"{value:,.{decimals}f}".replace(",", " ")


def quality_rows(m: SpectrumMetrics) -> list[tuple[str, str]]:
    """拟合质量：R²、RMSE、MAE（未拟合时为空）。"""
    if not m.fitted:
        return []
    return [("R²", fmt(m.r_squared, 4)), ("RMSE", fmt(m.rmse, 1)), ("MAE", fmt(m.mae, 1))]


def spectrum_rows(m: SpectrumMetrics, record: Record) -> list[tuple[str, str]]:
    unit = record.spec.x_unit
    return [
        (S.X_RANGE_OF.format(axis=S.AXIS_NAMES.get(record.method, S.X_AXIS)),
         f"{fmt(m.x_min)} – {fmt(m.x_max)} {unit}"),
        (S.POINT_COUNT, f"{m.point_count:,}".replace(",", " ")),
        (S.MAX_POSITION, f"{fmt(m.max_intensity_position)} {unit}"),
    ]


def component_rows(m: SpectrumMetrics) -> list[dict]:
    """分峰：峰位、峰高、面积、面积占比（%）。"""
    return [{"name": c.name, "position": fmt(c.position), "height": fmt(c.height, 0), "area": fmt(c.area, 0),
             "fraction": fmt(100 * c.area_fraction, 1) + "%" if math.isfinite(c.area_fraction) else "—",
             "fraction_value": c.area_fraction if math.isfinite(c.area_fraction) else 0.0}
            for c in m.components]


def metrics_frame(record: Record, m: SpectrumMetrics) -> pd.DataFrame:
    """一条谱图的分析结果，一行一个分峰；未拟合时只有一行谱图信息。数值不取整，方便再计算。"""
    base = {"Sample": record.sample, "Spectrum": record.name, "Points": m.point_count,
            f"Min ({record.spec.x_unit})": m.x_min, f"Max ({record.spec.x_unit})": m.x_max,
            f"Max intensity position ({record.spec.x_unit})": m.max_intensity_position}
    if m.fitted:
        base.update({"R2": m.r_squared, "RMSE": m.rmse, "MAE": m.mae, "Component mode": record.component_mode})
    if not m.components:
        return pd.DataFrame([base])
    rows = []
    for c in m.components:
        rows.append({**base, "Component": c.name, f"Position ({record.spec.x_unit})": c.position,
                     "Height": c.height, "Area": c.area, "Area fraction (%)": 100 * c.area_fraction})
    return pd.DataFrame(rows)


def table_text(record: Record, m: SpectrumMetrics) -> str:
    """复制表格：制表符分隔，可以直接粘贴到 Excel。"""
    return metrics_frame(record, m).to_csv(sep="\t", index=False, float_format="%.6g")


def export(records: list[Record], path, fmt: str) -> Path:
    """把若干谱图的分析结果导出为 CSV 或 Excel（一张表，一行一个分峰）。"""
    frames = [metrics_frame(r, metrics_for(r)) for r in records]
    table = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    path = Path(path)
    if fmt == "xlsx":
        path = path.with_suffix(".xlsx")
        table.to_excel(path, index=False, sheet_name="Analysis")
    else:
        path = path.with_suffix(".csv")
        table.to_csv(path, index=False, encoding="utf-8-sig")
    return path
