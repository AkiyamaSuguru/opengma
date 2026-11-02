# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
第二期（P5）中不需要窗口的部分：计算工具页的状态与计算、复制为代码、导出、出版图，
自动备份、项目锁、新建窗口的命令，以及界面文字。
"""
import json
import os
import re
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from GMA.project import Project, Record, save_project
from GMA.SC.Salts import salt_masses
from GMA.UI import strings, theme
from GMA.UI.services import autosave, codegen, figures, launch, locks, tools
from GMA.UI.services.figures import FigureOptions
from GMA.UI.services.text import field_text, parse_number, sci
from GMA.UI.session import ProjectSession
from GMA.UI.settings import Settings, clean_presets
from GMA.UI.views import registry
from GMA.UI.views.salt_view import SaltView
from GMA.UI.views.srim_view import SRIMView
from GMA.UI.workspace import VIEW_CLASSES

DATA = Path(__file__).parent / "data" / "srim"


def stub_app(settings: Settings | None = None):
    """计算工具页的计算不需要窗口：只用到设置、配色和页面宽度。"""
    return SimpleNamespace(settings=settings or Settings(), p=theme.palette(), page=SimpleNamespace(width=1400))


def srim_state(**extra) -> dict:
    files = {key: {"name": name, "path": str(DATA / name), "text": (DATA / name).read_text(encoding="latin-1")}
             for key, name in (("vacancy", "VACANCY.txt"), ("range", "RANGE.txt"))}
    return {**files, **extra}


def srim_view(state: dict) -> SRIMView:
    session = ProjectSession()
    return SRIMView(stub_app(), session, None, registry.get("srim"), state)


# ============================================================
# 注册表与文字
# ============================================================
def test_every_module_has_a_page():
    assert {m.key for m in registry.available()} <= set(VIEW_CLASSES)
    assert registry.get("srim").category == registry.TOOL and registry.get("salt").method is None


def test_strings_are_unique():
    """同一个名字定义两次时，后面的会悄悄覆盖前面的（P5 中出现过一次）。"""
    text = Path(strings.__file__).read_text(encoding="utf-8")
    names = re.findall(r"^    ([A-Z][A-Z0-9_]+)\s*(?::[^=\n]+)?=", text, re.MULTILINE)
    assert [n for n, c in Counter(names).items() if c > 1] == []


def test_number_text():
    assert parse_number("1e16") == 1e16 and parse_number("1,5") == 1.5 and parse_number("2.5×10^3") == 2500
    with pytest.raises(ValueError):
        parse_number("abc")
    assert sci(3.6e15) == "3.60e15" and sci(10.649) == "10.65" and sci(1.2e-5) == "1.20e-5" and sci(None) == "—"
    assert field_text(1e16) == "1e16" and field_text(100.0) == "100" and field_text(None) == ""


# ============================================================
# SRIM 页
# ============================================================
def test_srim_view_state_roundtrip():
    view = srim_view(srim_state(fluence=2e16, unit="um", densities=[1e23]))
    view.compute()
    assert view.profile is not None and view.used_ions is not None and view.warning == ""
    assert view.profile.attrs["fluence"] == 2e16 and view.densities() == [1e23]
    state = json.loads(json.dumps(view.state()))   # 标签状态随项目保存：必须能写成 JSON
    again = srim_view(state)
    again.compute()
    assert again.vacancy is not None and again.st["unit"] == "um"
    assert (again.profile["dpa"] == view.profile["dpa"]).all()
    # 束流 × 时间
    flux = srim_view(srim_state(mode="flux", flux=1e12, hours=2.0))
    assert flux.inputs().total_fluence == pytest.approx(7.2e15)
    # 状态中不合法的值用默认值；文件内容损坏时当作没有读取
    bad = srim_view({"vacancy": {"name": "x", "text": "not srim"}, "fluence": "abc", "unit": "mm"})
    assert bad.vacancy is None and bad.st["vacancy"] is None and bad.st["fluence"] == 1e16 and bad.st["unit"] == "nm"


def test_srim_mismatch_and_only_range():
    other = (DATA / "VACANCY.txt").read_text(encoding="latin-1").replace("Ion    = Ar   Energy = 2000 keV",
                                                                          "Ion    = Kr   Energy = 4000 keV")
    view = srim_view(srim_state(vacancy={"name": "VACANCY.txt", "path": "", "text": other}))
    view.compute()   # 不是同一次计算：只算 dpa，并提示
    assert view.used_ions is None and view.warning == strings.S.SRIM_MISMATCH and "Ions (at.%)" not in view.profile
    state = srim_state()
    state["vacancy"] = None
    only = srim_view(state)
    only.compute()
    assert only.base is only.ions and tools.has_columns(only.profile) == (False, True)


def test_srim_code_runs(tmp_path):
    view = srim_view(srim_state(window=[100.0, 1500.0], densities=[1.1e23]))
    view.compute()
    code = tools.srim_code(view.inputs(), tuple(view.st["window"]))
    namespace: dict = {}
    exec(compile(code, "copied.py", "exec"), namespace)  # noqa: S102 - 运行生成的代码，检查它能独立运行
    assert namespace["dpa_peak"] == pytest.approx(view.profile["dpa"].max())
    assert "densities=[1.1e23]" in code and "fluence=1e16" in code


def test_srim_figure_and_code(tmp_path):
    view = srim_view(srim_state())
    view.compute()
    options = FigureOptions(dpi=80)
    view.st["figure_parts"] = {"damage": True, "ions": True, "elements": False}
    request = view.figure_request(options)
    assert request.kwargs["depth_unit"] == "nm" and request.kwargs["concentration"] is True
    assert figures.render(request, options, fmt="png").data[:4] == b"\x89PNG"
    assert codegen.file_stem(request) == "SRIM_Ar_2000keV"
    code = codegen.figure_code(request, options)
    assert "from GMA.SC.SRIM import SRIMPlotter" in code and "plotter.plot_profile_static(" in code
    cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        exec(compile(code, "copied.py", "exec"), {})  # noqa: S102
    finally:
        os.chdir(cwd)
    assert (tmp_path / "SRIM_Ar_2000keV.png").is_file()
    # 两种曲线都关掉时至少画一种
    view.st["figure_parts"] = {"damage": False, "ions": False, "elements": False}
    assert view.figure_parts()["damage"] and view.figure_parts()["ions"]


def test_export_profile(tmp_path):
    view = srim_view(srim_state(unit="um"))
    view.compute()
    xlsx = tools.export_profile(view.profile, tmp_path / "srim.xlsx", "um", view.info_rows())
    sheets = pd.read_excel(xlsx, sheet_name=None)
    profile, info = sheets["Profile"], sheets[strings.S.SRIM_INFO_SHEET]
    assert profile.columns[0] == "Depth (um)" and profile["Depth (um)"].iloc[-1] == pytest.approx(2.0)
    assert "dpa" in profile and "Ions (at.%)" in profile
    assert dict(zip(info.iloc[:, 0], info.iloc[:, 1], strict=True))["Fluence (ions/cm2)"] == "1e+16"
    csv = tools.export_profile(view.profile, tmp_path / "srim.csv", "A", [])
    assert csv.read_bytes().startswith(b"\xef\xbb\xbf") and pd.read_csv(csv).columns[0] == "Depth (A)"


# ============================================================
# 熔盐配比页
# ============================================================
def test_salt_rows_and_table():
    rows = [{"salt": "LiF", "amount": "46.5", "molar_mass": ""}, {"salt": "", "amount": "", "molar_mass": ""},
            {"salt": "NaF", "amount": "11.5", "molar_mass": ""}, {"salt": "KF", "amount": "42", "molar_mass": ""},
            {"salt": "⁷LiF", "amount": "0", "molar_mass": "26.0"}]
    composition, overrides, errors = tools.salt_rows(rows)
    assert errors == [] and overrides == {"⁷LiF": 26.0} and composition[0] == ("LiF", 46.5)
    bad, _, errors = tools.salt_rows([{"salt": "7LiF", "amount": "1"}, {"salt": "KF", "amount": "x"},
                                      {"salt": "KF", "amount": "1"}, {"salt": "KF", "amount": "1"}])
    assert bad == [("KF", 1.0)] and len(errors) == 3 and errors[0].startswith(strings.S.SALT_ERROR_ROW.format(
        row=1, error=""))
    table = salt_masses(composition, 50.0, molar_masses=overrides)
    text = tools.salt_table_text(table)
    lines = text.splitlines()
    assert len(lines) == 2 + len(composition) and lines[-1].split("\t")[-1] == "50.0000"
    namespace: dict = {}
    exec(compile(tools.salt_code(composition, 50.0, overrides), "copied.py", "exec"), namespace)  # noqa: S102
    assert namespace["table"].equals(table)


def test_salt_view_presets(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENGMA_HOME", str(tmp_path))
    view = SaltView(stub_app(), ProjectSession(), None, registry.get("salt"), {})
    view.compute()
    assert view.table is not None and view.st["preset"] == "FLiNaK" and not view.is_modified()
    view.st["rows"][0]["amount"] = "50"
    assert view.is_modified()
    view.st["rows"][1]["salt"] = "Xx"
    view.compute()
    assert view.table is None and view.errors   # 有填错的行时不给出结果
    # 设置中的预设：None 为内置预设
    settings = Settings(salt_presets=[{"name": "Mine", "salts": [["NaCl", 1.0, None]]}])
    mine = SaltView(stub_app(settings), ProjectSession(), None, registry.get("salt"), {"preset": "Mine"})
    assert [p["name"] for p in mine.presets()] == ["Mine"] and mine.preset("FLiNaK") is None
    assert clean_presets([{"name": "A", "salts": [["LiF", 1, None]]}, {"name": "A", "salts": [["KF", 1, None]]},
                          {"name": "", "salts": []}, {"name": "B", "salts": [["x", True, None]]}]) == \
        [{"name": "A", "salts": [["LiF", 1.0, None]]}]
    assert Settings.from_dict({"salt_presets": "bad"}).salt_presets is None


# ============================================================
# 自动备份、项目锁、新建窗口
# ============================================================
def test_autosave(tmp_path, monkeypatch, c1s):
    monkeypatch.setenv("OPENGMA_HOME", str(tmp_path / "home"))
    project = Project("腐蚀")
    project.add_record(Record.from_dataframe(c1s, "XPS", "C1s", "B1"))
    source = save_project(project, tmp_path / "腐蚀.nc")
    project.ui_state = {"version": 1, "tabs": [{"module": "xps", "state": {}}], "active": 1}
    project.dirty = True
    from GMA.project import project_to_datatree
    autosave.write_backup("k1", project_to_datatree(project), name=project.name, source=source)
    assert project.dirty and project.file_path == source   # 写备份不改变项目的状态
    assert autosave.list_backups() == []   # 刚有心跳：程序还在运行，不提示恢复
    backup = autosave.list_backups(orphaned_only=False)[0]
    assert (backup.key, backup.name, backup.source) == ("k1", "腐蚀", str(source))
    assert backup.orphaned(datetime.now(UTC) + timedelta(seconds=autosave.STALE + 5))
    meta = json.loads((tmp_path / "home" / "autosave" / "k1.json").read_text(encoding="utf-8"))
    meta["alive_at"] = (datetime.now(UTC) - timedelta(minutes=10)).isoformat()
    (tmp_path / "home" / "autosave" / "k1.json").write_text(json.dumps(meta), encoding="utf-8")
    [orphan] = autosave.list_backups()
    restored = autosave.open_backup(orphan)
    assert restored.dirty and restored.file_path == source and restored.ui_state["active"] == 1
    assert len(restored.records) == 1
    autosave.heartbeat("k1")
    assert autosave.list_backups() == []   # 又有了心跳
    autosave.remove_backup("k1")
    assert autosave.list_backups(orphaned_only=False) == []


def test_project_lock(tmp_path):
    path = tmp_path / "项目.nc"
    assert locks.read_lock(path, "me") is None and locks.acquire(path, "me")
    assert locks.lock_path(path).name == ".项目.nc.lock"
    assert locks.read_lock(path, "me") is None   # 自己的锁
    info = locks.read_lock(path, "other")
    assert info["token"] == "me" and info["pid"] == os.getpid()
    locks.release(path, "other")                 # 别人的锁不动
    assert locks.lock_path(path).exists()
    data = json.loads(locks.lock_path(path).read_text(encoding="utf-8"))
    data["alive_at"] = (datetime.now(UTC) - timedelta(minutes=10)).isoformat()
    locks.lock_path(path).write_text(json.dumps(data), encoding="utf-8")
    assert locks.read_lock(path, "other") is None   # 没有心跳：程序已经退出，锁失效
    locks.heartbeat(path, "me")
    assert locks.read_lock(path, "other") is not None
    locks.heartbeat(path, "other")   # 锁是别人的：不动
    assert json.loads(locks.lock_path(path).read_text(encoding="utf-8"))["token"] == "me"
    locks.release(path, "me")
    assert not locks.lock_path(path).exists()
    assert not locks.acquire(tmp_path / "missing" / "x.nc", "me")   # 写不了时返回 False，不抛出异常


def test_new_window_command(tmp_path, monkeypatch):
    monkeypatch.delenv("FLET_PLATFORM", raising=False)
    assert launch.new_window_command() == [sys.executable, "-m", "GMA.UI"]
    monkeypatch.setenv("FLET_PLATFORM", "macos")   # 打包的程序：再运行一次程序本身
    program = tmp_path / "OpenGMA"
    program.write_text("", encoding="utf-8")
    monkeypatch.setattr(sys, "executable", str(program))
    assert launch.new_window_command() == [str(program.resolve())]
    monkeypatch.setenv(launch.NEW_WINDOW_ENV, "1")
    assert launch.is_new_window() and not launch.is_new_window()   # 读过之后清除


# ============================================================
# 英文界面
# ============================================================
def placeholders(text: str) -> set[str]:
    return {m.group(1) for m in re.finditer(r"\{(\w*)(?:[:!][^}]*)?\}", text)}


def test_english_strings_match_chinese():
    """每个中文文字都有英文，模板中的参数相同（缺了参数，format 时会出错或丢掉内容）。"""
    from GMA.UI.strings_en import EN
    text = Path(strings.__file__).read_text(encoding="utf-8")
    names = re.findall(r"^    ([A-Z][A-Z0-9_]+)\s*(?::[^=\n]+)?=", text, re.MULTILINE)
    zh = {name: strings.S.__dict__[name] for name in names}
    assert sorted(set(zh) - set(EN)) == [] and sorted(set(EN) - set(zh)) == []
    for name, value in zh.items():
        en = EN[name]
        assert type(en) is type(value), name
        if isinstance(value, str):
            assert placeholders(en) == placeholders(value), name
        elif isinstance(value, dict):
            assert set(en) == set(value), name
    assert len(EN["MONTHS"]) == 12 and set(strings.LANGUAGES) == {"zh", "en"}


def test_plural_templates():
    """英文的单复数：{n:file|files} 按 n 选词，其他参数照常替换；中文模板不受影响。"""
    text = strings.Text("{n} {n:file|files} in {folder}")
    assert text.format(n=1, folder="a") == "1 file in a" and text.format(n=0, folder="a") == "0 files in a"
    assert text.format(n="1", folder="a") == "1 file in a" and text.format(n="2 000", folder="a") == "2 000 files in a"
    assert strings.Text("{n:it was|they were}").format(n=1) == "it was"
    assert strings.S.IMPORT_N.format(n=1) == "导入 1 个文件"


def test_english_startup(tmp_path):
    """按设置选英文后再导入界面模块：注册表、主题色、默认参数都是英文（在新的进程中试，不影响其他测试）。"""
    import subprocess
    import textwrap
    (tmp_path / "settings.json").write_text(json.dumps({"language": "en"}), encoding="utf-8")
    code = textwrap.dedent("""
        from GMA.UI import strings
        from GMA.UI.settings import load_settings
        assert strings.use(load_settings().language) == 'en'
        from GMA.UI.views import registry
        from GMA.UI import theme
        from GMA.UI.services.text import when
        assert registry.get('salt').title == 'Molten salts', registry.get('salt').title
        assert registry.CATEGORY_TITLES[registry.TOOL] == 'Calculation tools'
        assert theme.PRESETS[0][0] == 'Teal'
        assert when('2025-10-28T09:00:00+00:00').startswith('Oct 28')
        assert strings.S.IMPORT_N.format(n=1) == 'Import 1 file' and strings.S.IMPORT_N.format(n=3) == 'Import 3 files'
        assert strings.S.TABLE_SIZE.format(rows='1 000', cols=1) == '1 000 rows · 1 column'
        import GMA.UI.app
        print('ok')
    """)
    result = subprocess.run([sys.executable, "-c", code], env={**os.environ, "OPENGMA_HOME": str(tmp_path)},
                            capture_output=True, text=True, timeout=120, check=False)
    assert result.returncode == 0 and result.stdout.strip().endswith("ok"), result.stderr


# ============================================================
# 打包
# ============================================================
ROOT = Path(__file__).resolve().parents[1]


def build_script():
    """scripts/build_app.py 不是包的一部分，按文件导入。"""
    import importlib.util
    spec = importlib.util.spec_from_file_location("build_app", ROOT / "scripts" / "build_app.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_packaging_config():
    """flet build 的入口和依赖：入口文件存在；打包的依赖只有运行需要的（不含 marimo 和开发工具）；应用图标齐全。"""
    import tomllib

    from PIL import Image
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    app = data["tool"]["flet"]["app"]
    assert (ROOT / app["path"] / f"{app['module']}.py").is_file()
    names = {re.split(r"[<>=\[ ;]", d, maxsplit=1)[0] for d in data["project"]["dependencies"]}
    assert {"flet", "flet-charts", "numpy", "h5netcdf"} <= names
    assert not names & {"marimo", "flet-cli", "flet-desktop", "flet-web", "pytest"}
    assets = ROOT / "src" / "GMA" / "UI" / "assets"
    for name in ("icon.png", "icon_macos.png"):
        image = Image.open(assets / name)
        assert image.size == (1024, 1024) and image.mode == "RGBA" and image.getpixel((0, 0))[3] == 0
    assert build_script().artifact_name() == data["tool"]["flet"]["artifact"] == "OpenGMA"


def test_smoke_checks():
    """打包后的自检在源码环境中也能通过（GitHub Actions 中在打包好的程序里运行同样的检查）。"""
    from GMA.UI.services import smoke
    result = smoke.run_checks()
    assert result["ok"], result
    assert set(result["checks"]) == {"project", "excel", "figure", "srim", "salt"}


def test_build_script_finds_program(tmp_path, monkeypatch):
    """自检时找到打包好的程序：Linux 的可执行文件、Windows 的 .exe、Mac 的 .app（按 Info.plist）。"""
    import plistlib
    script = build_script()
    monkeypatch.setattr(script, "output_dir", lambda target: tmp_path / "build" / target)
    linux = tmp_path / "build" / "linux"
    (linux / "lib").mkdir(parents=True)
    (linux / "lib" / "libapp.so").write_bytes(b"")
    program = linux / "OpenGMA"
    program.write_bytes(b"")
    program.chmod(0o755)
    assert script.executable("linux") == program
    windows = tmp_path / "build" / "windows"
    windows.mkdir(parents=True)
    (windows / "flutter_windows.dll").write_bytes(b"")
    (windows / "OpenGMA.exe").write_bytes(b"")
    assert script.executable("windows") == windows / "OpenGMA.exe"
    bundle = tmp_path / "build" / "macos" / "OpenGMA.app" / "Contents"
    (bundle / "MacOS").mkdir(parents=True)
    with open(bundle / "Info.plist", "wb") as f:
        plistlib.dump({"CFBundleExecutable": "OpenGMA"}, f)
    assert script.executable("macos") == bundle / "MacOS" / "OpenGMA"
