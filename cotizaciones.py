import datetime
from collections import defaultdict

import flet as ft

from flet_utils import DOCUMENT_TYPES, PALETTE, close_dialog, execute, expiry_badge, fetch_all, fetch_one, get_currency_symbol, page_title, shell_card, show_dialog, table_view


class Cotizaciones:
    def __init__(self, page: ft.Page, user: str | None = None) -> None:
        self.page = page
        self.user = user or "Sistema"
        self.currency = get_currency_symbol()
        self.cart: list[dict] = []
        self.selected_cart_index: int | None = None
        self.selected_quote: int | None = None
        self.numero_factura = self.obtener_numero_actual()

        self.entry_cliente = ft.Dropdown(label="Cliente", border_radius=16, filled=True, bgcolor=PALETTE["surface_alt"])
        self.entry_nombre = ft.Dropdown(
            label="Producto",
            border_radius=16,
            filled=True,
            bgcolor=PALETTE["surface_alt"],
            on_select=lambda _: self.actualizar_stock(),
        )
        self.entry_cantidad = ft.TextField(label="Cantidad", value="1", border_radius=16, filled=True, bgcolor=PALETTE["surface_alt"])
        self.stock_label = ft.Text("Stock: -", color=PALETTE["muted"])
        self.total_label = ft.Text(f"Total cotizacion: {self.currency} 0.00", size=22, weight=ft.FontWeight.BOLD)
        self.numero_label = ft.Text(str(self.numero_factura), size=18, weight=ft.FontWeight.BOLD)
        self.filter_quote = ft.TextField(label="Cotizacion", border_radius=16, filled=True, bgcolor=PALETTE["surface_alt"])
        self.filter_client = ft.TextField(label="Cliente", border_radius=16, filled=True, bgcolor=PALETTE["surface_alt"])

        self.cart_table = ft.DataTable(
            columns=[ft.DataColumn(ft.Text(label)) for label in ["Cotizacion", "Cliente", "Producto", "Lote", "Vencimiento", "Precio", "Cantidad", "Impuesto", "Total"]],
            rows=[],
            border=ft.border.all(1, PALETTE["border"]),
            border_radius=12,
            heading_row_color=PALETTE["surface_alt"],
        )
        self.history_table = ft.DataTable(
            columns=[ft.DataColumn(ft.Text(label)) for label in ["Cotizacion", "Cliente", "Total", "Fecha", "Hora", "Cajero"]],
            rows=[],
            border=ft.border.all(1, PALETTE["border"]),
            border_radius=12,
            heading_row_color=PALETTE["surface_alt"],
        )
        self.load_clients()
        self.load_products()

    def _notify(self, message: str, error: bool = False) -> None:
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=PALETTE["danger"] if error else PALETTE["primary"],
            open=True,
        )
        self.page.update()

    def obtener_numero_actual(self) -> int:
        return int(fetch_one("SELECT IFNULL(MAX(cotizacion), 0) + 1 AS numero FROM cotizaciones")["numero"])

    def load_clients(self) -> None:
        self.entry_cliente.options = [ft.dropdown.Option(row["nombre"]) for row in fetch_all("SELECT nombre FROM clientes ORDER BY nombre")]

    def load_products(self) -> None:
        self.entry_nombre.options = [ft.dropdown.Option(row["nombre"]) for row in fetch_all("SELECT nombre FROM inventario ORDER BY nombre")]

    def actualizar_stock(self) -> None:
        if not self.entry_nombre.value:
            self.stock_label.value = "Stock: -"
            self.page.update()
            return
        row = fetch_one("SELECT stock FROM inventario WHERE nombre=?", (self.entry_nombre.value,))
        self.stock_label.value = f"Stock: {row['stock'] if row else 0}"
        self.page.update()

    def agregar_articulo(self, _: ft.ControlEvent | None = None) -> None:
        cliente = self.entry_cliente.value or ""
        producto = self.entry_nombre.value or ""
        if not cliente or not producto:
            self._notify("Seleccione cliente y producto.", error=True)
            return
        try:
            cantidad = int(float(self.entry_cantidad.value or "0"))
        except ValueError:
            self._notify("Cantidad invalida.", error=True)
            return
        if cantidad <= 0:
            self._notify("La cantidad debe ser mayor a cero.", error=True)
            return
        product = fetch_one("SELECT precio, costo, stock, impuesto_id, fecha_vencimiento, lote FROM inventario WHERE nombre=?", (producto,))
        if not product:
            self._notify("Producto no encontrado.", error=True)
            return
        if cantidad > int(product["stock"]):
            self._notify(f"Stock insuficiente. Solo hay {product['stock']} unidades.", error=True)
            return
        tasa = 0.0
        if product.get("impuesto_id"):
            impuesto = fetch_one("SELECT tasa FROM impuestos WHERE id=?", (product["impuesto_id"],))
            tasa = float(impuesto["tasa"]) if impuesto else 0.0
        subtotal = float(product["precio"]) * cantidad
        impuesto_total = subtotal * (tasa / 100)
        total = subtotal + impuesto_total
        self.cart.append(
            {
                "cotizacion": self.numero_factura,
                "cliente": cliente,
                "producto": producto,
                "fecha_vencimiento": product.get("fecha_vencimiento") or "",
                "lote": product.get("lote") or "",
                "precio": float(product["precio"]),
                "cantidad": cantidad,
                "impuesto": impuesto_total,
                "total": total,
                "costo": float(product["costo"]) * cantidad,
            }
        )
        self.entry_nombre.value = None
        self.entry_cantidad.value = "1"
        self.actualizar_stock()
        self.refresh_cart()

    def abrir_cliente(self, _: ft.ControlEvent | None = None) -> None:
        nombre = ft.TextField(label="Nombre", border_radius=14)
        tipo_id = ft.Dropdown(label="Tipo de ID", border_radius=14, options=[ft.dropdown.Option(option) for option in DOCUMENT_TYPES])
        cedula = ft.TextField(label="Numero ID", border_radius=14)
        celular = ft.TextField(label="Celular", border_radius=14)
        direccion = ft.TextField(label="Direccion", border_radius=14)
        correo = ft.TextField(label="Correo", border_radius=14)

        def guardar(event: ft.ControlEvent) -> None:
            if not all([nombre.value, tipo_id.value, cedula.value, celular.value, direccion.value, correo.value]):
                close_dialog(self.page, dialog)
                self._notify("Complete todos los datos del cliente.", error=True)
                return
            execute(
                "INSERT INTO clientes (nombre, tipo_id, cedula, celular, direccion, correo) VALUES (?, ?, ?, ?, ?, ?)",
                (nombre.value, tipo_id.value, cedula.value, celular.value, direccion.value, correo.value),
            )
            self.load_clients()
            self.entry_cliente.value = nombre.value
            close_dialog(self.page, dialog)
            self._notify("Cliente agregado correctamente.")
            self.page.update()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Crear cliente"),
            content=ft.Container(width=420, content=ft.Column([nombre, tipo_id, cedula, celular, direccion, correo], tight=True)),
            actions=[ft.TextButton("Cancelar", on_click=lambda event: close_dialog(self.page, dialog)), ft.ElevatedButton("Guardar", on_click=guardar)],
        )
        show_dialog(self.page, dialog)

    def seleccionar_cart(self, index: int) -> None:
        self.selected_cart_index = index
        self.page.update()

    def eliminar_articulo(self, _: ft.ControlEvent | None = None) -> None:
        if self.selected_cart_index is None:
            self._notify("Seleccione un item para eliminar.", error=True)
            return
        self.cart.pop(self.selected_cart_index)
        self.selected_cart_index = None
        self.refresh_cart()

    def editar_articulo(self, _: ft.ControlEvent | None = None) -> None:
        if self.selected_cart_index is None:
            self._notify("Seleccione un item para editar.", error=True)
            return
        item = self.cart[self.selected_cart_index]
        current_qty = item["cantidad"]
        cantidad = ft.TextField(label="Nueva cantidad", value=str(current_qty), border_radius=14)

        def guardar(event: ft.ControlEvent) -> None:
            try:
                nueva = int(float(cantidad.value or "0"))
            except ValueError:
                close_dialog(self.page, dialog)
                self._notify("Cantidad invalida.", error=True)
                return
            if nueva <= 0:
                close_dialog(self.page, dialog)
                self._notify("La cantidad debe ser mayor a cero.", error=True)
                return
            rate = item["impuesto"] / max(1.0, item["precio"] * current_qty)
            item["cantidad"] = nueva
            item["impuesto"] = item["precio"] * nueva * rate
            item["total"] = item["precio"] * nueva + item["impuesto"]
            item["costo"] = (item["costo"] / max(1, current_qty)) * nueva
            close_dialog(self.page, dialog)
            self.refresh_cart()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Editar articulo"),
            content=cantidad,
            actions=[ft.TextButton("Cancelar", on_click=lambda event: close_dialog(self.page, dialog)), ft.ElevatedButton("Guardar", on_click=guardar)],
        )
        show_dialog(self.page, dialog)

    def calcular_total(self) -> float:
        return sum(item["total"] for item in self.cart)

    def refresh_cart(self) -> None:
        self.cart_table.rows = [
            ft.DataRow(
                cells=[
                    ft.DataCell(ft.Text(str(item["cotizacion"]))),
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
        self.total_label.value = f"Total cotizacion: {self.currency} {self.calcular_total():,.2f}"
        self.page.update()

    def registrar_cotizacion(self, _: ft.ControlEvent | None = None) -> None:
        if not self.cart:
            self._notify("No hay productos cargados en la cotizacion.", error=True)
            return
        fecha = datetime.datetime.now().strftime("%Y-%m-%d")
        hora = datetime.datetime.now().strftime("%H:%M:%S")
        for item in self.cart:
            execute(
                """
                INSERT INTO cotizaciones
                (cotizacion, cliente, producto, precio, cantidad, total, fecha, hora, costo, cajero, impuesto, fecha_vencimiento, lote)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.numero_factura,
                    item["cliente"],
                    item["producto"],
                    item["precio"],
                    item["cantidad"],
                    item["total"],
                    fecha,
                    hora,
                    item["costo"],
                    self.user,
                    item["impuesto"],
                    item.get("fecha_vencimiento") or "",
                    item.get("lote") or "",
                ),
            )
        self.cart.clear()
        self.selected_cart_index = None
        self.numero_factura = self.obtener_numero_actual()
        self.numero_label.value = str(self.numero_factura)
        self.refresh_cart()
        self.refresh_history()
        self._notify("Cotizacion registrada correctamente.")

    def _history_rows(self) -> list[dict]:
        rows = fetch_all("SELECT cotizacion, cliente, total, fecha, hora, cajero FROM cotizaciones ORDER BY cotizacion DESC")
        filter_quote = (self.filter_quote.value or "").strip()
        filter_client = (self.filter_client.value or "").strip().lower()
        grouped: dict[int, dict] = defaultdict(lambda: {"cliente": "", "total": 0.0, "fecha": "", "hora": "", "cajero": ""})
        for row in rows:
            if filter_quote and str(row["cotizacion"]) != filter_quote:
                continue
            if filter_client and filter_client not in row["cliente"].lower():
                continue
            item = grouped[row["cotizacion"]]
            item["cliente"] = row["cliente"]
            item["fecha"] = row["fecha"]
            item["hora"] = row["hora"]
            item["cajero"] = row["cajero"]
            item["total"] += float(row["total"])
        return [
            {
                "cotizacion": quote,
                "cliente": item["cliente"],
                "total": item["total"],
                "fecha": item["fecha"],
                "hora": item["hora"],
                "cajero": item["cajero"],
            }
            for quote, item in grouped.items()
        ]

    def seleccionar_cotizacion(self, quote: int) -> None:
        self.selected_quote = quote
        self.page.update()

    def refresh_history(self) -> None:
        rows = self._history_rows()
        self.history_table.rows = [
            ft.DataRow(
                cells=[
                    ft.DataCell(ft.Text(str(row["cotizacion"]))),
                    ft.DataCell(ft.Text(row["cliente"])),
                    ft.DataCell(ft.Text(f"{row['total']:,.2f}")),
                    ft.DataCell(ft.Text(row["fecha"])),
                    ft.DataCell(ft.Text(row["hora"])),
                    ft.DataCell(ft.Text(row["cajero"])),
                ],
                selected=row["cotizacion"] == self.selected_quote,
                on_select_change=lambda event, quote=row["cotizacion"]: self.seleccionar_cotizacion(quote),
            )
            for row in rows
        ]
        self.page.update()

    def ver_detalle(self, _: ft.ControlEvent | None = None) -> None:
        if self.selected_quote is None:
            self._notify("Seleccione una cotizacion para ver detalle.", error=True)
            return
        detalles = fetch_all(
            """
            SELECT producto, precio, cantidad, impuesto, total, fecha_vencimiento, lote
            FROM cotizaciones
            WHERE cotizacion=?
            """,
            (self.selected_quote,),
        )
        dialog = ft.AlertDialog(
            title=ft.Text(f"Detalle cotizacion {self.selected_quote}"),
            content=ft.Container(
                width=680,
                height=320,
                content=ft.Column(
                    [
                        table_view(ft.DataTable(
                            columns=[ft.DataColumn(ft.Text(label)) for label in ["Producto", "Lote", "Vencimiento", "Semaforo", "Precio", "Cantidad", "Impuesto", "Total"]],
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
                                    ]
                                )
                                for row in detalles
                            ],
                        ), expand=True)
                    ],
                    scroll=ft.ScrollMode.AUTO,
                ),
            ),
        )
        show_dialog(self.page, dialog)

    def build(self) -> ft.Control:
        self.refresh_cart()
        self.refresh_history()
        left = ft.Column(
            [
                page_title("Cotizaciones", "Carrito separado para cotizar sin afectar la caja."),
                ft.Row([ft.Container(expand=True, content=self.entry_cliente), ft.IconButton(ft.Icons.PERSON_ADD_ALT_1, on_click=self.abrir_cliente)]),
                self.entry_nombre,
                ft.Row(
                    [
                        ft.Container(expand=True, content=self.entry_cantidad),
                        ft.Container(
                            padding=12,
                            border_radius=16,
                            bgcolor=PALETTE["surface_alt"],
                            content=ft.Column([ft.Text("Nro. cotizacion", size=12, color=PALETTE["muted"]), self.numero_label], spacing=2),
                        ),
                    ]
                ),
                self.stock_label,
                ft.Row(
                    [
                        ft.ElevatedButton("Agregar", icon=ft.Icons.ADD_SHOPPING_CART, on_click=self.agregar_articulo),
                        ft.OutlinedButton("Editar", on_click=self.editar_articulo),
                        ft.OutlinedButton("Eliminar", on_click=self.eliminar_articulo),
                    ],
                    wrap=True,
                ),
                self.total_label,
                ft.ElevatedButton(
                    "Registrar cotizacion",
                    icon=ft.Icons.REQUEST_QUOTE_OUTLINED,
                    on_click=self.registrar_cotizacion,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=16), bgcolor=PALETTE["secondary"], color=ft.Colors.WHITE),
                ),
            ],
            spacing=14,
            scroll=ft.ScrollMode.AUTO,
        )
        right = ft.Column(
            [
                ft.Text("Carrito", size=20, weight=ft.FontWeight.BOLD),
                table_view(self.cart_table, height=220),
                ft.Divider(),
                ft.Text("Cotizaciones realizadas", size=20, weight=ft.FontWeight.BOLD),
                ft.ResponsiveRow(
                    [
                        ft.Container(col={"xs": 12, "md": 4}, content=self.filter_quote),
                        ft.Container(col={"xs": 12, "md": 4}, content=self.filter_client),
                        ft.Container(col={"xs": 12, "md": 4}, content=ft.Row([ft.ElevatedButton("Filtrar", on_click=lambda _: self.refresh_history()), ft.IconButton(ft.Icons.REFRESH_ROUNDED, on_click=lambda _: self.refresh_history())])),
                    ]
                ),
                ft.OutlinedButton("Ver detalle", on_click=self.ver_detalle),
                table_view(self.history_table, expand=True),
            ],
            spacing=14,
            expand=True,
        )
        return ft.ResponsiveRow(
            [
                ft.Container(col={"xs": 12, "xl": 4}, content=shell_card(left, expand=True)),
                ft.Container(col={"xs": 12, "xl": 8}, content=shell_card(right, expand=True)),
            ],
            expand=True,
        )
