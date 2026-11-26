from __future__ import annotations

from dataclasses import dataclass


STORE_ADMIN = "store_admin"
CASHIER = "cashier"
PLATFORM_ADMIN = "platform_admin"


@dataclass(frozen=True, slots=True)
class TenantContext:
    """Identity and tenant selected by the server after authentication."""

    auth_user_id: str
    email: str
    username: str
    organization_id: str | None
    role: str
    is_platform_admin: bool = False

    @property
    def can_manage_store(self) -> bool:
        return self.is_platform_admin or self.role == STORE_ADMIN

    @property
    def can_sell(self) -> bool:
        return self.role in {STORE_ADMIN, CASHIER} or self.is_platform_admin

    def require_organization(self) -> str:
        if not self.organization_id:
            raise PermissionError("Seleccione un almacén antes de continuar")
        return self.organization_id

    def require_store_admin(self) -> None:
        if not self.can_manage_store:
            raise PermissionError("Esta operación requiere administrar el almacén")

