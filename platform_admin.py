from __future__ import annotations

import hashlib
import secrets
import uuid

import flet as ft

from database import fetch_all, is_postgres, transaction
from flet_utils import PALETTE, page_title, shell_card
from role_permissions import DEFAULT_ROLE_MODULES
from supabase_service import admin_create_user, admin_delete_user
from tenant_context import TenantContext


def create_store_with_invitation(context: TenantContext, name: str, owner_email: str) -> tuple[str, str]:
    if not context.is_platform_admin:
        raise PermissionError("Solo la administración de plataforma puede crear almacenes")
    organization_id = str(uuid.uuid4())
    invitation_id = str(uuid.uuid4())
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    email = owner_email.strip().casefold()
    display_name = name.strip() or "Mi negocio"
    with transaction(context) as cursor:
        lock_suffix = " FOR UPDATE" if is_postgres() else ""
        cursor.execute(
            """SELECT id, organization_id FROM organization_invitations
               WHERE email=? AND role='store_admin' AND status='pending'
               ORDER BY created_at DESC LIMIT 1""" + lock_suffix, (email,),
        )
        pending = cursor.fetchone()
        if pending:
            expiry = "datetime('now', '+48 hours')" if not is_postgres() else "now()+interval '48 hours'"
            cursor.execute(
                "UPDATE organization_invitations SET token_hash=?, delivery_status='local', "
                f"delivery_attempts=delivery_attempts+1, expires_at={expiry} WHERE id=?",
                (token_hash, pending["id"]),
            )
            return str(pending["organization_id"]), token
        cursor.execute("INSERT INTO organizations(id, name, created_by) VALUES (?, ?, ?)", (organization_id, display_name, context.auth_user_id))
        cursor.execute("INSERT INTO empresa(organization_id, nombre, direccion, telefono, email, website, image_path, tipo_id, numero_id) VALUES (?, ?, '', '', '', '', '', '', '')", (organization_id, display_name))
        for role_name in ("Administrador", "Supervisor", "Vendedor"):
            if is_postgres():
                cursor.execute(
                    "INSERT INTO roles(organization_id, nombre) VALUES (?, ?) ON CONFLICT DO NOTHING",
                    (organization_id, role_name),
                )
            else:
                # La base SQLite heredada tiene UNIQUE(nombre), no el índice
                # compuesto usado por PostgreSQL. En la demo reutiliza esos roles.
                cursor.execute(
                    "INSERT OR IGNORE INTO roles(organization_id, nombre) VALUES (?, ?)",
                    (organization_id, role_name),
                )
        for role_name, modules in DEFAULT_ROLE_MODULES.items():
            for module_name in modules:
                if is_postgres():
                    cursor.execute(
                        """INSERT INTO permisos_rol(id_rol, id_permiso)
                           SELECT r.id, p.id FROM roles r CROSS JOIN permisos p
                           WHERE r.organization_id=? AND r.nombre=? AND p.modulo=?
                           ON CONFLICT DO NOTHING""",
                        (organization_id, role_name, module_name),
                    )
                else:
                    cursor.execute(
                        """INSERT OR IGNORE INTO permisos_rol(id_rol, id_permiso)
                           SELECT r.id, p.id FROM roles r CROSS JOIN permisos p
                           WHERE r.nombre=? AND p.modulo=?""",
                        (role_name, module_name),
                    )
        cursor.execute("INSERT INTO organization_invitations(id, organization_id, email, role, token_hash, status, delivery_status, delivery_attempts, invited_by, expires_at) VALUES (?, ?, ?, 'store_admin', ?, 'pending', 'local', 1, ?, datetime('now', '+48 hours'))" if not is_postgres() else "INSERT INTO organization_invitations(id, organization_id, email, role, token_hash, status, delivery_status, delivery_attempts, invited_by) VALUES (?, ?, ?, 'store_admin', ?, 'pending', 'local', 1, ?)", (invitation_id, organization_id, email, token_hash, context.auth_user_id))
    return organization_id, token


def delete_store(context: TenantContext, organization_id: str) -> list[str]:
    """Permanently remove one tenant and return Auth users safe to delete."""
    if not context.is_platform_admin:
        raise PermissionError("Solo la administración de plataforma puede eliminar negocios")
    if not organization_id:
        raise ValueError("Seleccione un negocio")

    auth_user_ids: list[str] = []
    with transaction(context) as cursor:
        cursor.execute(
            "SELECT id FROM organizations WHERE id=?" + (" FOR UPDATE" if is_postgres() else ""),
            (organization_id,),
        )
        if not cursor.fetchone():
            raise ValueError("El negocio ya no existe")
        cursor.execute(
            "SELECT auth_user_id FROM organization_memberships "
            "WHERE organization_id=? AND auth_user_id IS NOT NULL",
            (organization_id,),
        )
        candidate_ids = [str(row["auth_user_id"]) for row in cursor.fetchall()]

        for table_name in ("ventas", "cotizaciones", "pedidos", "gastos"):
            cursor.execute(f"DELETE FROM {table_name} WHERE organization_id=?", (organization_id,))
        cursor.execute("DELETE FROM sale_operations WHERE organization_id=?", (organization_id,))
        for table_name in (
            "inventario", "caja", "clientes", "proveedores", "categorias",
            "sucursal", "impuestos", "moneda",
        ):
            cursor.execute(f"DELETE FROM {table_name} WHERE organization_id=?", (organization_id,))
        cursor.execute(
            "DELETE FROM permisos_rol WHERE id_rol IN "
            "(SELECT id FROM roles WHERE organization_id=?)",
            (organization_id,),
        )
        cursor.execute("DELETE FROM roles WHERE organization_id=?", (organization_id,))
        cursor.execute("DELETE FROM organization_invitations WHERE organization_id=?", (organization_id,))
        cursor.execute("DELETE FROM organization_memberships WHERE organization_id=?", (organization_id,))
        cursor.execute("DELETE FROM usuarios WHERE organization_id=?", (organization_id,))
        cursor.execute("DELETE FROM empresa WHERE organization_id=?", (organization_id,))
        cursor.execute("DELETE FROM organizations WHERE id=?", (organization_id,))

        for user_id in candidate_ids:
            cursor.execute(
                "SELECT COUNT(*) AS total FROM organization_memberships WHERE auth_user_id=?",
                (user_id,),
            )
            membership_count = int(cursor.fetchone()["total"])
            cursor.execute("SELECT COUNT(*) AS total FROM platform_admins WHERE auth_user_id=?", (user_id,))
            platform_count = int(cursor.fetchone()["total"])
            if membership_count == 0 and platform_count == 0:
                auth_user_ids.append(user_id)
    return auth_user_ids


class PlatformAdminView:
    def __init__(self, page: ft.Page, context: TenantContext, on_enter_pos, on_logout) -> None:
        self.page = page
        self.context = context
        self.on_enter_pos = on_enter_pos
        self.on_logout = on_logout
        self.name = ft.TextField(label="Nombre del almacén (opcional)")
        self.email = ft.TextField(label="Correo de la administradora")
        self.password = ft.TextField(
            label="Contraseña temporal", password=True, can_reveal_password=True,
        )
        self.password.helper_text = (
            "Mínimo 8 caracteres. La administradora puede cambiarla luego."
        )
        self.result = ft.Text(selectable=True, color=PALETTE["muted"])
        organizations = fetch_all(
            """SELECT o.id, COALESCE(NULLIF(e.nombre, ''), o.name, 'Mi negocio') AS nombre
               FROM organizations o LEFT JOIN empresa e ON e.organization_id=o.id
               ORDER BY e.id, o.name""", context=context,
        )
        self.organization = ft.Dropdown(
            label="Comercio para entrar al POS",
            options=[ft.dropdown.Option(key=str(row["id"]), text=str(row["nombre"])) for row in organizations],
            value=str(organizations[0]["id"]) if organizations else None,
        )

    def _selected_name(self) -> str:
        selected = str(self.organization.value or "")
        for option in self.organization.options or []:
            if str(option.key) == selected:
                return str(option.text or "Mi negocio")
        return "Mi negocio"

    def confirm_delete(self, _=None) -> None:
        organization_id = str(self.organization.value or "")
        if not organization_id:
            self.result.value = "Seleccione un negocio para eliminar."
            self.result.color = PALETTE["danger"]
            self.page.update()
            return
        expected_name = self._selected_name()
        confirmation = ft.TextField(
            label=f'Escriba "{expected_name}" para confirmar', autofocus=True
        )

        def perform_delete(_event: ft.ControlEvent) -> None:
            if (confirmation.value or "").strip() != expected_name:
                confirmation.error_text = "El nombre no coincide."
                self.page.update()
                return
            try:
                auth_users = delete_store(self.context, organization_id)
                for user_id in auth_users:
                    if not user_id.startswith("local:"):
                        try:
                            admin_delete_user(user_id)
                        except Exception:
                            # La membresía ya fue retirada; una cuenta Auth huérfana
                            # no puede entrar ni ver datos de otro comercio.
                            pass
                self.organization.options = [
                    option for option in (self.organization.options or [])
                    if str(option.key) != organization_id
                ]
                self.organization.value = (
                    str(self.organization.options[0].key)
                    if self.organization.options else None
                )
                dialog.open = False
                self.result.value = f'Negocio "{expected_name}" eliminado definitivamente.'
                self.result.color = PALETTE["success"]
                self.page.update()
            except Exception as error:
                self.result.value = f"No fue posible eliminar el negocio: {error}"
                self.result.color = PALETTE["danger"]
                self.page.update()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Eliminar negocio definitivamente"),
            content=ft.Column([
                ft.Text(
                    "Se eliminarán usuarios, ventas, inventario, caja, reportes y configuración. "
                    "Esta acción no se puede deshacer."
                ),
                confirmation,
            ], tight=True, width=480),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _: setattr(dialog, "open", False)),
                ft.ElevatedButton(
                    "Eliminar definitivamente",
                    icon=ft.Icons.DELETE_FOREVER_OUTLINED,
                    bgcolor=PALETTE["danger"],
                    color=ft.Colors.WHITE,
                    on_click=perform_delete,
                ),
            ],
        )
        self.page.show_dialog(dialog)

    def create(self, _=None) -> None:
        try:
            if "@" not in (self.email.value or ""):
                raise ValueError("Ingrese un correo válido")
            if len(self.password.value or "") < 8:
                raise ValueError("La contraseña debe tener al menos 8 caracteres")
            organization_id, _token = create_store_with_invitation(self.context, self.name.value or "", self.email.value or "")
            admin_create_user(
                self.email.value or "", self.password.value or "",
                (self.email.value or "").split("@", 1)[0], "Administrador",
                organization_id, self.context,
            )
            self.result.value = (
                "Almacén y administradora creados correctamente. "
                "La cuenta ya puede iniciar sesión con su correo y contraseña."
            )
            self.result.color = PALETTE["success"]
            self.organization.options.append(
                ft.dropdown.Option(key=organization_id, text=(self.name.value or "Mi negocio").strip() or "Mi negocio")
            )
            self.organization.value = organization_id
            self.name.value = ""
            self.email.value = ""
            self.password.value = ""
        except Exception as error:
            self.result.value = f"No fue posible crear el almacén: {error}"
            self.result.color = PALETTE["danger"]
        self.page.update()

    def build(self) -> ft.Control:
        return ft.Container(
            expand=True, padding=24,
            content=ft.Column([
                page_title("Administración de plataforma", "Crea almacenes y sus credenciales de acceso."),
                shell_card(ft.Column([
                    self.organization,
                    ft.ElevatedButton(
                        "Entrar al sistema POS",
                        icon=ft.Icons.POINT_OF_SALE_ROUNDED,
                        on_click=lambda _: self.on_enter_pos(self.context, self.organization.value)
                        if self.organization.value else None,
                    ),
                    ft.OutlinedButton(
                        "Eliminar negocio",
                        icon=ft.Icons.DELETE_FOREVER_OUTLINED,
                        style=ft.ButtonStyle(color=PALETTE["danger"]),
                        on_click=self.confirm_delete,
                    ),
                ], spacing=16), padding=24),
                shell_card(ft.Column([
                    self.name, self.email, self.password,
                    ft.ElevatedButton("Crear almacén y administradora", on_click=self.create),
                    self.result,
                ], spacing=16), padding=24),
                ft.OutlinedButton("Cerrar sesión", on_click=lambda _: self.on_logout()),
            ], scroll=ft.ScrollMode.AUTO, spacing=20),
        )
