import datetime

import flet as ft

from flet_utils import FieldSpec, SimpleCrudModule, fetch_all


class Pedidos(SimpleCrudModule):
    def __init__(self, page: ft.Page, user: str | None = None) -> None:
        self.user = user
        proveedores = [row["nombre"] for row in fetch_all("SELECT nombre FROM proveedores ORDER BY nombre")]
        productos = [row["nombre"] for row in fetch_all("SELECT nombre FROM inventario ORDER BY nombre")]
        super().__init__(
            page=page,
            title="Pedidos",
            subtitle="Registra pedidos a proveedores sobre la misma base de datos ya existente.",
            table_name="pedidos",
            search_field="proveedor",
            fields=[
                FieldSpec("numero_pedido", "Nro. pedido"),
                FieldSpec("proveedor", "Proveedor", kind="dropdown", options=proveedores),
                FieldSpec("producto", "Producto", kind="dropdown", options=productos),
                FieldSpec("cantidad", "Cantidad"),
                FieldSpec("fecha", "Fecha"),
                FieldSpec("hora", "Hora"),
                FieldSpec("precio", "Precio"),
                FieldSpec("costo", "Costo"),
                FieldSpec("fecha_vencimiento", "Fecha vencimiento"),
                FieldSpec("lote", "Lote"),
            ],
        )
        now = datetime.datetime.now()
        fecha = self.form_controls["fecha"]
        hora = self.form_controls["hora"]
        if isinstance(fecha, ft.TextField):
            fecha.value = now.strftime("%d-%m-%Y")
        if isinstance(hora, ft.TextField):
            hora.value = now.strftime("%H:%M:%S")
