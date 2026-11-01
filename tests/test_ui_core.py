# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""界面中不需要窗口的部分：设置、界面状态、模块注册表、数据检查、文字、颜色、窗口尺寸。"""
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from GMA.project import CleanNote, Project, Record, load_project
from GMA.UI import theme
from GMA.UI.screen import window_size
from GMA.UI.services.checks import INFO, WARNING, data_issues
from GMA.UI.services.text import local_time, short_path, when
from GMA.UI.session import ProjectSession, make_ui_state, read_ui_state
from GMA.UI.settings import Settings, load_settings, save_settings
from GMA.UI.strings import S
from GMA.UI.views import registry


# ============================================================
# 设置
# ============================================================
def test_settings_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENGMA_HOME", str(tmp_path / "home"))
    settings = load_settings()  # 文件不存在：默认值
    assert settings.theme_mode == "system" and settings.primary == "#146C7E" and settings.recent == []
    settings.theme_mode, settings.primary = "dark", "#2C4F8C"
    settings.add_recent(tmp_path / "a.nc", ["xps", "xrd"], "xrd")
    path = save_settings(settings)
    assert path == tmp_path / "home" / "settings.json"
    again = load_settings()
    assert again.theme_mode == "dark" and again.primary == "#2C4F8C"
    assert again.recent[0].modules == ["xps", "xrd"] and again.recent[0].active == "xrd"


def test_settings_ignore_bad_values(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({
        "theme_mode": "purple", "primary": "teal", "recent_limit": -3, "dpi": "600", "remember_size": "yes",
        "launcher_ratio": [0.5, 2], "work_area": [1470, 937], "readers": {"XPS": "Avantage", "XRD": 5},
        "unknown": 1, "recent": [{"path": "/x.nc"}, {"nopath": 1}, "bad"],
    }), encoding="utf-8")
    s = load_settings(path)
    assert (s.theme_mode, s.primary, s.recent_limit, s.dpi, s.remember_size) == ("system", "#146C7E", 5, 600, True)
    assert s.launcher_ratio == [0.42, 0.52] and s.work_area == [1470.0, 937.0]
    assert s.readers["XRD"] == "D8 Advance" and [r.path for r in s.recent] == ["/x.nc"]
    path.write_text("{ broken", encoding="utf-8")
    assert load_settings(path) == Settings()


def test_recent_projects(tmp_path):
    s = Settings(recent_limit=3)
    for i in range(5):
        s.add_recent(tmp_path / f"{i}.nc", ["xps"])
    assert [Path(r.path).name for r in s.recent] == ["4.nc", "3.nc", "2.nc"]
    s.add_recent(tmp_path / "2.nc", ["raman"], "raman")  # 已有的项目移到最前面，不重复
    assert [Path(r.path).name for r in s.recent] == ["2.nc", "4.nc", "3.nc"]
    assert s.recent[0].modules == ["raman"] and not s.recent[0].exists
    s.remove_recent(s.recent[1].path)
    assert [Path(r.path).name for r in s.recent] == ["2.nc", "3.nc"]


# ============================================================
# 界面状态与项目
# ============================================================
def test_ui_state():
    state = make_ui_state([{"module": "xps", "state": {"sample": "B1"}}, {"module": "gone", "state": {}},
                           {"module": "xrd"}], active=3)
    tabs, active = read_ui_state(state, {"xps", "xrd"})
    assert tabs == [{"module": "xps", "state": {"sample": "B1"}}, {"module": "xrd", "state": {}}]
    assert active == 0  # 原来指向第 3 个标签，去掉不认识的模块后超出范围，退回“项目”标签
    assert read_ui_state({}, {"xps"}) == ([], 0)
    assert read_ui_state({"tabs": [{"module": "xps"}], "active": True}, {"xps"})[1] == 0


def test_session_save_and_reopen(tmp_path, c1s):
    session = ProjectSession()
    assert session.name == S.UNTITLED and session.path is None and not session.dirty
    events = []
    session.subscribe(events.append)
    session.project.add_record(Record.from_dataframe(c1s, "XPS", "C1s", "B1"))
    assert session.dirty
    ui_state = make_ui_state([{"module": "xps", "state": {}}], 1)
    saved = session.save(tmp_path / "腐蚀实验", ui_state)
    assert saved.name == "腐蚀实验.nc" and session.name == "腐蚀实验"  # 未命名项目用文件名作项目名
    assert events == ["saved"] and not session.dirty
    reopened = ProjectSession.open(saved)
    assert reopened.project.ui_state == ui_state and len(reopened.project) == 1
    reopened.rename("SiC 腐蚀")
    assert reopened.dirty and reopened.name == "SiC 腐蚀"


def test_add_field():
    project = Project()
    project.add_sample("B1")
    project.dirty = False
    assert project.add_field("  沉积温度 ") == "沉积温度"
    assert project.sample_fields == ["沉积温度"] and project.dirty
    project.add_field("沉积温度")
    assert project.sample_fields == ["沉积温度"]
    project.set_sample_info("B1", "状态", "沉积态")
    assert project.sample_fields == ["沉积温度", "状态"] and project.samples["B1"].info == {"状态": "沉积态"}


# ============================================================
# 模块注册表与数据检查
# ============================================================
def test_registry():
    keys = [m.key for m in registry.MODULES]
    assert len(keys) == len(set(keys))
    assert [registry.for_method(m).key for m in ("XPS", "Raman", "XRD")] == ["xps", "raman", "xrd"]
    groups = registry.by_category()
    assert [m.key for m in groups[registry.METHOD]] == ["xps", "raman", "xrd"]
    assert all(m.planned for m in groups[registry.TOOL])
    assert all((Path(theme.__file__).parent / "assets" / m.icon_src).is_file() for m in registry.MODULES)


def test_data_issues(c1s):
    project = Project()
    renamed = c1s.rename(columns={"C-C": "C-C/C-H"})
    project.add_record(Record.from_dataframe(c1s, "XPS", "C1s", "B1"))
    project.add_record(Record.from_dataframe(c1s, "XPS", "C1s", "B2"))
    project.add_record(Record.from_dataframe(renamed, "XPS", "C1s", "B3",
                                             clean_notes=[CleanNote("dropped_rows", {"rows": [3, 4], "count": 2})]))
    issues = data_issues(project)
    assert [i.level for i in issues] == [INFO, WARNING]
    assert issues[0].title == "B3 / XPS / C1s" and "2 行" in issues[0].text
    assert issues[1].title == "C1s" and issues[1].text == "3 个样品的分峰名不一致：C-C ／ C-C/C-H"
    assert len(issues[1].record_ids) == 3
    assert data_issues(Project()) == []


def test_demo_project(tmp_path):
    """scripts/ui_p2/demo_project.py 生成的演示项目能保存、打开。"""
    import importlib.util

    script = Path(__file__).parents[1] / "scripts" / "ui_p2" / "demo_project.py"
    spec = importlib.util.spec_from_file_location("demo_project", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    from GMA.project import save_project

    project = load_project(save_project(module.build(), tmp_path / "demo.nc"))
    assert len(project.samples) == 3 and project.methods() == ["XPS", "Raman", "XRD"]
    assert [i.level for i in data_issues(project)] == [INFO, WARNING]


# ============================================================
# 文字、颜色、窗口尺寸
# ============================================================
def test_when_and_short_path(tmp_path):
    now = datetime(2026, 11, 1, 17, 30).astimezone()  # 本地时间
    assert when("2026-11-01T09:05:00", now) == "今天 09:05"
    assert when("2026-10-31T21:14:00", now) == "昨天 21:14"
    assert when("2026-10-28T10:00:00", now) == "10月28日"
    assert when("2025-10-28T10:00:00", now) == "2025年10月28日"
    assert when("not a date", now) == "" and local_time(None) is None
    # 项目文件中的时间是 UTC，显示前换成本地时间
    utc = local_time("2026-11-01T09:05:00+00:00")
    assert utc == datetime(2026, 11, 1, 9, 5, tzinfo=UTC) and utc.utcoffset() == utc.astimezone().utcoffset()
    assert short_path(tmp_path / "a" / "b.nc", home=tmp_path) == str(Path("~") / "a" / "b.nc")
    assert short_path("/elsewhere/b.nc", home=tmp_path) == str(Path("/elsewhere/b.nc"))


def test_palette():
    light, dark = theme.palette(), theme.palette(dark=True)
    assert (light.primary, light.primary_weak, light.bg, light.panel) == ("#146C7E", "#E2F0F3", "#F4F6F8", "#FFFFFF")
    assert (dark.primary, dark.primary_weak, dark.bg, dark.panel) == ("#4FB3C4", "#12343B", "#0F1418", "#161C21")
    custom = theme.palette("#A2552B", dark=True)
    assert theme.is_hex(custom.primary) and theme.is_hex(custom.primary_weak) and custom.primary != "#A2552B"
    assert theme.palette("not a color").primary == "#146C7E"
    assert theme.on_color("#146C7E") == "#FFFFFF" and theme.on_color("#FBBF24") == "#1B2730"
    assert theme.mix("#000000", "#FFFFFF", 0.5) == "#808080"


@pytest.mark.parametrize(("area", "ratio", "limits", "expected"), [
    ((1470, 937), (0.42, 0.52), ((560, 420), (960, 700)), (617, 487)),
    ((1470, 937), (0.85, 0.90), ((960, 640), None), (1250, 843)),
    ((2560, 1400), (0.42, 0.52), ((560, 420), (960, 700)), (960, 700)),   # 大屏：不超过上限
    ((900, 560), (0.85, 0.90), ((960, 640), None), (900, 560)),          # 小屏：不超过可用区域
])
def test_window_size(area, ratio, limits, expected):
    assert window_size(area, ratio, *limits) == expected
