import sqlite3
from typing import Callable

import flet as ft

from flet_utils import DEFAULT_COMPANY_LOGO, PALETTE, get_company_info, image_base64, shell_card


class Login:
    db_name = "database.db"

    def __init__(
        self,
        page: ft.Page,
        on_success: Callable[[str, str], None],
        on_register: Callable[[], None],
    ) -> None:
        self.page = page
        self.on_success = on_success
        self.on_register = on_register
        self.company = get_company_info()
        self.username = ft.TextField(
            label="Nombre de usuario",
            border_radius=16,
            filled=True,
            bgcolor=PALETTE["surface_alt"],
            prefix_icon=ft.Icons.PERSON_OUTLINE,
        )
        self.password = ft.TextField(
            label="Contrasena",
            password=True,
            can_reveal_password=True,
            border_radius=16,
            filled=True,
            bgcolor=PALETTE["surface_alt"],
            prefix_icon=ft.Icons.LOCK_OUTLINE,
            on_submit=self.login,
        )

    def validacion(self, user: str, password: str) -> bool:
        return len(user.strip()) > 0 and len(password.strip()) > 0

    def _notify(self, message: str, error: bool = False) -> None:
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=PALETTE["danger"] if error else PALETTE["primary"],
            open=True,
        )
        self.page.update()

    def login(self, _: ft.ControlEvent | None = None) -> None:
        user = self.username.value or ""
        password = self.password.value or ""

        if not self.validacion(user, password):
            self._notify("Llene todas las casillas.", error=True)
            return

        try:
            with sqlite3.connect(self.db_name) as connection:
                cursor = connection.cursor()
                cursor.execute(
                    "SELECT rol FROM usuarios WHERE username=? AND password=?",
                    (user, password),
                )
                result = cursor.fetchone()
        except sqlite3.Error as error:
            self._notify(f"No se pudo abrir la base de datos: {error}", error=True)
            return

        if not result:
            self.username.value = ""
            self.password.value = ""
            self.page.update()
            self._notify("Usuario y/o contrasena incorrecta.", error=True)
            return

        rol = result[0]
        self.username.value = ""
        self.password.value = ""
        self.page.update()
        self._notify("Ingreso correcto.")
        self.on_success(user, rol)

    def _hero_panel(self) -> ft.Control:
        logo = image_base64(self.company["image_path"], DEFAULT_COMPANY_LOGO)
        return shell_card(
            ft.Column(
                [
                    ft.Container(
                        width=300,
                        height=260,
                        border_radius=8,
                        alignment=ft.Alignment(0, 0),
                        content=ft.Image(
                            src=logo,
                            width=300,
                            height=260,
                            fit="contain",
                        )
                        if logo
                        else ft.Icon(ft.Icons.STOREFRONT, size=90),
                    ),
                    ft.Text(
                        self.company["nombre"],
                        size=28,
                        weight=ft.FontWeight.BOLD,
                        color=PALETTE["text"],
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Text(
                        self.company["direccion"],
                        size=14,
                        color=PALETTE["muted"],
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Text(
                        self.company["telefono"],
                        size=14,
                        color=PALETTE["muted"],
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Text(
                        self.company["email"],
                        size=14,
                        color=PALETTE["muted"],
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Container(height=12),
                    ft.Text(
                        "Interfaz renovada en Flet para un punto de venta mas claro, rapido y moderno.",
                        size=14,
                        color=PALETTE["text"],
                        text_align=ft.TextAlign.CENTER,
                    ),
                ],
                spacing=10,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=32,
            expand=True,
        )

    def _form_panel(self) -> ft.Control:
        return shell_card(
            ft.Column(
                [
                    ft.Text(
                        "Inicio de sesion",
                        size=30,
                        weight=ft.FontWeight.BOLD,
                        color=PALETTE["text"],
                    ),
                    ft.Text(
                        "Accede al sistema con tus credenciales actuales.",
                        color=PALETTE["muted"],
                    ),
                    ft.Container(height=8),
                    self.username,
                    self.password,
                    ft.ElevatedButton(
                        "Iniciar",
                        icon=ft.Icons.LOGIN_ROUNDED,
                        height=50,
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=16),
                            bgcolor=PALETTE["primary"],
                            color=ft.Colors.WHITE,
                        ),
                        on_click=self.login,
                    ),
                    ft.OutlinedButton(
                        "Registrar usuario",
                        icon=ft.Icons.PERSON_ADD_ALT_1,
                        height=50,
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=16),
                            side=ft.BorderSide(1, PALETTE["border"]),
                            color=PALETTE["primary"],
                            bgcolor=PALETTE["surface"],
                        ),
                        on_click=lambda _: self.on_register(),
                    ),
                    ft.Container(height=10),
                    ft.Text(
                        "Version 4.2.1",
                        color=PALETTE["secondary"],
                        weight=ft.FontWeight.W_600,
                    ),
                ],
                spacing=14,
                tight=True,
            ),
            padding=32,
            expand=True,
        )

    def build(self) -> ft.Control:
        gradient = ft.LinearGradient(
            begin=ft.Alignment(-1, -1),
            end=ft.Alignment(1, 1),
            colors=["#D8E9FF", "#ECF5FF", "#F9FBFF"],
        )
        return ft.Container(
            expand=True,
            gradient=gradient,
            padding=32,
            content=ft.ResponsiveRow(
                [
                    ft.Container(col={"xs": 12, "md": 6}, content=self._hero_panel()),
                    ft.Container(col={"xs": 12, "md": 6}, content=self._form_panel()),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )


class Registro:
    db_name = "database.db"

    def __init__(self, page: ft.Page, on_back: Callable[[], None]) -> None:
        self.page = page
        self.on_back = on_back
        self.company = get_company_info()
        self.username = ft.TextField(
            label="Nombre de usuario",
            border_radius=16,
            filled=True,
            bgcolor=PALETTE["surface_alt"],
            prefix_icon=ft.Icons.PERSON_OUTLINE,
        )
        self.password = ft.TextField(
            label="Contrasena",
            password=True,
            can_reveal_password=True,
            border_radius=16,
            filled=True,
            bgcolor=PALETTE["surface_alt"],
            prefix_icon=ft.Icons.LOCK_OUTLINE,
        )
        self.rol = ft.Dropdown(
            label="Rol de usuario",
            border_radius=16,
            filled=True,
            bgcolor=PALETTE["surface_alt"],
            options=[
                ft.dropdown.Option("Vendedor"),
                ft.dropdown.Option("Supervisor"),
            ],
        )
        self.key = ft.TextField(
            label="Codigo de registro",
            password=True,
            can_reveal_password=True,
            border_radius=16,
            filled=True,
            bgcolor=PALETTE["surface_alt"],
            prefix_icon=ft.Icons.VPN_KEY_OUTLINED,
            on_submit=self.registro,
        )

    def _notify(self, message: str, error: bool = False) -> None:
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=PALETTE["danger"] if error else PALETTE["primary"],
            open=True,
        )
        self.page.update()

    def validacion(self, user: str, password: str, rol: str) -> bool:
        return len(user.strip()) > 0 and len(password.strip()) > 0 and len(rol.strip()) > 0

    def eje_consulta(self, consulta: str, parametros: tuple) -> None:
        with sqlite3.connect(self.db_name) as connection:
            cursor = connection.cursor()
            cursor.execute(consulta, parametros)
            connection.commit()

    def registro(self, _: ft.ControlEvent | None = None) -> None:
        user = self.username.value or ""
        password = self.password.value or ""
        rol = self.rol.value or ""
        key = self.key.value or ""

        if not self.validacion(user, password, rol):
            self._notify("Llene todos los datos.", error=True)
            return

        if len(password) < 6:
            self._notify("Contrasena demasiado corta.", error=True)
            return

        if key != "1234":
            self._notify("Error al ingresar el codigo de registro.", error=True)
            return

        try:
            self.eje_consulta(
                "INSERT INTO usuarios VALUES (?,?,?,?)",
                (None, user, password, rol),
            )
        except sqlite3.Error as error:
            self._notify(f"No se pudo crear el usuario: {error}", error=True)
            return

        self._notify("Usuario creado correctamente.")
        self.on_back()

    def build(self) -> ft.Control:
        logo = image_base64(self.company["image_path"], DEFAULT_COMPANY_LOGO)
        return ft.Container(
            expand=True,
            padding=32,
            gradient=ft.LinearGradient(
                begin=ft.Alignment(0, -1),
                end=ft.Alignment(0, 1),
                colors=["#DCEBFF", "#F4F8FF"],
            ),
            content=ft.ResponsiveRow(
                [
                    ft.Container(
                        col={"xs": 12, "md": 5},
                        content=shell_card(
                            ft.Column(
                                [
                                    ft.Image(src=logo, width=280, height=220, fit="contain")
                                    if logo
                                    else ft.Icon(ft.Icons.PERSON_ADD, size=80),
                                    ft.Text(
                                        "Nuevo acceso al sistema",
                                        size=26,
                                        weight=ft.FontWeight.BOLD,
                                        color=PALETTE["text"],
                                        text_align=ft.TextAlign.CENTER,
                                    ),
                                    ft.Text(
                                        "Mantuvimos la misma logica de usuarios y roles, solo cambiando la experiencia visual.",
                                        text_align=ft.TextAlign.CENTER,
                                        color=PALETTE["muted"],
                                    ),
                                ],
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                spacing=12,
                            ),
                            padding=28,
                            expand=True,
                        ),
                    ),
                    ft.Container(
                        col={"xs": 12, "md": 7},
                        content=shell_card(
                            ft.Column(
                                [
                                    ft.Text("Registro", size=30, weight=ft.FontWeight.BOLD),
                                    self.username,
                                    self.password,
                                    self.rol,
                                    self.key,
                                    ft.ElevatedButton(
                                        "Crear usuario",
                                        icon=ft.Icons.SAVE_OUTLINED,
                                        height=50,
                                        style=ft.ButtonStyle(
                                            shape=ft.RoundedRectangleBorder(radius=16),
                                            bgcolor=PALETTE["primary"],
                                            color=ft.Colors.WHITE,
                                        ),
                                        on_click=self.registro,
                                    ),
                                    ft.TextButton(
                                        "Volver al inicio",
                                        icon=ft.Icons.ARROW_BACK_ROUNDED,
                                        on_click=lambda _: self.on_back(),
                                    ),
                                ],
                                spacing=14,
                            ),
                            padding=32,
                            expand=True,
                        ),
                    ),
                ]
            ),
        )
