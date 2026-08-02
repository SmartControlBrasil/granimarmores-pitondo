# ruff: noqa: PT009, S106
from django.contrib.auth import get_user_model
from django.template import Context
from django.template import Template
from django.test import Client
from django.test import RequestFactory
from django.test import TestCase
from django.urls import reverse

from access_control.models import AccessPermission
from access_control.models import AccessRole
from access_control.models import DataScope
from access_control.models import RolePermission
from access_control.models import UserAccess
from access_control.permissions import PERMISSIONS
from access_control.templatetags.erp_permissions import _match_nav_rule
from access_control.templatetags.erp_permissions import nav_active


User = get_user_model()


def _sync_permissions():
    for code, name, module, action in PERMISSIONS:
        AccessPermission.objects.update_or_create(
            code=code,
            defaults={"name": name, "module": module, "action": action, "is_active": True},
        )


def _grant(role, *codes):
    for code in codes:
        perm = AccessPermission.objects.get(code=code)
        RolePermission.objects.get_or_create(role=role, permission=perm, defaults={"allowed": True})


class NavActiveTagTests(TestCase):
    def test_match_rules(self):
        self.assertTrue(_match_nav_rule("leads", "list", "leads"))
        self.assertTrue(_match_nav_rule("leads", "list", "leads:list"))
        self.assertTrue(_match_nav_rule("finance", "receivable_list", "finance:*receivable*"))
        self.assertTrue(_match_nav_rule("stock", "slab_receive", "stock:slab_*"))
        self.assertTrue(_match_nav_rule("", "my_commissions", ":my_commissions"))
        self.assertFalse(_match_nav_rule("quotes", "list", "leads"))
        self.assertFalse(_match_nav_rule("stock", "slab_list", "stock:slab_receive"))

    def test_nav_active_tag_uses_resolver_match(self):
        factory = RequestFactory()
        request = factory.get("/painel/")
        request.resolver_match = type(
            "M",
            (),
            {"namespace": "finance", "url_name": "dashboard"},
        )()
        self.assertTrue(nav_active(Context({"request": request}), "finance", "finance:dashboard"))
        self.assertFalse(nav_active(Context({"request": request}), "purchasing"))


class SidebarDropdownTests(TestCase):
    def setUp(self):
        _sync_permissions()
        self.admin_role = AccessRole.objects.create(
            name="Administrativo",
            slug="admin-nav",
            hierarchy_level=1,
            has_full_access=True,
            customer_scope=DataScope.ALL,
            quote_scope=DataScope.ALL,
        )
        self.seller_role = AccessRole.objects.create(
            name="Vendedor",
            slug="seller-nav",
            hierarchy_level=50,
            has_full_access=False,
            customer_scope=DataScope.OWN,
            quote_scope=DataScope.OWN,
        )
        _grant(
            self.seller_role,
            "leads.view",
            "quotes.view",
            "customers.view",
            "commission_events.view_own",
            "dashboard.view",
        )
        self.ops_role = AccessRole.objects.create(
            name="Operacional",
            slug="ops-nav",
            hierarchy_level=60,
            has_full_access=False,
            customer_scope=DataScope.OWN,
            quote_scope=DataScope.OWN,
        )
        _grant(
            self.ops_role,
            "production_dashboard.view",
            "production_orders.view",
            "dashboard.view",
        )
        self.admin = User.objects.create_user("navadmin", password="pass")
        UserAccess.objects.create(user=self.admin, role=self.admin_role)
        self.seller = User.objects.create_user("navseller", password="pass")
        UserAccess.objects.create(user=self.seller, role=self.seller_role)
        self.ops = User.objects.create_user("navops", password="pass")
        UserAccess.objects.create(user=self.ops, role=self.ops_role)
        self.client = Client()

    def test_sidebar_renders_dropdown_ids_for_admin(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("pages:dashboard"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        for collapse_id in [
            "sidebarHome",
            "sidebarCommercial",
            "sidebarOperations",
            "sidebarProduction",
            "sidebarStock",
            "sidebarSchedule",
            "sidebarAfterSales",
            "sidebarMedia",
            "sidebarFinance",
            "sidebarPurchasing",
            "sidebarCommissions",
            "sidebarAdministration",
        ]:
            self.assertIn(f'id="{collapse_id}"', content)
            self.assertIn(f'aria-controls="{collapse_id}"', content)
            self.assertEqual(content.count(f'id="{collapse_id}"'), 1)
        self.assertIn("Dashboard", content)
        self.assertIn("Comercial", content)
        self.assertIn("Financeiro", content)
        self.assertIn("Compras", content)
        self.assertIn("Comissões", content)
        self.assertIn("Administração", content)
        self.assertIn("Origens comerciais", content)
        self.assertIn("Resumo de Cadastros", content)
        self.assertIn("Chapas", content)
        self.assertIn('data-bs-toggle="collapse"', content)
        self.assertIn("nav-second-level", content)
        self.assertIn("menu-arrow", content)

    def test_home_group_open_on_dashboard(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("pages:dashboard"))
        content = response.content.decode()
        self.assertIn('class="collapse show" id="sidebarHome"', content)
        self.assertIn('aria-expanded="true" aria-controls="sidebarHome"', content)

    def test_seller_sees_commercial_not_finance_or_commissions_admin(self):
        self.client.force_login(self.seller)
        response = self.client.get(reverse("pages:dashboard"))
        content = response.content.decode()
        self.assertIn("sidebarCommercial", content)
        self.assertIn("Minhas Comissões", content)
        self.assertNotIn("sidebarFinance", content)
        self.assertNotIn("sidebarCommissions", content)
        self.assertNotIn("sidebarProduction", content)

    def test_production_role_sees_production_not_commissions(self):
        self.client.force_login(self.ops)
        response = self.client.get(reverse("pages:dashboard"))
        content = response.content.decode()
        self.assertIn("sidebarProduction", content)
        self.assertNotIn("sidebarCommissions", content)
        self.assertNotIn("sidebarFinance", content)

    def test_empty_group_not_rendered_without_children(self):
        role = AccessRole.objects.create(
            name="Somente Dashboard",
            slug="dash-only",
            hierarchy_level=90,
            has_full_access=False,
        )
        _grant(role, "dashboard.view")
        user = User.objects.create_user("dashonly", password="pass")
        UserAccess.objects.create(user=user, role=role)
        self.client.force_login(user)
        response = self.client.get(reverse("pages:dashboard"))
        content = response.content.decode()
        self.assertIn("sidebarHome", content)
        self.assertNotIn("sidebarCommercial", content)
        self.assertNotIn("sidebarFinance", content)
        self.assertNotIn("sidebarAdministration", content)

    def test_no_duplicate_menu_labels_for_core_entries(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("pages:dashboard"))
        content = response.content.decode()
        self.assertEqual(content.count('aria-controls="sidebarFinance"'), 1)
        self.assertEqual(content.count('aria-controls="sidebarPurchasing"'), 1)
        self.assertEqual(content.count('aria-controls="sidebarCommissions"'), 1)
        self.assertEqual(content.count('aria-controls="sidebarAdministration"'), 1)
        self.assertEqual(content.count('href="#sidebarFinance"'), 1)
        self.assertEqual(content.count("Resumo de Cadastros"), 1)
