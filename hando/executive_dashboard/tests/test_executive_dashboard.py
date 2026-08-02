# ruff: noqa: PT009, S106
from datetime import timedelta
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import Client
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from access_control.models import AccessPermission
from access_control.models import AccessRole
from access_control.models import DataScope
from access_control.models import RolePermission
from access_control.models import UserAccess
from access_control.permissions import PERMISSIONS
from commercial.lead_models import Lead
from commercial.lead_models import LeadStatus
from commercial.performance_definitions import CLOSED_SALE_QUOTE_STATUS
from commercial.performance_metrics import safe_divide
from commercial.performance_metrics import safe_rate
from commercial.performance_score import create_default_score_policy
from customers.models import Customer
from executive_dashboard.selectors.commercial import commercial_metrics
from executive_dashboard.services.aggregation import build_executive_dashboard
from executive_dashboard.services.export import sanitize_csv_cell
from executive_dashboard.services.periods import parse_executive_period
from quotes.models import Quote
from quotes.models import QuoteItem
from quotes.models import QuoteStatus
from salespeople.models import Salesperson


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


class _Req:
    def __init__(self, **get):
        self.GET = get


class ExecutiveDashboardTests(TestCase):
    def setUp(self):
        cache.clear()
        _sync_permissions()
        self.admin_role = AccessRole.objects.create(
            name="Administrativo",
            slug="admin-exec",
            hierarchy_level=1,
            has_full_access=True,
            customer_scope=DataScope.ALL,
            quote_scope=DataScope.ALL,
        )
        self.seller_role = AccessRole.objects.create(
            name="Vendedor",
            slug="seller-exec",
            hierarchy_level=50,
            has_full_access=False,
            customer_scope=DataScope.OWN,
            quote_scope=DataScope.OWN,
        )
        self.manager_role = AccessRole.objects.create(
            name="Gestor Comercial",
            slug="manager-exec",
            hierarchy_level=20,
            has_full_access=False,
            customer_scope=DataScope.TEAM,
            quote_scope=DataScope.TEAM,
        )
        _grant(
            self.manager_role,
            "executive_dashboard.view_commercial",
            "executive_dashboard.view_sales_values",
            "executive_dashboard.export",
            "executive_dashboard.print",
        )

        self.admin = User.objects.create_user("execadmin", password="pass")
        UserAccess.objects.create(user=self.admin, role=self.admin_role)
        self.seller = User.objects.create_user("execseller", password="pass")
        UserAccess.objects.create(user=self.seller, role=self.seller_role)
        self.manager = User.objects.create_user("execmanager", password="pass")
        UserAccess.objects.create(user=self.manager, role=self.manager_role)

        create_default_score_policy(actor=self.admin)
        self.sp = Salesperson.objects.create(code="VE", display_name="Vendedor Exec")
        self.customer = Customer.objects.create(
            customer_type="individual",
            name="Cliente Exec",
            assigned_salesperson=self.sp,
        )
        now = timezone.now()
        self.lead = Lead.objects.create(
            name="Lead Exec",
            status=LeadStatus.NEW,
            assigned_salesperson=self.sp,
            estimated_value=Decimal("1000.00"),
            city="Curitiba",
            created_by=self.admin,
        )
        Lead.objects.filter(pk=self.lead.pk).update(created_at=now)
        self.quote_accepted = Quote.objects.create(
            number="ORC-EXEC-001",
            customer=self.customer,
            salesperson=self.sp,
            status=QuoteStatus.ACCEPTED,
            subtotal=Decimal("2000.00"),
            grand_total=Decimal("2000.00"),
            valid_until=timezone.localdate(),
            accepted_at=now,
            created_by=self.admin,
        )
        QuoteItem.objects.create(
            quote=self.quote_accepted,
            description="Bancada",
            quantity=Decimal("1"),
            unit_price=Decimal("2000.00"),
            subtotal=Decimal("2000.00"),
        )
        self.quote_draft = Quote.objects.create(
            number="ORC-EXEC-002",
            customer=self.customer,
            salesperson=self.sp,
            status=QuoteStatus.DRAFT,
            subtotal=Decimal("9999.00"),
            grand_total=Decimal("9999.00"),
            valid_until=timezone.localdate(),
            created_by=self.admin,
        )
        self.client = Client()

    def test_access_authorized(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse("executive_dashboard:dashboard"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Painel da Diretoria")

    def test_access_denied_seller(self):
        self.client.force_login(self.seller)
        resp = self.client.get(reverse("executive_dashboard:dashboard"))
        self.assertEqual(resp.status_code, 403)

    def test_manager_commercial_access(self):
        self.client.force_login(self.manager)
        resp = self.client.get(reverse("executive_dashboard:dashboard"))
        self.assertEqual(resp.status_code, 200)

    def test_period_and_invalid(self):
        start, end, period, prev = parse_executive_period(_Req(period="30d"))
        self.assertEqual(period, "30d")
        self.assertLess(start, end)
        self.assertLess(prev[0], prev[1])
        with self.assertRaises(ValidationError):
            parse_executive_period(_Req(period="custom", start="2026-08-01", end="2026-07-01"))

    def test_accepted_sale_and_draft_excluded(self):
        start = timezone.now() - timedelta(days=7)
        end = timezone.now()
        metrics = commercial_metrics(start=start, end=end)
        self.assertEqual(metrics["quotes_accepted"], 1)
        self.assertEqual(metrics["approved_value"], Decimal("2000.00"))
        self.assertNotEqual(CLOSED_SALE_QUOTE_STATUS, QuoteStatus.DRAFT)

    def test_ticket_conversion_zero_division(self):
        self.assertEqual(safe_divide(Decimal("0"), 0), Decimal("0"))
        self.assertEqual(safe_rate(0, 0), Decimal("0"))
        start = timezone.now() - timedelta(days=7)
        end = timezone.now()
        metrics = commercial_metrics(start=start, end=end)
        self.assertEqual(metrics["ticket_average"], Decimal("2000.00"))

    def test_empty_state_and_trends(self):
        Lead.objects.all().delete()
        Quote.objects.all().delete()
        start = timezone.now() - timedelta(days=7)
        end = timezone.now()
        prev = (start - timedelta(days=7), start)
        data = build_executive_dashboard(
            user=self.admin,
            start=start,
            end=end,
            previous_period=prev,
        )
        self.assertEqual(data["summary"]["leads_received"], 0)
        self.assertEqual(data["summary"]["quotes_accepted"], 0)
        self.assertIn("leads", data["trends"])

    @override_settings(EXECUTIVE_DASHBOARD_CACHE_SECONDS=120)
    def test_cache_per_user(self):
        start = timezone.now() - timedelta(days=7)
        end = timezone.now()
        prev = (start - timedelta(days=7), start)
        d1 = build_executive_dashboard(user=self.admin, start=start, end=end, previous_period=prev)
        self.assertFalse(d1["from_cache"])
        d2 = build_executive_dashboard(user=self.admin, start=start, end=end, previous_period=prev)
        self.assertTrue(d2["from_cache"])
        d3 = build_executive_dashboard(user=self.manager, start=start, end=end, previous_period=prev)
        self.assertFalse(d3["from_cache"])

    def test_costs_restricted_for_manager(self):
        start = timezone.now() - timedelta(days=7)
        end = timezone.now()
        prev = (start - timedelta(days=7), start)
        data = build_executive_dashboard(
            user=self.manager,
            start=start,
            end=end,
            previous_period=prev,
        )
        self.assertFalse(data.get("can_view_stock_costs"))

    def test_report_and_csv(self):
        self.client.force_login(self.admin)
        report = self.client.get(reverse("executive_dashboard:report"))
        self.assertEqual(report.status_code, 200)
        self.assertContains(report, "Relatório Executivo")
        csv_resp = self.client.get(reverse("executive_dashboard:export_csv", args=["vendas"]))
        self.assertEqual(csv_resp.status_code, 200)
        self.assertIn("text/csv", csv_resp["Content-Type"])
        self.assertIn("Valor aprovado", csv_resp.content.decode("utf-8"))

    def test_csv_injection(self):
        self.assertEqual(sanitize_csv_cell("=1+1"), "'=1+1")
        self.assertEqual(sanitize_csv_cell("+cmd"), "'+cmd")
        self.assertEqual(sanitize_csv_cell("ok"), "ok")

    def test_seed_and_command(self):
        out = StringIO()
        call_command("setup_erp_foundation", stdout=out)
        self.assertTrue(
            AccessPermission.objects.filter(code="executive_dashboard.view").exists(),
        )
        out2 = StringIO()
        call_command("audit_executive_metrics", "--dry-run", stdout=out2)
        self.assertIn("Auditoria", out2.getvalue())

    def test_dashboard_shortcut(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse("pages:dashboard"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Painel da Diretoria")
