import datetime
import io
import os
import sqlite3

import flet as ft
import pandas as pd

from flet_utils import (
    DB_NAME,
    DEFAULT_COMPANY_LOGO,
    PALETTE,
    DOCUMENT_TYPES,
    FieldSpec,
    SimpleCrudModule,
    execute,
    fetch_one,
    fetch_scalar,
    get_company_info,
    image_base64,
    normalize_expiry_date,
    page_title,
    shell_card,
)


class Configuracion:
    def __init__(self, page: ft.Page, user: str | None = None) -> None:
        self.page = page
        self.user = user
        self.current_section = "empresa"
        self.navigation_container = ft.Container()
        self.section_content = ft.Container(expand=True)
        self.import_feedback = ft.Text("", color=PALETTE["muted"])
        self.file_picker = ft.FilePicker()
        services = getattr(self.page, "services", None)
        if isinstance(services, list) and self.file_picker not in services:
            services.append(self.file_picker)
        company = get_company_info()
        self.nombre = ft.TextField(label="Nombre empresa", value=company["nombre"], border_radius=16, filled=True, bgcolor=PALETTE["surface_alt"])
        self.tipo_id = ft.Dropdown(
            label="Tipo de identificacion",
            value=company["tipo_id"] or None,
            options=[ft.dropdown.Option(option) for option in DOCUMENT_TYPES],
            border_radius=16,
            filled=True,
            bgcolor=PALETTE["surface_alt"],
        )
        self.numero_id = ft.TextField(label="Numero identificacion", value=company["numero_id"], border_radius=16, filled=True, bgcolor=PALETTE["surface_alt"])
        self.direccion = ft.TextField(label="Direccion", value=company["direccion"], border_radius=16, filled=True, bgcolor=PALETTE["surface_alt"])
        self.telefono = ft.TextField(label="Telefono", value=company["telefono"], border_radius=16, filled=True, bgcolor=PALETTE["surface_alt"])
        self.email = ft.TextField(label="Email", value=company["email"], border_radius=16, filled=True, bgcolor=PALETTE["surface_alt"])
        self.website = ft.TextField(label="Sitio web", value=company["website"], border_radius=16, filled=True, bgcolor=PALETTE["surface_alt"])
        self.image_path = ft.TextField(label="Ruta del logo", value=company["image_path"], border_radius=16, filled=True, bgcolor=PALETTE["surface_alt"])

        self.categories = SimpleCrudModule(
            page=page,
            title="Categorias",
            subtitle="Catalogo de categorias.",
            table_name="categorias",
            search_field="nombre",
            fields=[FieldSpec("nombre", "Nombre")],
        )
        self.branches = SimpleCrudModule(
            page=page,
            title="Sucursales",
            subtitle="Catalogo de sucursales.",
            table_name="sucursal",
            search_field="nombre",
            fields=[FieldSpec("nombre", "Nombre")],
        )
        self.taxes = SimpleCrudModule(
            page=page,
            title="Impuestos",
            subtitle="Tabla de impuestos disponible para productos y ventas.",
            table_name="impuestos",
            search_field="nombre",
            fields=[
                FieldSpec("nombre", "Nombre"),
                FieldSpec("tasa", "Tasa"),
            ],
        )
        self.currency = SimpleCrudModule(
            page=page,
            title="Moneda",
            subtitle="Simbolo monetario usado por el sistema.",
            table_name="moneda",
            search_field="nombre",
            fields=[
                FieldSpec("nombre", "Nombre"),
                FieldSpec("simbolo", "Simbolo"),
            ],
        )

        self.section_builders = {
            "empresa": self.company_tab,
            "categorias": self.categories.build,
            "sucursales": self.branches.build,
            "impuestos": self.taxes.build,
            "moneda": self.currency.build,
            "importacion": self.import_tab,
            "plantillas": self.templates_tab,
        }

    def _notify(self, message: str, error: bool = False) -> None:
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=PALETTE["danger"] if error else PALETTE["primary"],
            open=True,
        )
        self.page.update()

    def _refresh_import_section(self) -> None:
        if self.current_section == "importacion":
            self.section_content.content = self.import_tab()
            self.navigation_container.content = self.navigation_bar()
        self.page.update()

    def save_company(self, _: ft.ControlEvent | None = None) -> None:
        values = (
            self.nombre.value or "",
            self.direccion.value or "",
            self.telefono.value or "",
            self.email.value or "",
            self.website.value or "",
            self.image_path.value or "",
            self.tipo_id.value or "",
            self.numero_id.value or "",
        )
        if not values[0].strip():
            self._notify("Ingrese al menos el nombre de la empresa.", error=True)
            return

        existing = fetch_one("SELECT id FROM empresa LIMIT 1")
        if existing:
            execute(
                """
                UPDATE empresa
                SET nombre=?, direccion=?, telefono=?, email=?, website=?, image_path=?, tipo_id=?, numero_id=?
                WHERE id=?
                """,
                values + (existing["id"],),
            )
        else:
            execute(
                """
                INSERT INTO empresa (id, nombre, direccion, telefono, email, website, image_path, tipo_id, numero_id)
                VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                values,
            )
        self._notify("Informacion de empresa actualizada.")

    def _normalize_column(self, value: str) -> str:
        return (
            value.strip()
            .lower()
            .replace(" ", "_")
            .replace("á", "a")
            .replace("é", "e")
            .replace("í", "i")
            .replace("ó", "o")
            .replace("ú", "u")
            .replace("ñ", "n")
        )

    async def _pick_excel_file(self) -> str | None:
        try:
            files = await self.file_picker.pick_files(
                dialog_title="Seleccionar archivo Excel",
                allowed_extensions=["xlsx", "xls"],
                file_type=ft.FilePickerFileType.CUSTOM,
                allow_multiple=False,
            )
        except Exception as error:
            self._notify(f"No se pudo abrir el selector de archivos: {error}", error=True)
            return None

        if not files:
            return None
        selected = files[0]
        return getattr(selected, "path", None)

    def _table_count(self, table_name: str) -> int:
        return int(fetch_scalar(f"SELECT COUNT(*) FROM {table_name}", default=0))

    def _import_dataframe(self, table_name: str, columns: list[str], rows: list[tuple]) -> int:
        placeholders = ", ".join("?" for _ in columns)
        with sqlite3.connect(DB_NAME) as connection:
            cursor = connection.cursor()
            cursor.executemany(
                f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders})",
                rows,
            )
            connection.commit()
        return len(rows)

    def _read_excel(self, file_path: str) -> pd.DataFrame:
        if not os.path.exists(file_path):
            raise FileNotFoundError("El archivo seleccionado no existe.")
        dataframe = pd.read_excel(file_path)
        dataframe.columns = [self._normalize_column(str(column)) for column in dataframe.columns]
        return dataframe.fillna("")

    def _template_definitions(self) -> dict[str, dict[str, object]]:
        return {
            "inventario": {
                "title": "Inventario",
                "file_name": "plantilla_importacion_inventario.xlsx",
                "sheet_name": "Inventario",
                "headers": [
                    "nombre",
                    "proveedor",
                    "precio",
                    "costo",
                    "stock",
                    "codigo",
                    "categoria",
                    "sucursal",
                    "estado",
                    "image_path",
                    "codigo_barras",
                    "fecha_vencimiento",
                    "lote",
                    "impuesto",
                    "impuesto_id",
                ],
            },
            "clientes": {
                "title": "Clientes",
                "file_name": "plantilla_importacion_clientes.xlsx",
                "sheet_name": "Clientes",
                "headers": ["nombre", "tipo_id", "cedula", "celular", "direccion", "correo"],
            },
            "proveedores": {
                "title": "Proveedor",
                "file_name": "plantilla_importacion_proveedor.xlsx",
                "sheet_name": "Proveedor",
                "headers": ["nombre", "tipo_id", "identificacion", "celular", "direccion", "correo"],
            },
            "pedidos": {
                "title": "Pedidos",
                "file_name": "plantilla_importacion_pedidos.xlsx",
                "sheet_name": "Pedidos",
                "headers": ["numero_pedido", "proveedor", "producto", "cantidad", "fecha", "hora", "precio", "costo", "fecha_vencimiento", "lote"],
            },
        }

    def _build_template_workbook(self, template_keys: list[str]) -> bytes:
        templates = self._template_definitions()
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            for template_key in template_keys:
                template = templates[template_key]
                headers = template["headers"]
                dataframe = pd.DataFrame(columns=headers)
                dataframe.to_excel(writer, index=False, sheet_name=str(template["sheet_name"]))
                worksheet = writer.sheets[str(template["sheet_name"])]
                for index, header in enumerate(headers, start=1):
                    worksheet.column_dimensions[worksheet.cell(row=1, column=index).column_letter].width = max(len(header) + 4, 14)
                worksheet.freeze_panes = "A2"
        return output.getvalue()

    async def download_template(self, template_key: str | None = None) -> None:
        templates = self._template_definitions()
        if template_key:
            template_keys = [template_key]
            file_name = str(templates[template_key]["file_name"])
            title = str(templates[template_key]["title"])
        else:
            template_keys = list(templates.keys())
            file_name = "plantillas_importacion_masiva.xlsx"
            title = "todas las plantillas"

        try:
            await self.file_picker.save_file(
                dialog_title=f"Guardar plantilla de {title}",
                file_name=file_name,
                file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=["xlsx"],
                src_bytes=self._build_template_workbook(template_keys),
            )
            self.import_feedback.value = f"Plantilla descargada: {file_name}"
            self._notify(self.import_feedback.value)
        except Exception as error:
            self._notify(f"No se pudo descargar la plantilla: {error}", error=True)
        self._refresh_import_section()

    def _download_template_handler(self, template_key: str | None = None):
        async def handler(_: ft.ControlEvent | None = None) -> None:
            await self.download_template(template_key)

        return handler

    async def import_clientes(self, _: ft.ControlEvent | None = None) -> None:
        file_path = await self._pick_excel_file()
        if not file_path:
            return
        try:
            dataframe = self._read_excel(file_path)
            required = ["nombre", "tipo_id", "cedula", "celular", "direccion", "correo"]
            missing = [column for column in required if column not in dataframe.columns]
            if missing:
                raise ValueError(f"Faltan columnas requeridas: {', '.join(missing)}")
            rows = [
                (
                    str(row["nombre"]).strip(),
                    str(row["tipo_id"]).strip(),
                    str(row["cedula"]).strip(),
                    str(row["celular"]).strip(),
                    str(row["direccion"]).strip(),
                    str(row["correo"]).strip(),
                )
                for _, row in dataframe.iterrows()
                if str(row["nombre"]).strip()
            ]
            imported = self._import_dataframe("clientes", required, rows)
            self.import_feedback.value = f"Clientes importados correctamente: {imported} registros."
            self._notify(self.import_feedback.value)
        except Exception as error:
            self._notify(f"No se pudo importar clientes: {error}", error=True)
        self._refresh_import_section()

    async def import_proveedores(self, _: ft.ControlEvent | None = None) -> None:
        file_path = await self._pick_excel_file()
        if not file_path:
            return
        try:
            dataframe = self._read_excel(file_path)
            required = ["nombre", "tipo_id", "identificacion", "celular", "direccion", "correo"]
            missing = [column for column in required if column not in dataframe.columns]
            if missing:
                raise ValueError(f"Faltan columnas requeridas: {', '.join(missing)}")
            rows = [
                (
                    str(row["nombre"]).strip(),
                    str(row["tipo_id"]).strip(),
                    str(row["identificacion"]).strip(),
                    str(row["celular"]).strip(),
                    str(row["direccion"]).strip(),
                    str(row["correo"]).strip(),
                )
                for _, row in dataframe.iterrows()
                if str(row["nombre"]).strip()
            ]
            imported = self._import_dataframe("proveedores", required, rows)
            self.import_feedback.value = f"Proveedores importados correctamente: {imported} registros."
            self._notify(self.import_feedback.value)
        except Exception as error:
            self._notify(f"No se pudo importar proveedores: {error}", error=True)
        self._refresh_import_section()

    async def import_pedidos(self, _: ft.ControlEvent | None = None) -> None:
        file_path = await self._pick_excel_file()
        if not file_path:
            return
        try:
            dataframe = self._read_excel(file_path)
            required = ["numero_pedido", "proveedor", "producto", "cantidad"]
            missing = [column for column in required if column not in dataframe.columns]
            if missing:
                raise ValueError(f"Faltan columnas requeridas: {', '.join(missing)}")
            now = datetime.datetime.now()
            rows = []
            for _, row in dataframe.iterrows():
                if not str(row["numero_pedido"]).strip():
                    continue
                rows.append(
                    (
                        int(float(row["numero_pedido"])),
                        str(row["proveedor"]).strip(),
                        str(row["producto"]).strip(),
                        int(float(row["cantidad"])),
                        str(row["fecha"]).strip() or now.strftime("%d-%m-%Y"),
                        str(row["hora"]).strip() or now.strftime("%H:%M:%S"),
                        float(row["precio"]) if str(row.get("precio", "")).strip() else 0.0,
                        float(row["costo"]) if str(row.get("costo", "")).strip() else 0.0,
                        normalize_expiry_date(row.get("fecha_vencimiento", "")),
                        str(row.get("lote", "")).strip(),
                    )
                )
            imported = self._import_dataframe(
                "pedidos",
                ["numero_pedido", "proveedor", "producto", "cantidad", "fecha", "hora", "precio", "costo", "fecha_vencimiento", "lote"],
                rows,
            )
            self.import_feedback.value = f"Pedidos importados correctamente: {imported} registros."
            self._notify(self.import_feedback.value)
        except Exception as error:
            self._notify(f"No se pudo importar pedidos: {error}", error=True)
        self._refresh_import_section()

    async def import_inventario(self, _: ft.ControlEvent | None = None) -> None:
        file_path = await self._pick_excel_file()
        if not file_path:
            return
        try:
            dataframe = self._read_excel(file_path)
            required = ["nombre", "proveedor", "precio", "costo", "stock", "codigo"]
            missing = [column for column in required if column not in dataframe.columns]
            if missing:
                raise ValueError(f"Faltan columnas requeridas: {', '.join(missing)}")
            with sqlite3.connect(DB_NAME) as connection:
                cursor = connection.cursor()
                cursor.execute("SELECT id, nombre FROM impuestos")
                impuesto_rows = cursor.fetchall()
            impuestos = {self._normalize_column(str(nombre)): impuesto_id for impuesto_id, nombre in impuesto_rows}

            rows = []
            for _, row in dataframe.iterrows():
                nombre = str(row["nombre"]).strip()
                if not nombre:
                    continue
                impuesto_name = self._normalize_column(str(row.get("impuesto", "")).strip())
                impuesto_id = None
                if "impuesto_id" in dataframe.columns and str(row.get("impuesto_id", "")).strip():
                    impuesto_id = int(float(row["impuesto_id"]))
                elif impuesto_name:
                    impuesto_id = impuestos.get(impuesto_name)

                codigo = str(row["codigo"]).strip()
                codigo_barras = (
                    str(row.get("codigo_barras", "")).strip()
                    or str(row.get("codigo_de_barras", "")).strip()
                    or str(row.get("barcode", "")).strip()
                    or codigo
                )

                rows.append(
                    (
                        nombre,
                        str(row["proveedor"]).strip(),
                        float(row["precio"]),
                        float(row["costo"]),
                        int(float(row["stock"])),
                        str(row.get("categoria", "")).strip(),
                        str(row.get("sucursal", "")).strip(),
                        str(row.get("estado", "")).strip() or "Activo",
                        str(row.get("image_path", "")).strip(),
                        codigo,
                        codigo_barras,
                        impuesto_id,
                        normalize_expiry_date(row.get("fecha_vencimiento", "")),
                        str(row.get("lote", "")).strip(),
                    )
                )
            imported = self._import_dataframe(
                "inventario",
                ["nombre", "proveedor", "precio", "costo", "stock", "categoria", "sucursal", "estado", "image_path", "codigo", "codigo_barras", "impuesto_id", "fecha_vencimiento", "lote"],
                rows,
            )
            self.import_feedback.value = f"Inventario importado correctamente: {imported} registros."
            self._notify(self.import_feedback.value)
        except Exception as error:
            self._notify(f"No se pudo importar inventario: {error}", error=True)
        self._refresh_import_section()

    def import_tab(self) -> ft.Control:
        stats = ft.ResponsiveRow(
            [
                ft.Container(col={"xs": 12, "md": 6, "xl": 3}, content=shell_card(ft.Column([ft.Text("Inventario", size=18, weight=ft.FontWeight.BOLD), ft.Text(str(self._table_count("inventario")), size=28)]))),
                ft.Container(col={"xs": 12, "md": 6, "xl": 3}, content=shell_card(ft.Column([ft.Text("Clientes", size=18, weight=ft.FontWeight.BOLD), ft.Text(str(self._table_count("clientes")), size=28)]))),
                ft.Container(col={"xs": 12, "md": 6, "xl": 3}, content=shell_card(ft.Column([ft.Text("Proveedor", size=18, weight=ft.FontWeight.BOLD), ft.Text(str(self._table_count("proveedores")), size=28)]))),
                ft.Container(col={"xs": 12, "md": 6, "xl": 3}, content=shell_card(ft.Column([ft.Text("Pedidos", size=18, weight=ft.FontWeight.BOLD), ft.Text(str(self._table_count("pedidos")), size=28)]))),
            ]
        )
        return ft.Column(
            [
                page_title("Importacion Masiva", "Carga archivos Excel por tabla para insertar registros masivos en el sistema."),
                stats,
                shell_card(
                    ft.Column(
                        [
                            ft.Text("Botones de importacion", size=20, weight=ft.FontWeight.BOLD),
                            ft.Text("Cada archivo Excel debe traer una hoja con encabezados compatibles. La importacion agrega registros a la tabla correspondiente.", color=PALETTE["muted"]),
                            ft.Row(
                                [
                                    ft.ElevatedButton("Importar Inventario", icon=ft.Icons.INVENTORY_2_OUTLINED, on_click=self.import_inventario),
                                    ft.ElevatedButton("Importar Clientes", icon=ft.Icons.GROUPS_OUTLINED, on_click=self.import_clientes),
                                ],
                                wrap=True,
                            ),
                            ft.Row(
                                [
                                    ft.ElevatedButton("Importar Proveedor", icon=ft.Icons.LOCAL_SHIPPING_OUTLINED, on_click=self.import_proveedores),
                                    ft.ElevatedButton("Importar Pedidos", icon=ft.Icons.SHOPPING_BAG_OUTLINED, on_click=self.import_pedidos),
                                    ft.ElevatedButton("Descargar Plantillas", icon=ft.Icons.DOWNLOAD_OUTLINED, on_click=self._download_template_handler()),
                                ],
                                wrap=True,
                            ),
                            self.import_feedback,
                        ],
                        spacing=14,
                    )
                ),
                shell_card(
                    ft.Column(
                        [
                            ft.Text("Columnas esperadas", size=20, weight=ft.FontWeight.BOLD),
                            ft.Text("Inventario: nombre, proveedor, precio, costo, stock, codigo, fecha_vencimiento, lote, categoria, sucursal, estado, image_path, codigo_barras opcional, impuesto o impuesto_id"),
                            ft.Text("Clientes: nombre, tipo_id, cedula, celular, direccion, correo"),
                            ft.Text("Proveedor: nombre, tipo_id, identificacion, celular, direccion, correo"),
                            ft.Text("Pedidos: numero_pedido, proveedor, producto, cantidad, fecha, hora, precio, costo, fecha_vencimiento, lote"),
                        ],
                        spacing=10,
                    )
                ),
            ],
            spacing=18,
            scroll=ft.ScrollMode.AUTO,
        )

    def templates_tab(self) -> ft.Control:
        templates = self._template_definitions()
        buttons = [
            ft.ElevatedButton(
                "Todas las plantillas",
                icon=ft.Icons.DOWNLOAD_OUTLINED,
                on_click=self._download_template_handler(),
            )
        ]
        for template_key, template in templates.items():
            buttons.append(
                ft.ElevatedButton(
                    f"Plantilla {template['title']}",
                    icon=ft.Icons.TABLE_VIEW_OUTLINED,
                    on_click=self._download_template_handler(template_key),
                )
            )

        return ft.Column(
            [
                page_title("Plantillas Excel", "Descarga archivos listos con las cabeceras para importacion masiva."),
                shell_card(
                    ft.Column(
                        [
                            ft.Text("Descargar planillas", size=20, weight=ft.FontWeight.BOLD),
                            ft.Text("Puedes bajar un libro con todas las hojas o una plantilla individual por modulo.", color=PALETTE["muted"]),
                            ft.Row(buttons, wrap=True),
                            self.import_feedback,
                        ],
                        spacing=14,
                    )
                ),
                shell_card(
                    ft.Column(
                        [
                            ft.Text("Cabeceras incluidas", size=20, weight=ft.FontWeight.BOLD),
                            *[
                                ft.Text(f"{template['title']}: {', '.join(template['headers'])}")
                                for template in templates.values()
                            ],
                        ],
                        spacing=10,
                    )
                ),
            ],
            spacing=18,
            scroll=ft.ScrollMode.AUTO,
        )

    def company_tab(self) -> ft.Control:
        preview = image_base64(self.image_path.value or "", DEFAULT_COMPANY_LOGO)
        return ft.ResponsiveRow(
            [
                ft.Container(
                    col={"xs": 12, "lg": 7},
                    content=shell_card(
                        ft.Column(
                            [
                                page_title("Empresa", "Actualiza los datos institucionales usados en login y dashboard."),
                                self.nombre,
                                ft.ResponsiveRow(
                                    [
                                        ft.Container(col={"xs": 12, "md": 5}, content=self.tipo_id),
                                        ft.Container(col={"xs": 12, "md": 7}, content=self.numero_id),
                                    ]
                                ),
                                self.direccion,
                                ft.ResponsiveRow(
                                    [
                                        ft.Container(col={"xs": 12, "md": 6}, content=self.telefono),
                                        ft.Container(col={"xs": 12, "md": 6}, content=self.email),
                                    ]
                                ),
                                self.website,
                                self.image_path,
                                ft.ElevatedButton(
                                    "Guardar empresa",
                                    icon=ft.Icons.SAVE_OUTLINED,
                                    on_click=self.save_company,
                                    style=ft.ButtonStyle(
                                        shape=ft.RoundedRectangleBorder(radius=16),
                                        bgcolor=PALETTE["primary"],
                                        color=ft.Colors.WHITE,
                                    ),
                                ),
                            ],
                            spacing=14,
                        ),
                        expand=True,
                    ),
                ),
                ft.Container(
                    col={"xs": 12, "lg": 5},
                    content=shell_card(
                        ft.Column(
                            [
                                ft.Text("Vista previa", size=22, weight=ft.FontWeight.BOLD),
                                ft.Container(
                                    height=300,
                                    alignment=ft.Alignment(0, 0),
                                    content=ft.Image(src=preview, height=300, fit="contain")
                                    if preview
                                    else ft.Icon(ft.Icons.STOREFRONT, size=80),
                                ),
                                ft.Text(
                                    "Puedes seguir usando la ruta actual de la imagen sin mover archivos del proyecto.",
                                    color=PALETTE["muted"],
                                ),
                            ],
                            spacing=12,
                        ),
                        expand=True,
                    ),
                ),
            ]
        )

    def change_section(self, section: str) -> None:
        self.current_section = section
        self.navigation_container.content = self.navigation_bar()
        self.section_content.content = self.section_builders[section]()
        self.page.update()

    def navigation_bar(self) -> ft.Control:
        buttons = [
            ("empresa", "Empresa"),
            ("categorias", "Categorias"),
            ("sucursales", "Sucursales"),
            ("impuestos", "Impuestos"),
            ("moneda", "Moneda"),
            ("importacion", "Importacion Excel"),
            ("plantillas", "Plantillas Excel"),
        ]
        controls: list[ft.Control] = []
        for section, label in buttons:
            active = section == self.current_section
            controls.append(
                ft.TextButton(
                    label,
                    on_click=lambda event, section=section: self.change_section(section),
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=16),
                        bgcolor=PALETTE["primary"] if active else PALETTE["surface"],
                        color=ft.Colors.WHITE if active else PALETTE["text"],
                        side=ft.BorderSide(1, PALETTE["border"]),
                        padding=16,
                    ),
                )
            )
        return ft.Row(controls, wrap=True)

    def build(self) -> ft.Control:
        self.navigation_container.content = self.navigation_bar()
        self.section_content.content = self.section_builders[self.current_section]()
        return ft.Column(
            [
                page_title("Configuracion", "Catalogos y datos maestros del sistema."),
                self.navigation_container,
                self.section_content,
            ],
            spacing=16,
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        )
