# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
打包 OpenGMA 图形界面（flet build），本机和 GitHub Actions 用同一个脚本，Windows、macOS、Linux 做法相同。

    uv run python scripts/build_app.py build macos     # 在 Mac 上打包，得到 build/macos/OpenGMA.app
    uv run python scripts/build_app.py build windows   # 在 Windows 上
    uv run python scripts/build_app.py build linux     # 在 Linux 上
    uv run python scripts/build_app.py smoke macos     # 运行打包好的程序做一次自检（见 GMA/UI/services/smoke.py）

build 做三件事：
1. 把界面资源（src/GMA/UI/assets：图标、字体、应用图标）复制到 src/assets。打包的程序从应用文件夹中的
   assets 读取图标和字体，flet build 也从这里的 icon.png 生成各系统的应用图标；
2. 运行 flet build（入口 src/main.py，配置见 pyproject.toml 的 [tool.flet]），程序里带着自己的 Python，
   用的电脑上不需要安装 Python；
3. 删除 src/assets，把结果压缩到 dist/（Linux 用 tar.gz 保留可执行权限，Mac 用 ditto 保留 .app 的元数据）。

第一次打包时 flet 会自动下载 Flutter SDK（放在用户目录下的 flutter 文件夹中），需要几分钟。
各系统还需要的工具见 README 的“打包”一节。
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import platform
import plistlib
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "src"
UI_ASSETS = APP_DIR / "GMA" / "UI" / "assets"
BUILD_ASSETS = APP_DIR / "assets"
TARGETS = {"macos": "Darwin", "windows": "Windows", "linux": "Linux"}   # 打包目标 → 需要在哪个系统上运行
SMOKE_TIMEOUT = 300   # 秒
IN_CI = os.environ.get("GITHUB_ACTIONS") == "true"


def project() -> dict:
    with open(ROOT / "pyproject.toml", "rb") as f:
        return tomllib.load(f)


def artifact_name() -> str:
    data = project()
    return data.get("tool", {}).get("flet", {}).get("artifact") or data["project"]["name"]


def version() -> str:
    return project()["project"]["version"]


def output_dir(target: str) -> Path:
    return ROOT / "build" / target


def annotate(title: str, lines, level: str = "error") -> None:
    """GitHub Actions 中把信息写成注释（出错时为 error），在运行结果的摘要中就能看到；本机运行时不输出。"""
    if not IN_CI:
        return
    text = "\n".join(lines)[-6000:]
    escaped = text.replace("%", "%25").replace("\r", "").replace("\n", "%0A")
    print(f"::{level} title={title}::{escaped}", flush=True)


def check_host(target: str) -> None:
    if target not in TARGETS:
        sys.exit(f"Unknown target {target!r}; use one of {', '.join(TARGETS)}.")
    if platform.system() != TARGETS[target]:
        sys.exit(f"`{target}` must be built on {TARGETS[target]} (this is {platform.system()}).")


# ============================================================
# build
# ============================================================
def prepare_assets() -> None:
    """界面资源复制到 src/assets（打包的程序在这里找图标和字体）；只是打包时的副本，不提交。"""
    remove_assets()
    shutil.copytree(UI_ASSETS, BUILD_ASSETS)


def remove_assets() -> None:
    if BUILD_ASSETS.exists():
        shutil.rmtree(BUILD_ASSETS)


def flet_command() -> list[str]:
    flet = shutil.which("flet")
    if flet is None:
        sys.exit("The flet command was not found. Run this script with `uv run python scripts/build_app.py ...` "
                 "so that the project's environment (with flet-cli) is used.")
    return [flet]


def run_flet_build(target: str, args) -> None:
    out = output_dir(target)
    command = [*flet_command(), "build", target, "--yes", "--output", str(out)]
    if args.build_number:
        command += ["--build-number", str(args.build_number)]
    if args.build_version:
        command += ["--build-version", args.build_version]
    if IN_CI:
        command += ["--verbose", "--no-rich-output"]
    command += args.extra
    print("+ " + " ".join(command), flush=True)
    env = {**os.environ, "PYTHONUTF8": "1"}
    tail: collections.deque[str] = collections.deque(maxlen=80)
    with subprocess.Popen(command, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, encoding="utf-8", errors="replace") as process:
        for line in process.stdout:
            print(line, end="", flush=True)
            tail.append(line.rstrip())
    if process.returncode != 0:
        annotate(f"flet build {target} failed (exit code {process.returncode})", tail)
        sys.exit(process.returncode)
    if not out.is_dir() or not any(out.iterdir()):
        sys.exit(f"flet build finished without producing files in {out}.")


def archive(target: str) -> Path:
    """把打包结果压缩成一个文件，放在 dist/。"""
    out = output_dir(target)
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    name = f"{artifact_name()}-{version()}-{target}"
    if target == "macos":
        bundle = next(out.glob("*.app"))
        path = dist / f"{name}.zip"
        path.unlink(missing_ok=True)
        subprocess.run(["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", str(bundle), str(path)], check=True)
    elif target == "linux":
        path = dist / f"{name}.tar.gz"
        with tarfile.open(path, "w:gz", format=tarfile.PAX_FORMAT) as tar:
            tar.add(out, arcname=artifact_name())
    else:
        path = dist / f"{name}.zip"
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for file in sorted(out.rglob("*")):
                if file.is_file():
                    zf.write(file, Path(artifact_name()) / file.relative_to(out))
    print(f"Archive: {path} ({path.stat().st_size / 1e6:.1f} MB)", flush=True)
    return path


def build(args) -> None:
    check_host(args.target)
    prepare_assets()
    try:
        run_flet_build(args.target, args)
    finally:
        remove_assets()
    path = archive(args.target)
    if IN_CI and os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
            f.write(f"archive={path}\narchive-name={path.name}\n")


# ============================================================
# smoke：运行打包好的程序做一次自检
# ============================================================
def executable(target: str) -> Path:
    out = output_dir(target)
    name = artifact_name()
    if target == "macos":
        bundle = next(out.glob("*.app"), None)
        if bundle is None:
            sys.exit(f"No .app in {out}; build it first.")
        with open(bundle / "Contents" / "Info.plist", "rb") as f:
            program = plistlib.load(f)["CFBundleExecutable"]
        return bundle / "Contents" / "MacOS" / program
    candidates = [out / f"{name}.exe"] if target == "windows" else [out / name]
    candidates += sorted(out.glob("*.exe")) if target == "windows" else [
        p for p in sorted(out.iterdir()) if p.is_file() and os.access(p, os.X_OK) and not p.suffix]
    for path in candidates:
        if path.is_file():
            return path
    sys.exit(f"No program found in {out}; build it first.")


def clean_environment() -> dict[str, str]:
    """
    运行打包好的程序时去掉开发环境的痕迹（uv run 设置的虚拟环境、PYTHONPATH 等），
    这样自检用的只能是程序自带的 Python 和依赖。
    """
    env = dict(os.environ)
    venv = env.pop("VIRTUAL_ENV", None)
    for name in ("PYTHONHOME", "PYTHONPATH", "CONDA_PREFIX", "UV_PROJECT_ENVIRONMENT"):
        env.pop(name, None)
    if venv:
        env["PATH"] = os.pathsep.join(p for p in env.get("PATH", "").split(os.pathsep)
                                      if not p.startswith(venv))
    return env


def smoke(args) -> None:
    check_host(args.target)
    program = executable(args.target)
    folder = Path(tempfile.mkdtemp(prefix="opengma-smoke-"))
    result_path = folder / "result.json"
    env = clean_environment()
    env.update({"OPENGMA_SMOKE_TEST": str(result_path), "OPENGMA_HOME": str(folder / "home")})
    print(f"+ {program}", flush=True)
    try:
        run = subprocess.run([str(program)], env=env, capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=SMOKE_TIMEOUT, check=False)
        output = (run.stdout + run.stderr).splitlines()
    except subprocess.TimeoutExpired as exc:
        output = [f"The program did not finish within {SMOKE_TIMEOUT} s."]
        for part in (exc.stdout, exc.stderr):
            if part:
                output += (part.decode("utf-8", "replace") if isinstance(part, bytes) else part).splitlines()
    print("\n".join(output[-60:]), flush=True)
    if not result_path.is_file():
        annotate(f"Smoke test of the {args.target} app: no result", output[-60:])
        sys.exit("The program exited without writing the self-check result.")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    print(json.dumps({k: v for k, v in result.items() if k != "tracebacks"}, ensure_ascii=False, indent=2))
    if not result.get("ok"):
        details = [f"{k}: {v}" for k, v in result["checks"].items()]
        for name, text in result.get("tracebacks", {}).items():
            details += [f"--- {name}", *text.splitlines()[-15:]]
        annotate(f"Smoke test of the {args.target} app failed", details)
        sys.exit("Self-check failed.")
    print("Smoke test passed: the packaged app runs with its own Python.", flush=True)
    annotate(f"Smoke test of the {args.target} app passed",
             [f"{key}: {result.get(key)}" for key in ("python", "executable", "prefix", "numpy", "platform",
                                                       "embedded", "window")], level="notice")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build and check the OpenGMA desktop app.")
    commands = parser.add_subparsers(dest="command", required=True)
    b = commands.add_parser("build", help="build the app for this computer's system")
    b.add_argument("target", choices=list(TARGETS))
    b.add_argument("--build-number", type=int, help="integer that increases with every build (CI: run number)")
    b.add_argument("--build-version", help="version shown to users; defaults to [project].version")
    b.add_argument("extra", nargs=argparse.REMAINDER, help="more `flet build` options after --")
    s = commands.add_parser("smoke", help="run the built app once with its self-check")
    s.add_argument("target", choices=list(TARGETS))
    args = parser.parse_args()
    if getattr(args, "extra", None) and args.extra[0] == "--":
        args.extra = args.extra[1:]
    (build if args.command == "build" else smoke)(args)


if __name__ == "__main__":
    main()
