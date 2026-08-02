# ruff: noqa: PT009, S106
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from access_control.models import AccessPermission
from access_control.models import AccessRole
from access_control.models import DataScope
from access_control.models import RolePermission
from access_control.models import UserAccess
from commercial.lead_conversion import create_lead
from commercial.lead_conversion import validate_lead_contact
from commercial.lead_forms import LeadForm
from commercial.lead_models import Lead
from commercial.lead_models import LeadActivity
from commercial.lead_models import LeadActivityType
from commercial.lead_models import LeadStatus
from commercial.lead_models import LeadTask
from commercial.lead_models import LeadTaskStatus
from commercial.lead_numbering import next_lead_code
from commercial.lead_workflow import assign_lead_salesperson
from commercial.lead_workflow import change_lead_status
from commercial.models import ChannelGroup
from commercial.models import CommercialSource
from commercial.models import LossReason
from customers.models import Customer
from salespeople.models import Salesperson

User = get_user_model()


LEAD_PERMISSIONS = [
    "leads.view",
    "leads.view_all",
    "leads.create",
    "leads.update",
    "leads.assign",
    "leads.change_status",
    "leads.override_status",
    "leads.convert",
    "leads.mark_won",
    "leads.mark_lost",
    "leads.reopen",
    "lead_activities.view",
    "lead_activities.create",
    "lead_tasks.view",
    "lead_tasks.create",
    "lead_tasks.complete",
    "lead_tasks.cancel",
    "quotes.create",
    "customers.view",
]


class LeadTestMixin:
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
        self.seller_role = AccessRole.objects.create(
            name="Vendedor CRM",
            slug="vendedor-crm",
            hierarchy_level=50,
            customer_scope=DataScope.OWN,
            quote_scope=DataScope.OWN,
            asset_scope=DataScope.OWN,
            maintenance_scope=DataScope.OWN,
        )
        self.admin = User.objects.create_user("admin", password="pass")
        self.seller_user = User.objects.create_user("seller", password="pass")
        self.other = User.objects.create_user("other", password="pass")
        UserAccess.objects.create(user=self.admin, role=self.admin_role)
        for code in LEAD_PERMISSIONS:
            perm, _ = AccessPermission.objects.get_or_create(
                code=code,
                defaults={"name": code, "module": code.split(".")[0], "action": code.split(".")[1]},
            )
            RolePermission.objects.create(role=self.admin_role, permission=perm, allowed=True)
        view_perm = AccessPermission.objects.get(code="leads.view")
        RolePermission.objects.create(role=self.seller_role, permission=view_perm, allowed=True)
        self.salesperson = Salesperson.objects.create(
            user=self.seller_user,
            code="VCRM",
            display_name="Vendedor CRM",
        )
        UserAccess.objects.create(user=self.seller_user, role=self.seller_role)
        self.loss_reason = LossReason.objects.create(
            name="Preço alto",
            slug="preco-alto",
            category="price",
            requires_notes=True,
        )


class LeadCreationTests(LeadTestMixin, TestCase):
    def test_contact_required(self):
        with self.assertRaises(ValidationError):
            validate_lead_contact(email="", phone="", whatsapp="")

    def test_automatic_code(self):
        code1 = next_lead_code()
        code2 = next_lead_code()
        self.assertTrue(code1.startswith("LEAD-"))
        self.assertNotEqual(code1, code2)

    def test_external_idempotency(self):
        form = LeadForm(
            data={
                "name": "Lead Externo",
                "phone": "11999998888",
                "external_source": "site",
                "external_id": "abc-123",
                "priority": "normal",
                "probability": 10,
                "estimated_value": "0",
            },
        )
        self.assertTrue(form.is_valid(), form.errors)
        create_lead(form=form, actor=self.admin)
        form2 = LeadForm(
            data={
                "name": "Lead Externo 2",
                "phone": "11999997777",
                "external_source": "site",
                "external_id": "abc-123",
                "priority": "normal",
                "probability": 10,
                "estimated_value": "0",
            },
        )
        self.assertFalse(form2.is_valid())

    def test_create_via_view(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("leads:create"),
            {
                "name": "Maria Silva",
                "phone": "11988887777",
                "priority": "normal",
                "probability": 20,
                "estimated_value": "15000.00",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Lead.objects.count(), 1)


class LeadWorkflowTests(LeadTestMixin, TestCase):
    def _lead(self, **kwargs):
        defaults = {
            "code": next_lead_code(),
            "name": "Lead Teste",
            "phone": "11977776666",
            "status": LeadStatus.NEW,
            "created_by": self.admin,
            "updated_by": self.admin,
        }
        defaults.update(kwargs)
        return Lead.objects.create(**defaults)

    def test_valid_transition(self):
        lead = self._lead()
        change_lead_status(lead=lead, new_status=LeadStatus.TRIAGE, actor=self.admin)
        assign_lead_salesperson(lead=lead, salesperson=self.salesperson, actor=self.admin)
        lead.refresh_from_db()
        self.assertEqual(lead.status, LeadStatus.ASSIGNED)

    def test_invalid_transition_blocked(self):
        lead = self._lead()
        with self.assertRaises(ValidationError):
            change_lead_status(lead=lead, new_status=LeadStatus.WON, actor=self.admin)

    def test_loss_requires_reason(self):
        lead = self._lead(status=LeadStatus.CONTACTED)
        with self.assertRaises(ValidationError):
            change_lead_status(
                lead=lead,
                new_status=LeadStatus.DISQUALIFIED,
                actor=self.admin,
            )

    def test_loss_requires_notes_when_configured(self):
        lead = self._lead(status=LeadStatus.QUALIFIED)
        with self.assertRaises(ValidationError):
            change_lead_status(
                lead=lead,
                new_status=LeadStatus.LOST,
                actor=self.admin,
                loss_reason=self.loss_reason,
                loss_notes="",
            )

    def test_activity_created_on_status_change(self):
        lead = self._lead()
        change_lead_status(lead=lead, new_status=LeadStatus.TRIAGE, actor=self.admin)
        self.assertTrue(
            LeadActivity.objects.filter(
                lead=lead,
                activity_type=LeadActivityType.STATUS_CHANGE,
            ).exists(),
        )


class LeadScopeTests(LeadTestMixin, TestCase):
    def test_seller_cannot_see_unassigned_lead_of_other(self):
        lead = Lead.objects.create(
            code=next_lead_code(),
            name="Lead Alheio",
            phone="11966665555",
            created_by=self.admin,
            updated_by=self.admin,
        )
        self.client.force_login(self.seller_user)
        response = self.client.get(reverse("leads:detail", args=[lead.pk]))
        self.assertEqual(response.status_code, 403)


class LeadConversionTests(LeadTestMixin, TestCase):
    def test_convert_new_customer(self):
        lead = Lead.objects.create(
            code=next_lead_code(),
            name="João",
            phone="11955554444",
            created_by=self.admin,
            updated_by=self.admin,
        )
        self.client.force_login(self.admin)
        response = self.client.post(reverse("leads:convert_new", args=[lead.pk]))
        self.assertEqual(response.status_code, 302)
        lead.refresh_from_db()
        self.assertIsNotNone(lead.converted_customer_id)

    def test_duplicate_conversion_blocked(self):
        customer = Customer.objects.create(customer_type="individual", name="Existente")
        lead = Lead.objects.create(
            code=next_lead_code(),
            name="João",
            phone="11944443333",
            converted_customer=customer,
            created_by=self.admin,
            updated_by=self.admin,
        )
        self.client.force_login(self.admin)
        response = self.client.post(reverse("leads:convert_new", args=[lead.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Customer.objects.count(), 1)


class LeadTaskTests(LeadTestMixin, TestCase):
    def test_overdue_task_property(self):
        lead = Lead.objects.create(
            code=next_lead_code(),
            name="Lead Tarefa",
            phone="11933332222",
            created_by=self.admin,
            updated_by=self.admin,
        )
        task = LeadTask.objects.create(
            lead=lead,
            title="Ligar",
            assigned_to=self.admin,
            due_at=timezone.now() - timedelta(hours=1),
            created_by=self.admin,
        )
        self.assertTrue(task.is_overdue)
        task.status = LeadTaskStatus.COMPLETED
        task.save()
        self.assertFalse(task.is_overdue)


class LeadDashboardTests(LeadTestMixin, TestCase):
    def test_dashboard_and_kanban(self):
        Lead.objects.create(
            code=next_lead_code(),
            name="Lead Dash",
            phone="11922221111",
            created_by=self.admin,
            updated_by=self.admin,
        )
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("leads:dashboard")).status_code, 200)
        self.assertEqual(self.client.get(reverse("leads:funnel")).status_code, 200)


class LeadSeedTests(TestCase):
    def test_permissions_seed_idempotent(self):
        before = AccessPermission.objects.filter(code__startswith="leads.").count()
        call_command("setup_erp_foundation")
        after = AccessPermission.objects.filter(code__startswith="leads.").count()
        call_command("setup_erp_foundation")
        self.assertEqual(AccessPermission.objects.filter(code__startswith="leads.").count(), after)
        self.assertGreater(after, before)


class ExistingDataCompatibilityTests(TestCase):
    def test_existing_customer_without_lead_fields(self):
        customer = Customer.objects.create(customer_type="individual", name="Legado")
        self.assertIsNone(customer.commercial_source_id)

    def test_existing_quote_without_lead(self):
        from quotes.models import Quote
        from salespeople.models import Salesperson

        sp = Salesperson.objects.create(code="LEG", display_name="Legado")
        customer = Customer.objects.create(customer_type="individual", name="Cliente")
        quote = Quote.objects.create(
            customer=customer,
            salesperson=sp,
            valid_until="2030-01-01",
        )
        self.assertIsNone(quote.lead_id)
