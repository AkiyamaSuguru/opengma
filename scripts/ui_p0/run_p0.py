# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
依次运行 UI P0 的全部检查，终端输出同时写入 scripts/ui_p0/results/。Windows、macOS、Linux 通用。

用法（在仓库根目录）：
    uv run python scripts/ui_p0/run_p0.py                     全部运行
    uv run python scripts/ui_p0/run_p0.py window matplotlib   只运行其中几项

可选的项目：env netcdf tests linechart window matplotlib
后三项会打开窗口：LineChart 和换窗会先自动测速，测完停在那里可以手动操作；关掉一个窗口后才会打开下一个。
按 Ctrl+C 停止整个运行。
"""
from __future__ import annotations

import os
import platform
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "results"
CHARTS = ["--with", "flet-charts==1.0.5"]
VERSIONS = """
import importlib.metadata as md
import platform
import sys

print("Python", sys.version.split()[0], platform.machine())
for name in ("flet", "flet-desktop", "numpy", "pandas", "matplotlib", "xarray", "h5netcdf", "h5py"):
    try:
        print(name, md.version(name))
    except md.PackageNotFoundError:
        print(name, "未安装")
"""
STEPS = {
    "env": [["uv", "--version"], ["uv", "sync"], ["uv", "run", "python", "-c", VERSIONS]],
    "netcdf": [["uv", "run", "--with", "xarray", "--with", "h5netcdf[h5py]", "python", "scripts/ui_p0/p0_netcdf.py"]],
    "tests": [["uv", "run", "pytest", "-q"]],
    "linechart": [["uv", "run", *CHARTS, "python", "scripts/ui_p0/p0_linechart.py"]],
    "window": [["uv", "run", "python", "scripts/ui_p0/p0_window.py"]],
    "matplotlib": [["uv", "run", *CHARTS, "python", "scripts/ui_p0/p0_matplotlib.py"]],
}
BENCH = {"linechart", "window"}  # 这两项打开窗口后先自动测速


def run(cmd, log, env):
    """运行一条命令，输出逐行显示并写入日志。"""
    proc = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace")
    try:
        for line in proc.stdout:
            print(line, end="", flush=True)
            log.write(line)
            log.flush()
        return proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        raise


def main(argv):
    steps = argv or list(STEPS)
    unknown = [s for s in steps if s not in STEPS]
    if unknown:
        print(f"不认识的项目：{'、'.join(unknown)}（可选：{' '.join(STEPS)}）")
        return 1
    OUT.mkdir(exist_ok=True)
    env = {**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONUTF8": "1"}  # 子进程按 UTF-8 输出，Windows 上也不乱码
    try:
        for step in steps:
            print(f"\n==================== {step} ====================", flush=True)
            with (OUT / f"{step}.log").open("w", encoding="utf-8") as log:
                if step == "env":
                    info = (f"{platform.platform()}\n机器 {platform.machine()} · CPU {os.cpu_count()} 核\n")
                    print(info, end="", flush=True)
                    log.write(info)
                step_env = {**env, "P0_BENCH": "1"} if step in BENCH else env
                for cmd in STEPS[step]:
                    if run(cmd, log, step_env) != 0 and step == "env":
                        print("安装依赖失败，停止。", flush=True)
                        return 1
    except KeyboardInterrupt:
        print("\n已停止（Ctrl+C）。", flush=True)
        return 130
    print(f"\n完成。结果在 {OUT}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
