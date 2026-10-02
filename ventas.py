import datetime
import os
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import flet as ft
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from flet_utils import (
    DOCUMENT_TYPES,
    PALETTE,
    close_dialog,
    execute,
    expiry_badge,
    fetch_all,
    fetch_one,
    fetch_scalar,
    get_company_info,
    get_currency_symbol,
    page_title,
    shell_card,
    show_dialog,
    table_view,
)


class Ventas:
    db_name = "database.db"

    def __init__(self, page: ft.Page, user: str | None = None) -> None:
        self.page = page
        self.user = user or "Sistema"
        self.currency = get_currency_symbol()
        self.cart: list[dict] = []
        self.product_lookup_by_name: dict[str, dict] = {}
        self.product_lookup_by_code: dict[str, dict] = {}
        self.selected_cart_index: int | None = None
        self.selected_invoice: int | None = None
        self.caja_abierta = False
        self.monto_total_ventas = 0.0
        self.numero_factura = self.obtener_numero_factura_actual()

        self.scan_input = ft.TextField(
            label="Escanear codigo de barras",
            hint_text="Pase el lector y envie Enter",
            border_radius=16,
            filled=True,
            bgcolor=PALETTE["surface_alt"],
            prefix_icon=ft.Icons.QR_CODE_SCANNER_ROUNDED,
            autofocus=True,
            on_submit=self.escanear_codigo,
        )
        self.scan_status = ft.Text(
            "Escanee un producto para agregarlo rapido al carrito.",
            color=PALETTE["muted"],
        )

        self.entry_cliente = ft.Dropdown(
            label="Cliente",
            border_radius=16,
            filled=True,
            bgcolor=PALETTE["surface_alt"],
        )
        self.entry_nombre = ft.Dropdown(
            label="Producto",
            border_radius=16,
            filled=True,
            bgcolor=PALETTE["surface_alt"],
            on_select=lambda _: self.actualizar_stock(),
        )
        self.entry_cantidad = ft.TextField(
            label="Cantidad",
            value="1",
            border_radius=16,
            filled=True,
            bgcolor=PALETTE["surface_alt"],
        )
        self.label_stock = ft.Text("Stock: -", color=PALETTE["muted"])
        self.label_numero_factura = ft.Text(str(self.numero_factura), size=18, weight=ft.FontWeight.BOLD)
        self.label_precio_total = ft.Text(
            f"Precio a pagar: {self.currency} 0.00",
            size=22,
            weight=ft.FontWeight.BOLD,
        )
        self.estado_caja = ft.Text("", color=PALETTE["muted"])
        self.invoice_filter = ft.TextField(label="Factura", border_radius=16, filled=True, bgcolor=PALETTE["surface_alt"])
        self.client_filter = ft.TextField(label="Cliente", border_radius=16, filled=True, bgcolor=PALETTE["surface_alt"])

        self.cart_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Factura")),
                ft.DataColumn(ft.Text("Cliente")),
                ft.DataColumn(ft.Text("Producto")),
                ft.DataColumn(ft.Text("Lote")),
                ft.DataColumn(ft.Text("Vencimiento")),
                ft.DataColumn(ft.Text("Precio")),
                ft.DataColumn(ft.Text("Cantidad")),
                ft.DataColumn(ft.Text("Impuesto")),
                ft.DataColumn(ft.Text("Total")),
            ],
            rows=[],
            border=ft.Border.all(1, PALETTE["border"]),
            border_radius=12,
            heading_row_color=PALETTE["surface_alt"],
            column_spacing=20,
        )
        self.sales_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Factura")),
                ft.DataColumn(ft.Text("Cliente")),
                ft.DataColumn(ft.Text("Total")),
                ft.DataColumn(ft.Text("Fecha")),
                ft.DataColumn(ft.Text("Hora")),
                ft.DataColumn(ft.Text("Cajero")),
            ],
            rows=[],
            border=ft.Border.all(1, PALETTE["border"]),
            border_radius=12,
            heading_row_color=PALETTE["surface_alt"],
        )
        self.load_clients()
        self.load_products()
        self.cargar_estado_caja()

    def _notify(self, message: str, error: bool = False) -> None:
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=PALETTE["danger"] if error else PALETTE["primary"],
            open=True,
        )
        self.page.update()

    def obtener_numero_factura_actual(self) -> int:
        return int(fetch_scalar("SELECT IFNULL(MAX(factura), 0) + 1 FROM ventas", default=1))

    @staticmethod
    def _normalize_code(value: object) -> str:
        text = "".join(char for char in str(value or "").strip() if char.isprintable())
        if not text:
            return ""
        if text.endswith(".0"):
            integer_part = text[:-2]
            if integer_part.isdigit():
                return integer_part
        return text

    @classmethod
    def _code_candidates(cls, value: object) -> list[str]:
        code = cls._normalize_code(value)
        if not code:
            return []
        candidates = [code]
        digits = "".join(char for char in code if char.isdigit())
        if digits and digits not in candidates:
            candidates.append(digits)
        if len(digits) > 8:
            for length in range(min(13, len(digits)) - 1, 7, -1):
                suffix = digits[-length:]
                if suffix and suffix not in candidates:
                    candidates.append(suffix)
        return candidates

    async def _focus_scan_input(self) -> None:
        await self.scan_input.focus()

    async def _focus_quantity_input(self) -> None:
        await self.entry_cantidad.focus()

    def _schedule_scan_focus(self) -> None:
        if hasattr(self.page, "run_task"):
            self.page.run_task(self._focus_scan_input)

    def _schedule_quantity_focus(self) -> None:
        if hasattr(self.page, "run_task"):
            self.page.run_task(self._focus_quantity_input)

    def load_clients(self) -> None:
        rows = fetch_all("SELECT nombre FROM clientes ORDER BY nombre")
        self.entry_cliente.options = [ft.dropdown.Option(row["nombre"]) for row in rows]

    def _quick_client(self) -> str:
        if self.entry_cliente.value:
            return self.entry_cliente.value

        row = fetch_one(
            """
            SELECT nombre
            FROM clientes
            ORDER BY
                CASE
                    WHEN LOWER(nombre) LIKE '%mostrador%' THEN 0
                    WHEN LOWER(nombre) LIKE '%prueba%' THEN 1
                    ELSE 2
                END,
                nombre
            LIMIT 1
            """
        )
        if not row:
            execute(
                """
                INSERT INTO clientes (nombre, tipo_id, cedula, celular, direccion, correo)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("Cliente Mostrador", "CC", 0, 0, "Venta rapida", "sin_correo@local"),
            )
            row = {"nombre": "Cliente Mostrador"}
            self.load_clients()

        self.entry_cliente.value = row["nombre"]
        return row["nombre"]

    def load_products(self) -> None:
        rows = fetch_all(
            """
            SELECT nombre, codigo, codigo_barras, precio, costo, stock, impuesto_id, estado, fecha_vencimiento, lote
            FROM inventario
            ORDER BY nombre
            """
        )
        self.product_lookup_by_name = {}
        self.product_lookup_by_code = {}
        options: list[ft.dropdown.Option] = []
        for row in rows:
            if str(row.get("estado") or "Activo").strip().lower() == "inactivo":
                continue
            product = {
                **row,
                "codigo": self._normalize_code(row.get("codigo")),
                "codigo_barras": self._normalize_code(row.get("codigo_barras")),
                "stock": int(float(row.get("stock") or 0)),
                "precio": float(row.get("precio") or 0),
                "costo": float(row.get("costo") or 0),
                "fecha_vencimiento": row.get("fecha_vencimiento") or "",
                "lote": row.get("lote") or "",
            }
            self.product_lookup_by_name[product["nombre"]] = product
            options.append(ft.dropdown.Option(product["nombre"]))
            for code in [product["codigo_barras"], product["codigo"]]:
                if code and code not in self.product_lookup_by_code:
                    self.product_lookup_by_code[code] = product
        self.entry_nombre.options = options

    def _find_product_by_code(self, code: object) -> dict | None:
        for candidate in self._code_candidates(code):
            product = self.product_lookup_by_code.get(candidate)
            if product:
                return product
        return None

    def _cart_reserved_quantity(self, producto: str, ignore_index: int | None = None) -> int:
        reserved = 0
        for index, item in enumerate(self.cart):
            if ignore_index is not None and index == ignore_index:
                continue
            if not item.get("manual") and item.get("producto") == producto:
                reserved += int(item.get("cantidad") or 0)
        return reserved

    def _available_stock(self, product: dict, ignore_index: int | None = None) -> int:
        return max(0, int(product["stock"]) - self._cart_reserved_quantity(product["nombre"], ignore_index))

    def _tax_rate_for_product(self, product: dict) -> float:
        impuesto_id = product.get("impuesto_id")
        if not impuesto_id:
            return 0.0
        impuesto = fetch_one("SELECT tasa FROM impuestos WHERE id=?", (impuesto_id,))
        return float(impuesto["tasa"]) if impuesto else 0.0

    def _find_cart_item_index(self, cliente: str, producto: str) -> int | None:
        for index, item in enumerate(self.cart):
            if (
                not item.get("manual")
                and item.get("factura") == self.numero_factura
                and item.get("cliente") == cliente
                and item.get("producto") == producto
            ):
                return index
        return None

    def _set_cart_item_quantity(self, index: int, cantidad: int) -> bool:
        if cantidad <= 0:
            self._notify("La cantidad debe ser mayor a cero.", error=True)
            return False

        item = self.cart[index]
        if not item.get("manual"):
            product = self.product_lookup_by_name.get(item["producto"])
            if not product:
                self._notify("El producto ya no existe en inventario.", error=True)
                return False
            available_stock = self._available_stock(product, ignore_index=index)
            if cantidad > available_stock:
                self._notify(
                    f"Stock insuficiente. Disponible para venta: {available_stock} unidades.",
                    error=True,
                )
                return False

        current_qty = int(item["cantidad"] or 1)
        unit_price = float(item["precio"])
        unit_cost = float(item["costo"]) / max(1, current_qty)
        rate = (float(item["impuesto"]) / (unit_price * current_qty)) if unit_price * current_qty else 0
        subtotal = unit_price * cantidad
        item["cantidad"] = cantidad
        item["impuesto"] = subtotal * rate
        item["total"] = subtotal + item["impuesto"]
        item["costo"] = unit_cost * cantidad
        return True

    def _set_product_selection(self, product: dict | None) -> None:
        self.entry_nombre.value = product["nombre"] if product else None
        self.actualizar_stock(update_page=False)

    def _entry_quantity(self) -> int | None:
        try:
            cantidad = int(float(self.entry_cantidad.value or "0"))
        except ValueError:
            self._notify("Ingrese una cantidad valida.", error=True)
            return None
        if cantidad <= 0:
            self._notify("La cantidad debe ser mayor a cero.", error=True)
            return None
        return cantidad

    def _sync_selected_product_to_cart(self) -> int | None:
        if not self.entry_nombre.value:
            return None

        cliente = self._quick_client()
        cantidad = self._entry_quantity()
        if cantidad is None:
            return None

        product = self.product_lookup_by_name.get(self.entry_nombre.value or "")
        if not product:
            self._notify("Producto no encontrado.", error=True)
            return None

        cart_index = self._find_cart_item_index(cliente, product["nombre"])
        if cart_index is None:
            if not self._upsert_catalog_item(cliente, product, cantidad):
                return None
            return len(self.cart) - 1

        if not self._set_cart_item_quantity(cart_index, cantidad):
            return None
        return cart_index

    def _upsert_catalog_item(self, cliente: str, product: dict, cantidad: int) -> bool:
        product_name = product["nombre"]
        cart_index = self._find_cart_item_index(cliente, product_name)
        available_stock = self._available_stock(product, ignore_index=cart_index)
        current_qty = self.cart[cart_index]["cantidad"] if cart_index is not None else 0
        nueva_cantidad = current_qty + cantidad
        if nueva_cantidad > available_stock:
            self._notify(
                f"Stock insuficiente. Disponible para venta: {available_stock} unidades.",
                error=True,
            )
            return False

        tasa = self._tax_rate_for_product(product)
        item = self.cart[cart_index] if cart_index is not None else None
        subtotal = float(product["precio"]) * nueva_cantidad
        impuesto_total = subtotal * (tasa / 100)
        total = subtotal + impuesto_total
        if item is None:
            self.cart.append(
                {
                    "factura": self.numero_factura,
                    "cliente": cliente,
                    "producto": product_name,
                    "fecha_vencimiento": product.get("fecha_vencimiento") or "",
                    "lote": product.get("lote") or "",
                    "precio": float(product["precio"]),
                    "cantidad": nueva_cantidad,
                    "impuesto": impuesto_total,
                    "total": total,
                    "costo": float(product["costo"]) * nueva_cantidad,
                    "manual": False,
                }
            )
        else:
            item["cantidad"] = nueva_cantidad
            item["impuesto"] = impuesto_total
            item["total"] = total
            item["costo"] = float(product["costo"]) * nueva_cantidad
        return True

    def actualizar_stock(self, update_page: bool = True) -> None:
        if not self.entry_nombre.value:
            self.label_stock.value = "Stock: -"
            if update_page:
                self.page.update()
            return
        product = self.product_lookup_by_name.get(self.entry_nombre.value or "")
        stock = self._available_stock(product) if product else 0
        self.label_stock.value = f"Stock disponible: {stock}"
        if update_page:
            self.page.update()

    def agregar_articulo(self, _: ft.ControlEvent | None = None) -> None:
        cliente = self.entry_cliente.value or ""

        if not cliente:
            self._notify("Seleccione un cliente.", error=True)
            return
        if not self.entry_nombre.value:
            self._notify("Seleccione un producto.", error=True)
            return

        cantidad = self._entry_quantity()
        if cantidad is None:
            return

        product = self.product_lookup_by_name.get(self.entry_nombre.value or "")
        if not product:
            self._notify("Producto no encontrado.", error=True)
            return
        if not self._upsert_catalog_item(cliente, product, cantidad):
            return
        self.entry_cantidad.value = ""
        self._set_product_selection(None)
        self.scan_status.value = f"Producto agregado: {product['nombre']}"
        self.refresh_cart()
        self._schedule_scan_focus()

    def escanear_codigo(self, _: ft.ControlEvent | None = None) -> None:
        barcode = self._normalize_code(self.scan_input.value)

        if not barcode:
            self._notify("Escanee o escriba un codigo valido.", error=True)
            self._schedule_scan_focus()
            return

        self.load_products()
        product = self._find_product_by_code(barcode)
        if not product:
            self.scan_status.value = f"Codigo no encontrado: {barcode}"
            self.scan_input.value = ""
            self.page.update()
            self._notify("No existe un producto con ese codigo de barras.", error=True)
            self._schedule_scan_focus()
            return

        self._quick_client()
        self._set_product_selection(product)
        self.scan_status.value = f"Producto encontrado: {product['nombre']}. Digite la cantidad."
        self.scan_input.value = ""
        self.entry_cantidad.value = ""
        self.page.update()
        self._schedule_quantity_focus()

    def productos_no_registrados(self, _: ft.ControlEvent | None = None) -> None:
        if not self.entry_cliente.value:
            self._notify("Seleccione primero un cliente.", error=True)
            return
        producto = ft.TextField(label="Producto", border_radius=14)
        cantidad = ft.TextField(label="Cantidad", value="1", border_radius=14)
        precio = ft.TextField(label="Precio", border_radius=14)
        costo = ft.TextField(label="Costo", border_radius=14)
        impuestos = fetch_all("SELECT nombre, tasa FROM impuestos ORDER BY nombre")
        impuesto = ft.Dropdown(
            label="Impuesto",
            border_radius=14,
            options=[ft.dropdown.Option(row["nombre"]) for row in impuestos],
        )

        def guardar(event: ft.ControlEvent) -> None:
            try:
                qty = int(float(cantidad.value or "0"))
                price = float(precio.value or "0")
                cost = float(costo.value or "0")
            except ValueError:
                close_dialog(self.page, dialog)
                self._notify("Cantidad, precio y costo deben ser numericos.", error=True)
                return

            rate = 0.0
            for row in impuestos:
                if row["nombre"] == impuesto.value:
                    rate = float(row["tasa"])
                    break
            subtotal = price * qty
            tax = subtotal * (rate / 100)
            total = subtotal + tax
            self.cart.append(
                {
                    "factura": self.numero_factura,
                    "cliente": self.entry_cliente.value,
                    "producto": producto.value or "Manual",
                    "fecha_vencimiento": "",
                    "lote": "",
                    "precio": price,
                    "cantidad": qty,
                    "impuesto": tax,
                    "total": total,
                    "costo": cost * qty,
                    "manual": True,
                }
            )
            close_dialog(self.page, dialog)
            self.refresh_cart()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Producto no registrado"),
            content=ft.Container(
                width=420,
                content=ft.Column([producto, impuesto, cantidad, precio, costo], tight=True),
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda event: close_dialog(self.page, dialog)),
                ft.ElevatedButton("Agregar", on_click=guardar),
            ],
        )
        show_dialog(self.page, dialog)

    def abrir_cliente(self, _: ft.ControlEvent | None = None) -> None:
        nombre = ft.TextField(label="Nombre", border_radius=14)
        tipo_id = ft.Dropdown(
            label="Tipo de ID",
            border_radius=14,
            options=[ft.dropdown.Option(option) for option in DOCUMENT_TYPES],
        )
        cedula = ft.TextField(label="Numero ID", border_radius=14)
        celular = ft.TextField(label="Celular", border_radius=14)
        direccion = ft.TextField(label="Direccion", border_radius=14)
        correo = ft.TextField(label="Correo", border_radius=14)

        def guardar(event: ft.ControlEvent) -> None:
            values = [nombre.value, tipo_id.value, cedula.value, celular.value, direccion.value, correo.value]
            if not all(values):
                close_dialog(self.page, dialog)
                self._notify("Complete todos los datos del cliente.", error=True)
                return
            execute(
                "INSERT INTO clientes (nombre, tipo_id, cedula, celular, direccion, correo) VALUES (?, ?, ?, ?, ?, ?)",
                tuple(values),
            )
            self.load_clients()
            self.entry_cliente.value = nombre.value
            close_dialog(self.page, dialog)
            self._notify("Cliente creado correctamente.")
            self.page.update()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Crear cliente"),
            content=ft.Container(
                width=420,
                content=ft.Column([nombre, tipo_id, cedula, celular, direccion, correo], tight=True),
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda event: close_dialog(self.page, dialog)),
                ft.ElevatedButton("Guardar", on_click=guardar),
            ],
        )
        show_dialog(self.page, dialog)

    def seleccionar_cart(self, index: int) -> None:
        self.selected_cart_index = index
        self.page.update()

    def eliminar_articulo(self, _: ft.ControlEvent | None = None) -> None:
        if self.selected_cart_index is None:
            self._notify("Seleccione un item del carrito para eliminar.", error=True)
            return
        self.cart.pop(self.selected_cart_index)
        self.selected_cart_index = None
        self.refresh_cart()

    def editar_articulo(self, _: ft.ControlEvent | None = None) -> None:
        if self.selected_cart_index is None:
            self._notify("Seleccione un item del carrito para editar.", error=True)
            return
        item = self.cart[self.selected_cart_index]
        cantidad = ft.TextField(label="Nueva cantidad", value=str(item["cantidad"]), border_radius=14)

        def guardar(event: ft.ControlEvent) -> None:
            try:
                nueva_cantidad = int(float(cantidad.value or "0"))
            except ValueError:
                close_dialog(self.page, dialog)
                self._notify("Cantidad invalida.", error=True)
                return
            if not self._set_cart_item_quantity(self.selected_cart_index, nueva_cantidad):
                close_dialog(self.page, dialog)
                return
            close_dialog(self.page, dialog)
            self.refresh_cart()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Editar cantidad"),
            content=cantidad,
            actions=[
                ft.TextButton("Cancelar", on_click=lambda event: close_dialog(self.page, dialog)),
                ft.ElevatedButton("Guardar", on_click=guardar),
            ],
        )
        show_dialog(self.page, dialog)

    def limpiar_lista(self, _: ft.ControlEvent | None = None) -> None:
        self.cart.clear()
        self.selected_cart_index = None
        self.scan_status.value = "Carrito limpio. Puede volver a escanear productos."
        self.refresh_cart()

    def calcular_precio_total(self) -> float:
        return sum(item["total"] for item in self.cart)

    def _money(self, amount: float) -> str:
        return f"{self.currency} {amount:,.2f}"

    def refresh_cart(self) -> None:
        self.cart_table.rows = [
            ft.DataRow(
                cells=[
                    ft.DataCell(ft.Text(str(item["factura"]))),
                    ft.DataCell(ft.Text(item["cliente"])),
                    ft.DataCell(ft.Text(item["producto"])),
                    ft.DataCell(ft.Text(str(item.get("lote") or ""))),
                    ft.DataCell(ft.Text(str(item.get("fecha_vencimiento") or ""))),
                    ft.DataCell(ft.Text(f"{item['precio']:,.2f}")),
                    ft.DataCell(ft.Text(str(item["cantidad"]))),
                    ft.DataCell(ft.Text(f"{item['impuesto']:,.2f}")),
                    ft.DataCell(ft.Text(f"{item['total']:,.2f}")),
                ],
                selected=index == self.selected_cart_index,
                on_select_change=lambda event, index=index: self.seleccionar_cart(index),
            )
            for index, item in enumerate(self.cart)
        ]
        self.label_precio_total.value = f"Precio a pagar: {self._money(self.calcular_precio_total())}"
        self.actualizar_stock(update_page=False)
        self.page.update()

    def abrir_caja(self, _: ft.ControlEvent | None = None) -> None:
        abierta = fetch_scalar("SELECT COUNT(*) FROM caja WHERE estado='abierta'", default=0)
        if abierta:
            self._notify("Ya existe una caja abierta.", error=True)
            return
        monto = ft.TextField(label="Monto inicial", border_radius=14)

        def confirmar(event: ft.ControlEvent) -> None:
            try:
                monto_inicial = float(monto.value or "0")
            except ValueError:
                close_dialog(self.page, dialog)
                self._notify("Monto inicial invalido.", error=True)
                return
            execute(
                "INSERT INTO caja (fecha_apertura, monto_inicial, total_en_caja, estado) VALUES (?, ?, ?, ?)",
                (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), monto_inicial, monto_inicial, "abierta"),
            )
            close_dialog(self.page, dialog)
            self.cargar_estado_caja()
            self._notify(f"Caja abierta con {self._money(monto_inicial)}.")

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Abrir caja"),
            content=monto,
            actions=[
                ft.TextButton("Cancelar", on_click=lambda event: close_dialog(self.page, dialog)),
                ft.ElevatedButton("Abrir", on_click=confirmar),
            ],
        )
        show_dialog(self.page, dialog)

    def cerrar_caja(self, _: ft.ControlEvent | None = None) -> None:
        caja = fetch_one(
            "SELECT id, monto_inicial, total_en_caja, total_ventas_acumuladas FROM caja WHERE estado='abierta' ORDER BY id DESC LIMIT 1"
        )
        if not caja:
            self._notify("La caja no esta abierta.", error=True)
            return
        execute(
            "UPDATE caja SET estado='cerrada', fecha_cierre=? WHERE id=?",
            (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), caja["id"]),
        )
        self.caja_abierta = False
        resumen = (
            f"Monto inicial: {self._money(float(caja['monto_inicial']))}\n"
            f"Ventas acumuladas: {self._money(float(caja['total_ventas_acumuladas'] or 0))}\n"
            f"Total en caja: {self._money(float(caja['total_en_caja'] or 0))}"
        )
        dialog = ft.AlertDialog(title=ft.Text("Caja cerrada"), content=ft.Text(resumen))
        show_dialog(self.page, dialog)
        self.cargar_estado_caja()

    def cargar_estado_caja(self) -> None:
        caja = fetch_one(
            "SELECT estado, total_ventas_acumuladas FROM caja WHERE estado='abierta' ORDER BY id DESC LIMIT 1"
        )
        self.caja_abierta = caja is not None
        self.monto_total_ventas = float(caja["total_ventas_acumuladas"]) if caja else 0.0
        self.estado_caja.value = (
            f"Caja abierta · ventas acumuladas {self._money(self.monto_total_ventas)}"
            if caja
            else "Caja cerrada"
        )
        self.page.update()

    def _mostrar_vuelto(self, factura: int, total_venta: float, monto_pagado: float, cambio: float, metodo_pago: str) -> None:
        def aceptar(event: ft.ControlEvent) -> None:
            close_dialog(self.page, dialog)
            self._schedule_scan_focus()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Pago registrado"),
            content=ft.Container(
                width=360,
                content=ft.Column(
                    [
                        ft.Text(f"Factura: {factura}", weight=ft.FontWeight.BOLD),
                        ft.Text(f"Medio de pago: {metodo_pago}"),
                        ft.Text(f"Total venta: {self._money(total_venta)}"),
                        ft.Text(f"Monto recibido: {self._money(monto_pagado)}"),
                        ft.Divider(),
                        ft.Text(
                            f"Vuelto a entregar: {self._money(cambio)}",
                            size=22,
                            weight=ft.FontWeight.BOLD,
                            color=PALETTE["secondary"],
                        ),
                    ],
                    tight=True,
                    spacing=8,
                ),
            ),
            actions=[
                ft.ElevatedButton("Aceptar", on_click=aceptar),
            ],
        )
        show_dialog(self.page, dialog)

    def procesar_pago(
        self,
        monto: str,
        metodo_pago: str,
        descuento: str,
        dialog: ft.AlertDialog | None,
        mostrar_vuelto: bool = True,
    ) -> None:
        if not self.caja_abierta:
            if dialog:
                close_dialog(self.page, dialog)
            self._notify("La caja no esta abierta.", error=True)
            return
        try:
            monto_pagado = float(monto or "0")
            descuento_valor = float(descuento or "0")
        except ValueError:
            if dialog:
                close_dialog(self.page, dialog)
            self._notify("Monto o descuento invalidos.", error=True)
            return
        total_original = self.calcular_precio_total()
        total_venta = max(0.0, total_original - descuento_valor)
        if monto_pagado < total_venta:
            if dialog:
                close_dialog(self.page, dialog)
            self._notify("El monto pagado es insuficiente.", error=True)
            return
        if not metodo_pago:
            if dialog:
                close_dialog(self.page, dialog)
            self._notify("Seleccione un medio de pago.", error=True)
            return

        fecha_actual = datetime.datetime.now().strftime("%Y-%m-%d")
        hora_actual = datetime.datetime.now().strftime("%H:%M:%S")
        total_impuesto = sum(item["impuesto"] for item in self.cart)
        factura_cobrada = self.numero_factura

        for item in self.cart:
            execute(
                """
                INSERT INTO ventas
                (factura, cliente, producto, precio, cantidad, total, fecha, hora, costo, cajero, medio_pago, impuesto, fecha_vencimiento, lote)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.numero_factura,
                    item["cliente"],
                    item["producto"],
                    item["precio"],
                    item["cantidad"],
                    item["total"],
                    fecha_actual,
                    hora_actual,
                    item["costo"],
                    self.user,
                    metodo_pago,
                    item["impuesto"],
                    item.get("fecha_vencimiento") or "",
                    item.get("lote") or "",
                ),
            )
            if not item["manual"]:
                execute(
                    "UPDATE inventario SET stock = stock - ? WHERE nombre = ?",
                    (item["cantidad"], item["producto"]),
                )

        caja = fetch_one("SELECT id, total_en_caja, total_ventas_acumuladas, impuesto, descuento FROM caja WHERE estado='abierta' ORDER BY id DESC LIMIT 1")
        if caja:
            execute(
                """
                UPDATE caja
                SET total_en_caja=?, total_ventas_acumuladas=?, impuesto=?, descuento=?
                WHERE id=?
                """,
                (
                    float(caja["total_en_caja"] or 0) + total_venta,
                    float(caja["total_ventas_acumuladas"] or 0) + total_venta,
                    float(caja.get("impuesto") or 0) + total_impuesto,
                    float(caja.get("descuento") or 0) + descuento_valor,
                    caja["id"],
                ),
            )

        cambio = monto_pagado - total_venta
        if dialog:
            close_dialog(self.page, dialog)
        self.cart.clear()
        self.selected_cart_index = None
        self.numero_factura = self.obtener_numero_factura_actual()
        self.selected_invoice = factura_cobrada
        self.label_numero_factura.value = str(self.numero_factura)
        self.scan_status.value = "Venta cobrada. Escanee el siguiente producto."
        self.scan_input.value = ""
        self.entry_cantidad.value = ""
        self._set_product_selection(None)
        self.load_products()
        self.refresh_cart()
        self.refresh_sales()
        self.cargar_estado_caja()
        if mostrar_vuelto:
            self._mostrar_vuelto(factura_cobrada, total_venta, monto_pagado, cambio, metodo_pago)
        else:
            self._notify(
                f"Venta rapida #{factura_cobrada}: total {self._money(total_venta)} · vuelto {self._money(cambio)}."
            )
        self._schedule_scan_focus()

    def venta_rapida(self, _: ft.ControlEvent | None = None) -> None:
        if not self.caja_abierta:
            self._notify("La caja no esta abierta.", error=True)
            self._schedule_scan_focus()
            return

        synced_index = self._sync_selected_product_to_cart()
        if self.entry_nombre.value and synced_index is None:
            self._schedule_quantity_focus()
            return

        if not self.cart:
            self._notify("No hay productos seleccionados para cobrar.", error=True)
            self._schedule_scan_focus()
            return

        item_index = synced_index if synced_index is not None else self.selected_cart_index if self.selected_cart_index is not None else len(self.cart) - 1
        self.refresh_cart()
        item = self.cart[item_index]
        monto = ft.TextField(
            label="Monto recibido",
            value=str(round(self.calcular_precio_total(), 2)),
            border_radius=14,
            autofocus=True,
        )
        total_label = ft.Text("", size=18, weight=ft.FontWeight.BOLD)
        vuelto_label = ft.Text("", size=20, weight=ft.FontWeight.BOLD, color=PALETTE["secondary"])

        def update_labels() -> None:
            total = self.calcular_precio_total()
            try:
                recibido = float(monto.value or "0")
            except ValueError:
                recibido = 0.0
            cambio = max(0.0, recibido - total)
            total_label.value = f"Total: {self._money(total)}"
            vuelto_label.value = f"Vuelto: {self._money(cambio)}"

        def update_change(event: ft.ControlEvent | None = None) -> None:
            update_labels()
            self.page.update()

        def cobrar(event: ft.ControlEvent) -> None:
            self.procesar_pago(monto.value or "0", "efectivo", "0", dialog, mostrar_vuelto=False)

        monto.on_change = update_change
        update_labels()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Venta rapida"),
            content=ft.Container(
                width=420,
                content=ft.Column(
                    [
                        ft.Text(str(item["producto"]), weight=ft.FontWeight.BOLD),
                        monto,
                        total_label,
                        vuelto_label,
                    ],
                    tight=True,
                    spacing=10,
                ),
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda event: close_dialog(self.page, dialog)),
                ft.ElevatedButton("Cobrar", icon=ft.Icons.FLASH_ON_OUTLINED, on_click=cobrar),
            ],
        )
        show_dialog(self.page, dialog)

    def realizar_pago(self, _: ft.ControlEvent | None = None) -> None:
        synced_index = self._sync_selected_product_to_cart()
        if self.entry_nombre.value and synced_index is None:
            self._schedule_quantity_focus()
            return
        if synced_index is not None:
            self.refresh_cart()

        if not self.cart:
            self._notify("No hay productos seleccionados para cobrar.", error=True)
            self._schedule_scan_focus()
            return
        total = self.calcular_precio_total()
        monto = ft.TextField(label="Monto pagado", border_radius=14)
        descuento = ft.TextField(label="Descuento", value="0", border_radius=14)
        metodo_pago = ft.Dropdown(
            label="Medio de pago",
            border_radius=14,
            options=[
                ft.dropdown.Option("efectivo"),
                ft.dropdown.Option("tarjeta_debito"),
                ft.dropdown.Option("tarjeta_credito"),
                ft.dropdown.Option("transferencia"),
            ],
        )
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Realizar pago"),
            content=ft.Container(
                width=420,
                content=ft.Column(
                    [
                        ft.Text(f"Total actual: {self._money(total)}", weight=ft.FontWeight.BOLD),
                        descuento,
                        monto,
                        metodo_pago,
                    ],
                    tight=True,
                ),
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda event: close_dialog(self.page, dialog)),
                ft.ElevatedButton(
                    "Confirmar",
                    on_click=lambda event: self.procesar_pago(monto.value or "0", metodo_pago.value or "", descuento.value or "0", dialog),
                ),
            ],
        )
        show_dialog(self.page, dialog)

    @staticmethod
    def _wrap_text(text: str, max_chars: int) -> list[str]:
        words = str(text or "").split()
        lines: list[str] = []
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if len(candidate) <= max_chars:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word[:max_chars]
        if current:
            lines.append(current)
        return lines or [""]

    def _abrir_pdf(self, path: Path) -> None:
        if sys.platform.startswith("win"):
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.Popen(["xdg-open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _mostrar_voucher_generado(self, pdf_path: Path) -> None:
        def abrir(event: ft.ControlEvent) -> None:
            try:
                self._abrir_pdf(pdf_path)
                close_dialog(self.page, dialog)
            except Exception:
                self._notify(f"No se pudo abrir automaticamente. Archivo: {pdf_path}", error=True)

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Voucher generado"),
            content=ft.Container(
                width=420,
                content=ft.Column(
                    [
                        ft.Text("El PDF del voucher quedo listo para imprimir."),
                        ft.Text(str(pdf_path), selectable=True, color=PALETTE["muted"]),
                    ],
                    tight=True,
                    spacing=8,
                ),
            ),
            actions=[
                ft.TextButton("Cerrar", on_click=lambda event: close_dialog(self.page, dialog)),
                ft.ElevatedButton("Abrir PDF", icon=ft.Icons.PICTURE_AS_PDF_OUTLINED, on_click=abrir),
            ],
        )
        show_dialog(self.page, dialog)

    def generar_voucher(self, _: ft.ControlEvent | None = None) -> None:
        if self.selected_invoice is None:
            dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text("Seleccione una factura"),
                content=ft.Text("Primero seleccione una venta realizada y luego presione Voucher."),
                actions=[ft.ElevatedButton("Aceptar", on_click=lambda event: close_dialog(self.page, dialog))],
            )
            show_dialog(self.page, dialog)
            return

        detalles = fetch_all(
            """
            SELECT factura, cliente, producto, precio, cantidad, total, fecha, hora, cajero, medio_pago, impuesto, fecha_vencimiento, lote
            FROM ventas WHERE factura=? ORDER BY rowid
            """,
            (self.selected_invoice,),
        )
        if not detalles:
            dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text("Factura no encontrada"),
                content=ft.Text("No se encontro la factura seleccionada para generar el voucher."),
                actions=[ft.ElevatedButton("Aceptar", on_click=lambda event: close_dialog(self.page, dialog))],
            )
            show_dialog(self.page, dialog)
            return

        company = get_company_info()
        total = sum(float(row["total"] or 0) for row in detalles)
        impuesto = sum(float(row["impuesto"] or 0) for row in detalles)
        cliente = str(detalles[0]["cliente"] or "")
        fecha = str(detalles[0]["fecha"] or "")
        hora = str(detalles[0]["hora"] or "")
        cajero = str(detalles[0]["cajero"] or "")
        medio_pago = str(detalles[0]["medio_pago"] or "")

        voucher_dir = Path("vouchers")
        voucher_dir.mkdir(exist_ok=True)
        pdf_path = voucher_dir / f"Voucher_{self.selected_invoice}.pdf"

        width = 80 * mm
        line_height = 4.2 * mm
        detail_lines = sum(max(1, len(self._wrap_text(row["producto"], 24))) + 1 for row in detalles)
        height = max(150 * mm, (34 + detail_lines * 2) * line_height)
        doc = canvas.Canvas(str(pdf_path), pagesize=(width, height))
        y = height - 8 * mm

        def center(text: str, size: int = 9, bold: bool = False) -> None:
            nonlocal y
            doc.setFont("Helvetica-Bold" if bold else "Helvetica", size)
            doc.drawCentredString(width / 2, y, text)
            y -= line_height

        def left(text: str, size: int = 8, bold: bool = False) -> None:
            nonlocal y
            doc.setFont("Helvetica-Bold" if bold else "Helvetica", size)
            doc.drawString(5 * mm, y, text)
            y -= line_height

        def right(label: str, amount: float, size: int = 8, bold: bool = False) -> None:
            nonlocal y
            doc.setFont("Helvetica-Bold" if bold else "Helvetica", size)
            doc.drawString(5 * mm, y, label)
            doc.drawRightString(width - 5 * mm, y, self._money(amount))
            y -= line_height

        center(str(company["nombre"]), size=11, bold=True)
        if company.get("numero_id"):
            center(f"{company.get('tipo_id', '')} {company['numero_id']}".strip(), size=8)
        if company.get("direccion"):
            for line in self._wrap_text(company["direccion"], 34):
                center(line, size=8)
        if company.get("telefono"):
            center(f"Tel: {company['telefono']}", size=8)
        y -= 2 * mm
        doc.line(5 * mm, y, width - 5 * mm, y)
        y -= line_height

        left(f"Voucher venta #{self.selected_invoice}", bold=True)
        left(f"Fecha: {fecha} {hora}")
        left(f"Cliente: {cliente}")
        left(f"Cajero: {cajero}")
        left(f"Medio pago: {medio_pago}")
        y -= 1 * mm
        doc.line(5 * mm, y, width - 5 * mm, y)
        y -= line_height

        for row in detalles:
            qty = int(row["cantidad"] or 0)
            price = float(row["precio"] or 0)
            item_total = float(row["total"] or 0)
            for line in self._wrap_text(row["producto"], 30):
                left(line, size=8)
            if row.get("lote") or row.get("fecha_vencimiento"):
                left(f"Lote: {row.get('lote') or '-'}  Vence: {row.get('fecha_vencimiento') or '-'}", size=7)
            doc.setFont("Helvetica", 8)
            doc.drawString(5 * mm, y, f"{qty} x {self._money(price)}")
            doc.drawRightString(width - 5 * mm, y, self._money(item_total))
            y -= line_height

        y -= 1 * mm
        doc.line(5 * mm, y, width - 5 * mm, y)
        y -= line_height
        right("Impuesto", impuesto)
        right("TOTAL", total, size=10, bold=True)
        y -= 3 * mm
        center("Gracias por su compra", size=9, bold=True)
        doc.save()

        self._mostrar_voucher_generado(pdf_path)
        try:
            self._abrir_pdf(pdf_path)
        except Exception:
            self._notify(f"Voucher generado en {pdf_path}. Abralo para imprimir.", error=True)

    def _sales_summary_rows(self) -> list[dict]:
        factura = (self.invoice_filter.value or "").strip()
        cliente = (self.client_filter.value or "").strip().lower()
        rows = fetch_all("SELECT factura, cliente, total, fecha, hora, cajero FROM ventas ORDER BY factura DESC")
        grouped: dict[int, dict] = defaultdict(lambda: {"cliente": "", "total": 0.0, "fecha": "", "hora": "", "cajero": ""})
        for row in rows:
            if factura and str(row["factura"]) != factura:
                continue
            if cliente and cliente not in row["cliente"].lower():
                continue
            data = grouped[row["factura"]]
            data["cliente"] = row["cliente"]
            data["fecha"] = row["fecha"]
            data["hora"] = row["hora"]
            data["cajero"] = row["cajero"]
            data["total"] += float(row["total"])
        result = []
        for invoice, data in grouped.items():
            result.append(
                {
                    "factura": invoice,
                    "cliente": data["cliente"],
                    "total": data["total"],
                    "fecha": data["fecha"],
                    "hora": data["hora"],
                    "cajero": data["cajero"],
                }
            )
        return result

    def select_invoice(self, invoice: int) -> None:
        self.selected_invoice = invoice
        self.page.update()

    def refresh_sales(self) -> None:
        rows = self._sales_summary_rows()
        self.sales_table.rows = [
            ft.DataRow(
                cells=[
                    ft.DataCell(ft.Text(str(row["factura"]))),
                    ft.DataCell(ft.Text(row["cliente"])),
                    ft.DataCell(ft.Text(f"{row['total']:,.2f}")),
                    ft.DataCell(ft.Text(row["fecha"])),
                    ft.DataCell(ft.Text(row["hora"])),
                    ft.DataCell(ft.Text(row["cajero"])),
                ],
                selected=row["factura"] == self.selected_invoice,
                on_select_change=lambda event, invoice=row["factura"]: self.select_invoice(invoice),
            )
            for row in rows
        ]
        self.page.update()

    def ver_detalle_factura(self, _: ft.ControlEvent | None = None) -> None:
        if self.selected_invoice is None:
            self._notify("Seleccione una factura para ver el detalle.", error=True)
            return
        detalles = fetch_all(
            """
            SELECT factura, cliente, producto, precio, cantidad, total, fecha, hora, costo, cajero, medio_pago, impuesto, fecha_vencimiento, lote
            FROM ventas WHERE factura=? ORDER BY rowid
            """,
            (self.selected_invoice,),
        )
        content = ft.DataTable(
            columns=[ft.DataColumn(ft.Text(col)) for col in ["Producto", "Lote", "Vencimiento", "Semaforo", "Precio", "Cantidad", "Impuesto", "Total", "Medio pago"]],
            rows=[
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(str(row["producto"]))),
                        ft.DataCell(ft.Text(str(row.get("lote") or ""))),
                        ft.DataCell(ft.Text(str(row.get("fecha_vencimiento") or ""))),
                        ft.DataCell(expiry_badge(row.get("fecha_vencimiento"))),
                        ft.DataCell(ft.Text(f"{float(row['precio']):,.2f}")),
                        ft.DataCell(ft.Text(str(row["cantidad"]))),
                        ft.DataCell(ft.Text(f"{float(row['impuesto'] or 0):,.2f}")),
                        ft.DataCell(ft.Text(f"{float(row['total']):,.2f}")),
                        ft.DataCell(ft.Text(str(row["medio_pago"] or ""))),
                    ]
                )
                for row in detalles
            ],
        )
        dialog = ft.AlertDialog(
            title=ft.Text(f"Detalle factura {self.selected_invoice}"),
            content=ft.Container(width=720, height=360, content=table_view(content, expand=True)),
        )
        show_dialog(self.page, dialog)

    def anular_factura(self, _: ft.ControlEvent | None = None) -> None:
        if self.selected_invoice is None:
            self._notify("Seleccione una factura para anular.", error=True)
            return
        detalles = fetch_all("SELECT producto, cantidad, total FROM ventas WHERE factura=?", (self.selected_invoice,))
        if not detalles:
            self._notify("No se encontro la factura seleccionada.", error=True)
            return
        total_factura = sum(float(row["total"]) for row in detalles)
        for row in detalles:
            execute("UPDATE inventario SET stock = stock + ? WHERE nombre = ?", (row["cantidad"], row["producto"]))
        execute("DELETE FROM ventas WHERE factura=?", (self.selected_invoice,))
        caja = fetch_one("SELECT id, total_ventas_acumuladas, total_en_caja FROM caja WHERE estado='abierta' ORDER BY id DESC LIMIT 1")
        if caja:
            execute(
                "UPDATE caja SET total_ventas_acumuladas=?, total_en_caja=? WHERE id=?",
                (
                    max(0.0, float(caja["total_ventas_acumuladas"] or 0) - total_factura),
                    max(0.0, float(caja["total_en_caja"] or 0) - total_factura),
                    caja["id"],
                ),
            )
        self.selected_invoice = None
        self.numero_factura = self.obtener_numero_factura_actual()
        self.label_numero_factura.value = str(self.numero_factura)
        self.load_products()
        self.refresh_sales()
        self.cargar_estado_caja()
        self._notify("Factura anulada y stock restaurado.")

    def build(self) -> ft.Control:
        self.refresh_cart()
        self.refresh_sales()
        left = ft.Column(
            [
                page_title("Ventas", "Caja, carrito y cobro de productos en una vista Flet."),
                ft.Row(
                    [
                        ft.Container(expand=True, content=self.scan_input),
                        ft.IconButton(
                            ft.Icons.CENTER_FOCUS_STRONG_ROUNDED,
                            tooltip="Volver a enfocar el lector",
                            on_click=lambda _: self._schedule_scan_focus(),
                        ),
                    ]
                ),
                self.scan_status,
                ft.Row(
                    [
                        ft.Container(expand=True, content=self.entry_cliente),
                        ft.IconButton(ft.Icons.PERSON_ADD_ALT_1, on_click=self.abrir_cliente),
                    ]
                ),
                ft.Row(
                    [
                        ft.Container(expand=True, content=self.entry_nombre),
                        ft.IconButton(ft.Icons.ADD_BOX_OUTLINED, on_click=self.productos_no_registrados),
                    ]
                ),
                ft.Row(
                    [
                        ft.Container(expand=True, content=self.entry_cantidad),
                        ft.Container(
                            padding=12,
                            border_radius=16,
                            bgcolor=PALETTE["surface_alt"],
                            content=ft.Column(
                                [
                                    ft.Text("Factura actual", size=12, color=PALETTE["muted"]),
                                    self.label_numero_factura,
                                ],
                                spacing=2,
                            ),
                        ),
                    ]
                ),
                self.label_stock,
                ft.Row(
                    [
                        ft.ElevatedButton("Agregar", icon=ft.Icons.ADD_SHOPPING_CART, on_click=self.agregar_articulo),
                        ft.OutlinedButton("Editar", icon=ft.Icons.EDIT_OUTLINED, on_click=self.editar_articulo),
                        ft.OutlinedButton("Eliminar", icon=ft.Icons.DELETE_OUTLINE, on_click=self.eliminar_articulo),
                        ft.OutlinedButton("Limpiar", icon=ft.Icons.CLEANING_SERVICES_OUTLINED, on_click=self.limpiar_lista),
                    ],
                    wrap=True,
                ),
                ft.Divider(),
                ft.Row(
                    [
                        ft.ElevatedButton("Abrir caja", icon=ft.Icons.LOCK_OPEN_OUTLINED, on_click=self.abrir_caja),
                        ft.OutlinedButton("Cerrar caja", icon=ft.Icons.LOCK_OUTLINE, on_click=self.cerrar_caja),
                    ],
                    wrap=True,
                ),
                self.estado_caja,
                self.label_precio_total,
                ft.Row(
                    [
                        ft.ElevatedButton(
                            "Pagar",
                            icon=ft.Icons.PAYMENTS_OUTLINED,
                            on_click=self.realizar_pago,
                            style=ft.ButtonStyle(
                                shape=ft.RoundedRectangleBorder(radius=16),
                                bgcolor=PALETTE["secondary"],
                                color=ft.Colors.WHITE,
                            ),
                        ),
                        ft.ElevatedButton(
                            "Venta rapida",
                            icon=ft.Icons.FLASH_ON_OUTLINED,
                            tooltip="Cobra el total exacto en efectivo",
                            on_click=self.venta_rapida,
                            style=ft.ButtonStyle(
                                shape=ft.RoundedRectangleBorder(radius=16),
                                bgcolor=PALETTE["accent"],
                                color=ft.Colors.WHITE,
                            ),
                        ),
                    ],
                    wrap=True,
                ),
            ],
            spacing=14,
            scroll=ft.ScrollMode.AUTO,
        )
        right = ft.Column(
            [
                ft.Text("Carrito", size=20, weight=ft.FontWeight.BOLD),
                table_view(self.cart_table, height=240),
                ft.Divider(),
                ft.Text("Ventas realizadas", size=20, weight=ft.FontWeight.BOLD),
                ft.ResponsiveRow(
                    [
                        ft.Container(col={"xs": 12, "md": 4}, content=self.invoice_filter),
                        ft.Container(col={"xs": 12, "md": 4}, content=self.client_filter),
                        ft.Container(
                            col={"xs": 12, "md": 4},
                            content=ft.Row(
                                [
                                    ft.ElevatedButton("Filtrar", on_click=lambda _: self.refresh_sales()),
                                    ft.IconButton(ft.Icons.REFRESH_ROUNDED, on_click=lambda _: self.refresh_sales()),
                                ]
                            ),
                        ),
                    ]
                ),
                ft.Row(
                    [
                        ft.OutlinedButton("Ver detalle", on_click=self.ver_detalle_factura),
                        ft.OutlinedButton("Anular factura", on_click=self.anular_factura),
                        ft.OutlinedButton("Voucher", icon=ft.Icons.RECEIPT_LONG_OUTLINED, on_click=self.generar_voucher),
                    ],
                    wrap=True,
                ),
                table_view(self.sales_table, expand=True),
            ],
            spacing=14,
            expand=True,
        )
        return ft.ResponsiveRow(
            [
                ft.Container(col={"xs": 12, "xl": 5}, content=shell_card(left, expand=True)),
                ft.Container(col={"xs": 12, "xl": 7}, content=shell_card(right, expand=True)),
            ],
            expand=True,
        )
