#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
#
# 在 Mac 上依次运行 UI P0 的全部检查，终端输出同时写入 scripts/ui_p0/results/。
#
# 用法（在任意目录都可以）：
#   bash scripts/ui_p0/run_mac.sh                     全部运行
#   bash scripts/ui_p0/run_mac.sh window matplotlib   只运行其中几项
# 可选的项目：env netcdf tests linechart window matplotlib
#
# 后三项会打开窗口：LineChart 和换窗会先自动测速，测完停在那里可以手动操作；
# 关掉一个窗口后才会打开下一个。
set -u
cd "$(dirname "$0")/../.." || exit 1
OUT="scripts/ui_p0/results"
mkdir -p "$OUT"
export PYTHONUNBUFFERED=1
CHARTS="--with flet-charts==1.0.5"

if ! command -v uv >/dev/null 2>&1; then
  echo "没有找到 uv。安装：brew install uv，或者 curl -LsSf https://astral.sh/uv/install.sh | sh"
  exit 1
fi

step() {
  case "$1" in
    env)
      date
      sw_vers
      echo "芯片：$(sysctl -n machdep.cpu.brand_string)  内存：$(( $(sysctl -n hw.memsize) / 1073741824 )) GB"
      system_profiler SPDisplaysDataType | grep -E "Display Type|Resolution|UI Looks like|Main Display"
      uv --version
      uv sync || return 1
      uv run python - <<'EOF'
import importlib.metadata as md
import platform
import sys

print("Python", sys.version.split()[0], platform.machine())
for name in ("flet", "flet-desktop", "numpy", "pandas", "matplotlib", "xarray", "h5netcdf", "h5py"):
    try:
        print(name, md.version(name))
    except md.PackageNotFoundError:
        print(name, "未安装")
EOF
      ;;
    netcdf)     uv run --with xarray --with "h5netcdf[h5py]" python scripts/ui_p0/p0_netcdf.py ;;
    tests)      uv run pytest -q ;;
    linechart)  P0_BENCH=1 uv run $CHARTS python scripts/ui_p0/p0_linechart.py ;;
    window)     P0_BENCH=1 uv run python scripts/ui_p0/p0_window.py ;;
    matplotlib) uv run $CHARTS python scripts/ui_p0/p0_matplotlib.py ;;
    *)          echo "不认识的项目：$1（可选：env netcdf tests linechart window matplotlib）"; return 1 ;;
  esac
}

if [ $# -eq 0 ]; then
  set -- env netcdf tests linechart window matplotlib
fi
for s in "$@"; do
  echo
  echo "==================== $s ===================="
  step "$s" 2>&1 | tee "$OUT/$s.log"
done
echo
echo "完成。结果在 $(pwd)/$OUT/"
