import flet as ft

from flet_utils import (
    MODULES,
    PALETTE,
    FieldSpec,
    SimpleCrudModule,
    close_dialog,
    execute,
    fetch_all,
    fetch_one,
    page_title,
    responsive_dialog_height,
    responsive_dialog_width,
    shell_card,
    show_dialog,
    table_view,
)
from supabase_service import admin_create_user, admin_delete_user, admin_update_user, supabase_enabled
from tenant_context import TenantContext


class Usuarios(SimpleCrudModule):
    def __init__(self, page: ft.Page, user: str | None = None, context: TenantContext | None = None) -> None:
        self.user = user
        self.context = context
        fields = [
            FieldSpec("username", "Usuario"),
            FieldSpec("password", "Contrasena", password=True),
            FieldSpec(
                "rol",
                "Rol",
                kind="dropdown",
                options=["Administrador", "Vendedor", "Supervisor"],
            ),
        ]
        if supabase_enabled():
            fields.insert(0, FieldSpec("email", "Correo electrónico"))
        super().__init__(
            page=page,
            title="Usuarios",
            subtitle="Gestiona cuentas y define permisos por rol sin cambiar la logica de seguridad.",
            table_name="usuarios",
            search_field="username",
            fields=fields,
            context=context,
        )
        if supabase_enabled():
            password_control = self.form_controls["password"]
            if isinstance(password_control, ft.TextField):
                password_control.helper_text = (
                    "Protegida por Supabase. Escribe una nueva solo para reemplazarla."
                )

    def _display_value(self, row: dict, field: FieldSpec) -> str:
        if supabase_enabled() and field.name == "password":
            return "••••••••"
        return super()._display_value(row, field)

    def validate(self) -> bool:
        if not supabase_enabled():
            return super().validate()
        required = ["email", "username", "rol"]
        if self.selected_id is None:
            required.append("password")
        if any(not (self.form_controls[name].value or "").strip() for name in required):
            self._notify("Complete correo, usuario, rol y contraseña para cuentas nuevas.", error=True)
            return False
        password = (self.form_controls["password"].value or "").strip()
        if password and len(password) < 8:
            self._notify("La contraseña debe tener al menos 8 caracteres.", error=True)
            return False
        return True

    def save(self, _: ft.ControlEvent | None = None) -> None:
        if self.context:
            self.context.require_store_admin()
        if not supabase_enabled():
            super().save()
            return
        if not self.validate():
            return
        email = (self.form_controls["email"].value or "").strip()
        username = (self.form_controls["username"].value or "").strip()
        password = (self.form_controls["password"].value or "").strip()
        role = str(self.form_controls["rol"].value or "Vendedor")
        try:
            if self.selected_id is None:
                admin_create_user(
                    email, password, username, role,
                    self.organization_id, self.context,
                )
                self._notify("Usuario creado. Ya puede iniciar sesión con su correo y contraseña.")
            else:
                profile = fetch_one("SELECT auth_user_id FROM usuarios WHERE id=? AND organization_id=?", (self.selected_id, self.organization_id))
                if not profile or not profile.get("auth_user_id"):
                    raise ValueError("El perfil no está vinculado a Supabase Auth")
                admin_update_user(str(profile["auth_user_id"]), email, password or None)
                execute(
                    "UPDATE usuarios SET email=?, username=?, rol=? WHERE id=? AND organization_id=?",
                    (email, username, role, self.selected_id, self.organization_id),
                )
                self._notify("Usuario actualizado.")
        except Exception as error:
            self._notify(f"No se pudo guardar el usuario: {error}", error=True)
            return
        self.clear_form()
        self.refresh()

    def _perform_delete(self, pin_value: str | None = None) -> None:
        if self.context:
            self.context.require_store_admin()
        if not supabase_enabled():
            super()._perform_delete(pin_value)
            return
        if self.selected_id is None:
            self._notify("Seleccione un usuario.", error=True)
            return
        try:
            profile = fetch_one("SELECT auth_user_id FROM usuarios WHERE id=? AND organization_id=?", (self.selected_id, self.organization_id))
            if not profile or not profile.get("auth_user_id"):
                raise ValueError("El perfil no está vinculado a Supabase Auth")
            admin_delete_user(str(profile["auth_user_id"]))
            self._notify("Usuario eliminado de Supabase Auth.")
        except Exception as error:
            self._notify(f"No se pudo eliminar el usuario: {error}", error=True)
            return
        self.clear_form()
        self.refresh()

    def _notify(self, message: str, error: bool = False) -> None:
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=PALETTE["danger"] if error else PALETTE["primary"],
            open=True,
        )
        self.page.update()

    def _role_id(self, role_name: str) -> int | None:
        role = fetch_one(
            "SELECT id FROM roles WHERE nombre = ? AND organization_id=?",
            (role_name, self.organization_id),
            context=self.context,
        )
        return int(role["id"]) if role else None

    def _current_modules_for_role(self, role_name: str) -> set[str]:
        role_id = self._role_id(role_name)
        if role_id is None:
            return set()
        rows = fetch_all(
            """
            SELECT p.modulo
            FROM permisos_rol pr
            JOIN permisos p ON p.id = pr.id_permiso
            WHERE pr.id_rol = ?
            """,
            (role_id,),
            context=self.context,
        )
        return {row["modulo"] for row in rows}

    def open_permissions(self, _: ft.ControlEvent | None = None) -> None:
        if self.context:
            self.context.require_store_admin()
        role_control = self.form_controls["rol"]
        role_name = role_control.value if isinstance(role_control, ft.Dropdown) else ""
        if not role_name:
            self._notify("Seleccione un usuario o al menos un rol para editar permisos.", error=True)
            return

        selected_modules = self._current_modules_for_role(role_name)
        checks: dict[str, ft.Checkbox] = {}
        module_controls: list[ft.Control] = []
        for module_name, label, _ in MODULES:
            if module_name == "dashboard":
                continue
            checkbox = ft.Checkbox(
                label=f"Ingresar a {label}",
                value=module_name in selected_modules,
                active_color=PALETTE["primary"],
            )
            checks[module_name] = checkbox
            module_controls.append(checkbox)

        def save_permissions(event: ft.ControlEvent) -> None:
            role_id = self._role_id(role_name)
            if role_id is None:
                close_dialog(self.page, dialog)
                self._notify("No se encontro el rol seleccionado.", error=True)
                return

            execute(
                "DELETE FROM permisos_rol WHERE id_rol = ?",
                (role_id,),
                context=self.context,
            )
            for module_name, checkbox in checks.items():
                if checkbox.value:
                    permission = fetch_one(
                        "SELECT id FROM permisos WHERE modulo = ?",
                        (module_name,),
                        context=self.context,
                    )
                    if permission:
                        execute(
                            "INSERT INTO permisos_rol (id_rol, id_permiso) VALUES (?, ?)",
                            (role_id, permission["id"]),
                            context=self.context,
                        )
            close_dialog(self.page, dialog)
            self._notify(f"Permisos guardados para el rol {role_name}.")

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(f"Permisos del rol {role_name}"),
            content=ft.Container(
                width=responsive_dialog_width(self.page, 460),
                height=responsive_dialog_height(self.page, 420),
                content=ft.Column(module_controls, scroll=ft.ScrollMode.AUTO),
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda event: close_dialog(self.page, dialog)),
                ft.ElevatedButton("Guardar", on_click=save_permissions),
            ],
        )
        show_dialog(self.page, dialog)

    def build(self) -> ft.Control:
        self.refresh()
        form = ft.Column(
            [
                page_title(self.title, self.subtitle),
                *self.form_controls.values(),
                ft.Row(
                    [
                        ft.ElevatedButton(
                            "Guardar",
                            icon=ft.Icons.SAVE_OUTLINED,
                            on_click=self.save,
                            style=ft.ButtonStyle(
                                shape=ft.RoundedRectangleBorder(radius=16),
                                bgcolor=PALETTE["primary"],
                                color=ft.Colors.WHITE,
                            ),
                        ),
                        ft.OutlinedButton("Limpiar", icon=ft.Icons.CLEANING_SERVICES_OUTLINED, on_click=self.clear_form),
                        ft.OutlinedButton("Eliminar", icon=ft.Icons.DELETE_OUTLINE, on_click=self.delete),
                    ],
                    wrap=True,
                ),
                ft.OutlinedButton(
                    "Configurar permisos del rol",
                    icon=ft.Icons.ADMIN_PANEL_SETTINGS_OUTLINED,
                    on_click=self.open_permissions,
                ),
            ],
            spacing=14,
            scroll=ft.ScrollMode.AUTO,
        )
        table_section = ft.Column(
            [
                ft.Row(
                    [
                        self.search,
                        ft.IconButton(ft.Icons.REFRESH_ROUNDED, on_click=lambda _: self.refresh()),
                    ]
                ),
                ft.Row(
                    [
                        ft.OutlinedButton("Anterior", on_click=self.prev_page),
                        ft.OutlinedButton("Siguiente", on_click=self.next_page),
                        self.page_label,
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                table_view(self.table, expand=True),
            ],
            expand=True,
            spacing=14,
        )
        return ft.ResponsiveRow(
            [
                ft.Container(col={"xs": 12, "lg": 5}, content=shell_card(form, expand=True)),
                ft.Container(col={"xs": 12, "lg": 7}, content=shell_card(table_section, expand=True)),
            ],
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        )
