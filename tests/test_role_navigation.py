import unittest
from unittest.mock import Mock, patch

from container import Container
from role_permissions import DEFAULT_ROLE_MODULES
from tenant_context import TenantContext


class RoleNavigationTests(unittest.TestCase):
    def _container(self, role="cashier"):
        context = TenantContext(
            auth_user_id="auth-user-isi",
            email="vendedor@isi.test",
            username="isidora",
            organization_id="org-isi",
            role=role,
        )
        return Container(Mock(), "isidora", role, context, Mock())

    def test_cashier_permissions_use_stable_identity_and_tenant_context(self):
        container = self._container()
        with patch(
            "container.fetch_all",
            return_value=[{"modulo": "ventas"}, {"modulo": "inventario"}],
        ) as query:
            self.assertTrue(container.verificar_acceso("ventas"))
            self.assertFalse(container.verificar_acceso("usuarios"))

        args, kwargs = query.call_args
        self.assertEqual(args[1], ("auth-user-isi", "org-isi", "org-isi"))
        self.assertIs(kwargs["context"], container.context)

    def test_store_admin_can_open_every_module_without_role_lookup(self):
        container = self._container("store_admin")
        with patch("container.fetch_all") as query:
            self.assertTrue(container.verificar_acceso("usuarios"))
            self.assertTrue(container.verificar_acceso("configuracion"))
        query.assert_not_called()

    def test_default_roles_receive_operational_modules(self):
        for role_name in ("Supervisor", "Vendedor"):
            self.assertTrue({"ventas", "inventario", "clientes"}.issubset(
                DEFAULT_ROLE_MODULES[role_name]
            ))
            self.assertNotIn("usuarios", DEFAULT_ROLE_MODULES[role_name])


if __name__ == "__main__":
    unittest.main()
