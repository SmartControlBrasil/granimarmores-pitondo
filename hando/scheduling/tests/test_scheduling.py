# ruff: noqa: PT009, S106
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from io import StringIO

from access_control.models import AccessPermission
from access_control.models import AccessRole
from access_control.models import DataScope
from access_control.models import RolePermission
from access_control.models import UserAccess
from customers.models import Customer
from fleet.models import Vehicle
from production.models import DeliverySchedule
from production.models import SalesOrder
from production.models import ScheduleStatus
from salespeople.models import Salesperson
from scheduling.models import EventStatus
from scheduling.models import EventType
from scheduling.models import HistoryAction
from scheduling.models import OperationalEvent
from scheduling.models import OperationalEventHistory
from scheduling.services.conflicts import check_schedule_conflicts
from scheduling.services.events import cancel_event
from scheduling.services.events import complete_event
from scheduling.services.events import confirm_event
from scheduling.services.events import create_operational_event
from scheduling.services.events import reschedule_event
from scheduling.services.events import start_event
from scheduling.services.events import sync_event_from_delivery
from scheduling.services.numbering import next_event_code


User = get_user_model()


class ScheduleTestMixin:
    def setUp(self):
        role = AccessRole.objects.create(
            name="Administrativo",
            slug="admin-agenda",
            hierarchy_level=1,
            has_full_access=True,
            customer_scope=DataScope.ALL,
            quote_scope=DataScope.ALL,
        )
        self.user = User.objects.create_user("agendaadmin", password="pass")
        UserAccess.objects.create(user=self.user, role=role)
        for code in [
            "operational_events.create",
            "operational_events.view",
            "operational_events.view_all",
            "operational_events.confirm",
            "operational_events.start",
            "operational_events.complete",
            "operational_events.reschedule",
            "operational_events.cancel",
            "operational_events.override_conflict",
            "schedule_dashboard.view",
            "schedule_calendar.view",
            "schedule_measurements.view",
        ]:
            perm, _ = AccessPermission.objects.get_or_create(
                code=code,
                defaults={
                    "name": code,
                    "module": code.split(".")[0],
                    "action": code.split(".")[1],
                },
            )
            RolePermission.objects.get_or_create(
                role=role,
                permission=perm,
                defaults={"allowed": True},
            )
        self.customer = Customer.objects.create(
            customer_type="individual",
            name="Cliente Agenda",
        )
        self.salesperson = Salesperson.objects.create(code="VA", display_name="Vendedor Agenda")
        self.other_user = User.objects.create_user("outro", password="pass")
        self.vehicle = Vehicle.objects.create(
            asset_code="VH-AG-01",
            plate="ABC1D23",
            brand="VW",
            model="Delivery",
        )

    def _start_end(self, hours=1, offset_hours=1):
        start = timezone.now() + timedelta(hours=offset_hours)
        end = start + timedelta(hours=hours)
        return start, end


class OperationalEventTests(ScheduleTestMixin, TestCase):
    def test_create_and_numbering(self):
        start, end = self._start_end()
        event = create_operational_event(
            actor=self.user,
            title="Reunião",
            event_type=EventType.CUSTOMER_MEETING,
            start_at=start,
            end_at=end,
            assigned_user=self.user,
            customer=self.customer,
            city="Joinville",
            address="Rua A",
        )
        self.assertTrue(event.code.startswith("AGE-"))
        code2 = next_event_code()
        self.assertNotEqual(event.code, code2)
        self.assertTrue(
            OperationalEventHistory.objects.filter(
                event=event,
                action=HistoryAction.CREATED,
            ).exists(),
        )

    def test_invalid_dates(self):
        start, end = self._start_end()
        with self.assertRaises(ValidationError):
            create_operational_event(
                actor=self.user,
                title="Inválido",
                event_type=EventType.INTERNAL_MEETING,
                start_at=end,
                end_at=start,
                assigned_user=self.user,
            )

    def test_inactive_user_rejected(self):
        inactive = User.objects.create_user("inativo", password="pass", is_active=False)
        start, end = self._start_end()
        with self.assertRaises(ValidationError):
            create_operational_event(
                actor=self.user,
                title="X",
                event_type=EventType.INTERNAL_MEETING,
                start_at=start,
                end_at=end,
                assigned_user=inactive,
            )

    def test_user_conflict_and_override(self):
        start, end = self._start_end()
        create_operational_event(
            actor=self.user,
            title="A",
            event_type=EventType.INTERNAL_MEETING,
            start_at=start,
            end_at=end,
            assigned_user=self.user,
        )
        with self.assertRaises(ValidationError):
            create_operational_event(
                actor=self.user,
                title="B",
                event_type=EventType.INTERNAL_MEETING,
                start_at=start + timedelta(minutes=30),
                end_at=end + timedelta(minutes=30),
                assigned_user=self.user,
            )
        event = create_operational_event(
            actor=self.user,
            title="C",
            event_type=EventType.INTERNAL_MEETING,
            start_at=start + timedelta(minutes=30),
            end_at=end + timedelta(minutes=30),
            assigned_user=self.user,
            override_conflicts=True,
            override_reason="Prioridade comercial",
        )
        self.assertTrue(
            OperationalEventHistory.objects.filter(
                event=event,
                action=HistoryAction.CONFLICT_OVERRIDDEN,
            ).exists(),
        )

    def test_cancelled_does_not_conflict(self):
        start, end = self._start_end()
        event = create_operational_event(
            actor=self.user,
            title="A",
            event_type=EventType.INTERNAL_MEETING,
            start_at=start,
            end_at=end,
            assigned_user=self.user,
        )
        cancel_event(event=event, actor=self.user, reason="Cliente pediu")
        create_operational_event(
            actor=self.user,
            title="B",
            event_type=EventType.INTERNAL_MEETING,
            start_at=start,
            end_at=end,
            assigned_user=self.user,
        )

    def test_vehicle_conflict(self):
        start, end = self._start_end()
        create_operational_event(
            actor=self.user,
            title="Entrega 1",
            event_type=EventType.DELIVERY,
            start_at=start,
            end_at=end,
            assigned_user=self.user,
            vehicle=self.vehicle,
            address="Rua 1",
            city="Joinville",
        )
        conflicts = check_schedule_conflicts(
            start_at=start,
            end_at=end,
            vehicle=self.vehicle,
        )
        self.assertTrue(conflicts)

    def test_lifecycle(self):
        start, end = self._start_end()
        event = create_operational_event(
            actor=self.user,
            title="Visita",
            event_type=EventType.TECHNICAL_VISIT,
            start_at=start,
            end_at=end,
            assigned_user=self.user,
            address="Rua X",
            city="Joinville",
        )
        confirm_event(event=event, actor=self.user)
        event.refresh_from_db()
        self.assertEqual(event.status, EventStatus.CONFIRMED)
        start_event(event=event, actor=self.user)
        event.refresh_from_db()
        self.assertEqual(event.status, EventStatus.IN_PROGRESS)
        complete_event(event=event, actor=self.user, completion_notes="Ok")
        event.refresh_from_db()
        self.assertEqual(event.status, EventStatus.COMPLETED)

    def test_reschedule_preserves_history(self):
        start, end = self._start_end()
        event = create_operational_event(
            actor=self.user,
            title="Medição",
            event_type=EventType.MEASUREMENT,
            start_at=start,
            end_at=end,
            assigned_user=self.user,
            address="Rua Y",
            city="Joinville",
        )
        new_start = start + timedelta(days=1)
        new_end = end + timedelta(days=1)
        reschedule_event(
            event=event,
            new_start_at=new_start,
            new_end_at=new_end,
            actor=self.user,
            reason="Cliente reagendou",
        )
        hist = OperationalEventHistory.objects.filter(
            event=event,
            action=HistoryAction.RESCHEDULED,
        ).first()
        self.assertIsNotNone(hist)
        self.assertEqual(hist.old_start_at, start)

    def test_delivery_sync_idempotent(self):
        from quotes.models import Quote
        from quotes.models import QuoteStatus

        quote = Quote.objects.create(
            number="ORC-AG-001",
            customer=self.customer,
            salesperson=self.salesperson,
            status=QuoteStatus.ACCEPTED,
            subtotal=100,
            grand_total=100,
            valid_until=timezone.localdate() + timedelta(days=10),
            created_by=self.user,
        )
        order = SalesOrder.objects.create(
            number="PED-AG-001",
            quote=quote,
            customer=self.customer,
            salesperson=self.salesperson,
            delivery_required=True,
            delivery_address="Rua Z",
            delivery_city="Joinville",
            created_by=self.user,
        )
        delivery = DeliverySchedule.objects.create(
            sales_order=order,
            scheduled_date=timezone.localdate() + timedelta(days=2),
            status=ScheduleStatus.SCHEDULED,
            address="Rua Z",
            city="Joinville",
            responsible=self.user,
            created_by=self.user,
        )
        e1 = sync_event_from_delivery(delivery=delivery, actor=self.user)
        e2 = sync_event_from_delivery(delivery=delivery, actor=self.user)
        self.assertEqual(e1.pk, e2.pk)
        self.assertEqual(
            OperationalEvent.objects.filter(delivery_schedule=delivery).count(),
            1,
        )

    def test_history_immutable(self):
        start, end = self._start_end()
        event = create_operational_event(
            actor=self.user,
            title="X",
            event_type=EventType.INTERNAL_MEETING,
            start_at=start,
            end_at=end,
            assigned_user=self.user,
        )
        hist = event.history.first()
        with self.assertRaises(ValueError):
            hist.description = "alterado"
            hist.save()

    def test_timezone_aware(self):
        start, end = self._start_end()
        event = create_operational_event(
            actor=self.user,
            title="TZ",
            event_type=EventType.INTERNAL_MEETING,
            start_at=start,
            end_at=end,
            assigned_user=self.user,
        )
        self.assertTrue(timezone.is_aware(event.start_at))

    def test_audit_command_dry_run(self):
        out = StringIO()
        call_command("audit_operational_schedule", stdout=out)
        self.assertIn("Nenhuma inconsistência", out.getvalue())

    def test_calendar_list_views(self):
        self.client.force_login(self.user)
        for name in [
            "scheduling:dashboard",
            "scheduling:calendar",
            "scheduling:week",
            "scheduling:today",
            "scheduling:event_list",
            "scheduling:measurement_list",
        ]:
            from django.urls import reverse

            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200, name)
