from __future__ import annotations

import os
import sqlite3
import sys
from dataclasses import dataclass, fields, is_dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import flet as ft
from flet.controls.base_control import BaseControl

PROJECT_DIR = Path(__file__).resolve().parent
DB_NAME = str(PROJECT_DIR / "database.db")
DEFAULT_COMPANY_LOGO = "imagenes/logo_at_logistica.png"
APP_TITLE = "Punto de Venta Versión 4.2.1"

PALETTE = {
    "bg": "#EAF2FF",
    "surface": "#FFFFFF",
    "surface_alt": "#E1ECFB",
    "surface_soft": "#F6FAFF",
    "sidebar": "#F7FAFF",
    "input_fill": "#EDF4FF",
    "primary": "#1565C0",
    "primary_soft": "#D9E9FF",
    "secondary": "#0F766E",
    "secondary_soft": "#D5F5F0",
    "accent": "#F59E0B",
    "text": "#10213A",
    "muted": "#445A77",
    "border": "#B9CBE3",
    "danger": "#C62828",
    "danger_soft": "#FDE7E9",
    "success": "#15803D",
    "success_soft": "#DCFCE7",
}

EXPIRY_WARNING_DAYS = 10

DOCUMENT_TYPES = [
    "CC",
    "CE",
    "NIT",
    "RUT",
    "RUC",
    "RFC",
    "CUIT",
    "CNPJ",
    "CPF",
    "NIF",
    "RIF",
    "NITE",
    "RNC",
    "RTN",
]

MODULES = [
    ("dashboard", "Resumen", ft.Icons.DASHBOARD_OUTLINED),
    ("ventas", "Ventas", ft.Icons.POINT_OF_SALE_OUTLINED),
    ("cotizaciones", "Cotizaciones", ft.Icons.REQUEST_QUOTE_OUTLINED),
    ("inventario", "Inventario", ft.Icons.INVENTORY_2_OUTLINED),
    ("clientes", "Clientes", ft.Icons.GROUPS_OUTLINED),
    ("proveedor", "Proveedor", ft.Icons.LOCAL_SHIPPING_OUTLINED),
    ("pedidos", "Pedidos", ft.Icons.SHOPPING_BAG_OUTLINED),
    ("reportes", "Reportes", ft.Icons.INSIGHTS_OUTLINED),
    ("configuracion", "Configuracion", ft.Icons.SETTINGS_OUTLINED),
    ("gastos", "Gastos", ft.Icons.RECEIPT_LONG_OUTLINED),
    ("usuarios", "Usuarios", ft.Icons.ADMIN_PANEL_SETTINGS_OUTLINED),
    ("informacion", "About Us", ft.Icons.INFO_OUTLINE),
]


@dataclass(slots=True)
class FieldSpec:
    name: str
    label: str
    kind: str = "text"
    options: list[str] | None = None
    password: bool = False
    read_only: bool = False
    multiline: bool = False


INPUT_TEXT_STYLE = ft.TextStyle(
    color=PALETTE["text"],
    size=16,
    weight=ft.FontWeight.W_600,
)
LABEL_TEXT_STYLE = ft.TextStyle(
    color=PALETTE["text"],
    size=14,
    weight=ft.FontWeight.W_600,
)
HINT_TEXT_STYLE = ft.TextStyle(
    color=PALETTE["muted"],
    size=14,
    weight=ft.FontWeight.W_500,
)
HELPER_TEXT_STYLE = ft.TextStyle(
    color=PALETTE["muted"],
    size=13,
)
ERROR_TEXT_STYLE = ft.TextStyle(
    color=PALETTE["danger"],
    size=13,
    weight=ft.FontWeight.W_600,
)

BUTTON_TEXT_STYLE = ft.TextStyle(
    size=15,
    weight=ft.FontWeight.W_600,
)


def _iter_controls(value: Any, seen: set[int]) -> list[BaseControl]:
    items: list[BaseControl] = []
    if isinstance(value, BaseControl):
        if id(value) not in seen:
            items.append(value)
        return items
    if isinstance(value, (list, tuple)):
        for item in value:
            items.extend(_iter_controls(item, seen))
    elif isinstance(value, dict):
        for item in value.values():
            items.extend(_iter_controls(item, seen))
    return items


def _walk_controls(control: BaseControl, seen: set[int] | None = None) -> list[BaseControl]:
    seen = seen or set()
    if id(control) in seen:
        return []
    seen.add(id(control))
    items = [control]
    if not is_dataclass(control):
        return items
    for field in fields(control):
        if field.metadata.get("skip"):
            continue
        try:
            value = getattr(control, field.name)
        except AttributeError:
            continue
        for child in _iter_controls(value, seen):
            items.extend(_walk_controls(child, seen))
    return items


def _apply_input_style(control: ft.TextField | ft.Dropdown) -> None:
    if control.height is None and not (
        isinstance(control, ft.TextField) and control.multiline
    ):
        control.height = 56
    control.filled = True
    control.color = PALETTE["text"]
    control.focused_color = PALETTE["text"]
    control.text_style = INPUT_TEXT_STYLE
    control.label_style = LABEL_TEXT_STYLE
    if isinstance(control.label, str):
        control.label = ft.Text(
            control.label,
            size=14,
            weight=ft.FontWeight.W_600,
            color=PALETTE["text"],
            max_lines=1,
            no_wrap=True,
            overflow=ft.TextOverflow.ELLIPSIS,
        )
    control.hint_style = HINT_TEXT_STYLE
    control.helper_style = HELPER_TEXT_STYLE
    control.error_style = ERROR_TEXT_STYLE
    control.border = ft.InputBorder.OUTLINE
    control.border_width = 1.4
    control.focused_border_width = 2
    control.border_color = PALETTE["border"]
    control.focused_border_color = PALETTE["primary"]
    control.content_padding = ft.Padding.symmetric(horizontal=14, vertical=17)
    if getattr(control, "border_radius", None) is None:
        control.border_radius = 16
    if isinstance(control, ft.TextField):
        control.bgcolor = PALETTE["input_fill"]
        control.fill_color = PALETTE["input_fill"]
        control.focused_bgcolor = PALETTE["surface"]
        control.hover_color = PALETTE["surface"]
        control.cursor_color = PALETTE["primary"]
        control.selection_color = PALETTE["primary_soft"]
    elif isinstance(control, ft.Dropdown):
        control.text_size = 16
        option_labels: list[str] = []
        for option in control.options:
            label = option.text or option.key
            if not label and isinstance(option.content, ft.Text):
                label = option.content.value
            option_labels.append(str(label or ""))

        # Keep the popup proportional to its contents instead of letting an
        # infinite-width form control expand the overlay across the screen.
        field_label = (
            str(control.label.value or "")
            if isinstance(control.label, ft.Text)
            else str(control.label or "")
        )
        longest_label = max(
            [len(field_label), *(len(label) for label in option_labels)],
            default=12,
        )
        if control.width is None:
            control.width = max(220, min(300, longest_label * 9 + 80))
        control.menu_width = max(180, min(440, longest_label * 9 + 72))
        control.menu_height = min(320, max(112, len(option_labels) * 48 + 16))
        control.expanded_insets = 0
        control.fill_color = PALETTE["surface_soft"]
        control.bgcolor = PALETTE["surface"]
        control.focused_bgcolor = PALETTE["surface_soft"]
        control.hover_color = PALETTE["surface"]
        control.menu_style = ft.MenuStyle(
            bgcolor=PALETTE["surface"],
            shadow_color="#240E1A2A",
            elevation=8,
            side=ft.BorderSide(1.2, PALETTE["border"]),
            shape=ft.RoundedRectangleBorder(radius=16),
            padding=ft.Padding.symmetric(vertical=8),
        )


def apply_visual_theme(root: ft.Control | BaseControl | None) -> ft.Control | BaseControl | None:
    if root is None or not isinstance(root, BaseControl):
        return root

    for control in _walk_controls(root):
        if isinstance(control, ft.TextField | ft.Dropdown):
            _apply_input_style(control)
        elif isinstance(control, ft.DataTable):
            control.border = None
            control.heading_row_color = PALETTE["surface_alt"]
            control.border_radius = 0
            control.divider_thickness = 1
            control.column_spacing = control.column_spacing or 16
            control.horizontal_margin = control.horizontal_margin or 14
        elif isinstance(control, ft.NavigationRail):
            control.bgcolor = PALETTE["sidebar"]
            control.indicator_color = PALETTE["primary_soft"]
        elif isinstance(control, ft.AlertDialog):
            control.bgcolor = PALETTE["surface"]
            control.shape = ft.RoundedRectangleBorder(radius=24)
        elif isinstance(control, ft.SnackBar):
            control.bgcolor = control.bgcolor or PALETTE["primary"]
        elif isinstance(control, (ft.ElevatedButton, ft.OutlinedButton, ft.TextButton)):
            if control.style is None:
                control.style = ft.ButtonStyle()
            if control.style.text_style is None:
                control.style.text_style = BUTTON_TEXT_STYLE
        elif isinstance(control, ft.Text):
            if control.color is None:
                control.color = PALETTE["text"]
            if control.size is None:
                control.size = 15
            if control.weight is None and control.size >= 20:
                control.weight = ft.FontWeight.BOLD
            elif control.weight is None and control.size >= 16:
                control.weight = ft.FontWeight.W_600
    return root


def show_dialog(page: ft.Page, dialog: ft.AlertDialog) -> None:
    apply_visual_theme(dialog)
    if hasattr(page, "show_dialog"):
        page.show_dialog(dialog)
    elif hasattr(page, "open"):
        page.open(dialog)
    else:
        setattr(page, "dialog", dialog)
    if hasattr(page, "update"):
        page.update()


def close_dialog(page: ft.Page, dialog: ft.AlertDialog | None = None) -> None:
    if hasattr(page, "pop_dialog"):
        page.pop_dialog()
    elif hasattr(page, "close") and dialog is not None:
        page.close(dialog)
    else:
        if hasattr(page, "dialog"):
            setattr(page, "dialog", None)
    if hasattr(page, "update"):
        page.update()


def responsive_dialog_width(page: ft.Page, preferred: int | float) -> int | float:
    """Keep dialogs inside narrow web and mobile viewports."""
    if not page.width:
        return preferred
    return max(260, min(preferred, page.width - 48))


def responsive_dialog_height(page: ft.Page, preferred: int | float) -> int | float:
    if not page.height:
        return preferred
    return max(240, min(preferred, page.height - 120))


def parse_expiry_date(value: object) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def normalize_expiry_date(value: object) -> str:
    expiry_date = parse_expiry_date(value)
    return expiry_date.strftime("%Y-%m-%d") if expiry_date else str(value or "").strip()


def expiry_status(value: object) -> tuple[str, str, str]:
    expiry_date = parse_expiry_date(value)
    if not expiry_date:
        return ("Sin fecha", PALETTE["muted"], ft.Icons.HELP_OUTLINE)
    remaining_days = (expiry_date - date.today()).days
    if remaining_days < 0:
        return ("Vencido", PALETTE["danger"], ft.Icons.ERROR_OUTLINE)
    if remaining_days <= EXPIRY_WARNING_DAYS:
        return (f"Vence en {remaining_days} dias", PALETTE["accent"], ft.Icons.WARNING_AMBER_ROUNDED)
    return ("Vigente", PALETTE["success"], ft.Icons.CHECK_CIRCLE_OUTLINE)


def expiry_badge(value: object) -> ft.Row:
    label, color, icon = expiry_status(value)
    return ft.Row(
        [
            ft.Icon(icon, size=16, color=color),
            ft.Text(label, color=color, weight=ft.FontWeight.W_600),
        ],
        spacing=4,
        tight=True,
    )


class SimpleCrudModule:
    def __init__(
        self,
        page: ft.Page,
        title: str,
        subtitle: str,
        table_name: str,
        fields: list[FieldSpec],
        search_field: str,
        id_field: str = "id",
        delete_pin: str | None = None,
        page_size: int = 12,
    ) -> None:
        self.page = page
        self.title = title
        self.subtitle = subtitle
        self.table_name = table_name
        self.fields = fields
        self.search_field = search_field
        self.id_field = id_field
        self.delete_pin = delete_pin
        self.page_size = page_size
        self.current_page = 0
        self.selected_id: int | None = None
        self.form_controls = self._build_form_controls()
        self.search = ft.TextField(
            label="Buscar",
            border_radius=16,
            filled=True,
            bgcolor=PALETTE["surface_alt"],
            prefix_icon=ft.Icons.SEARCH,
            on_submit=lambda _: self.refresh(),
        )
        self.page_label = ft.Text("", color=PALETTE["muted"])
        self.table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("ID", weight=ft.FontWeight.BOLD))
            ]
            + [
                ft.DataColumn(ft.Text(field.label, weight=ft.FontWeight.BOLD))
                for field in self.fields
            ],
            rows=[],
            border=ft.Border.all(1, PALETTE["border"]),
            border_radius=12,
            heading_row_color=PALETTE["surface_alt"],
            data_row_min_height=52,
            data_row_max_height=64,
            column_spacing=20,
            horizontal_margin=16,
        )

    def _build_form_controls(self) -> dict[str, ft.Control]:
        controls: dict[str, ft.Control] = {}
        for field in self.fields:
            if field.kind == "dropdown":
                control = ft.Dropdown(
                    label=field.label,
                    options=[ft.dropdown.Option(option) for option in field.options or []],
                    border_radius=16,
                    filled=True,
                    bgcolor=PALETTE["surface_alt"],
                )
            else:
                control = ft.TextField(
                    label=field.label,
                    password=field.password,
                    can_reveal_password=field.password,
                    read_only=field.read_only,
                    multiline=field.multiline,
                    min_lines=3 if field.multiline else None,
                    max_lines=4 if field.multiline else 1,
                    border_radius=16,
                    filled=True,
                    bgcolor=PALETTE["surface_alt"],
                )
            controls[field.name] = control
        return controls

    def _notify(self, message: str, error: bool = False) -> None:
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=PALETTE["danger"] if error else PALETTE["primary"],
            open=True,
        )
        self.page.update()

    def _base_query(self) -> tuple[str, tuple[Any, ...]]:
        search_text = (self.search.value or "").strip()
        query = f"SELECT * FROM {self.table_name}"
        params: tuple[Any, ...] = ()
        if search_text:
            query += f" WHERE {self.search_field} LIKE ?"
            params = (f"%{search_text}%",)
        return query, params

    def _count_rows(self) -> int:
        query, params = self._base_query()
        return fetch_scalar(f"SELECT COUNT(*) FROM ({query}) AS subquery", params, default=0)

    def refresh(self) -> None:
        base_query, params = self._base_query()
        offset = self.current_page * self.page_size
        rows = fetch_all(
            f"{base_query} ORDER BY {self.id_field} DESC LIMIT ? OFFSET ?",
            params + (self.page_size, offset),
        )
        self.table.rows = [
            ft.DataRow(
                cells=[ft.DataCell(ft.Text(str(row.get(self.id_field, ""))))]
                + [
                    ft.DataCell(ft.Text(str(row.get(field.name, ""))))
                    for field in self.fields
                ],
                on_select_change=lambda event, row=row: self.select_row(row),
            )
            for row in rows
        ]
        total_rows = self._count_rows()
        total_pages = max(1, (total_rows + self.page_size - 1) // self.page_size)
        if self.current_page >= total_pages:
            self.current_page = max(0, total_pages - 1)
        self.page_label.value = f"Pagina {self.current_page + 1} de {total_pages}"
        self.page.update()

    def select_row(self, row: dict[str, Any]) -> None:
        self.selected_id = int(row[self.id_field])
        for field in self.fields:
            control = self.form_controls[field.name]
            value = row.get(field.name, "")
            if isinstance(control, ft.Dropdown):
                control.value = str(value) if value is not None else None
            else:
                control.value = "" if value is None else str(value)
        self.page.update()

    def clear_form(self, _: ft.ControlEvent | None = None) -> None:
        self.selected_id = None
        for control in self.form_controls.values():
            if isinstance(control, ft.Dropdown):
                control.value = None
            else:
                control.value = ""
        self.page.update()

    def _field_value(self, field: FieldSpec) -> str:
        control = self.form_controls[field.name]
        value = control.value if hasattr(control, "value") else ""
        return (value or "").strip()

    def validate(self) -> bool:
        missing = [field.label for field in self.fields if not self._field_value(field)]
        if missing:
            self._notify("Complete todos los campos obligatorios.", error=True)
            return False
        return True

    def save(self, _: ft.ControlEvent | None = None) -> None:
        if not self.validate():
            return
        values = [self._field_value(field) for field in self.fields]
        columns = ", ".join(field.name for field in self.fields)
        placeholders = ", ".join("?" for _ in self.fields)
        try:
            if self.selected_id is None:
                execute(
                    f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})",
                    tuple(values),
                )
                self._notify("Registro creado correctamente.")
            else:
                set_clause = ", ".join(f"{field.name}=?" for field in self.fields)
                execute(
                    f"UPDATE {self.table_name} SET {set_clause} WHERE {self.id_field}=?",
                    tuple(values) + (self.selected_id,),
                )
                self._notify("Registro actualizado correctamente.")
        except sqlite3.Error as error:
            self._notify(f"No se pudo guardar el registro: {error}", error=True)
            return
        self.clear_form()
        self.refresh()

    def _perform_delete(self, pin_value: str | None = None) -> None:
        if self.selected_id is None:
            self._notify("Seleccione un registro para eliminar.", error=True)
            return
        if self.delete_pin and pin_value != self.delete_pin:
            self._notify("PIN incorrecto.", error=True)
            return
        try:
            execute(
                f"DELETE FROM {self.table_name} WHERE {self.id_field}=?",
                (self.selected_id,),
            )
        except sqlite3.Error as error:
            self._notify(f"No se pudo eliminar el registro: {error}", error=True)
            return
        self._notify("Registro eliminado correctamente.")
        self.clear_form()
        self.refresh()

    def delete(self, _: ft.ControlEvent | None = None) -> None:
        if self.delete_pin:
            pin_input = ft.TextField(
                label="PIN de seguridad",
                password=True,
                can_reveal_password=True,
                border_radius=14,
            )

            def confirm_delete(event: ft.ControlEvent) -> None:
                close_dialog(self.page, dialog)
                self._perform_delete(pin_input.value)

            dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text("Confirmar eliminacion"),
                content=pin_input,
                actions=[
                    ft.TextButton("Cancelar", on_click=lambda event: close_dialog(self.page, dialog)),
                    ft.ElevatedButton("Eliminar", on_click=confirm_delete),
                ],
            )
            show_dialog(self.page, dialog)
            return
        self._perform_delete()

    def prev_page(self, _: ft.ControlEvent | None = None) -> None:
        if self.current_page > 0:
            self.current_page -= 1
            self.refresh()

    def next_page(self, _: ft.ControlEvent | None = None) -> None:
        total_rows = self._count_rows()
        total_pages = max(1, (total_rows + self.page_size - 1) // self.page_size)
        if self.current_page < total_pages - 1:
            self.current_page += 1
            self.refresh()

    def build(self) -> ft.Control:
        self.refresh()
        action_bar = ft.Row(
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
                ft.OutlinedButton("Limpiar", icon=ft.Icons.CLEANING_SERVICES_OUTLINED, on_click=self.clear_form),
                ft.OutlinedButton("Eliminar", icon=ft.Icons.DELETE_OUTLINE, on_click=self.delete),
            ],
            wrap=True,
        )
        form = ft.Column(
            [
                page_title(self.title, self.subtitle),
                *self.form_controls.values(),
                action_bar,
            ],
            spacing=14,
            scroll=ft.ScrollMode.AUTO,
        )
        table_section = ft.Column(
            [
                ft.Row(
                    [
                        self.search,
                        ft.IconButton(ft.Icons.REFRESH_ROUNDED, on_click=lambda _: self.refresh()),
                    ]
                ),
                ft.Row(
                    [
                        ft.OutlinedButton("Anterior", on_click=self.prev_page),
                        ft.OutlinedButton("Siguiente", on_click=self.next_page),
                        self.page_label,
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                table_view(self.table, expand=True),
            ],
            expand=True,
            spacing=14,
        )
        return ft.ResponsiveRow(
            [
                ft.Container(col={"xs": 12, "lg": 5}, content=shell_card(form, expand=True)),
                ft.Container(col={"xs": 12, "lg": 7}, content=shell_card(table_section, expand=True)),
            ],
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        )


def resolve_path(path: str) -> str:
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = str(PROJECT_DIR)
    return os.path.join(base_path, path)


def asset_path(path: str) -> str:
    return str(Path(path).as_posix())


def image_base64(path: str | None, fallback: str | None = None) -> str | None:
    candidates = [path, fallback]
    for candidate in candidates:
        if not candidate:
            continue
        abs_candidate = resolve_path(candidate)
        if not os.path.exists(abs_candidate):
            continue
        return abs_candidate
    return None


def dict_factory(cursor: sqlite3.Cursor, row: sqlite3.Row) -> dict[str, Any]:
    return {column[0]: row[index] for index, column in enumerate(cursor.description)}


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_NAME)
    connection.row_factory = dict_factory
    return connection


def fetch_all(query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()


def fetch_one(query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    rows = fetch_all(query, params)
    return rows[0] if rows else None


def fetch_scalar(query: str, params: tuple[Any, ...] = (), default: Any = None) -> Any:
    row = fetch_one(query, params)
    if not row:
        return default
    return next(iter(row.values()))


def execute(query: str, params: tuple[Any, ...] = ()) -> None:
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(query, params)
        connection.commit()


def ensure_app_schema() -> None:
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS moneda (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT,
                simbolo TEXT DEFAULT '$'
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS roles (
                id INTEGER PRIMARY KEY,
                nombre TEXT NOT NULL UNIQUE
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS permisos (
                id INTEGER PRIMARY KEY,
                modulo TEXT NOT NULL,
                UNIQUE(modulo)
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS permisos_rol (
                id_rol INTEGER,
                id_permiso INTEGER,
                PRIMARY KEY (id_rol, id_permiso),
                FOREIGN KEY (id_rol) REFERENCES roles(id),
                FOREIGN KEY (id_permiso) REFERENCES permisos(id)
            )
            """
        )
        cursor.execute("INSERT OR IGNORE INTO roles (nombre) VALUES ('Administrador')")
        cursor.execute("INSERT OR IGNORE INTO roles (nombre) VALUES ('Vendedor')")
        cursor.execute("INSERT OR IGNORE INTO roles (nombre) VALUES ('Supervisor')")
        for module_name, _, _ in MODULES:
            if module_name == "dashboard":
                continue
            cursor.execute(
                "INSERT OR IGNORE INTO permisos (modulo) VALUES (?)",
                (module_name,),
            )

        existing_columns = {
            row["name"] for row in fetch_all("PRAGMA table_info(pedidos)")
        }
        if "precio" not in existing_columns:
            cursor.execute("ALTER TABLE pedidos ADD COLUMN precio REAL DEFAULT 0")
        if "costo" not in existing_columns:
            cursor.execute("ALTER TABLE pedidos ADD COLUMN costo REAL DEFAULT 0")
        if "fecha_vencimiento" not in existing_columns:
            cursor.execute("ALTER TABLE pedidos ADD COLUMN fecha_vencimiento TEXT")
        if "lote" not in existing_columns:
            cursor.execute("ALTER TABLE pedidos ADD COLUMN lote TEXT")

        existing_caja_columns = {
            row["name"] for row in fetch_all("PRAGMA table_info(caja)")
        }
        if "impuesto" not in existing_caja_columns:
            cursor.execute("ALTER TABLE caja ADD COLUMN impuesto REAL DEFAULT 0")
        if "descuento" not in existing_caja_columns:
            cursor.execute("ALTER TABLE caja ADD COLUMN descuento REAL DEFAULT 0")

        inventario_columns = {
            row["name"] for row in fetch_all("PRAGMA table_info(inventario)")
        }
        if "codigo_barras" not in inventario_columns:
            cursor.execute("ALTER TABLE inventario ADD COLUMN codigo_barras TEXT")
        if "fecha_vencimiento" not in inventario_columns:
            cursor.execute("ALTER TABLE inventario ADD COLUMN fecha_vencimiento TEXT")
        if "lote" not in inventario_columns:
            cursor.execute("ALTER TABLE inventario ADD COLUMN lote TEXT")
        cursor.execute(
            """
            UPDATE inventario
            SET codigo_barras = TRIM(CAST(codigo AS TEXT))
            WHERE (codigo_barras IS NULL OR TRIM(codigo_barras) = '')
              AND codigo IS NOT NULL
            """
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_inventario_codigo_barras ON inventario(codigo_barras)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_inventario_codigo ON inventario(codigo)"
        )

        ventas_columns = {
            row["name"] for row in fetch_all("PRAGMA table_info(ventas)")
        }
        if "fecha_vencimiento" not in ventas_columns:
            cursor.execute("ALTER TABLE ventas ADD COLUMN fecha_vencimiento TEXT")
        if "lote" not in ventas_columns:
            cursor.execute("ALTER TABLE ventas ADD COLUMN lote TEXT")

        cotizaciones_columns = {
            row["name"] for row in fetch_all("PRAGMA table_info(cotizaciones)")
        }
        if "fecha_vencimiento" not in cotizaciones_columns:
            cursor.execute("ALTER TABLE cotizaciones ADD COLUMN fecha_vencimiento TEXT")
        if "lote" not in cotizaciones_columns:
            cursor.execute("ALTER TABLE cotizaciones ADD COLUMN lote TEXT")

        connection.commit()


def get_company_info() -> dict[str, str]:
    row = fetch_one(
        "SELECT nombre, direccion, telefono, email, website, image_path, tipo_id, numero_id FROM empresa LIMIT 1"
    )
    image_path = row.get("image_path") if row else DEFAULT_COMPANY_LOGO
    if not image_path:
        image_path = DEFAULT_COMPANY_LOGO
    return {
        "nombre": row.get("nombre") if row else "Sistema Punto de Venta",
        "direccion": row.get("direccion") if row else "Región Metropolitana",
        "telefono": row.get("telefono") if row else "+56 9 0000 0000",
        "email": row.get("email") if row else "contacto@example.com",
        "website": row.get("website") if row else "",
        "image_path": image_path,
        "tipo_id": row.get("tipo_id") if row else "",
        "numero_id": row.get("numero_id") if row else "",
    }


def get_currency_symbol() -> str:
    return fetch_scalar("SELECT simbolo FROM moneda ORDER BY id LIMIT 1", default="$")


def page_title(title: str, subtitle: str | None = None) -> ft.Control:
    text_controls: list[ft.Control] = [
        ft.Text(title, size=28, weight=ft.FontWeight.BOLD, color=PALETTE["text"])
    ]
    if subtitle:
        text_controls.append(
            ft.Text(subtitle, size=14, weight=ft.FontWeight.W_500, color=PALETTE["muted"])
        )
    return ft.Column(text_controls, spacing=4)


def stat_card(title: str, value: str, icon: str, tone: str = "primary") -> ft.Container:
    color_map = {
        "primary": (PALETTE["primary_soft"], PALETTE["primary"]),
        "secondary": (PALETTE["secondary_soft"], PALETTE["secondary"]),
        "success": (PALETTE["success_soft"], PALETTE["success"]),
        "accent": ("#FEF3C7", PALETTE["accent"]),
    }
    bg, fg = color_map[tone]
    return ft.Container(
        bgcolor=PALETTE["surface"],
        border=ft.Border.all(1, PALETTE["border"]),
        border_radius=22,
        padding=20,
        content=ft.Row(
            [
                ft.Container(
                    width=52,
                    height=52,
                    border_radius=16,
                    bgcolor=bg,
                    alignment=ft.Alignment(0, 0),
                    content=ft.Icon(icon, color=fg, size=28),
                ),
                ft.Column(
                    [
                        ft.Text(title, size=13, color=PALETTE["muted"]),
                        ft.Text(value, size=24, weight=ft.FontWeight.BOLD),
                    ],
                    spacing=2,
                    expand=True,
                ),
            ]
        ),
    )


def shell_card(content: ft.Control, padding: int = 20, expand: bool = False) -> ft.Container:
    return ft.Container(
        expand=expand,
        padding=padding,
        bgcolor=PALETTE["surface"],
        border_radius=16,
        border=ft.Border.all(1, "#D4E0F0"),
        content=content,
        clip_behavior=ft.ClipBehavior.HARD_EDGE,
    )


def table_view(table: ft.DataTable, height: int | None = None, expand: bool = False) -> ft.Container:
    table.border = None
    table.border_radius = 0
    table.heading_row_color = PALETTE["surface_alt"]
    table.divider_thickness = 1
    return ft.Container(
        height=height,
        expand=expand,
        clip_behavior=ft.ClipBehavior.HARD_EDGE,
        border_radius=12,
        border=ft.Border.all(1, PALETTE["border"]),
        bgcolor=PALETTE["surface"],
        content=ft.Column(
            [
                ft.Row([table], scroll=ft.ScrollMode.AUTO),
            ],
            scroll=ft.ScrollMode.AUTO,
        ),
    )


def app_theme() -> ft.Theme:
    return ft.Theme(
        color_scheme_seed=PALETTE["primary"],
        color_scheme=ft.ColorScheme(
            primary=PALETTE["primary"],
            on_primary=ft.Colors.WHITE,
            primary_container=PALETTE["primary_soft"],
            on_primary_container=PALETTE["text"],
            secondary=PALETTE["secondary"],
            on_secondary=ft.Colors.WHITE,
            secondary_container=PALETTE["secondary_soft"],
            on_secondary_container=PALETTE["text"],
            tertiary=PALETTE["accent"],
            on_tertiary=PALETTE["text"],
            error=PALETTE["danger"],
            on_error=ft.Colors.WHITE,
            error_container=PALETTE["danger_soft"],
            on_error_container=PALETTE["text"],
            surface=PALETTE["surface"],
            on_surface=PALETTE["text"],
        ),
        scaffold_bgcolor=PALETTE["bg"],
        visual_density=ft.VisualDensity.ADAPTIVE_PLATFORM_DENSITY,
        font_family="Noto Sans",
        text_theme=ft.TextTheme(
            headline_large=ft.TextStyle(size=32, weight=ft.FontWeight.BOLD, color=PALETTE["text"]),
            headline_medium=ft.TextStyle(size=28, weight=ft.FontWeight.BOLD, color=PALETTE["text"]),
            headline_small=ft.TextStyle(size=24, weight=ft.FontWeight.BOLD, color=PALETTE["text"]),
            title_large=ft.TextStyle(size=21, weight=ft.FontWeight.BOLD, color=PALETTE["text"]),
            title_medium=ft.TextStyle(size=17, weight=ft.FontWeight.W_600, color=PALETTE["text"]),
            title_small=ft.TextStyle(size=15, weight=ft.FontWeight.W_600, color=PALETTE["text"]),
            body_large=ft.TextStyle(size=16, weight=ft.FontWeight.W_500, color=PALETTE["text"]),
            body_medium=ft.TextStyle(size=15, weight=ft.FontWeight.W_400, color=PALETTE["text"]),
            body_small=ft.TextStyle(size=13, weight=ft.FontWeight.W_400, color=PALETTE["muted"]),
            label_large=BUTTON_TEXT_STYLE,
            label_medium=ft.TextStyle(size=14, weight=ft.FontWeight.W_600, color=PALETTE["text"]),
            label_small=ft.TextStyle(size=12, weight=ft.FontWeight.W_600, color=PALETTE["muted"]),
        ),
        use_material3=True,
        divider_color=PALETTE["border"],
        dialog_theme=ft.DialogTheme(
            bgcolor=PALETTE["surface"],
            shape=ft.RoundedRectangleBorder(radius=24),
            title_text_style=ft.TextStyle(color=PALETTE["text"], size=21, weight=ft.FontWeight.BOLD),
            content_text_style=ft.TextStyle(color=PALETTE["text"], size=15),
            barrier_color="#7A10213A",
        ),
        button_theme=ft.ButtonTheme(
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=16),
                bgcolor=PALETTE["primary"],
                color=ft.Colors.WHITE,
                padding=ft.Padding.symmetric(horizontal=22, vertical=16),
                text_style=BUTTON_TEXT_STYLE,
            )
        ),
        outlined_button_theme=ft.OutlinedButtonTheme(
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=16),
                color=PALETTE["primary"],
                side=ft.BorderSide(1.4, PALETTE["border"]),
                bgcolor=PALETTE["surface"],
                padding=ft.Padding.symmetric(horizontal=22, vertical=16),
                text_style=BUTTON_TEXT_STYLE,
            )
        ),
        text_button_theme=ft.TextButtonTheme(
            style=ft.ButtonStyle(
                color=PALETTE["primary"],
                shape=ft.RoundedRectangleBorder(radius=14),
                text_style=BUTTON_TEXT_STYLE,
            )
        ),
        icon_button_theme=ft.IconButtonTheme(
            style=ft.ButtonStyle(
                color=PALETTE["primary"],
                shape=ft.RoundedRectangleBorder(radius=14),
            )
        ),
        dropdown_theme=ft.DropdownTheme(
            text_style=INPUT_TEXT_STYLE,
            menu_style=ft.MenuStyle(
                bgcolor=PALETTE["surface"],
                shadow_color="#240E1A2A",
                elevation=8,
                side=ft.BorderSide(1.2, PALETTE["border"]),
                shape=ft.RoundedRectangleBorder(radius=16),
                padding=ft.Padding.symmetric(vertical=8),
            ),
        ),
        data_table_theme=ft.DataTableTheme(
            heading_row_color=PALETTE["surface_alt"],
            heading_text_style=ft.TextStyle(color=PALETTE["text"], size=15, weight=ft.FontWeight.BOLD),
            data_text_style=ft.TextStyle(color=PALETTE["text"], size=15, weight=ft.FontWeight.W_500),
            divider_thickness=1,
            column_spacing=16,
            horizontal_margin=14,
            data_row_min_height=56,
            data_row_max_height=96,
        ),
        navigation_rail_theme=ft.NavigationRailTheme(
            bgcolor=PALETTE["sidebar"],
            indicator_color=PALETTE["primary_soft"],
            selected_label_text_style=ft.TextStyle(color=PALETTE["primary"], size=15, weight=ft.FontWeight.BOLD),
            unselected_label_text_style=ft.TextStyle(color=PALETTE["muted"], size=15, weight=ft.FontWeight.W_500),
        ),
    )
