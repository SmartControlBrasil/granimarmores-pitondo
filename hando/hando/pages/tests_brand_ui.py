# ruff: noqa: PT009
from django.contrib.auth import get_user_model
from django.test import Client
from django.test import TestCase
from django.urls import reverse

from access_control.models import AccessRole
from access_control.models import DataScope
from access_control.models import UserAccess
from access_control.models import AccessPermission
from access_control.permissions import PERMISSIONS


User = get_user_model()


def _sync_permissions():
    for code, name, module, action in PERMISSIONS:
        AccessPermission.objects.update_or_create(
            code=code,
            defaults={"name": name, "module": module, "action": action, "is_active": True},
        )


class ErpBrandUITests(TestCase):
    def setUp(self):
        _sync_permissions()
        role = AccessRole.objects.create(
            name="Administrativo",
            slug="admin-brand-ui",
            hierarchy_level=1,
            has_full_access=True,
            customer_scope=DataScope.ALL,
        )
        self.user = User.objects.create_user("brandui", password="pass")
        UserAccess.objects.create(user=self.user, role=role)
        self.client = Client()

    def test_dashboard_uses_granimarmores_branding(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("pages:dashboard"))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Granimármores Pitondo", content)
        self.assertIn("institutional/images/logo-gp.webp", content)
        self.assertIn("Smart Control Brasil", content)
        self.assertNotIn("Zoyothemes", content)
        self.assertNotIn("logo-light.png", content)

    def test_login_page_uses_granimarmores_logo(self):
        response = self.client.get(reverse("account_login"))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("institutional/images/logo-gp.webp", content)
        self.assertIn("Granimármores Pitondo", content)
        self.assertNotIn("logo-light.png", content)

    def test_base_title_suffix(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("pages:dashboard"))

        self.assertContains(response, "| Granimármores Pitondo</title>")
        self.assertNotContains(response, "Hando - Responsive Admin Dashboard Template")
