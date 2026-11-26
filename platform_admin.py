from __future__ import annotations

import hashlib
import os
import secrets
import uuid

import flet as ft

from database import fetch_all, is_postgres, transaction
from flet_utils import PALETTE, page_title, shell_card
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
        cursor.execute("INSERT INTO organization_invitations(id, organization_id, email, role, token_hash, status, delivery_status, delivery_attempts, invited_by, expires_at) VALUES (?, ?, ?, 'store_admin', ?, 'pending', 'local', 1, ?, datetime('now', '+48 hours'))" if not is_postgres() else "INSERT INTO organization_invitations(id, organization_id, email, role, token_hash, status, delivery_status, delivery_attempts, invited_by) VALUES (?, ?, ?, 'store_admin', ?, 'pending', 'local', 1, ?)", (invitation_id, organization_id, email, token_hash, context.auth_user_id))
    return organization_id, token


class PlatformAdminView:
    def __init__(self, page: ft.Page, context: TenantContext, on_logout) -> None:
        self.page = page
        self.context = context
        self.on_logout = on_logout
        self.name = ft.TextField(label="Nombre del almacén (opcional)")
        self.email = ft.TextField(label="Correo de la administradora")
        self.result = ft.Text(selectable=True, color=PALETTE["muted"])

    def create(self, _=None) -> None:
        try:
            if "@" not in (self.email.value or ""):
                raise ValueError("Ingrese un correo válido")
            organization_id, token = create_store_with_invitation(self.context, self.name.value or "", self.email.value or "")
            mode = os.getenv("INVITE_DELIVERY_MODE", "local").strip().lower()
            self.result.value = (
                f"Almacén creado: {organization_id}\n"
                f"Invitación local ({mode}): /aceptar-invitacion?token={token}"
            )
            self.name.value = ""
            self.email.value = ""
        except Exception as error:
            self.result.value = f"No fue posible crear el almacén: {error}"
            self.result.color = PALETTE["danger"]
        self.page.update()

    def build(self) -> ft.Control:
        return ft.Container(
            expand=True, padding=24,
            content=ft.Column([
                page_title("Administración de plataforma", "Crea almacenes e invita a su primera administradora."),
                shell_card(ft.Column([
                    self.name, self.email,
                    ft.ElevatedButton("Crear almacén e invitación", on_click=self.create),
                    self.result,
                ], spacing=16), padding=24),
                ft.OutlinedButton("Cerrar sesión", on_click=lambda _: self.on_logout()),
            ], scroll=ft.ScrollMode.AUTO, spacing=20),
        )
