# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
生成测试用的合成 SRIM 输出：VACANCY.txt、RANGE.txt（Quick K-P，Ar 2000 keV → SiC，靶厚 2 µm）。

这两个文件不是 SRIM 的计算结果：空位和离子的分布由下面的解析函数给出，只是按 TRIM（SRIM-2013）
Quick K-P 输出的格式写出（文件头、表头、TRIM 的数字写法、Windows 换行），用来测试读取和计算。
文件头中的总空位数、穿透的离子数、平均射程、歧离、偏度和峰度都由写出的表格算出，与表格一致；
横向、径向射程只出现在文件头中，读取时不用，取的是随意的合理数值。

重新生成（只用标准库）：
    python tests/data/srim/make_synthetic.py
"""
from __future__ import annotations

import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
NEWLINE = "\r\n"   # TRIM 在 Windows 上运行，输出文件用 Windows 换行

ION, ENERGY = "Ar", 2000            # 离子、能量（keV）
IONS = 10000                        # 计算的离子数
BINS, WIDTH = 100, 200.0            # 深度区间数、区间宽度（Å），靶厚 2 µm
TARGET = "SiC"
DENSITY, MASS_DENSITY = "9.643E22", "3.21"                     # atoms/cm3、g/cm3
ELEMENTS = (("Si", "50", "70.04"), ("C", "50", "29.96"))       # 元素、原子百分比、质量百分比
LATERAL, RADIAL = (1510.0, 1896.0), (2366.0, 1243.0)           # 横向、径向射程和歧离（Å），只写在文件头

# 离子分布：两侧宽度不同的正态分布（峰位、浅侧宽度、深侧宽度，Å），深侧有少量离子穿出靶
ION_PEAK, ION_SIGMA_SHALLOW, ION_SIGMA_DEEP = 16300.0, 2100.0, 1500.0


def _cutoff(x: float, end: float, sigma: float) -> float:
    """在 end 附近平滑地降到 0。"""
    return 0.5 * math.erfc((x - end) / (math.sqrt(2) * sigma))


def vacancies_by_ions(x: float) -> float:
    """离子产生的空位（vacancies/(Å·ion)），x 为深度（Å）。"""
    return 0.042 * (0.3 + (x / 14800) ** 2) * _cutoff(x, 14800, 1700)


def vacancies_by_recoils(x: float) -> float:
    """反冲原子产生的空位（vacancies/(Å·ion)）：比离子产生的多一个数量级，峰位略浅。"""
    return 0.37 * (0.25 + 1.1 * (x / 14300) ** 3) * _cutoff(x, 14300, 1900)


def ion_cdf(x: float) -> float:
    """离子停留深度的累积分布。"""
    s1, s2 = ION_SIGMA_SHALLOW, ION_SIGMA_DEEP
    phi = 0.5 * (1 + math.erf((x - ION_PEAK) / (math.sqrt(2) * (s1 if x <= ION_PEAK else s2))))
    if x <= ION_PEAK:
        return 2 * s1 / (s1 + s2) * phi
    return s1 / (s1 + s2) + 2 * s2 / (s1 + s2) * (phi - 0.5)


# ============================================================
# TRIM 的数字写法
# ============================================================
def depth_text(value: float) -> str:
    """深度：6 位有效数字的整数加指数，如 200.01 → 200010.E-03。"""
    exponent = math.floor(math.log10(value)) - 5
    mantissa = round(value / 10 ** exponent)
    if mantissa >= 1_000_000:
        mantissa, exponent = round(mantissa / 10), exponent + 1
    return f"{mantissa:06d}.E{exponent:+03d}"


def vacancy_text(value: float) -> str:
    """空位：小数点前 4 位、后 2 位，如 0.0368056 → 3680.56E-05。"""
    exponent = math.floor(math.log10(value)) - 3
    mantissa = value / 10 ** exponent
    if round(mantissa, 2) >= 10000:
        mantissa, exponent = mantissa / 10, exponent + 1
    return f"{mantissa:7.2f}E{exponent:+03d}"


def length_text(value: float) -> str:
    """文件头中的射程：4 位有效数字，如 16430 → 164.3E+02。"""
    exponent = math.floor(math.log10(value)) - 2
    mantissa = value / 10 ** exponent
    if round(mantissa, 1) >= 1000:
        mantissa, exponent = mantissa / 10, exponent + 1
    return f"{mantissa:5.1f}E{exponent:+03d}"


# ============================================================
# 生成
# ============================================================
def _target_lines(width_and_density_on_one_line: bool) -> list[str]:
    exponent = math.floor(math.log10(BINS * WIDTH))
    width = f"Layer Width =     {BINS * WIDTH / 10 ** exponent:g}.E+{exponent:02d} A"   # 如 2.E+04 A
    density = f"Layer # 1- Density = {DENSITY} atoms/cm3 = {MASS_DENSITY} g/cm3"
    lines = ["============= TARGET MATERIAL ======================================", f"Layer  1 : {TARGET}"]
    if width_and_density_on_one_line:   # RANGE.txt 中层厚和密度写在同一行
        lines.append(f"{width}   {density}")
    else:
        lines += [f"{width} ;", f"  {density}"]
    lines += [f"  Layer # 1- {symbol:>2} = {atomic}  Atomic Percent = {mass}  Mass Percent"
              for symbol, atomic, mass in ELEMENTS]
    return [*lines, "====================================================================",
            f" Total Ions calculated ={IONS:.2f}"]


def make() -> dict:
    depths = [depth_text(i * WIDTH + 0.01) for i in range(1, BINS + 1)]   # 区间右端，TRIM 多写 0.01 Å
    mids = [(i - 0.5) * WIDTH for i in range(1, BINS + 1)]
    by_ions = [vacancy_text(vacancies_by_ions(x)) for x in mids]
    by_recoils = [vacancy_text(vacancies_by_recoils(x)) for x in mids]
    total_vacancies = round(sum(float(a) + float(b) for a, b in zip(by_ions, by_recoils, strict=True)) * WIDTH)
    counts = [round(IONS * (ion_cdf(i * WIDTH) - ion_cdf((i - 1) * WIDTH))) for i in range(1, BINS + 1)]
    ions = [f"{n / (IONS * WIDTH * 1e-8):.4E}" for n in counts]   # (atoms/cm3)/(atoms/cm2)
    transmitted = IONS - sum(counts)

    # 平均射程等按写出的表格计算，区间中点与 GMA.SC.SRIM.centroid 相同（深度减半个区间宽度）
    right = [float(d) for d in depths]
    centers = [r - (right[1] - right[0]) / 2 for r in right]
    weights = [float(v) for v in ions]
    total = sum(weights)
    mean = sum(c * w for c, w in zip(centers, weights, strict=True)) / total
    moment = [sum((c - mean) ** k * w for c, w in zip(centers, weights, strict=True)) / total for k in (2, 3, 4)]
    straggling = math.sqrt(moment[0])
    skewness, kurtosis = moment[1] / straggling ** 3, moment[2] / straggling ** 4

    title = f"====== {ION} ({ENERGY}) into {TARGET} (synthetic test data) ======="
    vacancy = [
        title, "        SRIM-2013.00", "==========================================",
        "    Ion and Target VACANCY production     ", "  See SRIM Outputs\\TDATA.txt for calc. details",
        "==========================================",
        "--------------------------------------------------------------------",
        "    Recoil/Damage Calculations made with Kinchin-Pease Estimates    ",
        "--------------------------------------------------------------------",
        " See file :  SRIM Outputs\\TDATA.txt for calculation data",
        f" Ion    = {ION}   Energy = {ENERGY} keV",
        *_target_lines(False),
        f" Total Target Vacancies     = {total_vacancies} /Ion",
        "",
        "==========================================================",
        "  Table Units are  >>>> Vacancies/(Angstrom-Ion)  <<<<  ",
        "==========================================================",
        "   TARGET     VACANCIES     VACANCIES ",
        "   DEPTH         by            by     ",
        "   (Ang.)       IONS         RECOILS  ",
        "-----------  -----------  ------------",
        *[f"{d}  {a}  {b}  " for d, a, b in zip(depths, by_ions, by_recoils, strict=True)],
        "",
        " To convert to Energy Lost - multiply by Average Binding Energy =  3  eV/Vacancy",
        "",
    ]
    range_ = [
        title, "        SRIM-2013.00", "==================================================",
        "      ION and final RECOIL ATOM Distributions     ",
        " See  SRIM Outputs\\TDATA.txt for calculation details",
        "==================================================",
        "--------------------------------------------------------------------",
        "    Recoil/Damage Calculations made with Kinchin-Pease Estimates    ",
        "--------------------------------------------------------------------",
        "----------------------------------------------------------------",
        "  There are NO RECOILS unless a full TRIM calculation is made.   ",
        "----------------------------------------------------------------",
        "See file :  SRIM Outputs\\TDATA.txt   for details of calculation",
        f" Ion    = {ION}   Energy = {ENERGY}  keV",
        *_target_lines(True),
        f" Ion Average Range =   {length_text(mean)} A   Straggling =   {length_text(straggling)} A",
        f" Ion Lateral Range =   {length_text(LATERAL[0])} A   Straggling =   {length_text(LATERAL[1])} A",
        f" Ion Radial  Range =   {length_text(RADIAL[0])} A   Straggling =   {length_text(RADIAL[1])} A",
        "====================================================================",
        f" Transmitted Ions ={transmitted};  Backscattered Ions =",
        " (These are not included in Skewne- and Kurtosis below.)",
        "",
        f" Range Skewne- = {skewness:09.4f}  &= [-(X-Rp)^3]/[N*Straggle^3]",
        f" Range Kurtosis = {kurtosis:08.4f}  &= [-(X-Rp)^4]/[N*Straggle^4]",
        " Statistical definitions above are those used in VLSI implant modelling.",
        "====================================================================",
        "=================================================================",
        "  Table Distribution Units are >>>  (Atoms/cm3) / (Atoms/cm2)  <<<  ",
        "=================================================================",
        f"   DEPTH         {ION}       Recoil     ",
        "   (Ang.)       Ions     Distribution",
        "-----------  ----------  ------------",
        *[f"{d}  {n}  0.0000E+00" for d, n in zip(depths, ions, strict=True)],
        "",
    ]
    for name, lines in (("VACANCY.txt", vacancy), ("RANGE.txt", range_)):
        (HERE / name).write_bytes(NEWLINE.join(lines).encode("ascii"))
    return {"total_vacancies": total_vacancies, "transmitted": transmitted, "mean_range": mean,
            "straggling": straggling, "skewness": skewness, "kurtosis": kurtosis}


if __name__ == "__main__":
    for key, value in make().items():
        print(f"{key}: {value:g}")
