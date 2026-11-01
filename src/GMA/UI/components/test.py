"""OpenGMA 演示：启动器 → 关闭自身 → 打开带浏览器式标签页的工作区窗口（Flet 1.0）

运行：
    python gma_workspace_demo.py              # 启动器
    python gma_workspace_demo.py XRD          # 直接打开工作区，并打开 XRD 标签（启动器内部就是这样调用的）
"""
import subprocess
import sys

import flet as ft

MODULES = {
    "XRD": ft.Icons.SHOW_CHART,
    "Raman": ft.Icons.WAVES,
    "XPS": ft.Icons.INSIGHTS,
}


# ======================= 公共：设置、关于 =======================
def make_appbar(page: ft.Page, extra_actions=None) -> ft.AppBar:
    def close_dialog(e):
        page.pop_dialog()

    about_dlg = ft.AlertDialog(
        title=ft.Text("关于 OpenGMA"),
        content=ft.Text("版本 0.1.0\n材料表征数据处理工具"),
        actions=[ft.TextButton("关闭", on_click=close_dialog)],
    )
    settings_dlg = ft.AlertDialog(
        title=ft.Text("设置"),
        content=ft.Text("全局设置保存到配置文件，两个窗口都读取它。"),
        actions=[ft.TextButton("关闭", on_click=close_dialog)],
    )
    return ft.AppBar(
        title=ft.Text("OpenGMA"),
        actions=(extra_actions or []) + [
            ft.IconButton(ft.Icons.SETTINGS, tooltip="设置",
                          on_click=lambda e: page.show_dialog(settings_dlg)),
            ft.IconButton(ft.Icons.INFO_OUTLINE, tooltip="关于",
                          on_click=lambda e: page.show_dialog(about_dlg)),
        ],
    )


# ======================= 启动器窗口 =======================
async def launcher(page: ft.Page):
    page.title = "OpenGMA"
    page.window.width = 520
    page.window.height = 360
    page.window.resizable = False
    await page.window.center()
    page.appbar = make_appbar(page)

    async def open_workspace(name: str):
        # 放进库后改为: [sys.executable, "-m", "gma.gui", name]
        subprocess.Popen([sys.executable, __file__, name])
        await page.window.close()          # 关闭启动器

    def card(name, icon):
        async def on_click(e):
            await open_workspace(name)

        return ft.Card(
            content=ft.Container(
                content=ft.Column(
                    [ft.Icon(icon, size=40), ft.Text(name, size=16)],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                width=130, height=110, ink=True, on_click=on_click,
            )
        )

    page.add(
        ft.Container(
            content=ft.Row([card(n, i) for n, i in MODULES.items()],
                           alignment=ft.MainAxisAlignment.CENTER),
            alignment=ft.Alignment.CENTER,
            expand=True,
        )
    )


# ======================= 模块视图 =======================
class ModuleView(ft.Column):
    def __init__(self, name: str):
        super().__init__(expand=True, spacing=12)
        self.count = 0
        self.info = ft.Text("尚未处理数据")
        self.controls = [
            ft.Text(f"{name} 分析", size=22, weight=ft.FontWeight.BOLD),
            self.info,
            ft.Button("模拟处理一次", on_click=self.process),
        ]

    def process(self, e):
        self.count += 1
        self.info.value = f"已处理 {self.count} 次"
        self.update()


# ======================= 工作区窗口（浏览器式标签） =======================
def make_workspace(first_module: str):
    async def workspace(page: ft.Page):
        page.title = "OpenGMA"
        page.window.width = 1100
        page.window.height = 720
        page.window.min_width = 700
        page.window.min_height = 480
        await page.window.center()

        tab_bar = ft.TabBar(tabs=[], expand=True)
        tab_view = ft.TabBarView(controls=[], expand=True)
        tabs = ft.Tabs(length=0, content=ft.Column([tab_bar, tab_view], expand=True),
                       expand=True)
        open_counts: dict[str, int] = {}

        empty_hint = ft.Container(
            content=ft.Text("点击右上角 + 打开一个分析模块", size=16),
            alignment=ft.Alignment.CENTER,
            expand=True,
        )
        body = ft.Container(expand=True)

        def refresh():
            body.content = tabs if tab_bar.tabs else empty_hint
            page.update()

        def open_module(name: str):
            open_counts[name] = open_counts.get(name, 0) + 1
            n = open_counts[name]
            title = name if n == 1 else f"{name} ({n})"

            view = ft.Container(content=ModuleView(name), padding=20)
            tab = ft.Tab(
                label=ft.Row(
                    [ft.Text(title),
                     ft.IconButton(ft.Icons.CLOSE, icon_size=14,
                                   on_click=lambda e: close_tab(tab, view))],
                    tight=True, spacing=2,
                ),
                icon=MODULES[name],
            )
            tab_bar.tabs.append(tab)
            tab_view.controls.append(view)
            tabs.length = len(tab_bar.tabs)
            tabs.selected_index = tabs.length - 1
            refresh()

        def close_tab(tab, view):
            idx = tab_bar.tabs.index(tab)
            tab_bar.tabs.pop(idx)
            tab_view.controls.pop(idx)
            tabs.length = len(tab_bar.tabs)
            tabs.selected_index = max(0, min(tabs.selected_index, tabs.length - 1))
            refresh()

        new_tab_menu = ft.PopupMenuButton(
            icon=ft.Icons.ADD,
            tooltip="新建标签页",
            items=[
                ft.PopupMenuItem(content=name, icon=icon,
                                 on_click=lambda e, n=name: open_module(n))
                for name, icon in MODULES.items()
            ],
        )

        page.appbar = make_appbar(page, extra_actions=[new_tab_menu])
        page.add(body)
        open_module(first_module)

    return workspace


if __name__ == "__main__":
    if len(sys.argv) > 1:
        ft.run(make_workspace(sys.argv[1]))
    else:
        ft.run(launcher)