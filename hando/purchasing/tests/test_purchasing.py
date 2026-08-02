# ruff: noqa: PT009, S106
from datetime import timedelta
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import Client
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from access_control.models import AccessPermission
from access_control.models import AccessRole
from access_control.models import DataScope
from access_control.models import UserAccess
from access_control.permissions import PERMISSIONS
from finance.models import CategoryType
from finance.models import CostCenter
from finance.models import FinancialCategory
from materials.models import Material
from materials.models import MaterialCategory
from materials.models import MaterialSlab
from materials.models import Unit
from materials.stock_models import MaterialSupplier
from materials.stock_models import StockLocation
from materials.stock_models import StockMovement
from purchasing.export import sanitize_csv_cell
from purchasing.models import ItemType
from purchasing.models import PurchaseOrder
from purchasing.models import PurchaseReceipt
from purchasing.models import ReceiptCondition
from purchasing.models import RequestStatus
from purchasing.services.payables_integration import generate_payable_from_purchase_order
from purchasing.services.purchase_orders import approve_purchase_selection
from purchasing.services.quotations import compare_quotations
from purchasing.services.quotations import create_quotation
from purchasing.services.receiving import accept_receipt
from purchasing.services.receiving import create_and_complete_return
from purchasing.services.receiving import create_receipt
from purchasing.services.receiving import reject_receipt
from purchasing.services.requests import approve_purchase_request
from purchasing.services.requests import create_purchase_request
from purchasing.services.requests import reject_purchase_request
from purchasing.services.requests import submit_purchase_request
from purchasing.services.supplier_performance import supplier_performance


User = get_user_model()


def _sync_permissions():
    for code, name, module, action in PERMISSIONS:
        AccessPermission.objects.update_or_create(
            code=code,
            defaults={"name": name, "module": module, "action": action, "is_active": True},
        )


class PurchasingTests(TestCase):
    def setUp(self):
        _sync_permissions()
        role = AccessRole.objects.create(
            name="Administrativo",
            slug="admin-pur",
            hierarchy_level=1,
            has_full_access=True,
            customer_scope=DataScope.ALL,
            quote_scope=DataScope.ALL,
        )
        self.user = User.objects.create_user("puradmin", password="pass")
        UserAccess.objects.create(user=self.user, role=role)
        self.supplier = MaterialSupplier.objects.create(name="Fornecedor Pedras")
        self.supplier2 = MaterialSupplier.objects.create(name="Fornecedor B")
        cat = MaterialCategory.objects.create(name="Granito", slug="granito-pur")
        self.material = Material.objects.create(
            code="MAT-PUR-1",
            name="Granito Preto",
            category=cat,
            unit=Unit.SHEET,
            is_stock_controlled=True,
        )
        self.location = StockLocation.objects.create(name="Galpão", code="GAL-PUR")
        self.cost_center = CostCenter.objects.create(name="Produção", code="producao-pur")
        FinancialCategory.objects.create(
            name="Compra de material",
            code="compra-de-material",
            category_type=CategoryType.EXPENSE,
        )
        self.client = Client()

    def _create_approved_request(self, item_type=ItemType.SLAB):
        pr = create_purchase_request(
            data={
                "request_type": "slab",
                "priority": "high",
                "justification": "Necessidade de chapa para produção",
                "cost_center": self.cost_center,
                "source_type": "manual",
            },
            items=[
                {
                    "item_type": item_type,
                    "material": self.material,
                    "description": "Chapa granito 2x1",
                    "quantity": Decimal("2"),
                    "unit": "un",
                    "estimated_unit_cost": Decimal("500.00"),
                    "technical_specification": "Espessura 20mm",
                },
            ],
            actor=self.user,
        )
        submit_purchase_request(purchase_request=pr, actor=self.user)
        approve_purchase_request(purchase_request=pr, actor=self.user)
        return pr

    def test_request_numbering_submit_approve_reject(self):
        pr = create_purchase_request(
            data={"justification": "Teste", "source_type": "manual"},
            items=[
                {
                    "item_type": ItemType.MATERIAL,
                    "description": "Insumo X",
                    "quantity": Decimal("1"),
                    "unit": "un",
                    "technical_specification": "Spec",
                },
            ],
            actor=self.user,
        )
        self.assertTrue(pr.number.startswith("SC-"))
        submit_purchase_request(purchase_request=pr, actor=self.user)
        pr.refresh_from_db()
        self.assertEqual(pr.status, RequestStatus.SUBMITTED)
        approve_purchase_request(purchase_request=pr, actor=self.user)
        pr.refresh_from_db()
        self.assertEqual(pr.status, RequestStatus.APPROVED)
        pr2 = create_purchase_request(
            data={"justification": "Rejeitar", "source_type": "manual"},
            items=[
                {
                    "item_type": ItemType.OTHER,
                    "description": "Item",
                    "quantity": Decimal("1"),
                    "technical_specification": "x",
                },
            ],
            actor=self.user,
        )
        submit_purchase_request(purchase_request=pr2, actor=self.user)
        with self.assertRaises(ValidationError):
            reject_purchase_request(purchase_request=pr2, actor=self.user, reason="")
        reject_purchase_request(purchase_request=pr2, actor=self.user, reason="Sem necessidade")
        pr2.refresh_from_db()
        self.assertEqual(pr2.status, RequestStatus.REJECTED)

    def test_quotations_compare_selection_order_and_duplicate(self):
        pr = self._create_approved_request()
        req_item = pr.items.first()
        q1 = create_quotation(
            purchase_request=pr,
            supplier=self.supplier,
            data={"quotation_date": timezone.localdate(), "delivery_days": 5, "freight_amount": Decimal("50")},
            items=[
                {
                    "request_item": req_item,
                    "description": req_item.description,
                    "quantity": Decimal("2"),
                    "unit_price": Decimal("400.00"),
                },
            ],
            actor=self.user,
        )
        q2 = create_quotation(
            purchase_request=pr,
            supplier=self.supplier2,
            data={"quotation_date": timezone.localdate(), "delivery_days": 10},
            items=[
                {
                    "request_item": req_item,
                    "description": req_item.description,
                    "quantity": Decimal("2"),
                    "unit_price": Decimal("350.00"),
                },
            ],
            actor=self.user,
        )
        self.assertTrue(q1.number.startswith("COT-"))
        comparison = compare_quotations(purchase_request=pr)
        self.assertEqual(len(comparison["rows"][0]["offers"]), 2)
        # seleção do mais caro exige justificativa
        with self.assertRaises(ValidationError):
            approve_purchase_selection(
                purchase_request=pr,
                selections=[q1.items.first().pk],
                actor=self.user,
                justification="",
            )
        orders = approve_purchase_selection(
            purchase_request=pr,
            selections=[q2.items.first().pk],
            actor=self.user,
        )
        self.assertEqual(len(orders), 1)
        self.assertTrue(orders[0].number.startswith("PC-"))
        with self.assertRaises(ValidationError):
            approve_purchase_selection(
                purchase_request=pr,
                selections=[q2.items.first().pk],
                actor=self.user,
            )

    def test_receipt_partial_total_excess_slab_reject_return_payable(self):
        pr = self._create_approved_request()
        req_item = pr.items.first()
        q = create_quotation(
            purchase_request=pr,
            supplier=self.supplier,
            data={"quotation_date": timezone.localdate(), "delivery_days": 2},
            items=[
                {
                    "request_item": req_item,
                    "description": req_item.description,
                    "quantity": Decimal("2"),
                    "unit_price": Decimal("500.00"),
                },
            ],
            actor=self.user,
        )
        order = approve_purchase_selection(
            purchase_request=pr,
            selections=[q.items.first().pk],
            actor=self.user,
        )[0]
        order.delivery_location = self.location
        order.save(update_fields=["delivery_location"])
        poi = order.items.first()

        # excesso bloqueado
        with self.assertRaises(ValidationError):
            create_receipt(
                purchase_order=order,
                items=[
                    {
                        "purchase_order_item": poi,
                        "received_quantity": Decimal("3"),
                        "accepted_quantity": Decimal("3"),
                    },
                ],
                actor=self.user,
            )

        # parcial
        r1 = create_receipt(
            purchase_order=order,
            items=[
                {
                    "purchase_order_item": poi,
                    "received_quantity": Decimal("1"),
                    "accepted_quantity": Decimal("1"),
                    "width": Decimal("2000"),
                    "height": Decimal("1000"),
                    "thickness": Decimal("20"),
                    "actual_unit_cost": Decimal("500.00"),
                },
            ],
            actor=self.user,
            data={"stock_location": self.location},
        )
        accept_receipt(receipt=r1, actor=self.user)
        self.assertEqual(MaterialSlab.objects.count(), 1)
        self.assertTrue(StockMovement.objects.filter(movement_type="entry").exists())
        order.refresh_from_db()
        self.assertEqual(order.status, "partially_received")

        # rejeição sem estoque
        r_bad = create_receipt(
            purchase_order=order,
            items=[
                {
                    "purchase_order_item": poi,
                    "received_quantity": Decimal("1"),
                    "accepted_quantity": Decimal("0"),
                    "rejected_quantity": Decimal("1"),
                    "condition": ReceiptCondition.DAMAGED,
                    "divergence_notes": "Quebrada",
                    "width": Decimal("2000"),
                    "height": Decimal("1000"),
                    "thickness": Decimal("20"),
                },
            ],
            actor=self.user,
            data={"stock_location": self.location},
        )
        reject_receipt(receipt=r_bad, actor=self.user, reason="Recusar lote")
        self.assertEqual(MaterialSlab.objects.count(), 1)

        # total restante aceito
        r2 = create_receipt(
            purchase_order=order,
            items=[
                {
                    "purchase_order_item": poi,
                    "received_quantity": Decimal("1"),
                    "accepted_quantity": Decimal("1"),
                    "width": Decimal("2000"),
                    "height": Decimal("1000"),
                    "thickness": Decimal("20"),
                    "actual_unit_cost": Decimal("500.00"),
                    "condition": ReceiptCondition.WRONG_DIMENSION,
                    "divergence_notes": "Medida fora",
                },
            ],
            actor=self.user,
            data={"stock_location": self.location},
        )
        accept_receipt(receipt=r2, actor=self.user)
        self.assertEqual(MaterialSlab.objects.count(), 2)
        self.assertTrue(r2.divergences.exists())
        order.refresh_from_db()
        self.assertEqual(order.status, "received")

        payable = generate_payable_from_purchase_order(
            purchase_order=order,
            actor=self.user,
            due_date=timezone.localdate() + timedelta(days=30),
        )
        self.assertTrue(payable.number.startswith("PAG-"))
        with self.assertRaises(ValidationError):
            generate_payable_from_purchase_order(
                purchase_order=order,
                actor=self.user,
                due_date=timezone.localdate(),
            )

        slab = MaterialSlab.objects.first()
        ret = create_and_complete_return(
            supplier=self.supplier,
            receipt=r1,
            items=[
                {
                    "receipt_item": r1.items.first(),
                    "quantity": Decimal("1"),
                    "slab": slab,
                },
            ],
            actor=self.user,
            reason="Devolução por avaria posterior",
        )
        self.assertTrue(ret.number.startswith("DEV-"))
        slab.refresh_from_db()
        self.assertEqual(slab.status, MaterialSlab.Status.DISCARDED)

        perf = supplier_performance(supplier=self.supplier)
        self.assertGreaterEqual(perf["orders"], 1)
        self.assertEqual(sanitize_csv_cell("=1+1"), "'=1+1")

    def test_dashboard_seed_commands_rbac(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse("purchasing:dashboard"))
        self.assertEqual(resp.status_code, 200)
        out = StringIO()
        call_command("setup_erp_foundation", stdout=out)
        self.assertIn("Fundação ERP", out.getvalue())
        out2 = StringIO()
        call_command("audit_purchasing_consistency", "--dry-run", stdout=out2)
        self.assertIn("Auditoria compras", out2.getvalue())
        out3 = StringIO()
        call_command("sync_purchase_delays", "--dry-run", stdout=out3)
        self.assertIn("Dry-run", out3.getvalue())
        # ausência de dados não quebra
        self.assertFalse(PurchaseOrder.objects.exists() or False)
        self.assertEqual(PurchaseReceipt.objects.count(), 0)
