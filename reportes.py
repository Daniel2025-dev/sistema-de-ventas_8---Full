import datetime

import flet as ft

from flet_utils import PALETTE, fetch_all, fetch_scalar, page_title, shell_card, stat_card, table_view


class Reportes:
    def __init__(self, page: ft.Page, user: str | None = None) -> None:
        self.page = page
        self.user = user
        hoy = datetime.date.today().strftime("%Y-%m-%d")
        self.desde = ft.TextField(label="Desde (YYYY-MM-DD)", value=hoy, border_radius=16, filled=True, bgcolor=PALETTE["surface_alt"])
        self.hasta = ft.TextField(label="Hasta (YYYY-MM-DD)", value=hoy, border_radius=16, filled=True, bgcolor=PALETTE["surface_alt"])
        self.sales_table = ft.DataTable(
            columns=[ft.DataColumn(ft.Text(label)) for label in ["Producto", "Cantidad", "Ventas"]],
            rows=[],
            border=ft.border.all(1, PALETTE["border"]),
            border_radius=12,
            heading_row_color=PALETTE["surface_alt"],
        )
        self.cash_table = ft.DataTable(
            columns=[ft.DataColumn(ft.Text(label)) for label in ["Apertura", "Inicial", "Total caja", "Estado", "Ventas acumuladas", "Cierre"]],
            rows=[],
            border=ft.border.all(1, PALETTE["border"]),
            border_radius=12,
            heading_row_color=PALETTE["surface_alt"],
        )
        self.summary_section = ft.ResponsiveRow()

    def _notify(self, message: str, error: bool = False) -> None:
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=PALETTE["danger"] if error else PALETTE["primary"],
            open=True,
        )
        self.page.update()

    def _date_clause(self) -> tuple[str, tuple]:
        desde = (self.desde.value or "").strip()
        hasta = (self.hasta.value or "").strip()
        if not desde or not hasta:
            return "", ()
        return " WHERE fecha BETWEEN ? AND ? ", (desde, hasta)

    def refresh(self, _: ft.ControlEvent | None = None) -> None:
        clause, params = self._date_clause()

        total_ventas = float(fetch_scalar(f"SELECT IFNULL(SUM(total), 0) FROM ventas{clause}", params, default=0))
        ganancia_total = float(
            fetch_scalar(
                f"SELECT IFNULL(SUM(total - costo), 0) FROM ventas{clause}",
                params,
                default=0,
            )
        )
        costo_ventas = float(fetch_scalar(f"SELECT IFNULL(SUM(costo), 0) FROM ventas{clause}", params, default=0))
        total_productos_vendidos = int(fetch_scalar(f"SELECT IFNULL(SUM(cantidad), 0) FROM ventas{clause}", params, default=0))
        costo_inventario = float(fetch_scalar("SELECT IFNULL(SUM(costo * stock), 0) FROM inventario", default=0))

        self.summary_section.controls = [
            ft.Container(col={"xs": 12, "md": 6, "xl": 2}, content=stat_card("Ventas totales", f"{total_ventas:,.2f}", ft.Icons.PAYMENTS_OUTLINED, "secondary")),
            ft.Container(col={"xs": 12, "md": 6, "xl": 2}, content=stat_card("Ganancias", f"{ganancia_total:,.2f}", ft.Icons.TRENDING_UP_OUTLINED, "success")),
            ft.Container(col={"xs": 12, "md": 6, "xl": 2}, content=stat_card("Costo ventas", f"{costo_ventas:,.2f}", ft.Icons.ANALYTICS_OUTLINED, "accent")),
            ft.Container(col={"xs": 12, "md": 6, "xl": 3}, content=stat_card("Costo inventario", f"{costo_inventario:,.2f}", ft.Icons.INVENTORY_2_OUTLINED, "primary")),
            ft.Container(col={"xs": 12, "md": 6, "xl": 3}, content=stat_card("Productos vendidos", str(total_productos_vendidos), ft.Icons.SHOPPING_CART_OUTLINED, "secondary")),
        ]

        productos = fetch_all(
            f"""
            SELECT producto, SUM(cantidad) AS cantidad, SUM(total) AS ventas
            FROM ventas
            {clause}
            GROUP BY producto
            ORDER BY cantidad DESC
            LIMIT 15
            """,
            params,
        )
        self.sales_table.rows = [
            ft.DataRow(
                cells=[
                    ft.DataCell(ft.Text(str(row["producto"]))),
                    ft.DataCell(ft.Text(str(row["cantidad"]))),
                    ft.DataCell(ft.Text(f"{float(row['ventas'] or 0):,.2f}")),
                ]
            )
            for row in productos
        ]

        cajas = fetch_all(
            """
            SELECT fecha_apertura, monto_inicial, total_en_caja, estado, total_ventas_acumuladas, fecha_cierre
            FROM caja
            ORDER BY id DESC
            LIMIT 20
            """
        )
        self.cash_table.rows = [
            ft.DataRow(
                cells=[
                    ft.DataCell(ft.Text(str(row["fecha_apertura"] or ""))),
                    ft.DataCell(ft.Text(f"{float(row['monto_inicial'] or 0):,.2f}")),
                    ft.DataCell(ft.Text(f"{float(row['total_en_caja'] or 0):,.2f}")),
                    ft.DataCell(ft.Text(str(row["estado"] or ""))),
                    ft.DataCell(ft.Text(f"{float(row['total_ventas_acumuladas'] or 0):,.2f}")),
                    ft.DataCell(ft.Text(str(row["fecha_cierre"] or ""))),
                ]
            )
            for row in cajas
        ]
        self.page.update()

    def build(self) -> ft.Control:
        self.refresh()
        return ft.Column(
            [
                page_title("Reportes", "Panel resumido de ventas, ganancias, costos y caja."),
                shell_card(
                    ft.ResponsiveRow(
                        [
                            ft.Container(col={"xs": 12, "md": 4}, content=self.desde),
                            ft.Container(col={"xs": 12, "md": 4}, content=self.hasta),
                            ft.Container(
                                col={"xs": 12, "md": 4},
                                content=ft.Row(
                                    [
                                        ft.ElevatedButton("Actualizar", icon=ft.Icons.FILTER_ALT_OUTLINED, on_click=self.refresh),
                                    ]
                                ),
                            ),
                        ]
                    )
                ),
                self.summary_section,
                ft.ResponsiveRow(
                    [
                        ft.Container(
                            col={"xs": 12, "lg": 6},
                            content=shell_card(
                                ft.Column(
                                    [
                                        ft.Text("Productos mas vendidos", size=20, weight=ft.FontWeight.BOLD),
                                        table_view(self.sales_table, height=360),
                                    ],
                                    spacing=14,
                                ),
                                expand=True,
                            ),
                        ),
                        ft.Container(
                            col={"xs": 12, "lg": 6},
                            content=shell_card(
                                ft.Column(
                                    [
                                        ft.Text("Historial de caja", size=20, weight=ft.FontWeight.BOLD),
                                        table_view(self.cash_table, height=360),
                                    ],
                                    spacing=14,
                                ),
                                expand=True,
                            ),
                        ),
                    ]
                ),
            ],
            spacing=18,
            scroll=ft.ScrollMode.AUTO,
        )
