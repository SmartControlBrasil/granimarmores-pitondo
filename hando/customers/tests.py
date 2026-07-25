# ruff: noqa: PT009, S106
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from access_control.models import AccessRole
from access_control.models import DataScope
from access_control.models import UserAccess
from audit.models import AuditEvent
from customers.models import Customer

User = get_user_model()


class CustomerCrudTests(TestCase):
    def setUp(self):
        role = AccessRole.objects.create(
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
        UserAccess.objects.create(user=self.admin, role=role)
        self.client.force_login(self.admin)

    def test_customer_detail_renders(self):
        customer = Customer.objects.create(customer_type="company", name="Cliente A")
        response = self.client.get(reverse("customers:detail", args=[customer.pk]))
        self.assertEqual(response.status_code, 200)

    def test_update_customer_records_audit(self):
        customer = Customer.objects.create(customer_type="company", name="Cliente A")
        response = self.client.post(
            reverse("customers:update", args=[customer.pk]),
            {
                "customer_type": "company",
                "name": "Cliente B",
                "document": "12345678000190",
            },
        )
        self.assertEqual(response.status_code, 302)
        customer.refresh_from_db()
        self.assertEqual(customer.name, "Cliente B")
        self.assertTrue(
            AuditEvent.objects.filter(module="customers", action="update").exists(),
        )

    def test_deactivate_customer(self):
        customer = Customer.objects.create(customer_type="company", name="Cliente A")
        response = self.client.post(reverse("customers:deactivate", args=[customer.pk]))
        self.assertEqual(response.status_code, 302)
        customer.refresh_from_db()
        self.assertFalse(customer.is_active)
