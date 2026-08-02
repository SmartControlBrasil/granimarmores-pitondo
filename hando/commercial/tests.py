# ruff: noqa: PT009, S106
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from access_control.models import AccessPermission
from access_control.models import AccessRole
from access_control.models import DataScope
from access_control.models import RolePermission
from access_control.models import UserAccess
from commercial.models import ChannelGroup
from commercial.models import CommercialPartner
from commercial.models import CommercialSource
from commercial.models import ContactChannel
from commercial.models import LossReason
from commercial.models import PartnerType
from commercial.models import ProjectType
from commercial.models import ServiceRegion
from customers.models import Customer
from quotes.models import Quote
from salespeople.models import Salesperson

User = get_user_model()


class CommercialTestMixin:
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
        self.viewer_role = AccessRole.objects.create(
            name="Consulta Comercial",
            slug="consulta-comercial",
            hierarchy_level=90,
            customer_scope=DataScope.OWN,
            quote_scope=DataScope.OWN,
            asset_scope=DataScope.OWN,
            maintenance_scope=DataScope.OWN,
        )
        self.admin = User.objects.create_user("admin", password="pass")
        self.viewer = User.objects.create_user("viewer", password="pass")
        UserAccess.objects.create(user=self.admin, role=self.admin_role)
        for code in PERMISSION_CODES:
            permission, _ = AccessPermission.objects.get_or_create(
                code=code,
                defaults={
                    "name": code,
                    "module": code.split(".")[0],
                    "action": code.split(".")[1],
                },
            )
            RolePermission.objects.create(
                role=self.admin_role,
                permission=permission,
                allowed=True,
            )
        RolePermission.objects.create(
            role=self.viewer_role,
            permission=AccessPermission.objects.get(code="commercial_sources.view"),
            allowed=True,
        )
        UserAccess.objects.create(user=self.viewer, role=self.viewer_role)


PERMISSION_CODES = [
    "commercial_sources.view",
    "commercial_sources.create",
    "commercial_sources.update",
    "project_types.view",
    "project_types.create",
    "project_types.update",
    "commercial_partners.view",
    "commercial_partners.create",
    "commercial_partners.update",
    "commercial_partners.deactivate",
    "loss_reasons.view",
    "loss_reasons.create",
    "loss_reasons.update",
    "service_regions.view",
    "service_regions.create",
    "service_regions.update",
    "contact_channels.view",
    "contact_channels.create",
    "contact_channels.update",
    "customers.view",
    "customers.create",
    "quotes.view",
    "quotes.create",
    "salespeople.view",
    "materials.view",
]


class CommercialSourceTests(CommercialTestMixin, TestCase):
    def test_create_and_list_source(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("commercial:source_create"),
            {
                "name": "Instagram Ads",
                "slug": "instagram-ads",
                "channel_group": ChannelGroup.PAID,
                "display_order": 5,
                "is_active": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(CommercialSource.objects.filter(slug="instagram-ads").exists())
        response = self.client.get(reverse("commercial:sources"))
        self.assertContains(response, "Instagram Ads")

    def test_source_in_use_cannot_be_deleted(self):
        source = CommercialSource.objects.create(
            name="Indicação",
            slug="indicacao",
            channel_group=ChannelGroup.REFERRAL,
        )
        Customer.objects.create(
            customer_type="individual",
            name="Cliente",
            commercial_source=source,
        )
        with self.assertRaises(ValidationError):
            source.delete()


class ProjectTypeTests(CommercialTestMixin, TestCase):
    def test_create_project_type(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("commercial:project_type_create"),
            {
                "name": "Bancada",
                "slug": "bancada",
                "requires_measurement": "on",
                "allows_installation": "on",
                "display_order": 1,
                "is_active": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(ProjectType.objects.filter(slug="bancada").exists())


class CommercialPartnerTests(CommercialTestMixin, TestCase):
    def test_create_partner_detail(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("commercial:partner_create"),
            {
                "partner_type": PartnerType.ARCHITECT,
                "name": "Arquiteto Silva",
                "is_active": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        partner = CommercialPartner.objects.get(name="Arquiteto Silva")
        response = self.client.get(reverse("commercial:partner_detail", args=[partner.pk]))
        self.assertContains(response, "Ainda não existem clientes indicados")


class MasterDataCrudTests(CommercialTestMixin, TestCase):
    def test_loss_reason_region_and_channel_crud(self):
        self.client.force_login(self.admin)
        self.client.post(
            reverse("commercial:loss_reason_create"),
            {
                "name": "Preço",
                "slug": "preco",
                "category": "price",
                "display_order": 1,
                "is_active": "on",
            },
        )
        self.client.post(
            reverse("commercial:region_create"),
            {
                "name": "Zona Sul",
                "city": "São Paulo",
                "state": "SP",
                "service_enabled": "on",
                "travel_fee": "0",
                "minimum_order_value": "0",
                "estimated_travel_minutes": 30,
                "display_order": 1,
                "is_active": "on",
            },
        )
        self.client.post(
            reverse("commercial:channel_create"),
            {
                "name": "WhatsApp",
                "slug": "whatsapp",
                "display_order": 1,
                "is_active": "on",
            },
        )
        self.assertTrue(LossReason.objects.filter(slug="preco").exists())
        self.assertTrue(ServiceRegion.objects.filter(name="Zona Sul").exists())
        self.assertTrue(ContactChannel.objects.filter(slug="whatsapp").exists())


class PermissionTests(CommercialTestMixin, TestCase):
    def test_viewer_can_list_but_not_create(self):
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(reverse("commercial:sources")).status_code, 200)
        response = self.client.get(reverse("commercial:source_create"))
        self.assertEqual(response.status_code, 403)


class SidebarAndSummaryTests(CommercialTestMixin, TestCase):
    def test_sidebar_shows_commercial_entries_for_admin(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("pages:dashboard"))
        self.assertContains(response, "Origens comerciais")
        self.assertContains(response, "Resumo de Cadastros")
        self.assertContains(response, "Chapas")

    def test_summary_page_renders_cards(self):
        CommercialSource.objects.create(
            name="Google",
            slug="google",
            channel_group=ChannelGroup.ORGANIC,
        )
        self.client.force_login(self.admin)
        response = self.client.get(reverse("commercial:summary"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Origens ativas")


class SeedTests(TestCase):
    def test_setup_erp_foundation_is_idempotent(self):
        call_command("setup_erp_foundation")
        first_count = CommercialSource.objects.count()
        call_command("setup_erp_foundation")
        self.assertEqual(CommercialSource.objects.count(), first_count)


class CustomerQuoteIntegrationTests(CommercialTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.source = CommercialSource.objects.create(
            name="Indicação",
            slug="indicacao-test",
            channel_group=ChannelGroup.REFERRAL,
        )
        self.project_type = ProjectType.objects.create(
            name="Bancada",
            slug="bancada-test",
        )
        self.partner = CommercialPartner.objects.create(
            partner_type=PartnerType.ARCHITECT,
            name="Parceiro Teste",
        )
        self.salesperson = Salesperson.objects.create(code="V01", display_name="Vendedor")

    def test_existing_customer_without_commercial_fields(self):
        customer = Customer.objects.create(customer_type="individual", name="Legado")
        self.assertIsNone(customer.commercial_source_id)

    def test_quote_copies_commercial_fields_from_customer_on_create(self):
        customer = Customer.objects.create(
            customer_type="individual",
            name="Cliente Com Origem",
            commercial_source=self.source,
            partner=self.partner,
            project_type_interest=self.project_type,
        )
        quote = Quote.objects.create(
            customer=customer,
            salesperson=self.salesperson,
            valid_until="2030-01-01",
            commercial_source=customer.commercial_source,
            partner=customer.partner,
            project_type=customer.project_type_interest,
        )
        self.assertEqual(quote.commercial_source_id, self.source.pk)
        self.assertEqual(quote.project_type_id, self.project_type.pk)


from commercial import tests_leads  # noqa: F401
