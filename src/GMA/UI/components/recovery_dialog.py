# SPDX-FileCopyrightText: 2026 Jay Ma
# SPDX-License-Identifier: AGPL-3.0-only
"""
启动时发现上次没有正常关闭留下的自动备份：列出项目名、原来的文件和备份时间，可以打开或删除。
“以后再说”时备份保留，下次启动时再提示。
"""
from __future__ import annotations

import flet as ft

from .. import theme as th
from ..services import autosave
from ..services.text import short_path, when
from ..strings import S
from . import widgets as w
from .dialogs import close, dialog, show


class RecoveryDialog:
    def __init__(self, app, backups: list[autosave.Backup]):
        self.app = app
        self.backups = list(backups)
        self.list = ft.Column(spacing=8, tight=True, scroll=ft.ScrollMode.AUTO)
        self.box: ft.AlertDialog | None = None

    def show(self) -> None:
        p = self.app.p
        self.refresh(update=False)
        content = ft.Container(width=560, content=ft.Column([
            ft.Text(S.RECOVER_BODY, size=th.SIZE_BODY, color=p.muted),
            ft.Container(content=self.list, height=min(76 * len(self.backups), 320)),
        ], spacing=12, tight=True))
        self.box = dialog(p, S.RECOVER_TITLE, content, [ft.TextButton(S.RECOVER_LATER, on_click=lambda e: close(self.box))],
                          width=560)
        show(self.app.page, self.box)

    def refresh(self, update: bool = True) -> None:
        p = self.app.p
        rows = []
        for backup in self.backups:
            where = short_path(backup.source) if backup.source else S.RECOVER_NEVER_SAVED
            rows.append(ft.Container(
                padding=ft.Padding.symmetric(horizontal=12, vertical=10), border=ft.Border.all(1, p.border),
                border_radius=th.RADIUS_CONTROL,
                content=ft.Row([
                    ft.Icon(ft.Icons.RESTORE_PAGE_OUTLINED, size=22, color=p.primary),
                    ft.Column([w.text(backup.name, p, th.SIZE_BODY, bold=True, max_lines=1),
                               w.muted(where, p, th.SIZE_TINY, max_lines=1, tooltip=backup.source),
                               w.faint(S.RECOVER_SAVED_AT.format(time=when(backup.saved_at)), p, th.SIZE_TINY)],
                              spacing=1, tight=True, expand=True),
                    ft.TextButton(S.RECOVER_DELETE, on_click=lambda e, b=backup: self.delete(b)),
                    ft.FilledButton(S.RECOVER_OPEN, on_click=lambda e, b=backup: self.open(b)),
                ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER)))
        self.list.controls = rows
        if update:
            self.list.update()

    def open(self, backup: autosave.Backup) -> None:
        close(self.box)
        self.app.page.run_task(self.app.open_backup, backup)

    def delete(self, backup: autosave.Backup) -> None:
        autosave.remove_backup(backup.key)
        self.backups.remove(backup)
        self.app.toast(S.RECOVER_DELETED)
        if not self.backups:
            close(self.box)
        else:
            self.refresh()
