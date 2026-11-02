# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
出版图对话框（方案 6.3）：预览是用 GMA 的出版图函数生成的图片，放在可以缩放、拖动的查看器中，
预览就是导出的效果（P0 发现 MatplotlibChart 会把图拉伸到控件大小，所以不用它）。

选项：尺寸、字体、字号、图例、隐藏纵轴刻度、分峰填充不透明度、子图、格式、分辨率；
可以复制图片、复制为代码、导出。选项保存在模块标签的状态中，下次打开时沿用。
"""
from __future__ import annotations

import asyncio
import tempfile
import traceback
from pathlib import Path

import flet as ft

from .. import theme as th
from ..services import codegen, figures
from ..services.figures import FigureOptions, PlotRequest
from ..strings import S
from . import widgets as w
from .dialogs import close, dialog, show

PREVIEW_DPI = 220      # 预览图的分辨率；导出时用对话框中的分辨率
MAX_PREVIEW_PX = 2600  # 预览图的长边最多这么多像素，尺寸很大时自动降低预览分辨率
FORMAT_LABELS = [("png", "PNG"), ("svg", "SVG"), ("pdf", "PDF"), ("tiff", "TIFF"), ("jpg", "JPG"),
                 (figures.HTML, S.FORMAT_HTML)]


class FigureDialog:
    def __init__(self, view, describe: str):
        self.view = view
        self.describe = describe       # 对话框副标题中的“画的是什么”，如“C1s · B1_SiC_1100℃”
        self.options = view.figure_options()
        self.request: PlotRequest | None = None
        self.result: figures.RenderResult | None = None
        self._pending: asyncio.Task | None = None
        self.preview = ft.Container(expand=True, alignment=ft.Alignment.CENTER)
        self.caption = ft.Text("", size=th.SIZE_SMALL, color=view.p.muted, text_align=ft.TextAlign.CENTER)
        self.note = ft.Text("", size=th.SIZE_SMALL, color=view.p.warning, text_align=ft.TextAlign.CENTER,
                            visible=False)
        self.busy = ft.ProgressRing(width=18, height=18, stroke_width=2, visible=False)
        # 对话框中的操作结果（已复制、已导出）显示在按钮旁边，不用底部提示条（会被对话框挡住）
        self.status = ft.Text("", size=th.SIZE_SMALL, color=view.p.success, max_lines=1,
                              overflow=ft.TextOverflow.ELLIPSIS, expand=True)
        self._flash_task = None
        self.options_panel = ft.Column(spacing=14, scroll=ft.ScrollMode.AUTO, expand=True)
        self.buttons: list[ft.Control] = []
        self.box: ft.AlertDialog | None = None

    @property
    def p(self):
        return self.view.p

    @property
    def app(self):
        return self.view.app

    # ============================================================
    # 对话框
    # ============================================================
    def show(self) -> None:
        p = self.p
        self.request = self.make_request()
        self.build_options()
        title = ft.Column([ft.Text(S.FIGURE_TITLE, size=17, weight=ft.FontWeight.W_600, color=p.text),
                           w.muted(S.FIGURE_SUBTITLE.format(what=self.describe, function=self.request.function), p,
                                   th.SIZE_SMALL)], spacing=2, tight=True)
        left = ft.Container(
            expand=True, bgcolor=p.subtle if not p.dark else p.bg, border_radius=th.RADIUS_CONTROL, padding=14,
            content=ft.Column([
                ft.Row([ft.Container(expand=True), self.busy,
                        w.icon_button(ft.Icons.CENTER_FOCUS_STRONG_OUTLINED, S.ZOOM_RESET, self.reset_zoom, p)],
                       spacing=6),
                self.preview, self.caption, self.note,
            ], spacing=8, expand=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER))
        right = ft.Container(width=290, content=self.options_panel, padding=ft.Padding.only(left=4, right=8))
        content = ft.Container(width=1000, height=min(max((self.app.page.height or 800) * 0.7, 420), 640),
                               content=ft.Row([left, right], spacing=16, expand=True,
                                              vertical_alignment=ft.CrossAxisAlignment.STRETCH))
        self.buttons = [
            ft.OutlinedButton(S.COPY_CODE, icon=ft.Icons.CODE_ROUNDED, on_click=self.copy_code),
            ft.OutlinedButton(S.COPY_IMAGE, icon=ft.Icons.CONTENT_COPY_ROUNDED, on_click=self.copy_image,
                              tooltip=S.COPY_IMAGE_TIP),
            ft.FilledButton(S.EXPORT_FIGURE, icon=ft.Icons.DOWNLOAD_ROUNDED, on_click=self.export),
        ]
        actions = [ft.Row([ft.Icon(ft.Icons.INFO_OUTLINE, size=15, color=p.faint), w.faint(S.FIGURE_HINT, p),
                           ft.Container(width=8), self.status, ft.TextButton(S.CLOSE, on_click=self.close),
                           *self.buttons], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER)]
        self.box = dialog(p, "", content, actions, width=1000)
        self.box.title = title
        self.box.on_dismiss = lambda e: self.cancel_pending()
        show(self.app.page, self.box)
        self.schedule(0)

    def cancel_pending(self) -> None:
        if self._pending is not None:
            self._pending.cancel()

    def close(self, e=None) -> None:
        self.cancel_pending()
        close(self.box)

    def flash(self, message: str, error: bool = False) -> None:
        """在按钮旁边显示操作结果，几秒后消失。"""
        self.status.value = message
        self.status.color = self.p.error if error else self.p.success
        self.status.tooltip = message
        self.status.update()
        if self._flash_task is not None:
            self._flash_task.cancel()
        self._flash_task = self.app.page.run_task(self._clear_flash, message)

    async def _clear_flash(self, message: str) -> None:
        await asyncio.sleep(4)
        if self.status.value == message:
            self.status.value = ""
            self.status.update()

    def make_request(self) -> PlotRequest:
        return self.view.figure_request(self.options)

    # ============================================================
    # 选项
    # ============================================================
    def build_options(self) -> None:
        p, o, req = self.p, self.options, self.request
        size_w, size_h = figures.figure_size(o, req.panels)

        def section(title):
            return w.label(title, p)

        def number(value, on_done, width=90, suffix=None, disabled=False):
            def done(e):
                try:
                    on_done(float(e.control.value))
                    e.control.error = None
                except ValueError:
                    e.control.error = S.NUMBER_REQUIRED
                e.control.update()
            return ft.TextField(value=f"{value:g}", width=width, dense=True, text_size=th.SIZE_BODY, suffix=suffix,
                                on_submit=done, on_blur=done, disabled=disabled,
                                keyboard_type=ft.KeyboardType.NUMBER)

        def row(label, control):
            return ft.Row([w.text(label, p, th.SIZE_BODY), ft.Container(expand=True), control], spacing=8,
                          vertical_alignment=ft.CrossAxisAlignment.CENTER)

        custom = o.size == "custom"
        size = ft.SegmentedButton(selected=[o.size], show_selected_icon=False,
                                  on_change=lambda e: self.change(size=(e.control.selected or ["single"])[0]),
                                  segments=[ft.Segment(value="single", label=S.SIZE_SINGLE),
                                            ft.Segment(value="double", label=S.SIZE_DOUBLE),
                                            ft.Segment(value="custom", label=S.SIZE_CUSTOM)])
        dims = ft.Row([number(size_w, lambda v: self.change(width=v, size="custom"), 72, disabled=not custom),
                       ft.Text("×", color=p.muted),
                       number(size_h, lambda v: self.change(height=v, size="custom"), 72, disabled=not custom)],
                      spacing=6, tight=True)
        fonts = list(figures.FIGURE_FONTS)
        if o.font not in fonts:
            fonts.insert(0, o.font)
        font = ft.Dropdown(value=o.font, width=170, dense=True, text_size=th.SIZE_BODY,
                           options=[ft.DropdownOption(key=f, text=f) for f in fonts],
                           on_select=lambda e: self.change(font=e.control.value))
        legend_loc = ft.Dropdown(value=o.legend_loc, width=130, dense=True, text_size=th.SIZE_SMALL,
                                 disabled=not o.legend,
                                 options=[ft.DropdownOption(key=k, text=k) for k in figures.LEGEND_LOCS],
                                 on_select=lambda e: self.change(legend_loc=e.control.value))
        controls = [
            section(S.FIGURE_SIZE), size, row(S.WIDTH_HEIGHT, dims),
            section(S.FIGURE_TEXT),
            row(S.FONT, font),
            row(S.FONT_SIZE, number(o.font_size, lambda v: self.change(font_size=v), 80, "pt")),
            section(S.FIGURE_ELEMENTS),
            row(S.LEGEND, ft.Row([legend_loc, ft.Switch(value=o.legend,
                                                        on_change=lambda e: self.change(legend=e.control.value))],
                                 spacing=6, tight=True)),
            row(S.HIDE_Y_TICKS, ft.Switch(value=o.hide_y_ticks,
                                          on_change=lambda e: self.change(hide_y_ticks=e.control.value))),
        ]
        if any(r.fitted for r in req.records) and req.function in figures.FIT_FUNCTIONS.values():
            controls.append(row(S.FILL_ALPHA, number(o.component_alpha,
                                                     lambda v: self.change(component_alpha=min(max(v, 0), 1)), 80)))
        if self.view.view_mode == "overlay" and len(req.records) > 1:
            controls.append(row(S.SUBPLOTS, ft.Switch(value=o.subplots,
                                                      on_change=lambda e: self.change(subplots=e.control.value))))
        if req.panels > 1:
            cols = ft.Dropdown(value=str(o.n_cols), width=100, dense=True, text_size=th.SIZE_BODY,
                               options=[ft.DropdownOption(key="0", text=S.AUTO)] +
                               [ft.DropdownOption(key=str(n), text=str(n)) for n in range(1, min(req.panels, 6) + 1)],
                               on_select=lambda e: self.change(n_cols=int(e.control.value)))
            controls.append(row(S.N_COLS, cols))
        formats = [(k, t) for k, t in FORMAT_LABELS if k != figures.HTML or req.interactive]
        fmt = o.format if any(k == o.format for k, _ in formats) else "png"
        controls += [
            section(S.OUTPUT),
            row(S.FORMAT, ft.Dropdown(value=fmt, width=150, dense=True, text_size=th.SIZE_BODY,
                                      options=[ft.DropdownOption(key=k, text=t) for k, t in formats],
                                      on_select=lambda e: self.change(format=e.control.value or "png"))),
            row(S.DPI, number(o.dpi, lambda v: self.change(dpi=int(v)), 90, "dpi",
                              disabled=fmt in ("svg", "pdf", figures.HTML))),
        ]
        self.options_panel.controls = controls

    def change(self, **values) -> None:
        data = self.options.to_dict()
        data.update(values)
        self.options = FigureOptions.from_dict(data)
        self.view.save_figure_options(self.options)
        self.request = self.make_request()
        self.build_options()
        self.options_panel.update()
        self.schedule()

    # ============================================================
    # 预览
    # ============================================================
    def schedule(self, delay: float = 0.25) -> None:
        """选项改动后稍等再重画，连续修改时只画最后一次。"""
        if self._pending is not None:
            self._pending.cancel()
        self._pending = self.app.page.run_task(self._render_later, delay)

    async def _render_later(self, delay: float) -> None:
        await asyncio.sleep(delay)
        await self.render_preview()

    def preview_dpi(self) -> int:
        w_in, h_in = figures.figure_size(self.options, self.request.panels)
        return int(max(min(PREVIEW_DPI, MAX_PREVIEW_PX / max(w_in, h_in, 0.1)), 60))

    async def render_preview(self) -> None:
        p = self.p
        self.busy.visible = True
        self.busy.update()
        try:
            self.result = await asyncio.to_thread(
                figures.render, self.request, self.options, fmt="png", dpi=self.preview_dpi(),
                palette=self.view.palette, use_latex=self.app.settings.latex)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - 出错的原因显示在预览区
            self.result = None
            self.preview.content = ft.Column([
                ft.Icon(ft.Icons.ERROR_OUTLINE_ROUNDED, color=p.error, size=28),
                ft.Text(S.LATEX_FAILED if self.app.settings.latex else S.FIGURE_FAILED, color=p.error,
                        size=th.SIZE_BODY),
                ft.Text(str(exc), color=p.muted, size=th.SIZE_SMALL, selectable=True),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, tight=True)
            self.caption.value = ""
            print(traceback.format_exc(), flush=True)
        else:
            self.show_image(self.result.data)
            self.update_caption()
        finally:
            self.busy.visible = False
        for c in (self.preview, self.caption, self.note, self.busy):
            c.update()

    def show_image(self, data: bytes) -> None:
        image = ft.Container(content=ft.Image(src=data, fit=ft.BoxFit.CONTAIN, filter_quality=ft.FilterQuality.HIGH),
                             bgcolor="#FFFFFF", padding=10,
                             shadow=ft.BoxShadow(blur_radius=10, color=ft.Colors.with_opacity(0.12, "#000000")))
        self.preview.content = ft.InteractiveViewer(content=image, min_scale=0.5, max_scale=8,
                                                    boundary_margin=ft.Margin.all(400), expand=True)

    def reset_zoom(self, e=None) -> None:
        if self.result is not None and self.result.data:
            self.show_image(self.result.data)
            self.preview.update()

    def update_caption(self) -> None:
        o = self.options
        width, height = figures.figure_size(o, self.request.panels)
        size = {"single": S.SIZE_SINGLE, "double": S.SIZE_DOUBLE, "custom": S.SIZE_CUSTOM}[o.size]
        self.caption.value = S.FIGURE_CAPTION.format(size=size, w=f"{width:g}", h=f"{height:g}", font=o.font,
                                                     font_size=o.font_size, dpi=o.dpi)
        notes = []
        if self.result is not None and self.result.substituted:
            notes.append(S.FONT_SUBSTITUTED.format(font=self.result.substituted, used=self.result.font))
        if self.view.view_mode == "side" and figures.mixed_modes(self.request.records):
            notes.append(S.MIXED_MODES)
        self.note.value = "\n".join(notes)
        self.note.visible = bool(notes)

    # ============================================================
    # 复制、导出
    # ============================================================
    async def copy_code(self, e=None) -> None:
        session = self.view.session
        code = codegen.figure_code(self.request, self.options, project_path=session.path, dirty=session.dirty,
                                   palette=self.view.palette, use_latex=self.app.settings.latex,
                                   substituted=self.result.substituted if self.result else None)
        await self.app.clipboard.set(code)
        self.flash(S.CODE_COPIED)

    async def copy_image(self, e=None) -> None:
        """
        复制图片（PNG，按对话框中的分辨率）。桌面版的剪贴板只能放文件，所以先写一个临时 PNG 文件再复制它，
        可以粘贴到 Word、PPT 或文件夹中；网页版直接复制图片。
        """
        folder = Path(tempfile.gettempdir()) / "opengma-figures"
        folder.mkdir(exist_ok=True)
        path = folder / f"{codegen.file_stem(self.request)}.png"
        try:
            await asyncio.to_thread(figures.render, self.request, self.options, fmt="png", path=path,
                                    palette=self.view.palette, use_latex=self.app.settings.latex)
            if self.app.page.web:
                await self.app.clipboard.set_image(path.read_bytes())
            else:
                await self.app.clipboard.set_files([str(path)])
        except Exception as exc:  # noqa: BLE001
            self.flash(f"{S.COPY_IMAGE_FAILED}：{exc}", error=True)
            print(traceback.format_exc(), flush=True)
            return
        self.flash(S.IMAGE_COPIED)

    async def export(self, e=None) -> None:
        fmt = self.options.format
        if fmt == figures.HTML and not self.request.interactive:
            self.flash(S.HTML_UNAVAILABLE, error=True)
            return
        name = f"{codegen.file_stem(self.request)}.{fmt}"
        path = await self.app.file_picker.save_file(dialog_title=S.EXPORT_FIGURE.rstrip("…"), file_name=name,
                                                    file_type=ft.FilePickerFileType.CUSTOM, allowed_extensions=[fmt])
        if not path:
            return
        path = Path(path)
        if path.suffix.lower() != f".{fmt}":
            path = path.with_name(path.name + f".{fmt}")
        self.busy.visible = True
        self.busy.update()
        try:
            await asyncio.to_thread(figures.render, self.request, self.options, path=path,
                                    palette=self.view.palette, use_latex=self.app.settings.latex)
        except Exception as exc:  # noqa: BLE001
            self.flash(f"{S.FIGURE_FAILED}：{exc}", error=True)
            print(traceback.format_exc(), flush=True)
            return
        finally:
            self.busy.visible = False
            self.busy.update()
        self.flash(S.FIGURE_EXPORTED.format(path=path))
