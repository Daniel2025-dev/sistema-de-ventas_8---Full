import flet as ft

from flet_utils import PALETTE, execute, expiry_badge, fetch_all, fetch_one, normalize_expiry_date, page_title, shell_card, table_view


class Inventario:
    def __init__(self, page: ft.Page, user: str | None = None) -> None:
        self.page = page
        self.user = user
        self.selected_id: int | None = None
        self.impuestos = {
            row["nombre"]: row["id"] for row in fetch_all("SELECT id, nombre FROM impuestos ORDER BY nombre")
        }
        self.impuestos_por_id = {value: key for key, value in self.impuestos.items()}
        self.search = ft.TextField(
            label="Buscar producto",
            border_radius=16,
            filled=True,
            bgcolor=PALETTE["surface_alt"],
            prefix_icon=ft.Icons.SEARCH,
            on_submit=lambda _: self.refresh(),
        )
        self.nombre = ft.TextField(label="Producto", border_radius=16, filled=True, bgcolor=PALETTE["surface_alt"])
        self.codigo = ft.TextField(label="Codigo interno", border_radius=16, filled=True, bgcolor=PALETTE["surface_alt"])
        self.codigo_barras = ft.TextField(
            label="Codigo de barras",
            border_radius=16,
            filled=True,
            bgcolor=PALETTE["surface_alt"],
            hint_text="EAN / UPC / Code128",
        )
        self.proveedor = ft.Dropdown(
            label="Proveedor",
            border_radius=16,
            filled=True,
            bgcolor=PALETTE["surface_alt"],
            options=[ft.dropdown.Option(row["nombre"]) for row in fetch_all("SELECT nombre FROM proveedores ORDER BY nombre")],
        )
        self.precio = ft.TextField(label="Precio", border_radius=16, filled=True, bgcolor=PALETTE["surface_alt"])
        self.costo = ft.TextField(label="Costo", border_radius=16, filled=True, bgcolor=PALETTE["surface_alt"])
        self.stock = ft.TextField(label="Stock", border_radius=16, filled=True, bgcolor=PALETTE["surface_alt"])
        self.fecha_vencimiento = ft.TextField(
            label="Fecha vencimiento",
            hint_text="AAAA-MM-DD",
            border_radius=16,
            filled=True,
            bgcolor=PALETTE["surface_alt"],
        )
        self.lote = ft.TextField(label="Lote", border_radius=16, filled=True, bgcolor=PALETTE["surface_alt"])
        self.categoria = ft.Dropdown(
            label="Categoria",
            border_radius=16,
            filled=True,
            bgcolor=PALETTE["surface_alt"],
            options=[ft.dropdown.Option(row["nombre"]) for row in fetch_all("SELECT nombre FROM categorias ORDER BY nombre")],
        )
        self.sucursal = ft.Dropdown(
            label="Sucursal",
            border_radius=16,
            filled=True,
            bgcolor=PALETTE["surface_alt"],
            options=[ft.dropdown.Option(row["nombre"]) for row in fetch_all("SELECT nombre FROM sucursal ORDER BY nombre")],
        )
        self.estado = ft.Dropdown(
            label="Estado",
            value="Activo",
            border_radius=16,
            filled=True,
            bgcolor=PALETTE["surface_alt"],
            options=[ft.dropdown.Option("Activo"), ft.dropdown.Option("Inactivo")],
        )
        self.impuesto = ft.Dropdown(
            label="Impuesto",
            border_radius=16,
            filled=True,
            bgcolor=PALETTE["surface_alt"],
            options=[ft.dropdown.Option(nombre) for nombre in self.impuestos],
        )
        self.image_path = ft.TextField(
            label="Ruta imagen",
            border_radius=16,
            filled=True,
            bgcolor=PALETTE["surface_alt"],
            hint_text="fotos/default.png",
            on_submit=lambda _: self._update_preview(),
        )
        self.preview = ft.Container(
            height=220,
            border_radius=20,
            bgcolor=PALETTE["surface_alt"],
            alignment=ft.Alignment(0, 0),
        )
        self.table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("ID")),
                ft.DataColumn(ft.Text("Producto")),
                ft.DataColumn(ft.Text("Codigo")),
                ft.DataColumn(ft.Text("Cod. barras")),
                ft.DataColumn(ft.Text("Proveedor")),
                ft.DataColumn(ft.Text("Precio")),
                ft.DataColumn(ft.Text("Stock")),
                ft.DataColumn(ft.Text("Vencimiento")),
                ft.DataColumn(ft.Text("Lote")),
                ft.DataColumn(ft.Text("Semaforo")),
                ft.DataColumn(ft.Text("Estado")),
            ],
            rows=[],
            border=ft.border.all(1, PALETTE["border"]),
            border_radius=12,
            heading_row_color=PALETTE["surface_alt"],
            column_spacing=18,
        )

    def _notify(self, message: str, error: bool = False) -> None:
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=PALETTE["danger"] if error else PALETTE["primary"],
            open=True,
        )
        self.page.update()

    def _update_preview(self) -> None:
        path = (self.image_path.value or "").strip()
        if path:
            self.preview.content = ft.Image(src=path, fit="contain")
        else:
            self.preview.content = ft.Icon(ft.Icons.IMAGE_OUTLINED, size=64, color=PALETTE["muted"])
        self.page.update()

    @staticmethod
    def _normalize_code(value: object) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        if text.endswith(".0"):
            integer_part = text[:-2]
            if integer_part.isdigit():
                return integer_part
        return text

    def _clear(self, _: ft.ControlEvent | None = None) -> None:
        self.selected_id = None
        for control in [
            self.nombre,
            self.codigo,
            self.codigo_barras,
            self.precio,
            self.costo,
            self.stock,
            self.fecha_vencimiento,
            self.lote,
            self.image_path,
        ]:
            control.value = ""
        for dropdown, default in [
            (self.proveedor, None),
            (self.categoria, None),
            (self.sucursal, None),
            (self.impuesto, None),
            (self.estado, "Activo"),
        ]:
            dropdown.value = default
        self._update_preview()

    def _validate(self) -> bool:
        required = [
            ("Producto", self.nombre.value),
            ("Codigo interno", self.codigo.value),
            ("Precio", self.precio.value),
            ("Costo", self.costo.value),
            ("Stock", self.stock.value),
            ("Estado", self.estado.value),
        ]
        missing = [label for label, value in required if not value or not str(value).strip()]
        if missing:
            self._notify(f"Faltan datos obligatorios: {', '.join(missing)}.", error=True)
            return False

        for label, value in [("Precio", self.precio.value), ("Costo", self.costo.value), ("Stock", self.stock.value)]:
            try:
                float(value)
            except (TypeError, ValueError):
                self._notify(f"El campo {label} debe ser numerico.", error=True)
                return False

        codigo = self._normalize_code(self.codigo.value)
        codigo_barras = self._normalize_code(self.codigo_barras.value) or codigo
        duplicate = fetch_one(
            """
            SELECT id, nombre
            FROM inventario
            WHERE id != COALESCE(?, -1)
              AND (
                    TRIM(CAST(codigo AS TEXT)) = ?
                    OR (? <> '' AND TRIM(COALESCE(codigo_barras, '')) = ?)
                  )
            LIMIT 1
            """,
            (self.selected_id, codigo, codigo_barras, codigo_barras),
        )
        if duplicate:
            self._notify(
                f"El codigo o codigo de barras ya existe en el producto {duplicate['nombre']}.",
                error=True,
            )
            return False
        return True

    def save(self, _: ft.ControlEvent | None = None) -> None:
        if not self._validate():
            return

        impuesto_id = self.impuestos.get(self.impuesto.value or "")
        codigo = self._normalize_code(self.codigo.value)
        codigo_barras = self._normalize_code(self.codigo_barras.value) or codigo
        try:
            values = (
                self.nombre.value.strip(),
                self.proveedor.value or "",
                float(self.precio.value),
                float(self.costo.value),
                int(float(self.stock.value)),
                self.categoria.value or "",
                self.sucursal.value or "",
                self.estado.value or "Activo",
                self.image_path.value or "",
                codigo,
                codigo_barras,
                impuesto_id,
                normalize_expiry_date(self.fecha_vencimiento.value),
                (self.lote.value or "").strip(),
            )
            if self.selected_id is None:
                execute(
                    """
                    INSERT INTO inventario
                    (nombre, proveedor, precio, costo, stock, categoria, sucursal, estado, image_path, codigo, codigo_barras, impuesto_id, fecha_vencimiento, lote)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    values,
                )
                self._notify("Producto agregado correctamente.")
            else:
                execute(
                    """
                    UPDATE inventario
                    SET nombre=?, proveedor=?, precio=?, costo=?, stock=?, categoria=?, sucursal=?, estado=?, image_path=?, codigo=?, codigo_barras=?, impuesto_id=?, fecha_vencimiento=?, lote=?
                    WHERE id=?
                    """,
                    values + (self.selected_id,),
                )
                self._notify("Producto actualizado correctamente.")
        except Exception as error:
            self._notify(f"No se pudo guardar el producto: {error}", error=True)
            return
        self._clear()
        self.refresh()

    def delete(self, _: ft.ControlEvent | None = None) -> None:
        if self.selected_id is None:
            self._notify("Seleccione un producto para eliminar.", error=True)
            return
        try:
            execute("DELETE FROM inventario WHERE id=?", (self.selected_id,))
        except Exception as error:
            self._notify(f"No se pudo eliminar el producto: {error}", error=True)
            return
        self._notify("Producto eliminado correctamente.")
        self._clear()
        self.refresh()

    def select_row(self, row: dict) -> None:
        self.selected_id = int(row["id"])
        self.nombre.value = row.get("nombre", "")
        self.codigo.value = self._normalize_code(row.get("codigo", ""))
        self.codigo_barras.value = self._normalize_code(row.get("codigo_barras", ""))
        self.proveedor.value = row.get("proveedor", "")
        self.precio.value = str(row.get("precio", ""))
        self.costo.value = str(row.get("costo", ""))
        self.stock.value = str(row.get("stock", ""))
        self.fecha_vencimiento.value = row.get("fecha_vencimiento", "")
        self.lote.value = row.get("lote", "")
        self.categoria.value = row.get("categoria", "")
        self.sucursal.value = row.get("sucursal", "")
        self.estado.value = row.get("estado", "Activo")
        self.impuesto.value = self.impuestos_por_id.get(row.get("impuesto_id"))
        self.image_path.value = row.get("image_path", "")
        self._update_preview()

    def refresh(self) -> None:
        term = (self.search.value or "").strip()
        if term:
            rows = fetch_all(
                """
                SELECT id, nombre, codigo, codigo_barras, proveedor, precio, stock, estado, costo, categoria, sucursal, image_path, impuesto_id, fecha_vencimiento, lote
                FROM inventario
                WHERE nombre LIKE ? OR CAST(codigo AS TEXT) LIKE ? OR COALESCE(codigo_barras, '') LIKE ? OR COALESCE(lote, '') LIKE ?
                ORDER BY id DESC
                """,
                (f"%{term}%", f"%{term}%", f"%{term}%", f"%{term}%"),
            )
        else:
            rows = fetch_all(
                """
                SELECT id, nombre, codigo, codigo_barras, proveedor, precio, stock, estado, costo, categoria, sucursal, image_path, impuesto_id, fecha_vencimiento, lote
                FROM inventario ORDER BY id DESC
                """
            )

        self.table.rows = [
            ft.DataRow(
                cells=[
                    ft.DataCell(ft.Text(str(row["id"]))),
                    ft.DataCell(ft.Text(str(row["nombre"]))),
                    ft.DataCell(ft.Text(self._normalize_code(row["codigo"]))),
                    ft.DataCell(ft.Text(self._normalize_code(row.get("codigo_barras", "")))),
                    ft.DataCell(ft.Text(str(row["proveedor"]))),
                    ft.DataCell(ft.Text(f"{float(row['precio']):,.2f}")),
                    ft.DataCell(ft.Text(str(row["stock"]))),
                    ft.DataCell(ft.Text(str(row.get("fecha_vencimiento") or ""))),
                    ft.DataCell(ft.Text(str(row.get("lote") or ""))),
                    ft.DataCell(expiry_badge(row.get("fecha_vencimiento"))),
                    ft.DataCell(ft.Text(str(row["estado"]))),
                ],
                on_select_change=lambda event, row=row: self.select_row(row),
            )
            for row in rows
        ]
        self.page.update()

    def build(self) -> ft.Control:
        self._update_preview()
        self.refresh()
        form = ft.Column(
            [
                page_title("Inventario", "Gestion completa de productos con catalogos y previsualizacion."),
                self.nombre,
                ft.ResponsiveRow(
                    [
                        ft.Container(col={"xs": 12, "md": 4}, content=self.codigo),
                        ft.Container(col={"xs": 12, "md": 4}, content=self.codigo_barras),
                        ft.Container(col={"xs": 12, "md": 4}, content=self.proveedor),
                    ]
                ),
                ft.ResponsiveRow(
                    [
                        ft.Container(col={"xs": 12, "md": 4}, content=self.precio),
                        ft.Container(col={"xs": 12, "md": 4}, content=self.costo),
                        ft.Container(col={"xs": 12, "md": 4}, content=self.stock),
                    ]
                ),
                ft.ResponsiveRow(
                    [
                        ft.Container(col={"xs": 12, "md": 6}, content=self.categoria),
                        ft.Container(col={"xs": 12, "md": 6}, content=self.sucursal),
                    ]
                ),
                ft.ResponsiveRow(
                    [
                        ft.Container(col={"xs": 12, "md": 4}, content=self.fecha_vencimiento),
                        ft.Container(col={"xs": 12, "md": 4}, content=self.lote),
                        ft.Container(col={"xs": 12, "md": 4}, content=self.estado),
                    ]
                ),
                ft.ResponsiveRow(
                    [
                        ft.Container(col={"xs": 12, "md": 6}, content=self.impuesto),
                    ]
                ),
                self.image_path,
                ft.Row(
                    [
                        ft.ElevatedButton(
                            "Guardar",
                            icon=ft.Icons.SAVE_OUTLINED,
                            on_click=self.save,
                            style=ft.ButtonStyle(
                                shape=ft.RoundedRectangleBorder(radius=16),
                                bgcolor=PALETTE["primary"],
                                color=ft.Colors.WHITE,
                            ),
                        ),
                        ft.OutlinedButton("Limpiar", on_click=self._clear),
                        ft.OutlinedButton("Eliminar", on_click=self.delete),
                    ],
                    wrap=True,
                ),
            ],
            spacing=14,
            scroll=ft.ScrollMode.AUTO,
        )
        right = ft.Column(
            [
                ft.Row(
                    [
                        self.search,
                        ft.IconButton(ft.Icons.REFRESH_ROUNDED, on_click=lambda _: self.refresh()),
                    ]
                ),
                self.preview,
                table_view(self.table, expand=True),
            ],
            spacing=14,
            expand=True,
        )
        return ft.ResponsiveRow(
            [
                ft.Container(col={"xs": 12, "lg": 5}, content=shell_card(form, expand=True)),
                ft.Container(col={"xs": 12, "lg": 7}, content=shell_card(right, expand=True)),
            ],
            expand=True,
        )
