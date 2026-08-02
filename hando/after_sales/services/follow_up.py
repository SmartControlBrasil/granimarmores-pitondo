# ruff: noqa: EM101, PLR0913, TRY003
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from access_control.services.authorization import user_has_permission
from after_sales.models import CaseType
from after_sales.models import InstallationPendingItem
from after_sales.models import PendingStatus
from after_sales.services.cases import open_after_sales_case
from audit.services import record_audit_event


@transaction.atomic
def create_installation_pending(
    *,
    actor,
    installation_schedule,
    description,
    priority="normal",
    responsible=None,
    due_date=None,
    create_case=False,
    request=None,
):
    if not user_has_permission(actor, "installation_pending_items.create"):
        raise PermissionDenied("Sem permissão para registrar pendência.")
    if not description.strip():
        raise ValidationError("Descrição obrigatória.")

    duplicate = InstallationPendingItem.objects.filter(
        installation_schedule=installation_schedule,
        description__iexact=description.strip(),
        status__in=[PendingStatus.OPEN, PendingStatus.SCHEDULED, PendingStatus.IN_PROGRESS],
    ).exists()
    if duplicate:
        raise ValidationError("Já existe pendência aberta semelhante.")

    item = InstallationPendingItem.objects.create(
        installation_schedule=installation_schedule,
        sales_order=installation_schedule.sales_order,
        description=description.strip(),
        priority=priority,
        responsible=responsible,
        due_date=due_date,
        created_by=actor,
        updated_by=actor,
    )

    case = None
    if create_case:
        case = open_after_sales_case(
            actor=actor,
            customer=installation_schedule.sales_order.customer,
            sales_order=installation_schedule.sales_order,
            installation_schedule=installation_schedule,
            subject=f"Pendência instalação — {installation_schedule.sales_order.number}",
            description=description.strip(),
            case_type=CaseType.INSTALLATION_PENDING,
            priority=priority,
            assigned_user=responsible,
            request=request,
        )
        item.after_sales_case = case
        item.save(update_fields=["after_sales_case", "updated_at"])

    record_audit_event(
        request=request,
        user=actor,
        event_type="create",
        module="after_sales",
        action="installation_pending_created",
        obj=item,
    )
    return item, case


@transaction.atomic
def resolve_installation_pending(*, item, actor, resolution, request=None):
    if not user_has_permission(actor, "installation_pending_items.update"):
        raise PermissionDenied("Sem permissão.")
    if not resolution.strip():
        raise ValidationError("Resolução obrigatória.")
    if item.status == PendingStatus.RESOLVED:
        raise ValidationError("Pendência já resolvida.")
    item.status = PendingStatus.RESOLVED
    item.resolution = resolution.strip()
    item.resolved_at = timezone.now()
    item.resolved_by = actor
    item.updated_by = actor
    item.save()
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="after_sales",
        action="installation_pending_resolved",
        obj=item,
    )
    return item
