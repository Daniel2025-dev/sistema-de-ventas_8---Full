import flet as ft

from container import Container
from flet_utils import APP_TITLE, PALETTE, app_theme, apply_visual_theme, ensure_app_schema
from login import Login, Registro


class Manager:
    def __init__(self) -> None:
        self.page: ft.Page | None = None
        self.current_view: ft.Control | None = None

    def _configure_page(self, page: ft.Page) -> None:
        page.title = APP_TITLE
        page.theme = app_theme()
        page.bgcolor = PALETTE["bg"]
        page.padding = 0
        page.spacing = 0
        page.window_width = 1280
        page.window_height = 760
        page.window_min_width = 1180
        page.window_min_height = 720
        page.window_bgcolor = PALETTE["bg"]
        page.vertical_alignment = ft.MainAxisAlignment.START
        page.horizontal_alignment = ft.CrossAxisAlignment.START

    def _mount(self, control: ft.Control) -> None:
        if not self.page:
            return
        apply_visual_theme(control)
        self.page.controls.clear()
        self.page.add(control)
        self.current_view = control
        self.page.update()

    def show_login(self) -> None:
        if not self.page:
            return
        self._mount(
            Login(
                page=self.page,
                on_success=self.show_container,
                on_register=self.show_register,
            ).build()
        )

    def show_register(self) -> None:
        if not self.page:
            return
        self._mount(
            Registro(
                page=self.page,
                on_back=self.show_login,
            ).build()
        )

    def show_container(self, user: str, rol: str) -> None:
        if not self.page:
            return
        self._mount(
            Container(
                page=self.page,
                user=user,
                rol=rol,
                on_logout=self.show_login,
            ).build()
        )

    def main(self, page: ft.Page) -> None:
        self.page = page
        self._configure_page(page)
        ensure_app_schema()
        self.show_login()


def main() -> None:
    manager = Manager()
    ft.run(main=manager.main, assets_dir=".")


if __name__ == "__main__":
    main()
