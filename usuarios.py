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
    shell_card,
    show_dialog,
    table_view,
)


class Usuarios(SimpleCrudModule):
    def __init__(self, page: ft.Page, user: str | None = None) -> None:
        self.user = user
        super().__init__(
            page=page,
            title="Usuarios",
            subtitle="Gestiona cuentas y define permisos por rol sin cambiar la logica de seguridad.",
            table_name="usuarios",
            search_field="username",
            fields=[
                FieldSpec("username", "Usuario"),
                FieldSpec("password", "Contrasena", password=True),
                FieldSpec(
                    "rol",
                    "Rol",
                    kind="dropdown",
                    options=["Administrador", "Vendedor", "Supervisor"],
                ),
            ],
        )

    def _notify(self, message: str, error: bool = False) -> None:
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=PALETTE["danger"] if error else PALETTE["primary"],
            open=True,
        )
        self.page.update()

    def _role_id(self, role_name: str) -> int | None:
        role = fetch_one("SELECT id FROM roles WHERE nombre = ?", (role_name,))
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
        )
        return {row["modulo"] for row in rows}

    def open_permissions(self, _: ft.ControlEvent | None = None) -> None:
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

            execute("DELETE FROM permisos_rol WHERE id_rol = ?", (role_id,))
            for module_name, checkbox in checks.items():
                if checkbox.value:
                    permission = fetch_one(
                        "SELECT id FROM permisos WHERE modulo = ?",
                        (module_name,),
                    )
                    if permission:
                        execute(
                            "INSERT INTO permisos_rol (id_rol, id_permiso) VALUES (?, ?)",
                            (role_id, permission["id"]),
                        )
            close_dialog(self.page, dialog)
            self._notify(f"Permisos guardados para el rol {role_name}.")

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(f"Permisos del rol {role_name}"),
            content=ft.Container(
                width=460,
                height=420,
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
        )
