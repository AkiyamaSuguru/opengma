# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
复制为代码：生成一段 GMA 代码，粘贴到 marimo（或 Jupyter、脚本）中就能复现当前的出版图（方案 6.3、Q6）。

代码从项目文件读取数据，调用与界面相同的 Plotter 方法和参数，所以得到的图与对话框中的预览一致。
"""
from __future__ import annotations

import keyword
import re

from .figures import CJK_FONT, FigureOptions, PlotRequest, figure_size

DEFAULT_PALETTE = "tab10"
PROJECT_PLACEHOLDER = "项目.nc"


def identifier(name: str, used: set[str]) -> str:
    """把谱图名变成变量名：C1s → c1s，Si 2p → si_2p；重复时加序号。"""
    text = re.sub(r"\W+", "_", str(name).strip().lower()).strip("_") or "spectrum"
    if text[0].isdigit():
        text = "s_" + text
    if keyword.iskeyword(text):
        text += "_"
    base, i = text, 2
    while text in used:
        text = f"{base}_{i}"
        i += 1
    used.add(text)
    return text


def file_stem(request: PlotRequest) -> str:
    names = {r.name for r in request.records}
    stem = next(iter(names)) if len(names) == 1 else "figure"
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", stem).strip() or "figure"


def has_cjk(request: PlotRequest) -> bool:
    """
    图中会出现中文或 ℃ 等西文字体中常常没有的字符（样品名、谱图名、分峰名作为图例或子图标题），
    需要用附带的 Noto Sans SC 补字。
    """
    texts = [*request.keys, *(r.name for r in request.records), *(r.sample for r in request.records),
             *(n for r in request.records for n in r.components)]
    for value in request.kwargs.values():
        if isinstance(value, dict):
            texts += [str(k) for k in value]
    return any(any(ord(ch) >= 0x2100 for ch in t) for t in texts)


def _value(value) -> str:
    if isinstance(value, float):
        return repr(round(value, 6))
    if isinstance(value, tuple):
        return "(" + ", ".join(_value(v) for v in value) + ")"
    if isinstance(value, dict):
        return "{" + ", ".join(f"{_value(k)}: {_value(v)}" for k, v in value.items()) + "}"
    if isinstance(value, list):
        return "[" + ", ".join(_value(v) for v in value) + "]"
    return repr(value)


def figure_code(request: PlotRequest, options: FigureOptions, *, project_path=None, dirty: bool = False,
                palette=None, use_latex: bool = False, substituted: str | None = None) -> str:
    """
    生成复现出版图的代码。project_path 为 None（项目还没有保存）时用占位的文件名并提示先保存。
    """
    plotter = f"{request.method}Plotter"
    lines = ["# OpenGMA 生成：复现出版图。可以粘贴到 marimo、Jupyter 或脚本中运行。"]
    if project_path is None:
        lines.append(f"# 项目还没有保存：先保存项目，再把 {PROJECT_PLACEHOLDER} 改成项目文件的路径。")
    elif dirty:
        lines.append("# 代码读取的是项目文件中保存的数据；项目还有未保存的修改，请先保存。")
    cjk = has_cjk(request)
    lines += [f"from GMA import {plotter}", "from GMA.project import load_project"]
    if cjk:
        lines.append("from GMA.UI.services.figures import register_fonts")
    lines.append("")
    if cjk:
        lines += [f"register_fonts()  # 登记 OpenGMA 附带的字体：图中的中文用 {CJK_FONT} 显示，与预览相同", ""]
    path = str(project_path) if project_path is not None else PROJECT_PLACEHOLDER
    lines.append(f"project = load_project({path!r})")

    used: set[str] = {"project", "plotter", "fig", "axes", "data"}

    def get(record) -> str:
        return (f"project.get({record.sample!r}, {record.method!r}, {record.name!r})"
                ".to_dataframe()")

    if request.single:
        var = identifier(request.records[0].name, used)
        lines.append(f"{var} = {get(request.records[0])}")
        data = var
    else:
        lines.append("data = {")
        for key, record in zip(request.keys, request.records, strict=True):
            lines.append(f"    {key!r}: {get(record)},")
        lines.append("}")
        data = "data"
    lines.append("")

    family = [options.font, CJK_FONT] if cjk else options.font
    args = [f"font_family={_value(family)}", f"font_size={_value(float(options.font_size))}"]
    if palette and palette != DEFAULT_PALETTE:
        args.append(f"palette={_value(palette)}")
    if use_latex:
        args.append("use_latex=True")
    if substituted:
        lines.append(f"# 预览时本机没有 {substituted}，用了字宽相同的代替字体；在有这个字体的电脑上运行即可。")
    lines.append(f"plotter = {plotter}({', '.join(args)})")

    stem = file_stem(request)
    fmt = options.format if options.format != "html" else "png"
    call = [f"    {data},"]
    for key, value in request.kwargs.items():
        call.append(f"    {key}={_value(value)},")
    call += [f"    figsize={_value(figure_size(options, request.panels))},",
             f"    save_path={f'{stem}.{fmt}'!r},",
             f"    dpi={int(options.dpi)},",
             "    show=False,"]
    lines += [f"fig, axes = plotter.{request.function}(", *call, ")", "fig"]
    return "\n".join(lines) + "\n"
