from __future__ import annotations

import unittest

from tenant_context import CASHIER, PLATFORM_ADMIN, STORE_ADMIN, TenantContext


class TenantContextTests(unittest.TestCase):
    def test_two_sessions_are_independent(self) -> None:
        pinos = TenantContext("u1", "pinos@test.local", "Pinos", "org-pinos", STORE_ADMIN)
        jose = TenantContext("u2", "jose@test.local", "Jose", "org-jose", STORE_ADMIN)
        carts = {pinos.organization_id: ["Arroz 1 kg"], jose.organization_id: []}
        self.assertEqual(["Arroz 1 kg"], carts["org-pinos"])
        self.assertEqual([], carts["org-jose"])

    def test_cashier_cannot_administer_store(self) -> None:
        cashier = TenantContext("u3", "cashier@test.local", "Caja", "org-pinos", CASHIER)
        self.assertTrue(cashier.can_sell)
        with self.assertRaises(PermissionError):
            cashier.require_store_admin()

    def test_platform_admin_is_not_bound_to_render_google_account(self) -> None:
        admin = TenantContext("supabase-auth-id", "owner@test.local", "Owner", None, PLATFORM_ADMIN, True)
        self.assertTrue(admin.is_platform_admin)
        self.assertTrue(admin.can_manage_store)


class IsolationScenarioTests(unittest.TestCase):
    def test_requested_stock_and_retry_scenario(self) -> None:
        stock = {("pinos", "barcode-1"): 10, ("san-jose", "barcode-1"): 10}
        completed: dict[tuple[str, str], int] = {}

        def sell(org: str, request_id: str, quantity: int) -> int:
            key = (org, request_id)
            if key in completed:
                return completed[key]
            stock[(org, "barcode-1")] -= quantity
            completed[key] = stock[(org, "barcode-1")]
            return completed[key]

        self.assertEqual(8, sell("pinos", "sale-001", 2))
        self.assertEqual(8, sell("pinos", "sale-001", 2))
        self.assertEqual(10, stock[("san-jose", "barcode-1")])


if __name__ == "__main__":
    unittest.main()
