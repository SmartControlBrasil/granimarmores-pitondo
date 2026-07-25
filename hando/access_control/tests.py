# ruff: noqa: PT009, S106
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from access_control.models import AccessPermission
from access_control.models import AccessRole
from access_control.models import DataScope
from access_control.models import RolePermission
from access_control.models import UserAccess
from audit.models import AuditEvent

User = get_user_model()


class RoleCrudTests(TestCase):
    def setUp(self):
        self.admin_role = AccessRole.objects.create(
            name="Administrativo",
            slug="administrativo",
            hierarchy_level=1,
            has_full_access=True,
            customer_scope=DataScope.ALL,
            quote_scope=DataScope.ALL,
            asset_scope=DataScope.ALL,
            maintenance_scope=DataScope.ALL,
        )
        self.admin = User.objects.create_user("admin", password="pass")
        UserAccess.objects.create(user=self.admin, role=self.admin_role)
        self.client.force_login(self.admin)
        self.permission = AccessPermission.objects.create(
            code="customers.view",
            name="Visualizar clientes",
            module="customers",
            action="view",
        )

    def test_role_matrix_renders(self):
        response = self.client.get(
            reverse("access_control:role_permissions", args=[self.admin_role.pk]),
        )
        self.assertEqual(response.status_code, 200)

    def test_create_role(self):
        response = self.client.post(
            reverse("access_control:role_create"),
            {
                "name": "Supervisor",
                "hierarchy_level": 30,
                "customer_scope": DataScope.TEAM,
                "quote_scope": DataScope.TEAM,
                "asset_scope": DataScope.OWN,
                "maintenance_scope": DataScope.OWN,
                "is_active": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(AccessRole.objects.filter(slug="supervisor").exists())

    def test_permission_matrix_updates_role_permission(self):
        response = self.client.post(
            reverse("access_control:role_permissions", args=[self.admin_role.pk]),
            {f"permission_{self.permission.pk}": "on"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            RolePermission.objects.get(
                role=self.admin_role,
                permission=self.permission,
            ).allowed,
        )
        self.assertTrue(
            AuditEvent.objects.filter(action="update_permission_matrix").exists(),
        )
