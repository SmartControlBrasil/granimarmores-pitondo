# ruff: noqa: EM101, TRY003
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.db import transaction

from access_control.services.authorization import user_has_permission
from audit.services import record_audit_event
from production.models import SalesOrderStatus
from production.models import TERMINAL_ORDER_STATUSES
from production.services.logging import add_production_log
from production.models import ProductionLogType


ORDER_TRANSITIONS = {
    SalesOrderStatus.DRAFT: {SalesOrderStatus.CONFIRMED, SalesOrderStatus.CANCELLED},
    SalesOrderStatus.CONFIRMED: {
        SalesOrderStatus.TECHNICAL_REVIEW,
        SalesOrderStatus.ON_HOLD,
        SalesOrderStatus.CANCELLED,
    },
    SalesOrderStatus.TECHNICAL_REVIEW: {
        SalesOrderStatus.AWAITING_MEASUREMENT,
        SalesOrderStatus.READY_FOR_PRODUCTION,
        SalesOrderStatus.ON_HOLD,
        SalesOrderStatus.CANCELLED,
    },
    SalesOrderStatus.AWAITING_MEASUREMENT: {
        SalesOrderStatus.READY_FOR_PRODUCTION,
        SalesOrderStatus.ON_HOLD,
        SalesOrderStatus.CANCELLED,
    },
    SalesOrderStatus.READY_FOR_PRODUCTION: {
        SalesOrderStatus.IN_PRODUCTION,
        SalesOrderStatus.ON_HOLD,
        SalesOrderStatus.CANCELLED,
    },
    SalesOrderStatus.IN_PRODUCTION: {
        SalesOrderStatus.QUALITY_CONTROL,
        SalesOrderStatus.ON_HOLD,
        SalesOrderStatus.CANCELLED,
    },
    SalesOrderStatus.QUALITY_CONTROL: {
        SalesOrderStatus.READY_FOR_DELIVERY,
        SalesOrderStatus.ON_HOLD,
        SalesOrderStatus.CANCELLED,
    },
    SalesOrderStatus.READY_FOR_DELIVERY: {
        SalesOrderStatus.SCHEDULED,
        SalesOrderStatus.ON_HOLD,
        SalesOrderStatus.CANCELLED,
    },
    SalesOrderStatus.SCHEDULED: {
        SalesOrderStatus.DELIVERED,
        SalesOrderStatus.ON_HOLD,
        SalesOrderStatus.CANCELLED,
    },
    SalesOrderStatus.DELIVERED: {
        SalesOrderStatus.INSTALLED,
        SalesOrderStatus.COMPLETED,
        SalesOrderStatus.ON_HOLD,
        SalesOrderStatus.CANCELLED,
    },
    SalesOrderStatus.INSTALLED: {
        SalesOrderStatus.COMPLETED,
        SalesOrderStatus.ON_HOLD,
        SalesOrderStatus.CANCELLED,
    },
}

OPERATIONAL_STATUSES = set(ORDER_TRANSITIONS.keys()) - {
    SalesOrderStatus.DRAFT,
}


def _validate_transition(order, new_status):
    if order.status in TERMINAL_ORDER_STATUSES:
        raise ValidationError("Pedido encerrado não permite alteração de status.")
    if new_status == SalesOrderStatus.ON_HOLD:
        return
    if order.status == SalesOrderStatus.ON_HOLD:
        if new_status == order.previous_status:
            return
        allowed = ORDER_TRANSITIONS.get(order.previous_status or SalesOrderStatus.CONFIRMED, set())
        if new_status not in allowed:
            raise ValidationError("Transição de retomada inválida.")
        return
    allowed = ORDER_TRANSITIONS.get(order.status, set())
    if new_status not in allowed:
        raise ValidationError(
            f"Transição inválida: {order.get_status_display()} → "
            f"{dict(SalesOrderStatus.choices).get(new_status, new_status)}.",
        )


@transaction.atomic
def change_order_status(*, order, new_status, actor, reason="", request=None):
    if not user_has_permission(actor, "sales_orders.change_status"):
        raise PermissionDenied("Sem permissão para alterar status do pedido.")

    new_status = SalesOrderStatus(new_status)
    _validate_transition(order, new_status)

    if new_status == SalesOrderStatus.ON_HOLD:
        return hold_order(order=order, actor=actor, reason=reason, request=request)
    if new_status == SalesOrderStatus.CANCELLED:
        return cancel_order(order=order, actor=actor, reason=reason, request=request)

    old_status = order.status
    if order.status == SalesOrderStatus.ON_HOLD and new_status != order.previous_status:
        order.status = new_status
        order.previous_status = ""
        order.hold_reason = ""
    elif order.status == SalesOrderStatus.ON_HOLD:
        order.status = new_status
        order.previous_status = ""
        order.hold_reason = ""
    else:
        order.status = new_status

    order.updated_by = actor
    order.save(update_fields=["status", "previous_status", "hold_reason", "updated_by", "updated_at"])

    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="production",
        action="sales_order_status_changed",
        obj=order,
        metadata={"from": old_status, "to": new_status, "reason": reason[:500]},
    )
    return order


@transaction.atomic
def hold_order(*, order, actor, reason, request=None):
    if not reason.strip():
        raise ValidationError("Motivo obrigatório para colocar pedido em espera.")
    if order.status == SalesOrderStatus.ON_HOLD:
        raise ValidationError("Pedido já está em espera.")
    if order.status in TERMINAL_ORDER_STATUSES:
        raise ValidationError("Pedido encerrado não pode ser pausado.")

    order.previous_status = order.status
    order.status = SalesOrderStatus.ON_HOLD
    order.hold_reason = reason.strip()
    order.updated_by = actor
    order.save(update_fields=[
        "status",
        "previous_status",
        "hold_reason",
        "updated_by",
        "updated_at",
    ])

    if hasattr(order, "production_order"):
        from production.services.work_orders import pause_production_order

        production = getattr(order, "production_order", None)
        if production and production.status not in {"completed", "cancelled"}:
            pause_production_order(
                production_order=production,
                actor=actor,
                reason=reason,
                request=request,
            )

    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="production",
        action="sales_order_on_hold",
        obj=order,
        metadata={"reason": reason[:500]},
    )
    return order


@transaction.atomic
def cancel_order(*, order, actor, reason, request=None):
    if not user_has_permission(actor, "sales_orders.cancel"):
        raise PermissionDenied("Sem permissão para cancelar pedido.")
    if not reason.strip():
        raise ValidationError("Motivo obrigatório para cancelamento.")
    if order.status in TERMINAL_ORDER_STATUSES:
        raise ValidationError("Pedido já encerrado.")

    if order.status == SalesOrderStatus.IN_PRODUCTION:
        raise ValidationError("Pedido em produção exige encerramento operacional antes do cancelamento.")

    old_status = order.status
    order.status = SalesOrderStatus.CANCELLED
    order.cancel_reason = reason.strip()
    order.updated_by = actor
    order.save(update_fields=["status", "cancel_reason", "updated_by", "updated_at"])

    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="production",
        action="sales_order_cancelled",
        obj=order,
        metadata={"from": old_status, "reason": reason[:500]},
    )
    return order
