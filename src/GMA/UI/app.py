# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
OpenGMA 图形界面的入口：启动器与工作区之间的换窗、主题、设置、打开与保存项目、快捷键。

运行：
    uv run opengma          （安装后的命令）
    uv run python -m GMA.UI

Windows、macOS、Linux 用同一套做法（设计原则第 1 条）：
- 启动器和工作区是同一个窗口，换窗时把透明度设为 0，改尺寸和内容并居中后再设回 1；不隐藏窗口；
- 两个窗口都用系统标题栏，共用一个最小尺寸；默认尺寸按可用屏幕区域的比例（screen.py）；
- 快捷键用 Ctrl + 字母，同时接受 ⌘。
"""
from __future__ import annotations

import asyncio
import contextlib
import traceback
from pathlib import Path

import flet as ft

from . import theme as th
from .components.dialogs import confirm_unsaved, show_error, toast
from .screen import (
    FALLBACK_AREA,
    LAUNCHER_LIMITS,
    MIN_SIZE,
    WORKSPACE_LIMITS,
    WindowTracker,
    measure_work_area,
    window_size,
)
from .session import ProjectSession, read_ui_state
from .settings import load_settings, save_settings, settings_path
from .strings import S
from .views import registry

ASSETS = Path(__file__).parent / "assets"
REPO_URL = "https://github.com/AkiyamaSuguru/opengma"
LAUNCHER, WORKSPACE = "launcher", "workspace"


class App:
    def __init__(self, page: ft.Page):
        self.page = page
        self.settings = load_settings()
        self.font = th.available_font()
        self.mode: str | None = None
        self.session: ProjectSession | None = None
        self.workspace = None
        self.tracker = WindowTracker(page)
        self.tracker.handlers.append(self.on_window_event)
        self.file_picker = ft.FilePicker()
        self.url_launcher = ft.UrlLauncher()
        self.clipboard = ft.Clipboard()
        self.p = th.palette(self.settings.primary, False)
        self._busy = False   # 换窗、关闭等进行中时忽略重复的关闭请求

    # ============================================================
    # 启动
    # ============================================================
    async def start(self) -> None:
        page = self.page
        page.title = S.APP_NAME
        page.padding = 0
        page.spacing = 0
        page.fonts = th.font_files()
        page.window.opacity = 0
        page.window.min_width, page.window.min_height = MIN_SIZE
        page.window.prevent_close = True
        page.on_keyboard_event = self.on_key
        page.on_platform_brightness_change = self.on_brightness
        self.apply_theme(rebuild=False)
        page.update()
        if not self.settings.work_area:
            area = await measure_work_area(page, self.tracker)
            if area:
                self.settings.work_area = list(area)
                self.save_settings()
        last = next((r for r in self.settings.recent if r.exists), None)
        if self.settings.startup == "last_project" and last is not None and await self.open_project(last.path):
            return
        await self.show_launcher()

    @property
    def area(self) -> tuple[float, float]:
        return tuple(self.settings.work_area or FALLBACK_AREA)

    # ============================================================
    # 主题
    # ============================================================
    def is_dark(self) -> bool:
        mode = self.settings.theme_mode
        if mode in ("light", "dark"):
            return mode == "dark"
        return self.page.platform_brightness == ft.Brightness.DARK

    def apply_theme(self, rebuild: bool = True) -> None:
        page = self.page
        self.p = th.palette(self.settings.primary, self.is_dark())
        page.theme_mode = {"light": ft.ThemeMode.LIGHT, "dark": ft.ThemeMode.DARK}.get(
            self.settings.theme_mode, ft.ThemeMode.SYSTEM)
        page.theme = th.make_theme(th.palette(self.settings.primary, False), self.font)
        page.dark_theme = th.make_theme(th.palette(self.settings.primary, True), self.font)
        page.bgcolor = self.p.bg
        if rebuild:
            self.rebuild()

    def rebuild(self) -> None:
        """主题变了：按新的颜色重新生成当前界面（标签、选择等状态保留在各个视图对象中）。"""
        if self.mode == LAUNCHER:
            from .launcher import Launcher
            self.page.controls[:] = [Launcher(self).build()]
        elif self.mode == WORKSPACE and self.workspace is not None:
            self.page.controls[:] = [self.workspace.build()]
        self.page.update()

    def toggle_theme(self, e=None) -> None:
        self.settings.theme_mode = "light" if self.is_dark() else "dark"
        self.save_settings()
        self.apply_theme()

    def on_brightness(self, e=None) -> None:
        if self.settings.theme_mode == "system":
            self.apply_theme()

    # ============================================================
    # 换窗
    # ============================================================
    def size_for(self, mode: str) -> tuple[int, int]:
        remembered = self.settings.launcher_size if mode == LAUNCHER else self.settings.workspace_size
        limits = LAUNCHER_LIMITS if mode == LAUNCHER else WORKSPACE_LIMITS
        ratio = self.settings.launcher_ratio if mode == LAUNCHER else self.settings.workspace_ratio
        if self.settings.remember_size and remembered:
            return window_size(self.area, (1, 1), MIN_SIZE, remembered)
        return window_size(self.area, ratio, *limits)

    async def _swap(self, mode: str, content: ft.Control, title: str) -> None:
        """透明度设为 0 → 改尺寸、换内容并居中 → 透明度设回 1（P0-2 验证的做法）。"""
        page = self.page
        page.window.opacity = 0
        page.update()
        self.mode = mode
        page.window.width, page.window.height = self.size_for(mode)
        page.title = title
        page.controls[:] = [content]
        page.update()
        with contextlib.suppress(Exception):
            await page.window.center()
        page.window.opacity = 1
        page.update()
        with contextlib.suppress(Exception):
            await asyncio.wait_for(page.window.to_front(), 3)

    async def show_launcher(self) -> None:
        from .launcher import Launcher
        if self.session is not None and self.workspace is not None:
            self.session.unsubscribe(self.workspace.on_session_change)
        self.session, self.workspace = None, None
        await self._swap(LAUNCHER, Launcher(self).build(), S.APP_NAME)

    async def show_workspace(self, session: ProjectSession, tabs: list[dict], active: int) -> None:
        from .workspace import Workspace
        if self.session is not None and self.workspace is not None:
            self.session.unsubscribe(self.workspace.on_session_change)
        self.session = session
        self.workspace = Workspace(self, session, tabs, active)
        await self._swap(WORKSPACE, self.workspace.build(), self.window_title())

    def window_title(self) -> str:
        return S.WINDOW_TITLE.format(name=self.session.name) if self.session else S.APP_NAME

    # ============================================================
    # 窗口事件与退出
    # ============================================================
    async def on_window_event(self, e: ft.WindowEvent) -> None:
        if e.type == ft.WindowEventType.RESIZED and self.settings.remember_size and self.mode is not None:
            w, h = self.page.window.width, self.page.window.height
            if w and h and self.page.window.opacity == 1:
                size = [round(w), round(h)]
                if self.mode == LAUNCHER:
                    self.settings.launcher_size = size
                else:
                    self.settings.workspace_size = size
        elif e.type == ft.WindowEventType.CLOSE:
            await self.request_close()

    async def request_close(self) -> None:
        """点了窗口的关闭按钮：工作区按设置回到启动器或退出；启动器直接退出。"""
        if self._busy:
            return
        self._busy = True
        try:
            if self.mode == WORKSPACE:
                await self.close_workspace(quit_app=self.settings.close_workspace == "quit")
            else:
                await self.quit()
        finally:
            self._busy = False

    async def close_workspace(self, quit_app: bool = False) -> None:
        if not await self.confirm_discard():
            return
        self.remember_recent()
        if quit_app:
            await self.quit()
        else:
            await self.show_launcher()

    async def quit(self) -> None:
        self.save_settings()
        self.page.window.prevent_close = False
        self.page.update()
        await self.page.window.destroy()

    # ============================================================
    # 项目：新建、打开、保存
    # ============================================================
    async def confirm_discard(self) -> bool:
        """当前项目有未保存的修改时询问；返回 False 表示取消。"""
        if self.session is None or not self.session.dirty:
            return True
        choice = await confirm_unsaved(self.page, self.p, self.session.name)
        if choice == "save":
            return await self.save()
        return choice == "discard"

    async def new_project(self, module_key: str | None = None) -> None:
        """新建空项目并打开工作区；从启动器的模块卡片进入时同时打开该模块。"""
        if not await self.confirm_discard():
            return
        tabs = [{"module": module_key, "state": {}}] if module_key else []
        await self.show_workspace(ProjectSession(), tabs, 1 if tabs else 0)

    async def open_project(self, path=None) -> bool:
        """打开项目文件，恢复上次的标签；没有保存过界面状态时按已有的数据打开对应模块。"""
        if path is None:
            files = await self.file_picker.pick_files(dialog_title=S.OPEN_PROJECT.rstrip("…"),
                                                      file_type=ft.FilePickerFileType.CUSTOM,
                                                      allowed_extensions=["nc"])
            if not files or not files[0].path:
                return False
            path = files[0].path
        if not await self.confirm_discard():
            return False
        try:
            session = await asyncio.to_thread(ProjectSession.open, path)
        except Exception as exc:  # noqa: BLE001 - 打不开的原因都显示给用户
            if not Path(path).is_file():
                self.settings.remove_recent(path)
                self.save_settings()
                if self.mode == LAUNCHER:
                    self.rebuild()
            show_error(self.page, self.p, S.OPEN_FAILED, S.FILE_ERROR.format(name=Path(path).name, error=exc), traceback.format_exc())
            return False
        tabs, active = read_ui_state(session.project.ui_state, {m.key for m in registry.available()})
        if not tabs:
            tabs = [{"module": registry.for_method(m).key, "state": {}} for m in session.project.methods()]
            active = 1 if tabs else 0
        await self.show_workspace(session, tabs, active)
        self.remember_recent()
        toast(self.page, self.p, S.OPENED.format(name=session.name))
        return True

    async def save(self, save_as: bool = False) -> bool:
        session = self.session
        if session is None:
            return False
        path = None
        if save_as or session.path is None:
            path = await self.file_picker.save_file(dialog_title=S.SAVE_PROJECT_AS.rstrip("…"),
                                                    file_name=f"{session.name}.nc",
                                                    file_type=ft.FilePickerFileType.CUSTOM,
                                                    allowed_extensions=["nc"])
            if not path:
                return False
        ui_state = self.workspace.ui_state() if self.workspace is not None else None
        try:
            saved = await asyncio.to_thread(session.write, path, ui_state)
        except Exception as exc:  # noqa: BLE001
            show_error(self.page, self.p, S.SAVE_FAILED, str(exc), traceback.format_exc())
            return False
        session.changed("saved")
        self.page.title = self.window_title()
        self.page.update()
        self.remember_recent()
        toast(self.page, self.p, S.SAVED_TO.format(path=saved))
        return True

    def remember_recent(self) -> None:
        if self.session is None or self.session.path is None:
            return
        modules = self.workspace.module_keys() if self.workspace is not None else []
        active = self.workspace.active_key() if self.workspace is not None else None
        self.settings.add_recent(self.session.path, modules, active)
        self.save_settings()

    # ============================================================
    # 设置、关于、其他
    # ============================================================
    def save_settings(self) -> None:
        with contextlib.suppress(OSError):
            save_settings(self.settings)

    def open_settings(self, e=None) -> None:
        from .components.settings_dialog import SettingsDialog
        SettingsDialog(self).show()

    def open_about(self, e=None) -> None:
        from .components.about_dialog import show_about
        show_about(self)

    async def open_url(self, url: str = REPO_URL) -> None:
        with contextlib.suppress(Exception):
            await self.url_launcher.launch_url(url)

    def not_yet(self, phase: str = "P3") -> None:
        toast(self.page, self.p, S.NOT_YET.format(phase=phase))

    @property
    def settings_file(self) -> Path:
        return settings_path()

    # ============================================================
    # 快捷键：Ctrl + 字母，同时接受 ⌘
    # ============================================================
    async def on_key(self, e: ft.KeyboardEvent) -> None:
        if not (e.ctrl or e.meta):
            return
        key = (e.key or "").lower()
        if key in (",", "comma"):
            self.open_settings()
        elif key == "o":
            await self.open_project()
        elif self.mode == WORKSPACE and self.workspace is not None:
            await self.workspace.on_shortcut(key, e.shift)


async def main(page: ft.Page) -> None:
    app = App(page)
    await app.start()


def run() -> None:
    """启动图形界面。"""
    ft.run(main, assets_dir=str(ASSETS))
