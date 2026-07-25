# ruff: noqa: PT009, S106
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from access_control.models import AccessRole
from access_control.models import UserAccess
from audit.models import AuditEvent
from salespeople.models import Salesperson

User = get_user_model()


class SalespersonCrudTests(TestCase):
    def setUp(self):
        role = AccessRole.objects.create(
            name="Administrativo",
            slug="administrativo",
            hierarchy_level=1,
            has_full_access=True,
        )
        self.admin = User.objects.create_user("admin", password="pass")
        UserAccess.objects.create(user=self.admin, role=role)
        self.client.force_login(self.admin)

    def test_salesperson_detail_renders(self):
        salesperson = Salesperson.objects.create(code="V01", display_name="Vendedor Um")
        response = self.client.get(reverse("salespeople:detail", args=[salesperson.pk]))
        self.assertEqual(response.status_code, 200)

    def test_create_salesperson_records_audit(self):
        response = self.client.post(
            reverse("salespeople:create"),
            {
                "code": "V01",
                "display_name": "Vendedor Um",
                "commission_percentage": "2.50",
                "is_active": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Salesperson.objects.filter(code="V01").exists())
        self.assertTrue(
            AuditEvent.objects.filter(module="salespeople", action="create").exists(),
        )

    def test_deactivate_salesperson(self):
        salesperson = Salesperson.objects.create(code="V01", display_name="Vendedor Um")
        response = self.client.post(
            reverse("salespeople:deactivate", args=[salesperson.pk]),
        )
        self.assertEqual(response.status_code, 302)
        salesperson.refresh_from_db()
        self.assertFalse(salesperson.is_active)
