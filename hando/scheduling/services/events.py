# ruff: noqa: EM101, PLR0913, TRY003
from datetime import datetime
from datetime import time
from datetime import timedelta

from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from access_control.services.authorization import user_has_permission
from audit.services import record_audit_event
from scheduling.models import ADDRESS_REQUIRED_TYPES
from scheduling.models import ConfirmationChannel
from scheduling.models import ConfirmationStatus
from scheduling.models import EventStatus
from scheduling.models import EventType
from scheduling.models import HistoryAction
from scheduling.models import MeasurementAppointment
from scheduling.models import MeasurementType
from scheduling.models import OPERATIONAL_EVENT_TYPES
from scheduling.models import OperationalEvent
from scheduling.models import OperationalEventHistory
from scheduling.services.conflicts import check_schedule_conflicts
from scheduling.services.numbering import next_event_code


def _ensure_aware(dt):
    if dt is None:
        return None
    if timezone.is_naive(dt):
        return timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def _add_history(
    *,
    event,
    action,
    actor,
    description="",
    old_start_at=None,
    old_end_at=None,
    new_start_at=None,
    new_end_at=None,
    old_status="",
    new_status="",
):
    return OperationalEventHistory.objects.create(
        event=event,
        action=action,
        old_start_at=old_start_at,
        old_end_at=old_end_at,
        new_start_at=new_start_at,
        new_end_at=new_end_at,
        old_status=old_status or "",
        new_status=new_status or "",
        description=description,
        actor=actor,
    )


def _validate_assignees(*, assigned_user, assigned_salesperson, event_type):
    if event_type in OPERATIONAL_EVENT_TYPES:
        if not assigned_user and not assigned_salesperson:
            raise ValidationError("Evento operacional exige responsável interno.")
    if assigned_user and not assigned_user.is_active:
        raise ValidationError("Usuário inativo não pode receber novo evento.")
    if assigned_salesperson and not assigned_salesperson.is_active:
        raise ValidationError("Vendedor inativo não pode receber novo evento.")


def _validate_address(*, event_type, address, city):
    if event_type in ADDRESS_REQUIRED_TYPES and not (address and city):
        raise ValidationError("Endereço e cidade são obrigatórios para este tipo de evento.")


def _handle_conflicts(
    *,
    start_at,
    end_at,
    assigned_user,
    assigned_salesperson,
    vehicle,
    exclude_event,
    all_day,
    actor,
    override_conflicts,
    override_reason,
):
    conflicts = check_schedule_conflicts(
        start_at=start_at,
        end_at=end_at,
        assigned_user=assigned_user,
        assigned_salesperson=assigned_salesperson,
        vehicle=vehicle,
        exclude_event=exclude_event,
        all_day=all_day,
    )
    if not conflicts:
        return []
    if not override_conflicts:
        messages = "; ".join(c["message"] for c in conflicts)
        raise ValidationError(f"Conflito de agenda: {messages}")
    if not user_has_permission(actor, "operational_events.override_conflict"):
        raise PermissionDenied("Sem permissão para override de conflito.")
    if not (override_reason or "").strip():
        raise ValidationError("Override de conflito exige justificativa.")
    return conflicts


@transaction.atomic
def create_operational_event(
    *,
    actor,
    title,
    event_type,
    start_at,
    end_at=None,
    all_day=False,
    priority="normal",
    description="",
    assigned_user=None,
    assigned_salesperson=None,
    external_responsible="",
    customer=None,
    lead=None,
    quote=None,
    sales_order=None,
    production_order=None,
    production_piece=None,
    delivery_schedule=None,
    installation_schedule=None,
    vehicle=None,
    address="",
    district="",
    city="",
    state="",
    postal_code="",
    contact_name="",
    contact_phone="",
    internal_notes="",
    status=EventStatus.SCHEDULED,
    override_conflicts=False,
    override_reason="",
    request=None,
    measurement_type=None,
    skip_conflict_check=False,
    skip_permission_check=False,
):
    if not skip_permission_check and not user_has_permission(actor, "operational_events.create"):
        raise PermissionDenied("Sem permissão para criar eventos.")

    start_at = _ensure_aware(start_at)
    end_at = _ensure_aware(end_at)
    if all_day and not end_at:
        end_at = timezone.make_aware(
            datetime.combine(timezone.localtime(start_at).date(), time(23, 59, 59)),
        )

    if not assigned_user and not assigned_salesperson and event_type in OPERATIONAL_EVENT_TYPES:
        assigned_user = actor

    _validate_assignees(
        assigned_user=assigned_user,
        assigned_salesperson=assigned_salesperson,
        event_type=event_type,
    )
    if not skip_conflict_check:
        _validate_address(event_type=event_type, address=address, city=city)

    conflicts = []
    if not skip_conflict_check:
        conflicts = _handle_conflicts(
            start_at=start_at,
            end_at=end_at,
            assigned_user=assigned_user,
            assigned_salesperson=assigned_salesperson,
            vehicle=vehicle,
            exclude_event=None,
            all_day=all_day,
            actor=actor,
            override_conflicts=override_conflicts,
            override_reason=override_reason,
        )

    event = OperationalEvent(
        code=next_event_code(),
        title=title,
        description=description,
        event_type=event_type,
        status=status,
        priority=priority,
        start_at=start_at,
        end_at=end_at,
        all_day=all_day,
        assigned_user=assigned_user,
        assigned_salesperson=assigned_salesperson,
        external_responsible=external_responsible,
        customer=customer,
        lead=lead,
        quote=quote,
        sales_order=sales_order,
        production_order=production_order,
        production_piece=production_piece,
        delivery_schedule=delivery_schedule,
        installation_schedule=installation_schedule,
        vehicle=vehicle,
        address=address,
        district=district,
        city=city,
        state=state,
        postal_code=postal_code,
        contact_name=contact_name,
        contact_phone=contact_phone,
        internal_notes=internal_notes,
        conflict_override_reason=override_reason.strip() if conflicts else "",
        created_by=actor,
        updated_by=actor,
    )
    event.full_clean()
    event.save()

    if event_type == EventType.MEASUREMENT:
        MeasurementAppointment.objects.create(
            event=event,
            measurement_type=measurement_type or MeasurementType.INITIAL,
            technician=assigned_user,
            created_by=actor,
            updated_by=actor,
        )

    _add_history(
        event=event,
        action=HistoryAction.CREATED,
        actor=actor,
        description="Evento criado",
        new_start_at=start_at,
        new_end_at=end_at,
        new_status=event.status,
    )
    if conflicts:
        _add_history(
            event=event,
            action=HistoryAction.CONFLICT_OVERRIDDEN,
            actor=actor,
            description=override_reason.strip(),
            new_status=event.status,
        )

    if lead:
        from commercial.lead_models import LeadActivity
        from commercial.lead_models import LeadActivityType

        LeadActivity.objects.create(
            lead=lead,
            activity_type=LeadActivityType.OTHER,
            title="Compromisso agendado",
            description=f"{event.code}: {event.title}",
            occurred_at=timezone.now(),
            created_by=actor,
        )

    record_audit_event(
        request=request,
        user=actor,
        event_type="create",
        module="scheduling",
        action="operational_event_created",
        obj=event,
        metadata={"code": event.code, "type": event.event_type},
    )
    return event


@transaction.atomic
def confirm_event(
    *,
    event,
    actor,
    channel=ConfirmationChannel.PHONE,
    notes="",
    request=None,
):
    if not user_has_permission(actor, "operational_events.confirm"):
        raise PermissionDenied("Sem permissão para confirmar evento.")
    if event.status in {EventStatus.CANCELLED, EventStatus.COMPLETED}:
        raise ValidationError("Evento encerrado não pode ser confirmado.")

    event.confirmation_status = ConfirmationStatus.CONFIRMED
    event.confirmed_at = timezone.now()
    event.confirmed_by = actor
    event.confirmation_channel = channel
    event.confirmation_notes = notes
    if event.status == EventStatus.SCHEDULED:
        old_status = event.status
        event.status = EventStatus.CONFIRMED
    else:
        old_status = event.status
    event.updated_by = actor
    event.save()

    _add_history(
        event=event,
        action=HistoryAction.CONFIRMED,
        actor=actor,
        description=notes or "Compromisso confirmado",
        old_status=old_status,
        new_status=event.status,
    )
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="scheduling",
        action="operational_event_confirmed",
        obj=event,
    )
    return event


@transaction.atomic
def register_confirmation_attempt(*, event, actor, channel="", notes="", request=None):
    if not user_has_permission(actor, "operational_events.confirm"):
        raise PermissionDenied("Sem permissão para registrar confirmação.")
    event.confirmation_status = ConfirmationStatus.ATTEMPTED
    event.confirmation_channel = channel or event.confirmation_channel
    event.confirmation_notes = notes
    event.updated_by = actor
    event.save(update_fields=[
        "confirmation_status",
        "confirmation_channel",
        "confirmation_notes",
        "updated_by",
        "updated_at",
    ])
    _add_history(
        event=event,
        action=HistoryAction.CONFIRMATION_ATTEMPTED,
        actor=actor,
        description=notes or "Tentativa de confirmação",
        old_status=event.status,
        new_status=event.status,
    )
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="scheduling",
        action="operational_event_confirmation_attempted",
        obj=event,
    )
    return event


@transaction.atomic
def start_event(*, event, actor, request=None):
    if not user_has_permission(actor, "operational_events.start"):
        raise PermissionDenied("Sem permissão para iniciar evento.")
    if event.status not in {
        EventStatus.SCHEDULED,
        EventStatus.CONFIRMED,
        EventStatus.RESCHEDULED,
    }:
        raise ValidationError("Evento não está pronto para início.")
    old_status = event.status
    event.status = EventStatus.IN_PROGRESS
    event.started_at = timezone.now()
    event.updated_by = actor
    event.save()
    _add_history(
        event=event,
        action=HistoryAction.STARTED,
        actor=actor,
        description="Evento iniciado",
        old_status=old_status,
        new_status=event.status,
    )
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="scheduling",
        action="operational_event_started",
        obj=event,
    )
    return event


@transaction.atomic
def complete_event(*, event, actor, completion_notes="", request=None, force=False):
    if not user_has_permission(actor, "operational_events.complete"):
        raise PermissionDenied("Sem permissão para concluir evento.")
    if event.status == EventStatus.COMPLETED:
        raise ValidationError("Evento já concluído.")
    if event.status not in {EventStatus.CONFIRMED, EventStatus.IN_PROGRESS} and not force:
        raise ValidationError("Evento deve estar confirmado ou em andamento.")

    old_status = event.status
    event.status = EventStatus.COMPLETED
    event.completed_at = timezone.now()
    event.completion_notes = completion_notes
    event.updated_by = actor
    event.save()

    if event.delivery_schedule_id:
        from production.models import ScheduleStatus
        from production.services.delivery_ops import complete_delivery

        if event.delivery_schedule.status != ScheduleStatus.COMPLETED:
            complete_delivery(
                delivery=event.delivery_schedule,
                actor=actor,
                request=request,
                notes=completion_notes,
            )

    if event.installation_schedule_id:
        from production.models import ScheduleStatus
        from production.services.delivery_ops import complete_installation

        if event.installation_schedule.status != ScheduleStatus.COMPLETED:
            complete_installation(
                installation=event.installation_schedule,
                actor=actor,
                request=request,
                result_notes=completion_notes,
            )

    if hasattr(event, "measurement"):
        measurement = event.measurement
        measurement.measurement_completed = True
        if completion_notes:
            measurement.measurement_notes = completion_notes
        measurement.updated_by = actor
        measurement.save()

    if event.lead_id:
        from commercial.lead_models import LeadActivity
        from commercial.lead_models import LeadActivityType

        LeadActivity.objects.create(
            lead=event.lead,
            activity_type=LeadActivityType.OTHER,
            title="Compromisso concluído",
            description=f"{event.code}: {completion_notes or event.title}",
            occurred_at=timezone.now(),
            created_by=actor,
        )

    _add_history(
        event=event,
        action=HistoryAction.COMPLETED,
        actor=actor,
        description=completion_notes or "Evento concluído",
        old_status=old_status,
        new_status=event.status,
    )
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="scheduling",
        action="operational_event_completed",
        obj=event,
    )
    return event


@transaction.atomic
def cancel_event(*, event, actor, reason, request=None):
    if not user_has_permission(actor, "operational_events.cancel"):
        raise PermissionDenied("Sem permissão para cancelar evento.")
    if not (reason or "").strip():
        raise ValidationError("Motivo obrigatório para cancelamento.")
    if event.status == EventStatus.CANCELLED:
        raise ValidationError("Evento já cancelado.")
    if event.status == EventStatus.COMPLETED:
        raise ValidationError("Evento concluído não pode ser cancelado.")

    old_status = event.status
    event.status = EventStatus.CANCELLED
    event.cancel_reason = reason.strip()
    event.cancelled_at = timezone.now()
    event.updated_by = actor
    event.save()

    _add_history(
        event=event,
        action=HistoryAction.CANCELLED,
        actor=actor,
        description=reason.strip(),
        old_status=old_status,
        new_status=event.status,
    )
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="scheduling",
        action="operational_event_cancelled",
        obj=event,
        metadata={"reason": reason[:500]},
    )
    return event


@transaction.atomic
def reschedule_event(
    *,
    event,
    new_start_at,
    new_end_at,
    actor,
    reason,
    override_conflicts=False,
    request=None,
):
    if not user_has_permission(actor, "operational_events.reschedule"):
        raise PermissionDenied("Sem permissão para reagendar.")
    if not (reason or "").strip():
        raise ValidationError("Motivo obrigatório para reagendamento.")
    if event.status in {EventStatus.CANCELLED, EventStatus.COMPLETED}:
        raise ValidationError("Evento encerrado não pode ser reagendado.")

    new_start_at = _ensure_aware(new_start_at)
    new_end_at = _ensure_aware(new_end_at)
    conflicts = _handle_conflicts(
        start_at=new_start_at,
        end_at=new_end_at,
        assigned_user=event.assigned_user,
        assigned_salesperson=event.assigned_salesperson,
        vehicle=event.vehicle,
        exclude_event=event,
        all_day=event.all_day,
        actor=actor,
        override_conflicts=override_conflicts,
        override_reason=reason,
    )

    old_start = event.start_at
    old_end = event.end_at
    old_status = event.status
    event.start_at = new_start_at
    event.end_at = new_end_at
    event.status = EventStatus.SCHEDULED
    event.updated_by = actor
    if conflicts:
        event.conflict_override_reason = reason.strip()
    event.full_clean()
    event.save()

    if event.delivery_schedule_id:
        delivery = event.delivery_schedule
        delivery.scheduled_date = timezone.localtime(new_start_at).date()
        delivery.scheduled_time_start = timezone.localtime(new_start_at).time()
        if new_end_at:
            delivery.scheduled_time_end = timezone.localtime(new_end_at).time()
        delivery.updated_by = actor
        delivery.save()

    if event.installation_schedule_id:
        installation = event.installation_schedule
        installation.scheduled_date = timezone.localtime(new_start_at).date()
        installation.scheduled_time_start = timezone.localtime(new_start_at).time()
        if new_end_at:
            installation.scheduled_time_end = timezone.localtime(new_end_at).time()
        installation.updated_by = actor
        installation.save()

    _add_history(
        event=event,
        action=HistoryAction.RESCHEDULED,
        actor=actor,
        description=reason.strip(),
        old_start_at=old_start,
        old_end_at=old_end,
        new_start_at=new_start_at,
        new_end_at=new_end_at,
        old_status=old_status,
        new_status=event.status,
    )
    if conflicts:
        _add_history(
            event=event,
            action=HistoryAction.CONFLICT_OVERRIDDEN,
            actor=actor,
            description=reason.strip(),
            new_status=event.status,
        )
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="scheduling",
        action="operational_event_rescheduled",
        obj=event,
        metadata={"reason": reason[:500]},
    )
    return event


@transaction.atomic
def mark_no_show(*, event, actor, notes="", request=None):
    if not user_has_permission(actor, "operational_events.complete"):
        raise PermissionDenied("Sem permissão para registrar no-show.")
    old_status = event.status
    event.status = EventStatus.NO_SHOW
    event.completion_notes = notes
    event.completed_at = timezone.now()
    event.updated_by = actor
    event.save()
    _add_history(
        event=event,
        action=HistoryAction.NO_SHOW,
        actor=actor,
        description=notes or "Cliente não compareceu",
        old_status=old_status,
        new_status=event.status,
    )
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="scheduling",
        action="operational_event_no_show",
        obj=event,
    )
    return event


def combine_date_time(date_value, time_value=None, end=False):
    if time_value is None:
        time_value = time(23, 59, 59) if end else time(8, 0, 0)
    return timezone.make_aware(datetime.combine(date_value, time_value))


def sync_event_from_delivery(*, delivery, actor, request=None):
    existing = OperationalEvent.objects.filter(delivery_schedule=delivery).first()
    if existing:
        return existing
    start = combine_date_time(delivery.scheduled_date, delivery.scheduled_time_start)
    end = combine_date_time(
        delivery.scheduled_date,
        delivery.scheduled_time_end,
        end=True,
    )
    return create_operational_event(
        actor=actor,
        title=f"Entrega — {delivery.sales_order.number}",
        event_type=EventType.DELIVERY,
        start_at=start,
        end_at=end,
        assigned_user=delivery.responsible or actor,
        customer=delivery.sales_order.customer,
        sales_order=delivery.sales_order,
        delivery_schedule=delivery,
        vehicle=delivery.vehicle,
        address=delivery.address or delivery.sales_order.delivery_address,
        city=delivery.city or delivery.sales_order.delivery_city,
        state=delivery.state or delivery.sales_order.delivery_state,
        postal_code=delivery.postal_code or delivery.sales_order.delivery_postal_code,
        internal_notes=delivery.notes,
        skip_conflict_check=True,
        skip_permission_check=True,
        request=request,
    )


def sync_event_from_installation(*, installation, actor, request=None):
    existing = OperationalEvent.objects.filter(installation_schedule=installation).first()
    if existing:
        return existing
    start = combine_date_time(installation.scheduled_date, installation.scheduled_time_start)
    end = combine_date_time(
        installation.scheduled_date,
        installation.scheduled_time_end,
        end=True,
    )
    return create_operational_event(
        actor=actor,
        title=f"Instalação — {installation.sales_order.number}",
        event_type=EventType.INSTALLATION,
        start_at=start,
        end_at=end,
        assigned_user=installation.responsible or actor,
        customer=installation.sales_order.customer,
        sales_order=installation.sales_order,
        installation_schedule=installation,
        vehicle=installation.vehicle,
        address=installation.address or installation.sales_order.delivery_address,
        city=installation.city or installation.sales_order.delivery_city,
        state=installation.state or installation.sales_order.delivery_state,
        postal_code=installation.postal_code or installation.sales_order.delivery_postal_code,
        internal_notes=installation.notes,
        skip_conflict_check=True,
        skip_permission_check=True,
        request=request,
    )
