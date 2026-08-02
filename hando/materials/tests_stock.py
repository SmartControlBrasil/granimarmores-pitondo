# ruff: noqa: PT009, S106
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from access_control.models import AccessPermission
from access_control.models import AccessRole
from access_control.models import DataScope
from access_control.models import RolePermission
from access_control.models import UserAccess
from customers.models import Customer
from materials.models import Material
from materials.models import MaterialCategory
from materials.models import MaterialSlab
from materials.services.stock_operations import block_slab
from materials.services.stock_operations import consume_slab_reservation
from materials.services.stock_operations import next_slab_code
from materials.services.stock_operations import receive_slab
from materials.services.stock_operations import register_slab_loss
from materials.services.stock_operations import release_slab_reservation
from materials.services.stock_operations import reserve_slab_for_piece
from materials.services.stock_operations import transfer_slab
from materials.stock_models import MaterialSupplier
from materials.stock_models import SlabSequence
from materials.stock_models import StockLocation
from materials.stock_models import StockMovement
from production.models import ProductionStage
from production.services.piece_workflow import complete_stage
from production.services.piece_workflow import start_stage
from production.services.work_orders import create_production_order
from production.services.work_orders import generate_piece_stages
from production.services.work_orders import generate_pieces_from_order
from quotes.models import Quote
from quotes.models import QuoteItem
from quotes.models import QuoteStatus
from quotes.services.acceptance import accept_quote
from salespeople.models import Salesperson


User = get_user_model()


class StockFoundationMixin:
    _quote_counter = 0

    def setUp(self):
        StockFoundationMixin._quote_counter += 1
        suffix = StockFoundationMixin._quote_counter
        role = AccessRole.objects.create(
            name="Administrativo",
            slug="administrativo-stock",
            hierarchy_level=1,
            has_full_access=True,
            customer_scope=DataScope.ALL,
            quote_scope=DataScope.ALL,
            asset_scope=DataScope.ALL,
            maintenance_scope=DataScope.ALL,
        )
        self.user = User.objects.create_user("stockadmin", password="pass")
        UserAccess.objects.create(user=self.user, role=role)
        for code in [
            "slabs.create",
            "slabs.view",
            "slabs.transfer",
            "slabs.block",
            "slabs.unblock",
            "slab_reservations.reserve",
            "slab_reservations.release",
            "slab_consumption.consume",
            "slab_losses.create",
            "stock_adjustments.execute",
            "stock_costs.view",
            "production_stages.start",
            "production_stages.complete",
            "slab_reservations.override_cut",
        ]:
            perm, _ = AccessPermission.objects.get_or_create(
                code=code,
                defaults={"name": code, "module": code.split(".")[0], "action": code.split(".")[1]},
            )
            RolePermission.objects.get_or_create(role=role, permission=perm, defaults={"allowed": True})

        self.category = MaterialCategory.objects.create(name="Granito", slug="granito-stock")
        self.material = Material.objects.create(
            code="GR-ST",
            name="Granito Stock",
            category=self.category,
            thickness_mm=Decimal("20.00"),
            is_stock_controlled=True,
        )
        self.supplier = MaterialSupplier.objects.create(name="Fornecedor Teste")
        self.location = StockLocation.objects.create(code="GAL-01", name="Galpão Teste")
        self.location_b = StockLocation.objects.create(code="GAL-02", name="Galpão B")
        self.salesperson = Salesperson.objects.create(code="VS", display_name="Vendedor Stock")
        self.customer = Customer.objects.create(
            name="Cliente Stock",
            customer_type="person",
        )
        self.quote = Quote.objects.create(
            number=f"ORC-ST-{suffix:03d}",
            customer=self.customer,
            salesperson=self.salesperson,
            status=QuoteStatus.SENT,
            subtotal=Decimal("1000.00"),
            grand_total=Decimal("1000.00"),
            valid_until=timezone.localdate() + timezone.timedelta(days=10),
            created_by=self.user,
        )
        QuoteItem.objects.create(
            quote=self.quote,
            description="Bancada",
            quantity=Decimal("1"),
            unit_price=Decimal("1000.00"),
            subtotal=Decimal("1000.00"),
        )
        ProductionStage.objects.create(name="Corte", slug="corte", display_order=1, is_active=True)


class StockOperationsTests(StockFoundationMixin, TestCase):
    def test_receive_slab_and_numbering(self):
        slab = receive_slab(
            material=self.material,
            width=Decimal("3000"),
            height=Decimal("2000"),
            thickness=Decimal("20"),
            supplier=self.supplier,
            location=self.location,
            cost_value=Decimal("1000.00"),
            actor=self.user,
        )
        self.assertTrue(slab.slab_code.startswith("CHP-"))
        self.assertEqual(slab.total_area, Decimal("6.0000"))
        self.assertEqual(slab.available_area, Decimal("6.0000"))
        self.assertEqual(StockMovement.objects.filter(slab=slab).count(), 1)
        code2 = next_slab_code()
        self.assertNotEqual(slab.slab_code, code2)

    def test_transfer_and_block(self):
        slab = receive_slab(
            material=self.material,
            width=Decimal("1000"),
            height=Decimal("1000"),
            thickness=Decimal("20"),
            supplier=self.supplier,
            location=self.location,
            cost_value=Decimal("100.00"),
            actor=self.user,
        )
        transfer_slab(slab=slab, destination=self.location_b, actor=self.user)
        slab.refresh_from_db()
        self.assertEqual(slab.stock_location_id, self.location_b.pk)
        block_slab(slab=slab, reason="Defeito", actor=self.user)
        slab.refresh_from_db()
        self.assertEqual(slab.status, MaterialSlab.Status.BLOCKED)

    def test_reservation_consume_and_release(self):
        slab = receive_slab(
            material=self.material,
            width=Decimal("3000"),
            height=Decimal("2000"),
            thickness=Decimal("20"),
            supplier=self.supplier,
            location=self.location,
            cost_value=Decimal("1000.00"),
            actor=self.user,
        )
        piece = self._make_piece()
        reservation = reserve_slab_for_piece(
            slab=slab,
            production_piece=piece,
            reserved_area=Decimal("2.0000"),
            actor=self.user,
        )
        slab.refresh_from_db()
        self.assertEqual(slab.available_area, Decimal("4.0000"))
        with self.assertRaises(ValidationError):
            reserve_slab_for_piece(
                slab=slab,
                production_piece=piece,
                reserved_area=Decimal("1.0000"),
                actor=self.user,
            )
        consume_slab_reservation(
            reservation=reservation,
            consumed_area=Decimal("1.5000"),
            lost_area=Decimal("0.1000"),
            actor=self.user,
        )
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, reservation.Status.PARTIALLY_CONSUMED)
        release_slab_reservation(reservation=reservation, actor=self.user)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, reservation.Status.RELEASED)

    def test_loss_blocks_negative(self):
        slab = receive_slab(
            material=self.material,
            width=Decimal("1000"),
            height=Decimal("1000"),
            thickness=Decimal("20"),
            supplier=self.supplier,
            location=self.location,
            cost_value=Decimal("50.00"),
            actor=self.user,
        )
        with self.assertRaises(ValidationError):
            register_slab_loss(
                slab=slab,
                area=Decimal("99.0000"),
                loss_reason="breakage",
                actor=self.user,
            )

    def test_movement_immutable(self):
        slab = receive_slab(
            material=self.material,
            width=Decimal("1000"),
            height=Decimal("1000"),
            thickness=Decimal("20"),
            supplier=self.supplier,
            location=self.location,
            cost_value=Decimal("50.00"),
            actor=self.user,
        )
        movement = StockMovement.objects.get(slab=slab)
        with self.assertRaises(ValueError):
            movement.description = "alterado"
            movement.save()

    def test_cut_requires_reservation(self):
        piece = self._make_piece()
        generate_piece_stages(piece=piece, actor=self.user)
        stage = piece.stages.first()
        with self.assertRaises(ValidationError):
            start_stage(piece_stage=stage, actor=self.user)

    def test_cut_complete_requires_consumption(self):
        slab = receive_slab(
            material=self.material,
            width=Decimal("3000"),
            height=Decimal("2000"),
            thickness=Decimal("20"),
            supplier=self.supplier,
            location=self.location,
            cost_value=Decimal("1000.00"),
            actor=self.user,
        )
        piece = self._make_piece()
        generate_piece_stages(piece=piece, actor=self.user)
        reserve_slab_for_piece(
            slab=slab,
            production_piece=piece,
            reserved_area=Decimal("1.0000"),
            actor=self.user,
        )
        stage = piece.stages.first()
        start_stage(piece_stage=stage, actor=self.user)
        with self.assertRaises(ValidationError):
            complete_stage(piece_stage=stage, actor=self.user)

    def test_cost_per_m2_zero_area_safe(self):
        slab = MaterialSlab(
            material=self.material,
            slab_code="TMP",
            width_mm=Decimal("0"),
            height_mm=Decimal("0"),
            total_area=Decimal("0"),
        )
        self.assertEqual(slab.cost_per_m2(), Decimal("0.00"))

    def _make_piece(self):
        order = accept_quote(quote=self.quote, actor=self.user)
        production = create_production_order(sales_order=order, actor=self.user)
        if production.pieces.exists():
            piece = production.pieces.first()
        else:
            piece = generate_pieces_from_order(production_order=production, actor=self.user)[0]
        piece.material = self.material
        piece.save(update_fields=["material", "updated_at"])
        return piece
