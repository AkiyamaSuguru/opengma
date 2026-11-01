# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""XPS 分析：数据范围、拟合质量、分峰峰位 / 峰高 / 面积 / 面积占比。"""
import math

import numpy as np
import pytest

from GMA import XPSAnalyzer
from GMA.CM.common.metrics import spectrum_metrics
from GMA.CM.Raman.schema import AXIS as RAMAN_AXIS

GAUSS_AREA = math.sqrt(math.pi / (4 * math.log(2)))  # 高斯峰面积 = 峰高 × 半高宽 × 该系数


def test_fitted_element_metrics(c1s):
    m = XPSAnalyzer().metrics(c1s)
    assert m.fitted and m.point_count == len(c1s)
    assert (m.x_min, m.x_max) == pytest.approx((280.0, 291.95))
    assert m.r_squared > 0.99
    assert m.rmse > 0 and m.mae > 0 and m.mae <= m.rmse
    comps = {c.name: c for c in m.components}
    assert list(comps) == ["C-Si", "C-C"]
    assert comps["C-Si"].position == pytest.approx(283.3)
    assert comps["C-C"].position == pytest.approx(284.8)
    # 峰高含背景：分峰曲线在峰位处的值
    i = int(np.argmin(np.abs(c1s["Binding Energy (eV)"] - 283.3)))
    assert comps["C-Si"].height == pytest.approx(c1s["C-Si"].iloc[i])
    assert comps["C-Si"].area == pytest.approx(8000 * 1.0 * GAUSS_AREA, rel=0.01)
    assert comps["C-C"].area == pytest.approx(3000 * 1.3 * GAUSS_AREA, rel=0.01)
    assert sum(c.area_fraction for c in m.components) == pytest.approx(1.0)
    assert m.max_intensity_position == pytest.approx(283.3, abs=0.2)


def test_relative_mode_gives_same_components(c1s):
    relative = c1s.copy()
    for col in ("C-Si", "C-C"):
        relative[col] = c1s[col] - c1s["Background"]
    absolute = XPSAnalyzer().metrics(c1s, component_mode="absolute")
    rel = XPSAnalyzer().metrics(relative, component_mode="relative")
    for a, b in zip(absolute.components, rel.components, strict=True):
        assert (a.position, a.height, a.area) == pytest.approx((b.position, b.height, b.area))


def test_unfitted_spectra(f1s_raw, surveys):
    analyzer = XPSAnalyzer()
    m = analyzer.metrics(f1s_raw)
    assert not m.fitted and m.rmse is None and m.r_squared is None and m.components == ()
    assert m.max_intensity_position == pytest.approx(685.2, abs=0.2)
    s = analyzer.survey_metrics(surveys["As-deposited"])
    assert s.max_intensity_position == pytest.approx(284.8, abs=1)


def test_component_table(c1s):
    analyzer = XPSAnalyzer()
    table = analyzer.component_table(analyzer.metrics(c1s))
    assert table.columns.tolist() == ["Component", "Position (eV)", "Height", "Area", "Area fraction (%)"]
    assert table["Area fraction (%)"].sum() == pytest.approx(100)


def test_common_metrics_work_for_raman(raman_fit):
    m = spectrum_metrics(raman_fit, RAMAN_AXIS)
    assert [c.name for c in m.components] == ["D", "G"]
    assert m.components[1].position == pytest.approx(1585, abs=2)


def test_invalid_mode(c1s):
    with pytest.raises(ValueError, match="component_mode"):
        XPSAnalyzer().metrics(c1s, component_mode="other")
