from __future__ import annotations

from typing import Callable

import flet as ft

from flet_utils import (
    DEFAULT_COMPANY_LOGO,
    MODULES,
    PALETTE,
    apply_visual_theme,
    fetch_all,
    fetch_one,
    fetch_scalar,
    get_company_info,
    image_base64,
    page_title,
    shell_card,
    stat_card,
)


class Container:
    def __init__(
        self,
        page: ft.Page,
        user: str,
        rol: str,
        on_logout: Callable[[], None],
    ) -> None:
        self.page = page
        self.user = user
        self.rol = rol
        self.on_logout = on_logout
        self.company = get_company_info()
        self.active_module = "dashboard"
        self.content = ft.Container(expand=True)
        self.root = ft.Container(expand=True, bgcolor=PALETTE["bg"])
        self.compact_mode: bool | None = None
        self.navigation = ft.NavigationRail(
            selected_index=0,
            label_type=ft.NavigationRailLabelType.ALL,
            min_width=96,
            min_extended_width=220,
            extended=True,
            bgcolor=PALETTE["surface"],
            destinations=[
                ft.NavigationRailDestination(
                    icon=ft.Icon(icon, color=PALETTE["muted"]),
                    selected_icon=ft.Icon(icon, color=PALETTE["primary"]),
                    label=label,
                )
                for _, label, icon in MODULES
            ],
            on_change=self._on_navigation_change,
        )
        self.mobile_navigation = ft.Dropdown(
            label="Modulo",
            value="dashboard",
            options=[
                ft.dropdown.Option(key=module_name, text=label)
                for module_name, label, _ in MODULES
            ],
            border_radius=14,
            dense=True,
            on_select=self._on_mobile_navigation_change,
        )

    def _notify(self, message: str, error: bool = False) -> None:
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=PALETTE["danger"] if error else PALETTE["primary"],
            open=True,
        )
        self.page.update()

    def set_user(self, user: str) -> None:
        self.user = user

    def set_rol(self, rol: str) -> None:
        self.rol = rol

    def verificar_acceso(self, modulo: str) -> bool:
        if self.rol == "Administrador":
            return True
        permiso = fetch_one(
            """
            SELECT p.modulo
            FROM usuarios u
            JOIN roles r ON LOWER(r.nombre) = LOWER(u.rol)
            JOIN permisos_rol pr ON pr.id_rol = r.id
            JOIN permisos p ON p.id = pr.id_permiso
            WHERE u.username = ? AND p.modulo = ?
            """,
            (self.user, modulo),
        )
        return permiso is not None

    def _on_navigation_change(self, event: ft.ControlEvent) -> None:
        module_name = MODULES[event.control.selected_index][0]
        self._navigate_to(module_name)

    def _on_mobile_navigation_change(self, event: ft.ControlEvent) -> None:
        self._navigate_to(str(event.control.value or "dashboard"))

    def _navigate_to(self, module_name: str) -> None:
        if module_name != "dashboard" and not self.verificar_acceso(module_name):
            self.navigation.selected_index = next(
                index for index, module in enumerate(MODULES) if module[0] == self.active_module
            )
            self.mobile_navigation.value = self.active_module
            self._notify(
                f"Usted no posee permisos para ingresar al modulo {module_name}.",
                error=True,
            )
            return
        self.active_module = module_name
        selected_index = next(
            index for index, module in enumerate(MODULES) if module[0] == module_name
        )
        self.navigation.selected_index = selected_index
        self.mobile_navigation.value = module_name
        self._render_content()

    def _summary_view(self) -> ft.Control:
        total_productos = fetch_scalar("SELECT COUNT(*) FROM inventario", default=0)
        total_clientes = fetch_scalar("SELECT COUNT(*) FROM clientes", default=0)
        total_ventas = fetch_scalar("SELECT COUNT(*) FROM ventas", default=0)
        total_gastos = fetch_scalar("SELECT IFNULL(SUM(valor), 0) FROM gastos", default=0)
        empresa_logo = image_base64(self.company["image_path"], DEFAULT_COMPANY_LOGO)

        return ft.Column(
            [
                page_title(
                    "Resumen general",
                    "Bienvenido al sistema de ventas y control de inventario. Aqui podras ver un resumen de la actividad del negocio.",
                ),
                ft.ResponsiveRow(
                    [
                        ft.Container(
                            col={"xs": 12, "md": 6, "xl": 3},
                            content=stat_card(
                                "Productos",
                                str(total_productos),
                                ft.Icons.INVENTORY_2_OUTLINED,
                                "secondary",
                            ),
                        ),
                        ft.Container(
                            col={"xs": 12, "md": 6, "xl": 3},
                            content=stat_card(
                                "Clientes",
                                str(total_clientes),
                                ft.Icons.GROUPS_OUTLINED,
                                "primary",
                            ),
                        ),
                        ft.Container(
                            col={"xs": 12, "md": 6, "xl": 3},
                            content=stat_card(
                                "Ventas",
                                str(total_ventas),
                                ft.Icons.POINT_OF_SALE_OUTLINED,
                                "success",
                            ),
                        ),
                        ft.Container(
                            col={"xs": 12, "md": 6, "xl": 3},
                            content=stat_card(
                                "Gastos",
                                f"{total_gastos:.2f}",
                                ft.Icons.RECEIPT_LONG_OUTLINED,
                                "accent",
                            ),
                        ),
                    ]
                ),
                ft.ResponsiveRow(
                    [
                        ft.Container(
                            col={"xs": 12, "lg": 7},
                            content=shell_card(
                                ft.Column(
                                    [
                                        ft.Text(
                                            "Informacion de empresa",
                                            size=20,
                                            weight=ft.FontWeight.BOLD,
                                        ),
                                        ft.Text(self.company["nombre"], size=18),
                                        ft.Text(self.company["direccion"], color=PALETTE["muted"]),
                                        ft.Text(self.company["telefono"], color=PALETTE["muted"]),
                                        ft.Text(self.company["email"], color=PALETTE["muted"]),
                                        ft.Text(
                                            "Usa el menu lateral para entrar a cada modulo.",
                                            color=PALETTE["text"],
                                        ),
                                    ],
                                    spacing=10,
                                ),
                                expand=True,
                            ),
                        ),
                        ft.Container(
                            col={"xs": 12, "lg": 5},
                            content=shell_card(
                                ft.Column(
                                    [
                                        ft.Text(
                                            "Marca visual",
                                            size=20,
                                            weight=ft.FontWeight.BOLD,
                                        ),
                                        ft.Container(
                                            alignment=ft.Alignment(0, 0),
                                            height=260,
                                            content=ft.Image(
                                                src=empresa_logo,
                                                height=260,
                                                fit="contain",
                                            )
                                            if empresa_logo
                                            else ft.Icon(ft.Icons.STOREFRONT, size=80),
                                        ),
                                    ]
                                ),
                                expand=True,
                            ),
                        ),
                    ]
                ),
            ],
            scroll=ft.ScrollMode.AUTO,
            spacing=20,
        )

    def _placeholder_view(self, title: str) -> ft.Control:
        return ft.Column(
            [
                page_title(title, "Este modulo requiere una migracion funcional mas profunda."),
                shell_card(
                    ft.Column(
                        [
                            ft.Icon(ft.Icons.CONSTRUCTION_ROUNDED, size=56, color=PALETTE["accent"]),
                            ft.Text(
                                f"{title} quedo marcado dentro del nuevo shell Flet.",
                                size=20,
                                weight=ft.FontWeight.BOLD,
                                text_align=ft.TextAlign.CENTER,
                            ),
                            ft.Text(
                                "La logica original mezcla interfaz, eventos y consultas en un mismo archivo. "
                                "Ya deje la base lista para continuar el traspaso sin tocar la base de datos ni los recursos.",
                                text_align=ft.TextAlign.CENTER,
                                color=PALETTE["muted"],
                            ),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=12,
                    ),
                    padding=36,
                ),
            ],
            spacing=20,
        )

    def _module_registry(self) -> dict[str, Callable[[], ft.Control]]:
        from clientes import Clientes
        from configuracion import Configuracion
        from cotizaciones import Cotizaciones
        from gastos import Gastos
        from informacion import Informacion
        from inventario import Inventario
        from pedidos import Pedidos
        from proveedor import Proveedor
        from reportes import Reportes
        from usuarios import Usuarios
        from ventas import Ventas

        return {
            "dashboard": self._summary_view,
            "ventas": lambda: Ventas(self.page, self.user).build(),
            "cotizaciones": lambda: Cotizaciones(self.page, self.user).build(),
            "inventario": lambda: Inventario(self.page, self.user).build(),
            "clientes": lambda: Clientes(self.page).build(),
            "proveedor": lambda: Proveedor(self.page).build(),
            "pedidos": lambda: Pedidos(self.page).build(),
            "reportes": lambda: Reportes(self.page, self.user).build(),
            "gastos": lambda: Gastos(self.page).build(),
            "usuarios": lambda: Usuarios(self.page).build(),
            "informacion": lambda: Informacion(self.page).build(),
            "configuracion": lambda: Configuracion(self.page).build(),
        }

    def _render_content(self) -> None:
        registry = self._module_registry()
        view_builder = registry.get(self.active_module, self._summary_view)
        self.content.content = apply_visual_theme(view_builder())
        self.page.update()

    def _sidebar(self) -> ft.Control:
        logo = image_base64(self.company["image_path"], DEFAULT_COMPANY_LOGO)
        return ft.Container(
            width=300,
            padding=20,
            bgcolor=PALETTE["sidebar"],
            border=ft.Border.only(right=ft.BorderSide(1, PALETTE["border"])),
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Container(
                                width=72,
                                height=72,
                                border_radius=8,
                                alignment=ft.Alignment(0, 0),
                                content=ft.Image(src=logo, width=72, height=72, fit="contain")
                                if logo
                                else ft.Icon(ft.Icons.STOREFRONT),
                            ),
                            ft.Column(
                                [
                                    ft.Text(
                                        self.company["nombre"],
                                        size=17,
                                        weight=ft.FontWeight.BOLD,
                                        no_wrap=True,
                                    ),
                                    ft.Text(
                                        f"{self.user} · {self.rol}",
                                        color=PALETTE["muted"],
                                        size=12,
                                    ),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                        ]
                    ),
                    ft.Divider(height=18, color=PALETTE["border"]),
                    ft.Container(expand=True, content=self.navigation),
                    ft.OutlinedButton(
                        "Cerrar sesion",
                        icon=ft.Icons.LOGOUT_ROUNDED,
                        on_click=lambda _: self.on_logout(),
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=16),
                            side=ft.BorderSide(1, PALETTE["border"]),
                        ),
                    ),
                ],
                expand=True,
            ),
        )

    def _mobile_header(self) -> ft.Control:
        logo = image_base64(self.company["image_path"], DEFAULT_COMPANY_LOGO)
        return ft.Container(
            padding=12,
            bgcolor=PALETTE["sidebar"],
            border=ft.Border.only(bottom=ft.BorderSide(1, PALETTE["border"])),
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Image(src=logo, width=42, height=42, fit="contain")
                            if logo
                            else ft.Icon(ft.Icons.STOREFRONT, size=32),
                            ft.Column(
                                [
                                    ft.Text(
                                        self.company["nombre"],
                                        size=15,
                                        weight=ft.FontWeight.BOLD,
                                        max_lines=1,
                                        overflow=ft.TextOverflow.ELLIPSIS,
                                    ),
                                    ft.Text(
                                        f"{self.user} · {self.rol}",
                                        size=11,
                                        color=PALETTE["muted"],
                                    ),
                                ],
                                spacing=1,
                                expand=True,
                            ),
                            ft.IconButton(
                                ft.Icons.LOGOUT_ROUNDED,
                                tooltip="Cerrar sesion",
                                on_click=lambda _: self.on_logout(),
                            ),
                        ],
                        spacing=10,
                    ),
                    self.mobile_navigation,
                ],
                spacing=8,
            ),
        )

    def _is_compact(self) -> bool:
        return bool(self.page.width and self.page.width < 900)

    def _apply_layout(self, force: bool = False) -> None:
        compact = self._is_compact()
        if not force and compact == self.compact_mode:
            return
        self.compact_mode = compact
        if compact:
            self.root.content = ft.Column(
                [
                    self._mobile_header(),
                    ft.Container(
                        expand=True,
                        padding=12,
                        content=self.content,
                    ),
                ],
                spacing=0,
                expand=True,
            )
        else:
            self.root.content = ft.Row(
                [
                    self._sidebar(),
                    ft.Container(
                        expand=True,
                        padding=20,
                        content=self.content,
                    ),
                ],
                spacing=0,
                expand=True,
            )

    def _on_resize(self, _: ft.ControlEvent) -> None:
        previous_mode = self.compact_mode
        self._apply_layout()
        if self.compact_mode != previous_mode:
            self.page.update()

    def build(self) -> ft.Control:
        self._render_content()
        self.page.on_resize = self._on_resize
        self._apply_layout(force=True)
        return self.root
