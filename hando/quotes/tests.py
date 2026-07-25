# ruff: noqa: PT009, S106, PT027
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from access_control.models import AccessRole
from access_control.models import DataScope
from access_control.models import UserAccess
from audit.models import AuditEvent
from customers.models import Customer
from materials.models import AdditionalService
from materials.models import Material
from materials.models import MaterialCategory
from quotes.models import CommercialPolicy
from quotes.models import Quote
from quotes.models import QuoteDelivery
from quotes.models import QuoteItem
from quotes.models import QuoteStatus
from quotes.services.calculation import area_from_mm
from quotes.services.calculation import calculate_item
from quotes.services.calculation import calculate_quote
from quotes.services.delivery import send_quote
from quotes.services.numbering import next_quote_number
from quotes.services.pdf import generate_quote_pdf
from quotes.services.query import quote_queryset_for_user
from quotes.services.versioning import create_version
from quotes.services.workflow import approve_quote
from quotes.services.workflow import cancel_quote
from quotes.services.workflow import submit_for_approval
from salespeople.models import Salesperson

User = get_user_model()


class QuoteCommercialTests(TestCase):
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
        self.sales_role = AccessRole.objects.create(
            name="Vendedor",
            slug="vendedor",
            hierarchy_level=50,
            customer_scope=DataScope.OWN,
            quote_scope=DataScope.OWN,
        )
        self.admin = User.objects.create_user("admin", password="pass")
        self.seller_user = User.objects.create_user("seller", password="pass")
        UserAccess.objects.create(user=self.admin, role=self.admin_role)
        UserAccess.objects.create(user=self.seller_user, role=self.sales_role)
        self.salesperson = Salesperson.objects.create(
            user=self.seller_user,
            code="V01",
            display_name="Vendedor",
        )
        self.other_salesperson = Salesperson.objects.create(
            code="V02",
            display_name="Outro",
        )
        self.customer = Customer.objects.create(
            customer_type="company",
            name="Cliente",
            email="cliente@example.com",
        )
        self.category = MaterialCategory.objects.create(name="Granito", slug="granito")
        self.material = Material.objects.create(
            code="GR01",
            name="Preto",
            category=self.category,
            cost_price=Decimal("100.00"),
            sale_price=Decimal("200.00"),
            minimum_sale_price=Decimal("150.00"),
            loss_percentage=Decimal("10.00"),
        )
        self.service = AdditionalService.objects.create(
            code="INST",
            name="Instalação",
            sale_price=Decimal("100.00"),
        )
        CommercialPolicy.objects.create(
            is_active=True,
            minimum_margin_percentage=Decimal("20.00"),
        )
        self.client.force_login(self.admin)

    def make_quote(self, salesperson=None):
        salesperson = salesperson or self.salesperson
        return Quote.objects.create(
            number=next_quote_number(),
            customer=self.customer,
            salesperson=salesperson,
            valid_until=timezone.localdate() + timezone.timedelta(days=10),
            created_by=salesperson.user or self.admin,
        )

    def test_calculates_area_loss_profit_and_margin(self):
        quote = self.make_quote()
        item = QuoteItem.objects.create(
            quote=quote,
            material=self.material,
            material_code_snapshot=self.material.code,
            material_name_snapshot=self.material.name,
            quantity=Decimal("1.000"),
            unit="m2",
            width_mm=Decimal("1000"),
            length_mm=Decimal("2000"),
            unit_cost=Decimal("100.00"),
            unit_price=Decimal("200.00"),
            loss_percentage=Decimal("10.00"),
        )
        calculate_item(item)
        item.save()
        calculate_quote(quote)
        self.assertEqual(area_from_mm(1000, 2000), Decimal("2.0000"))
        self.assertEqual(item.subtotal, Decimal("440.00"))
        self.assertEqual(quote.grand_total, Decimal("440.00"))
        self.assertEqual(quote.gross_profit, Decimal("220.00"))
        self.assertEqual(quote.gross_margin_percentage, Decimal("50.00"))

    def test_quote_number_is_unique(self):
        first = next_quote_number()
        second = next_quote_number()
        self.assertNotEqual(first, second)

    def test_own_scope_sees_only_own_quotes(self):
        own = self.make_quote(self.salesperson)
        self.make_quote(self.other_salesperson)
        qs = quote_queryset_for_user(self.seller_user)
        self.assertIn(own, qs)
        self.assertEqual(qs.count(), 1)

    def test_submit_approve_version_pdf_and_send(self):
        quote = self.make_quote()
        item = QuoteItem.objects.create(
            quote=quote,
            material=self.material,
            material_code_snapshot=self.material.code,
            material_name_snapshot=self.material.name,
            quantity=Decimal("1.000"),
            unit="unit",
            unit_cost=Decimal("50.00"),
            unit_price=Decimal("100.00"),
        )
        calculate_item(item)
        item.save()
        calculate_quote(quote)
        quote.save()
        submit_for_approval(quote=quote, actor=self.seller_user)
        quote.refresh_from_db()
        self.assertEqual(quote.status, QuoteStatus.PENDING_APPROVAL)
        version = approve_quote(quote=quote, actor=self.admin)
        self.assertEqual(version.version_number, 1)
        generate_quote_pdf(version=version, actor=self.admin)
        self.assertTrue(version.pdf_hash)
        delivery = send_quote(
            quote=quote,
            version=version,
            channel=QuoteDelivery.Channel.EMAIL,
            recipient="cliente@example.com",
            subject="Orçamento",
            message="Segue orçamento.",
            actor=self.admin,
        )
        self.assertEqual(delivery.status, QuoteDelivery.Status.SENT)
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue(AuditEvent.objects.filter(action="quote_sent").exists())

    def test_cancel_requires_reason_and_records_author(self):
        quote = self.make_quote()
        with self.assertRaises(ValidationError):
            cancel_quote(quote=quote, actor=self.admin, reason="")
        cancel_quote(quote=quote, actor=self.admin, reason="Cliente desistiu")
        quote.refresh_from_db()
        self.assertEqual(quote.status, QuoteStatus.CANCELLED)
        self.assertEqual(quote.cancelled_by, self.admin)

    def test_version_snapshot_is_immutable(self):
        quote = self.make_quote()
        calculate_quote(quote)
        quote.save()
        version = create_version(quote=quote, actor=self.admin)
        self.customer.name = "Cliente alterado"
        self.customer.save()
        self.assertEqual(version.snapshot["customer"], "Cliente")

    def test_quote_list_renders(self):
        response = self.client.get(reverse("quotes:list"))
        self.assertEqual(response.status_code, 200)
