from __future__ import annotations


OPERATIONAL_MODULES = {
    "ventas",
    "cotizaciones",
    "inventario",
    "clientes",
    "proveedor",
    "pedidos",
    "reportes",
    "gastos",
    "informacion",
}

DEFAULT_ROLE_MODULES = {
    "Administrador": OPERATIONAL_MODULES | {"configuracion", "usuarios"},
    "Supervisor": set(OPERATIONAL_MODULES),
    "Vendedor": set(OPERATIONAL_MODULES),
}
