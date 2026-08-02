# ruff: noqa: EM101, PLR0913, TRY003
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from access_control.services.authorization import user_has_permission
from audit.services import record_audit_event
from production.models import DeliverySchedule
from production.models import InstallationSchedule
from production.models import ProductionLogType
from production.models import SalesOrderStatus
from production.models import ScheduleStatus
from production.services.logging import add_production_log
from production.services.order_workflow import change_order_status


@transaction.atomic
def schedule_delivery(*, sales_order, actor, scheduled_date, request=None, **fields):
    if not user_has_permission(actor, "deliveries.schedule"):
        raise PermissionDenied("Sem permissão para agendar entrega.")
    if not sales_order.delivery_required:
        raise ValidationError("Pedido não exige entrega.")

    delivery = DeliverySchedule.objects.create(
        sales_order=sales_order,
        scheduled_date=scheduled_date,
        scheduled_time_start=fields.get("scheduled_time_start"),
        scheduled_time_end=fields.get("scheduled_time_end"),
        address=fields.get("address") or sales_order.delivery_address,
        city=fields.get("city") or sales_order.delivery_city,
        state=fields.get("state") or sales_order.delivery_state,
        postal_code=fields.get("postal_code") or sales_order.delivery_postal_code,
        responsible=fields.get("responsible"),
        vehicle=fields.get("vehicle"),
        status=ScheduleStatus.SCHEDULED,
        notes=fields.get("notes", ""),
        created_by=actor,
        updated_by=actor,
    )

    if sales_order.status == SalesOrderStatus.READY_FOR_DELIVERY:
        change_order_status(
            order=sales_order,
            new_status=SalesOrderStatus.SCHEDULED,
            actor=actor,
            request=request,
        )

    record_audit_event(
        request=request,
        user=actor,
        event_type="create",
        module="production",
        action="delivery_scheduled",
        obj=delivery,
    )
    from scheduling.services.events import sync_event_from_delivery

    sync_event_from_delivery(delivery=delivery, actor=actor, request=request)
    return delivery


@transaction.atomic
def complete_delivery(*, delivery, actor, request=None, notes=""):
    if not user_has_permission(actor, "deliveries.complete"):
        raise PermissionDenied("Sem permissão para concluir entrega.")

    now = timezone.now()
    delivery.status = ScheduleStatus.COMPLETED
    delivery.completed_at = now
    delivery.completed_by = actor
    if notes:
        delivery.notes = notes
    delivery.updated_by = actor
    delivery.save(update_fields=[
        "status",
        "completed_at",
        "completed_by",
        "notes",
        "updated_by",
        "updated_at",
    ])

    sales_order = delivery.sales_order
    if sales_order.status == SalesOrderStatus.SCHEDULED:
        change_order_status(
            order=sales_order,
            new_status=SalesOrderStatus.DELIVERED,
            actor=actor,
            request=request,
        )

    production = getattr(sales_order, "production_order", None)
    if production:
        add_production_log(
            production_order=production,
            log_type=ProductionLogType.DELIVERY,
            description=f"Entrega concluída em {delivery.scheduled_date}.",
            actor=actor,
        )

    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="production",
        action="delivery_completed",
        obj=delivery,
    )
    return delivery


@transaction.atomic
def schedule_installation(*, sales_order, actor, scheduled_date, request=None, **fields):
    if not user_has_permission(actor, "installations.schedule"):
        raise PermissionDenied("Sem permissão para agendar instalação.")
    if not sales_order.installation_required:
        raise ValidationError("Pedido não exige instalação.")

    installation = InstallationSchedule.objects.create(
        sales_order=sales_order,
        scheduled_date=scheduled_date,
        scheduled_time_start=fields.get("scheduled_time_start"),
        scheduled_time_end=fields.get("scheduled_time_end"),
        address=fields.get("address") or sales_order.delivery_address,
        city=fields.get("city") or sales_order.delivery_city,
        state=fields.get("state") or sales_order.delivery_state,
        postal_code=fields.get("postal_code") or sales_order.delivery_postal_code,
        responsible=fields.get("responsible"),
        vehicle=fields.get("vehicle"),
        status=ScheduleStatus.SCHEDULED,
        notes=fields.get("notes", ""),
        created_by=actor,
        updated_by=actor,
    )

    record_audit_event(
        request=request,
        user=actor,
        event_type="create",
        module="production",
        action="installation_scheduled",
        obj=installation,
    )
    from scheduling.services.events import sync_event_from_installation

    sync_event_from_installation(installation=installation, actor=actor, request=request)
    return installation


@transaction.atomic
def complete_installation(*, installation, actor, request=None, result_notes="", return_required=False):
    if not user_has_permission(actor, "installations.complete"):
        raise PermissionDenied("Sem permissão para concluir instalação.")

    now = timezone.now()
    installation.status = ScheduleStatus.COMPLETED
    installation.completed_at = now
    installation.completed_by = actor
    installation.result_notes = result_notes or ""
    installation.return_required = return_required
    installation.updated_by = actor
    installation.save(update_fields=[
        "status",
        "completed_at",
        "completed_by",
        "result_notes",
        "return_required",
        "updated_by",
        "updated_at",
    ])

    sales_order = installation.sales_order
    if sales_order.status in {SalesOrderStatus.DELIVERED, SalesOrderStatus.SCHEDULED}:
        change_order_status(
            order=sales_order,
            new_status=SalesOrderStatus.INSTALLED,
            actor=actor,
            request=request,
        )

    production = getattr(sales_order, "production_order", None)
    if production:
        add_production_log(
            production_order=production,
            log_type=ProductionLogType.INSTALLATION,
            description=f"Instalação concluída em {installation.scheduled_date}.",
            actor=actor,
        )

    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="production",
        action="installation_completed",
        obj=installation,
    )
    return installation
