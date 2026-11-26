from __future__ import annotations

import os
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from database import fetch_one, transaction
from tenant_context import PLATFORM_ADMIN, TenantContext


@dataclass(frozen=True)
class AuthIdentity:
    user_id: str
    email: str
    username: str
    role: str
    access_token: str
    organization_id: str | None
    is_platform_admin: bool = False

    def tenant_context(self) -> TenantContext:
        return TenantContext(
            auth_user_id=self.user_id, email=self.email, username=self.username,
            organization_id=self.organization_id, role=self.role,
            is_platform_admin=self.is_platform_admin,
        )


def supabase_url() -> str:
    return os.getenv("SUPABASE_URL", "").strip()


def supabase_publishable_key() -> str:
    return (
        os.getenv("SUPABASE_PUBLISHABLE_KEY", "").strip()
        or os.getenv("SUPABASE_ANON_KEY", "").strip()
    )


def supabase_enabled() -> bool:
    return bool(supabase_url() and supabase_publishable_key())


def _client():
    try:
        from supabase import create_client
    except ImportError as error:
        raise RuntimeError(
            "Falta el cliente de Supabase. Ejecute: pip install -r requirements.txt"
        ) from error
    return create_client(supabase_url(), supabase_publishable_key())


def sign_in(email: str, password: str) -> AuthIdentity:
    if not supabase_enabled():
        raise RuntimeError("Supabase Auth no está configurado")
    response = _client().auth.sign_in_with_password(
        {"email": email.strip(), "password": password}
    )
    if not response.user or not response.session:
        raise RuntimeError("No se recibió una sesión válida")

    platform_admin = fetch_one(
        "SELECT auth_user_id FROM platform_admins WHERE auth_user_id=?",
        (str(response.user.id),),
    )
    auth_probe = TenantContext(
        auth_user_id=str(response.user.id), email=str(response.user.email or email),
        username="", organization_id=None, role="cashier",
    )
    membership = fetch_one(
        """SELECT organization_id, username, role, status
           FROM organization_memberships
           WHERE auth_user_id=? AND status='active'
           ORDER BY created_at LIMIT 1""",
        (str(response.user.id),), context=auth_probe,
    )
    if not platform_admin and not membership:
        raise PermissionError("El usuario no tiene una membresía activa")

    username = str((membership or {}).get("username") or response.user.email or "usuario")
    return AuthIdentity(
        user_id=str(response.user.id), email=str(response.user.email or email),
        username=username,
        role=PLATFORM_ADMIN if platform_admin else str(membership["role"]),
        access_token=str(response.session.access_token),
        organization_id=str(membership["organization_id"]) if membership else None,
        is_platform_admin=bool(platform_admin),
    )


def accept_invitation(token: str, auth_user_id: str, authenticated_email: str) -> str:
    """Bind an authenticated Supabase user to exactly the invited store."""
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    email = authenticated_email.strip().casefold()
    probe = TenantContext(auth_user_id, email, "", None, "cashier")
    row = fetch_one(
        "SELECT private.accept_organization_invitation(?, ?, ?) AS organization_id",
        (token_hash, auth_user_id, email), context=probe,
    )
    if not row or not row.get("organization_id"):
        raise PermissionError("La invitación no es válida para este correo")
    return str(row["organization_id"])


def register_from_invitation(token: str, email: str, password: str) -> str:
    if len(password) < 8:
        raise ValueError("La contraseña debe tener al menos 8 caracteres")
    response = _client().auth.sign_up({"email": email.strip(), "password": password})
    if not response.user:
        raise RuntimeError("Supabase no creó el usuario")
    return accept_invitation(token.strip(), str(response.user.id), email)


def request_password_recovery(email: str) -> None:
    if not supabase_enabled():
        raise RuntimeError("Supabase Auth no está configurado")
    redirect = os.getenv("PUBLIC_APP_URL", "").strip() or None
    options = {"redirect_to": redirect} if redirect else None
    _client().auth.reset_password_for_email(email.strip(), options=options)


def admin_create_user(email: str, password: str, username: str, role: str) -> str:
    secret = (
        os.getenv("SUPABASE_SECRET_KEY", "").strip()
        or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    )
    if not supabase_url() or not secret:
        raise RuntimeError("Se requiere SUPABASE_SECRET_KEY para crear usuarios")
    from supabase import create_client

    admin = create_client(supabase_url(), secret)
    response: Any = admin.auth.admin.create_user(
        {"email": email, "password": password, "email_confirm": True}
    )
    user_id = str(response.user.id)
    admin.table("usuarios").insert(
        {
            "auth_user_id": user_id,
            "email": email,
            "username": username,
            "rol": role,
            "activo": True,
        }
    ).execute()
    return user_id


def admin_update_user(user_id: str, email: str, password: str | None = None) -> None:
    secret = os.getenv("SUPABASE_SECRET_KEY", "").strip()
    if not secret:
        raise RuntimeError("Se requiere SUPABASE_SECRET_KEY para actualizar usuarios")
    from supabase import create_client

    attributes: dict[str, Any] = {"email": email, "email_confirm": True}
    if password:
        attributes["password"] = password
    create_client(supabase_url(), secret).auth.admin.update_user_by_id(user_id, attributes)


def admin_delete_user(user_id: str) -> None:
    secret = os.getenv("SUPABASE_SECRET_KEY", "").strip()
    if not secret:
        raise RuntimeError("Se requiere SUPABASE_SECRET_KEY para eliminar usuarios")
    from supabase import create_client

    create_client(supabase_url(), secret).auth.admin.delete_user(user_id)


def upload_private_file(path: Path, bucket: str, object_name: str) -> str:
    """Upload a server-generated artifact and return a temporary signed URL."""
    secret = os.getenv("SUPABASE_SECRET_KEY", "").strip()
    if not supabase_url() or not secret:
        raise RuntimeError("Supabase Storage no está configurado")
    from supabase import create_client

    client = create_client(supabase_url(), secret)
    with path.open("rb") as file_handle:
        client.storage.from_(bucket).upload(
            object_name,
            file_handle,
            {"content-type": "application/pdf", "upsert": "true"},
        )
    response = client.storage.from_(bucket).create_signed_url(object_name, 3600)
    signed_url = response.get("signedURL") or response.get("signedUrl")
    if not signed_url:
        raise RuntimeError("Supabase no devolvió la URL del archivo")
    return str(signed_url)


def upload_public_bytes(
    content: bytes,
    bucket: str,
    object_name: str,
    content_type: str,
) -> str:
    """Upload a public brand asset and return its stable CDN URL."""
    secret = os.getenv("SUPABASE_SECRET_KEY", "").strip()
    if not supabase_url() or not secret:
        raise RuntimeError("Supabase Storage no está configurado")
    from supabase import create_client

    client = create_client(supabase_url(), secret)
    # Brand assets are intentionally public so the login screen can render them.
    client.storage.update_bucket(bucket, {"public": True})
    client.storage.from_(bucket).upload(
        object_name,
        content,
        {"content-type": content_type, "upsert": "true", "cache-control": "3600"},
    )
    public_url = client.storage.from_(bucket).get_public_url(object_name)
    if isinstance(public_url, dict):
        public_url = public_url.get("publicURL") or public_url.get("publicUrl")
    if not public_url:
        raise RuntimeError("Supabase no devolvió la URL pública de la imagen")
    return str(public_url)
