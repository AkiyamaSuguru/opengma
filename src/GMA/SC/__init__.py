# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
SC（Simulation and Calculation）：模拟和计算。

- SRIM：读取 TRIM 的 VACANCY.txt、RANGE.txt，计算离子辐照的损伤（dpa）和注入离子浓度随深度的分布；
- Salts：熔盐配比，按摩尔分数和总质量计算各盐的质量。

    from GMA.SC.SRIM import read_vacancy, depth_profile
    from GMA.SC.Salts import salt_masses
"""
