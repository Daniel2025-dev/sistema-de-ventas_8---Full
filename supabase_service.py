from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from database import fetch_one


@dataclass(frozen=True)
class AuthIdentity:
    user_id: str
    email: str
    username: str
    role: str
    access_token: str


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

    profile = fetch_one(
        "SELECT username, rol, activo FROM usuarios WHERE auth_user_id = ?",
        (str(response.user.id),),
    )
    if not profile:
        raise PermissionError("El usuario no tiene un perfil habilitado en el sistema")
    if not profile.get("activo", True):
        raise PermissionError("El usuario está desactivado")

    username = str(profile.get("username") or response.user.email or "usuario")
    return AuthIdentity(
        user_id=str(response.user.id),
        email=str(response.user.email or email),
        username=username,
        role=str(profile.get("rol") or "Vendedor"),
        access_token=str(response.session.access_token),
    )


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
