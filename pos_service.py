from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from database import fetch_one, reserve_document_number, transaction
from tenant_context import TenantContext


@dataclass(frozen=True, slots=True)
class SaleResult:
    sale_id: str
    invoice: int
    total: Decimal
    replayed: bool


def normalize_email(email: str) -> str:
    return email.strip().casefold()


def create_local_invitation(
    context: TenantContext,
    email: str,
    role: str,
) -> str:
    """Create/retry an invite without sending email; returns the test token."""
    context.require_store_admin()
    organization_id = context.require_organization()
    normalized = normalize_email(email)
    if role not in {"store_admin", "cashier"}:
        raise ValueError("Rol de invitación no permitido")
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    invitation_id = str(uuid.uuid4())
    with transaction(context) as cursor:
        cursor.execute(
            """
            INSERT INTO organization_invitations
                (id, organization_id, email, role, token_hash, status,
                 delivery_status, delivery_attempts, invited_by)
            VALUES (?, ?, ?, ?, ?, 'pending', 'local', 1, ?)
            ON CONFLICT (organization_id, email, role) WHERE status = 'pending'
            DO UPDATE SET token_hash=EXCLUDED.token_hash,
                          delivery_status='local',
                          delivery_attempts=organization_invitations.delivery_attempts + 1,
                          expires_at=now() + interval '48 hours'
            """,
            (invitation_id, organization_id, normalized, role, token_hash, context.auth_user_id),
        )
    return raw_token


def complete_sale(
    context: TenantContext,
    *,
    request_id: str,
    cash_register_id: int,
    customer_id: int | None,
    payment_method: str,
    items: list[dict[str, Any]],
) -> SaleResult:
    """Atomically charge, decrement stock and update the tenant cash register."""
    organization_id = context.require_organization()
    if not context.can_sell:
        raise PermissionError("El usuario no puede registrar ventas")
    if not request_id or not items:
        raise ValueError("La venta requiere identificador e ítems")

    with transaction(context) as cursor:
        cursor.execute(
            "SELECT id, factura, total FROM sale_operations "
            "WHERE organization_id=? AND request_id=?",
            (organization_id, request_id),
        )
        previous = cursor.fetchone()
        if previous:
            return SaleResult(
                str(previous["id"]), int(previous["factura"]),
                Decimal(str(previous["total"])), True,
            )

        cursor.execute(
            "SELECT id FROM caja WHERE id=? AND organization_id=? AND estado='abierta' FOR UPDATE",
            (cash_register_id, organization_id),
        )
        if not cursor.fetchone():
            raise ValueError("La caja no pertenece al almacén o no está abierta")

        prepared: list[dict[str, Any]] = []
        total = Decimal("0")
        tax_total = Decimal("0")
        for requested in items:
            product_id = int(requested["product_id"])
            quantity = int(requested["quantity"])
            if quantity <= 0:
                raise ValueError("Cantidad inválida")
            cursor.execute(
                "SELECT id, nombre, precio, costo, stock, fecha_vencimiento, lote "
                "FROM inventario WHERE id=? AND organization_id=? FOR UPDATE",
                (product_id, organization_id),
            )
            product = cursor.fetchone()
            if not product or int(product["stock"]) < quantity:
                raise ValueError("Producto inexistente o stock insuficiente")
            price = Decimal(str(product["precio"]))
            line_total = price * quantity
            prepared.append({**dict(product), "quantity": quantity, "line_total": line_total})
            total += line_total

        operation_id = str(uuid.uuid4())
        invoice = reserve_document_number(cursor, "factura", organization_id)
        cursor.execute(
            "INSERT INTO sale_operations "
            "(id, organization_id, request_id, factura, caja_id, customer_id, total, payment_method, created_by) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (operation_id, organization_id, request_id, invoice, cash_register_id,
             customer_id, total, payment_method, context.auth_user_id),
        )
        now = datetime.now(timezone.utc)
        for product in prepared:
            cursor.execute(
                "UPDATE inventario SET stock=stock-? WHERE id=? AND organization_id=? AND stock>=?",
                (product["quantity"], product["id"], organization_id, product["quantity"]),
            )
            if cursor.rowcount != 1:
                raise ValueError("El stock cambió durante el cobro")
            cursor.execute(
                """INSERT INTO ventas
                   (organization_id, operation_id, product_id, factura, cliente, producto,
                    precio, cantidad, total, fecha, hora, costo, cajero, medio_pago,
                    impuesto, fecha_vencimiento, lote)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (organization_id, operation_id, product["id"], invoice,
                 str(customer_id or "Cliente Mostrador"), product["nombre"],
                 product["precio"], product["quantity"], product["line_total"],
                 now.date().isoformat(), now.time().replace(microsecond=0).isoformat(),
                 Decimal(str(product["costo"])) * product["quantity"], context.username,
                 payment_method, Decimal("0"), product.get("fecha_vencimiento") or "",
                 product.get("lote") or ""),
            )
        cursor.execute(
            "UPDATE caja SET total_en_caja=COALESCE(total_en_caja,0)+?, "
            "total_ventas_acumuladas=COALESCE(total_ventas_acumuladas,0)+?, "
            "impuesto=COALESCE(impuesto,0)+? WHERE id=? AND organization_id=?",
            (total, total, tax_total, cash_register_id, organization_id),
        )
        return SaleResult(operation_id, invoice, total, False)

