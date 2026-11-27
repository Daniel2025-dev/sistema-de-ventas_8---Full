import unittest
from unittest.mock import Mock, patch

import flet as ft

from ventas import Ventas


class FastPosTests(unittest.TestCase):
    def _cart_view(self) -> Ventas:
        sales = Ventas.__new__(Ventas)
        sales.page = Mock()
        sales.currency = "$"
        sales.cart = []
        sales._cart_rows = {}
        sales.selected_cart_index = None
        sales.cart_table = ft.DataTable(columns=[], rows=[])
        sales.label_precio_total = ft.Text()
        sales.label_stock = ft.Text()
        sales.scan_status = ft.Text()
        sales.scan_input = ft.TextField()
        sales.entry_nombre = ft.Dropdown()
        sales.product_lookup_by_name = {}
        return sales

    def test_repeated_scan_updates_existing_row_in_place(self):
        sales = self._cart_view()
        item = {
            "factura": 1,
            "cliente": "Cliente Mostrador",
            "producto": "Arroz 1 kg",
            "lote": "",
            "fecha_vencimiento": "",
            "precio": 1000.0,
            "cantidad": 1,
            "impuesto": 0.0,
            "total": 1000.0,
        }
        sales.cart.append(item)
        sales.refresh_cart(changed_index=0)
        first_row = sales.cart_table.rows[0]

        item["cantidad"] = 2
        item["total"] = 2000.0
        sales.refresh_cart(changed_index=0)

        self.assertIs(sales.cart_table.rows[0], first_row)
        self.assertEqual(first_row.cells[6].content.value, "2")
        self.assertEqual(first_row.cells[8].content.value, "2,000.00")

    def test_quick_sale_charges_exact_total_without_dialog(self):
        sales = Ventas.__new__(Ventas)
        sales.caja_abierta = True
        sales.cart = [{"total": 2500.0}]
        sales.entry_nombre = ft.Dropdown()
        sales.selected_cart_index = None
        sales._sync_selected_product_to_cart = Mock(return_value=None)
        sales.procesar_pago = Mock()

        sales.venta_rapida()

        sales.procesar_pago.assert_called_once_with(
            "2500.0", "efectivo", "0", None, mostrar_vuelto=False
        )

    def test_sales_history_is_aggregated_and_limited_in_database(self):
        sales = Ventas.__new__(Ventas)
        sales.organization_id = "store-a"
        sales.invoice_filter = ft.TextField(value="")
        sales.client_filter = ft.TextField(value="")
        with patch("ventas.fetch_all", return_value=[]) as fetch:
            sales._sales_summary_rows()

        query, params = fetch.call_args.args
        self.assertIn("GROUP BY factura", query)
        self.assertIn("LIMIT 100", query)
        self.assertEqual(params, ("store-a",))


if __name__ == "__main__":
    unittest.main()
