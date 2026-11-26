from typing import Callable

import flet as ft

from flet_utils import DB_NAME, DEFAULT_COMPANY_LOGO, PALETTE, execute, fetch_one, get_company_info, image_base64, shell_card
from supabase_service import register_from_invitation, register_local_from_invitation, request_password_recovery, sign_in, supabase_enabled
from tenant_context import TenantContext


class Login:
    db_name = DB_NAME

    def __init__(
        self,
        page: ft.Page,
        on_success: Callable[[TenantContext], None],
        on_register: Callable[[], None],
    ) -> None:
        self.page = page
        self.on_success = on_success
        self.on_register = on_register
        self.username = ft.TextField(
            label="Correo electrónico" if supabase_enabled() else "Nombre de usuario",
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
            if supabase_enabled():
                identity = sign_in(user, password)
                context = identity.tenant_context()
            else:
                result = fetch_one(
                    "SELECT rol FROM usuarios WHERE username=? AND password=?",
                    (user, password),
                )
                if not result:
                    raise PermissionError("Usuario y/o contraseña incorrecta")
                profile = fetch_one("SELECT organization_id FROM usuarios WHERE username=?", (user,)) or {}
                is_platform_admin = str(user).strip().casefold() == "admin"
                context = TenantContext(
                    auth_user_id=f"local:{user}", email="", username=user,
                    organization_id=None if is_platform_admin else str(profile.get("organization_id") or "00000000-0000-0000-0000-000000000001"),
                    role="platform_admin" if is_platform_admin else ("store_admin" if str(result["rol"]).lower() == "administrador" else "cashier"),
                    is_platform_admin=is_platform_admin,
                )
        except Exception as error:
            self.username.value = ""
            self.password.value = ""
            self.page.update()
            self._notify(f"No fue posible iniciar sesión: {error}", error=True)
            return
        self.username.value = ""
        self.password.value = ""
        self.page.update()
        self._notify("Ingreso correcto.")
        self.on_success(context)

    def _hero_panel(self) -> ft.Control:
        return shell_card(
            ft.Column(
                [
                    ft.Container(
                        width=300,
                        height=260,
                        border_radius=8,
                        alignment=ft.Alignment(0, 0),
                        content=ft.Icon(ft.Icons.POINT_OF_SALE_ROUNDED, size=90),
                    ),
                    ft.Text(
                        "Sistema de Punto de Venta",
                        size=28,
                        weight=ft.FontWeight.BOLD,
                        color=PALETTE["text"],
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Container(height=12),
                    ft.Text(
                        "Conectando personas a través de la tecnología.",
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
                        visible=not supabase_enabled(),
                    ),
                    ft.TextButton(
                        "Recuperar contraseña",
                        on_click=self._recover_password,
                        visible=supabase_enabled(),
                    ),
                    ft.Container(height=10),
                    ft.Text(
                        "Version 1.1.1",
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

    def _recover_password(self, _: ft.ControlEvent | None = None) -> None:
        email = (self.username.value or "").strip()
        if "@" not in email:
            self._notify("Escriba su correo en el campo de inicio de sesión.", error=True)
            return
        try:
            request_password_recovery(email)
            self._notify("Supabase envió el enlace de recuperación si el correo existe.")
        except Exception as error:
            self._notify(f"No fue posible solicitar la recuperación: {error}", error=True)

    def _show_invitation_dialog(self, _: ft.ControlEvent | None = None) -> None:
        token = ft.TextField(label="Token de invitación")
        email = ft.TextField(label="Correo invitado")
        password = ft.TextField(label="Nueva contraseña", password=True, can_reveal_password=True)

        def accept(_event: ft.ControlEvent) -> None:
            try:
                if supabase_enabled():
                    register_from_invitation(token.value or "", email.value or "", password.value or "")
                else:
                    register_local_from_invitation(token.value or "", email.value or "", password.value or "")
                dialog.open = False
                self.username.value = email.value
                self._notify("Invitación aceptada. Confirme su correo si Supabase se lo solicita y luego inicie sesión.")
            except Exception as error:
                self._notify(f"No fue posible aceptar la invitación: {error}", error=True)

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Aceptar invitación al almacén"),
            content=ft.Column([token, email, password], tight=True, width=460),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _: setattr(dialog, "open", False)),
                ft.ElevatedButton("Crear mi cuenta", on_click=accept),
            ],
        )
        self.page.show_dialog(dialog)

    def build(self) -> ft.Control:
        gradient = ft.LinearGradient(
            begin=ft.Alignment(-1, -1),
            end=ft.Alignment(1, 1),
            colors=["#D8E9FF", "#ECF5FF", "#F9FBFF"],
        )
        return ft.Container(
            expand=True,
            gradient=gradient,
            padding=ft.Padding.symmetric(horizontal=20, vertical=24),
            content=ft.Column(
                [
                    ft.ResponsiveRow(
                        [
                            ft.Container(col={"xs": 12, "md": 6}, content=self._hero_panel()),
                            ft.Container(col={"xs": 12, "md": 6}, content=self._form_panel()),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        run_spacing=16,
                    ),
                ],
                expand=True,
                scroll=ft.ScrollMode.AUTO,
            ),
        )


class Registro:
    db_name = DB_NAME

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
        execute(consulta, parametros)

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
        except Exception as error:
            self._notify(f"No se pudo crear el usuario: {error}", error=True)
            return

        self._notify("Usuario creado correctamente.")
        self.on_back()

    def build(self) -> ft.Control:
        logo = image_base64(self.company["image_path"], DEFAULT_COMPANY_LOGO)
        return ft.Container(
            expand=True,
            padding=ft.Padding.symmetric(horizontal=20, vertical=24),
            gradient=ft.LinearGradient(
                begin=ft.Alignment(0, -1),
                end=ft.Alignment(0, 1),
                colors=["#DCEBFF", "#F4F8FF"],
            ),
            content=ft.Column(
                [
                    ft.ResponsiveRow(
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
                        ],
                        run_spacing=16,
                    ),
                ],
                expand=True,
                scroll=ft.ScrollMode.AUTO,
            ),
        )
