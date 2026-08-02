# ruff: noqa: PT009, S106
from datetime import timedelta
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db.models import Sum
from django.test import Client
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from access_control.models import AccessPermission
from access_control.models import AccessRole
from access_control.models import DataScope
from access_control.models import RolePermission
from access_control.models import UserAccess
from access_control.permissions import PERMISSIONS
from commercial.models import CommercialPartner
from commercial.models import PartnerType
from commissions.export import sanitize_csv_cell
from commissions.models import CommissionEvent
from commissions.models import CommissionPolicy
from commissions.models import EventStatus
from commissions.models import EventType
from commissions.models import SettlementStatus
from commissions.services.calculation import calculate_commission_amount
from commissions.services.calculation import simulate_commission
from commissions.services.policies import create_policy
from commissions.services.policies import detect_policy_overlaps
from commissions.services.provisioning import provision_commission
from commissions.services.provisioning import release_commission_for_receivable_payment
from commissions.services.reversals import cancel_commissions_for_sale
from commissions.services.reversals import create_manual_adjustment
from commissions.services.reversals import reverse_commission_event
from commissions.services.settlement import approve_settlement
from commissions.services.settlement import create_settlement
from commissions.services.settlement import generate_payable_from_settlement
from commissions.services.settlement import register_commission_payment
from customers.models import Customer
from finance.models import AccountType
from finance.models import CategoryType
from finance.models import CostCenter
from finance.models import FinancialCategory
from finance.models import MethodType
from finance.models import PaymentMethod
from finance.models import PaymentTerm
from finance.services.payments import register_receivable_payment
from finance.services.payments import reverse_receivable_payment
from finance.services.receivables import generate_receivable_from_order
from finance.services.reconciliation import create_financial_account
from production.models import SalesOrder
from production.models import SalesOrderStatus
from production.services.order_workflow import change_order_status
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


class CommissionTests(TestCase):
    def setUp(self):
        _sync_permissions()
        self.admin_role = AccessRole.objects.create(
            name="Administrativo",
            slug="admin-comm",
            hierarchy_level=1,
            has_full_access=True,
            customer_scope=DataScope.ALL,
            quote_scope=DataScope.ALL,
        )
        self.seller_role = AccessRole.objects.create(
            name="Vendedor",
            slug="seller-comm",
            hierarchy_level=50,
            has_full_access=False,
            customer_scope=DataScope.OWN,
            quote_scope=DataScope.OWN,
        )
        _grant(self.seller_role, "commission_events.view_own")
        self.user = User.objects.create_user("commadmin", password="pass")
        UserAccess.objects.create(user=self.user, role=self.admin_role)
        self.seller_user = User.objects.create_user("commseller", password="pass")
        UserAccess.objects.create(user=self.seller_user, role=self.seller_role)
        self.sp = Salesperson.objects.create(
            code="VC",
            display_name="Vendedor Comm",
            user=self.seller_user,
        )
        self.partner = CommercialPartner.objects.create(
            partner_type=PartnerType.ARCHITECT,
            name="Parceiro Comm",
            document="123",
        )
        self.customer = Customer.objects.create(
            customer_type="individual",
            name="Cliente Comm",
            assigned_salesperson=self.sp,
        )
        FinancialCategory.objects.create(
            name="Comissões Comerciais",
            code="comissoes-comerciais",
            category_type=CategoryType.EXPENSE,
        )
        FinancialCategory.objects.create(
            name="Venda de peças",
            code="venda-de-pecas",
            category_type=CategoryType.INCOME,
        )
        self.cost_center = CostCenter.objects.create(name="Comercial", code="comercial")
        self.method = PaymentMethod.objects.create(
            name="PIX",
            code="pix-comm",
            method_type=MethodType.PIX,
        )
        self.term = PaymentTerm.objects.create(
            name="À vista",
            installment_count=1,
            first_due_days=0,
            interval_days=0,
        )
        self.account = create_financial_account(
            data={
                "name": "Caixa Comm",
                "account_type": AccountType.CASH,
                "initial_balance": Decimal("10000.00"),
            },
            actor=self.user,
        )
        self.client = Client()
        today = timezone.localdate()
        self.policy = create_policy(
            data={
                "name": "Política padrão vendedor",
                "commission_target": "salesperson",
                "calculation_basis": "net_order_value",
                "trigger_type": "quote_accepted",
                "valid_from": today - timedelta(days=30),
                "priority": 10,
                "release_only_after_payment": True,
            },
            tiers=[
                {
                    "sequence": 1,
                    "minimum_value": "0",
                    "maximum_value": "20000",
                    "commission_type": "percentage",
                    "commission_value": "2",
                },
                {
                    "sequence": 2,
                    "minimum_value": "20000.01",
                    "maximum_value": "50000",
                    "commission_type": "percentage",
                    "commission_value": "3",
                },
                {
                    "sequence": 3,
                    "minimum_value": "50000.01",
                    "maximum_value": None,
                    "commission_type": "percentage",
                    "commission_value": "4",
                },
            ],
            actor=self.user,
        )
        self.partner_policy = create_policy(
            data={
                "name": "Política parceiro",
                "commission_target": "commercial_partner",
                "calculation_basis": "net_order_value",
                "trigger_type": "quote_accepted",
                "valid_from": today - timedelta(days=30),
                "priority": 20,
                "release_only_after_payment": True,
            },
            tiers=[
                {
                    "sequence": 1,
                    "minimum_value": "0",
                    "maximum_value": None,
                    "commission_type": "percentage",
                    "commission_value": "1",
                },
            ],
            actor=self.user,
        )

    def _accepted_quote(self, total="10000.00", with_partner=False, status=QuoteStatus.ACCEPTED):
        now = timezone.now()
        quote = Quote.objects.create(
            number=f"ORC-COMM-{Quote.objects.count() + 1}",
            customer=self.customer,
            salesperson=self.sp,
            partner=self.partner if with_partner else None,
            status=status,
            subtotal=Decimal(total),
            grand_total=Decimal(total),
            valid_until=timezone.localdate() + timedelta(days=10),
            accepted_at=now if status == QuoteStatus.ACCEPTED else None,
            created_by=self.user,
        )
        QuoteItem.objects.create(
            quote=quote,
            description="Peça",
            quantity=Decimal("1"),
            unit_price=Decimal(total),
            subtotal=Decimal(total),
        )
        return quote

    def _order_for(self, quote):
        return SalesOrder.objects.create(
            number=f"PED-COMM-{SalesOrder.objects.count() + 1}",
            quote=quote,
            customer=self.customer,
            salesperson=self.sp,
            status=SalesOrderStatus.CONFIRMED,
            order_date=timezone.localdate(),
            subtotal=quote.grand_total,
            total=quote.grand_total,
            created_by=self.user,
        )

    def test_policy_validity_overlap_and_tiers(self):
        today = timezone.localdate()
        with self.assertRaises(ValidationError):
            create_policy(
                data={
                    "name": "Sobreposta",
                    "commission_target": "salesperson",
                    "trigger_type": "quote_accepted",
                    "valid_from": today,
                    "priority": 10,
                },
                tiers=[{"sequence": 1, "commission_value": "5"}],
                actor=self.user,
            )
        overlap = detect_policy_overlaps(self.policy)
        self.assertEqual(overlap, [])
        amount, rate = calculate_commission_amount(
            policy=self.policy,
            rule=None,
            basis_amount=Decimal("10000"),
        )
        self.assertEqual(amount, Decimal("200.00"))
        self.assertEqual(rate, Decimal("2"))
        amount2, rate2 = calculate_commission_amount(
            policy=self.policy,
            rule=None,
            basis_amount=Decimal("30000"),
        )
        self.assertEqual(amount2, Decimal("900.00"))
        self.assertEqual(rate2, Decimal("3"))
        fixed_policy = create_policy(
            data={
                "name": "Fixo",
                "commission_target": "salesperson",
                "trigger_type": "manual",
                "valid_from": today,
                "priority": 99,
            },
            tiers=[
                {
                    "sequence": 1,
                    "minimum_value": "0",
                    "commission_type": "fixed_amount",
                    "commission_value": "150",
                },
            ],
            actor=self.user,
        )
        amount3, rate3 = calculate_commission_amount(
            policy=fixed_policy,
            rule=None,
            basis_amount=Decimal("999"),
        )
        self.assertEqual(amount3, Decimal("150"))
        self.assertEqual(rate3, Decimal("0"))

    def test_provision_accepted_not_draft_and_idempotent(self):
        draft = self._accepted_quote(status=QuoteStatus.DRAFT)
        with self.assertRaises(ValidationError):
            provision_commission(quote=draft, actor=self.user)
        quote = self._accepted_quote(total="10000.00")
        created = provision_commission(quote=quote, actor=self.user)
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].commission_amount, Decimal("200.00"))
        self.assertEqual(created[0].status, EventStatus.PROVISIONED)
        self.assertTrue(created[0].number.startswith("COM-"))
        again = provision_commission(quote=quote, actor=self.user)
        self.assertEqual(again, [])
        with self.assertRaises(ValidationError):
            created[0].commission_amount = Decimal("1.00")
            created[0].save()

    def test_partner_provision(self):
        quote = self._accepted_quote(total="10000.00", with_partner=True)
        created = provision_commission(quote=quote, actor=self.user)
        types = {e.beneficiary_type for e in created}
        self.assertIn("salesperson", types)
        self.assertIn("commercial_partner", types)
        partner_ev = next(e for e in created if e.beneficiary_type == "commercial_partner")
        self.assertEqual(partner_ev.commission_amount, Decimal("100.00"))
        self.assertEqual(partner_ev.beneficiary_name_snapshot, "Parceiro Comm")

    def test_partial_and_full_release_and_finance_reverse(self):
        quote = self._accepted_quote(total="10000.00")
        order = self._order_for(quote)
        provision_commission(quote=quote, sales_order=order, actor=self.user)
        recv = generate_receivable_from_order(
            sales_order=order,
            payment_term=self.term,
            actor=self.user,
            category=FinancialCategory.objects.get(code="venda-de-pecas"),
            cost_center=self.cost_center,
        )
        inst = recv.installments.first()
        p1 = register_receivable_payment(
            installment=inst,
            amount=Decimal("4000.00"),
            payment_date=timezone.localdate(),
            actor=self.user,
            payment_method=self.method,
            financial_account=self.account,
        )
        releases = CommissionEvent.objects.filter(
            event_type=EventType.RELEASE,
            receivable_payment=p1,
        )
        self.assertEqual(releases.count(), 1)
        self.assertEqual(releases.first().commission_amount, Decimal("80.00"))
        p2 = register_receivable_payment(
            installment=inst,
            amount=Decimal("6000.00"),
            payment_date=timezone.localdate(),
            actor=self.user,
            payment_method=self.method,
            financial_account=self.account,
        )
        total_released = (
            CommissionEvent.objects.filter(
                event_type=EventType.RELEASE,
                quote=quote,
            )
            .exclude(status__in=[EventStatus.REVERSED, EventStatus.CANCELLED])
            .aggregate(v=Sum("commission_amount"))["v"]
        )
        self.assertEqual(total_released, Decimal("200.00"))
        reverse_receivable_payment(payment=p2, actor=self.user, reason="Erro de caixa")
        active = CommissionEvent.objects.filter(
            event_type=EventType.RELEASE,
            receivable_payment=p2,
        ).exclude(status=EventStatus.REVERSED)
        self.assertFalse(active.exists())

    def test_cancel_sale_and_manual_adjustment_settlement_payable_payment(self):
        quote = self._accepted_quote(total="10000.00")
        order = self._order_for(quote)
        provision_commission(quote=quote, sales_order=order, actor=self.user)
        recv = generate_receivable_from_order(
            sales_order=order,
            payment_term=self.term,
            actor=self.user,
            category=FinancialCategory.objects.get(code="venda-de-pecas"),
        )
        inst = recv.installments.first()
        payment = register_receivable_payment(
            installment=inst,
            amount=Decimal("10000.00"),
            payment_date=timezone.localdate(),
            actor=self.user,
            payment_method=self.method,
            financial_account=self.account,
        )
        release = CommissionEvent.objects.get(
            event_type=EventType.RELEASE,
            receivable_payment=payment,
        )
        self.assertEqual(release.status, EventStatus.AVAILABLE)
        settlement = create_settlement(
            beneficiary_type="salesperson",
            salesperson=self.sp,
            period_start=timezone.localdate() - timedelta(days=1),
            period_end=timezone.localdate() + timedelta(days=1),
            actor=self.user,
        )
        self.assertEqual(settlement.status, SettlementStatus.UNDER_REVIEW)
        self.assertTrue(settlement.number.startswith("FEC-"))
        approve_settlement(settlement=settlement, actor=self.user)
        payable = generate_payable_from_settlement(
            settlement=settlement,
            actor=self.user,
            due_date=timezone.localdate() + timedelta(days=7),
        )
        self.assertEqual(payable.reference_type, "commission_settlement")
        with self.assertRaises(ValidationError):
            generate_payable_from_settlement(
                settlement=settlement,
                actor=self.user,
                due_date=timezone.localdate(),
            )
        pcm = register_commission_payment(
            settlement=settlement,
            amount=settlement.net_amount,
            payment_date=timezone.localdate(),
            actor=self.user,
            payment_method=self.method,
            financial_account=self.account,
        )
        self.assertTrue(pcm.number.startswith("PCM-"))
        settlement.refresh_from_db()
        self.assertEqual(settlement.status, SettlementStatus.PAID)

        adj = create_manual_adjustment(
            beneficiary_type="salesperson",
            salesperson=self.sp,
            amount=Decimal("25.00"),
            direction="positive",
            competence_date=timezone.localdate(),
            reason="Ajuste comercial aprovado",
            actor=self.user,
        )
        self.assertEqual(adj.event_type, EventType.ADJUSTMENT_POSITIVE)

        quote2 = self._accepted_quote(total="5000.00")
        order2 = self._order_for(quote2)
        events = provision_commission(quote=quote2, sales_order=order2, actor=self.user)
        self.assertTrue(events)
        cancel_commissions_for_sale(
            quote=quote2,
            sales_order=order2,
            actor=self.user,
            reason="Venda cancelada",
        )
        events[0].refresh_from_db()
        self.assertEqual(events[0].status, EventStatus.REVERSED)

    def test_cancel_order_hooks_commission(self):
        quote = self._accepted_quote(total="8000.00")
        order = self._order_for(quote)
        events = provision_commission(quote=quote, sales_order=order, actor=self.user)
        change_order_status(
            order=order,
            new_status=SalesOrderStatus.CANCELLED,
            actor=self.user,
            reason="Cliente desistiu",
        )
        events[0].refresh_from_db()
        self.assertEqual(events[0].status, EventStatus.REVERSED)

    def test_no_policy_and_simulator_and_csv(self):
        CommissionPolicy.objects.all().update(is_active=False)
        quote = self._accepted_quote(total="1000.00")
        created = provision_commission(quote=quote, actor=self.user)
        self.assertEqual(created, [])
        sim = simulate_commission(value=Decimal("10000"), trigger_type="quote_accepted")
        self.assertFalse(sim["eligible"])
        CommissionPolicy.objects.filter(pk=self.policy.pk).update(is_active=True)
        sim2 = simulate_commission(
            value=Decimal("10000"),
            trigger_type="quote_accepted",
            target="salesperson",
        )
        self.assertTrue(sim2["eligible"])
        self.assertEqual(sim2["amount"], Decimal("200.00"))
        self.assertEqual(sanitize_csv_cell("=1+1"), "'=1+1")
        self.assertEqual(sanitize_csv_cell(Decimal("10.5")), "10.5")

    def test_rbac_scope_dashboard_and_my_commissions(self):
        quote = self._accepted_quote(total="10000.00")
        provision_commission(quote=quote, actor=self.user)
        self.client.force_login(self.seller_user)
        resp = self.client.get(reverse("my_commissions"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "COM-")
        resp_dash = self.client.get(reverse("commissions:dashboard"))
        self.assertEqual(resp_dash.status_code, 403)
        self.client.force_login(self.user)
        resp2 = self.client.get(reverse("commissions:dashboard"))
        self.assertEqual(resp2.status_code, 200)
        resp3 = self.client.get(reverse("commissions:simulator"))
        self.assertEqual(resp3.status_code, 200)

    def test_seed_commands_and_manual_reverse(self):
        call_command("setup_erp_foundation", stdout=StringIO())
        self.assertTrue(AccessPermission.objects.filter(code="commission_policies.view").exists())
        self.assertTrue(
            FinancialCategory.objects.filter(code="comissoes-comerciais").exists(),
        )
        self.assertFalse(CommissionPolicy.objects.filter(name__icontains="fict").exists())
        quote = self._accepted_quote(total="10000.00")
        events = provision_commission(quote=quote, actor=self.user)
        reverse_commission_event(
            event=events[0],
            actor=self.user,
            reason="Correção manual",
        )
        events[0].refresh_from_db()
        self.assertEqual(events[0].status, EventStatus.REVERSED)
        dry = StringIO()
        call_command("process_commissions", "--dry-run", stdout=dry)
        self.assertIn("Dry-run", dry.getvalue())
        audit = StringIO()
        call_command("audit_commission_consistency", "--dry-run", stdout=audit)
        self.assertTrue(audit.getvalue())

    def test_release_idempotent_direct(self):
        quote = self._accepted_quote(total="10000.00")
        order = self._order_for(quote)
        provision_commission(quote=quote, sales_order=order, actor=self.user)
        recv = generate_receivable_from_order(
            sales_order=order,
            payment_term=self.term,
            actor=self.user,
            category=FinancialCategory.objects.get(code="venda-de-pecas"),
        )
        inst = recv.installments.first()
        payment = register_receivable_payment(
            installment=inst,
            amount=Decimal("10000.00"),
            payment_date=timezone.localdate(),
            actor=self.user,
            payment_method=self.method,
            financial_account=self.account,
        )
        again = release_commission_for_receivable_payment(payment=payment, actor=self.user)
        self.assertEqual(again, [])
