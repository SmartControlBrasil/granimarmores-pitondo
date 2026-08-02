# ruff: noqa: PLR0912
from datetime import timedelta

from django.utils import timezone

from commercial.lead_models import Lead
from commercial.lead_models import LeadStatus
from commercial.lead_models import LeadTask
from commercial.lead_models import LeadTaskStatus
from commercial.lead_models import LOSS_STATUSES
from commercial.lead_models import TERMINAL_STATUSES
from commercial.performance_definitions import UNATTENDED_LEAD_HOURS
from commercial.performance_models import ScoreEventType
from commercial.performance_score import event_exists
from commercial.performance_score import get_active_score_policy
from commercial.performance_score import record_score_event
from quotes.models import Quote
from quotes.models import QuoteStatus


def process_penalties(*, start=None, end=None, salesperson=None, dry_run=False):
    now = timezone.now()
    start = start or (now - timedelta(days=30))
    end = end or now
    policy = get_active_score_policy()
    if not policy:
        return {"created": 0, "skipped": 0, "details": ["Nenhuma política ativa."]}

    created = 0
    skipped = 0
    details = []

    lead_qs = Lead.objects.filter(
        assigned_salesperson__isnull=False,
        assigned_salesperson__is_active=True,
        first_contact_at__isnull=True,
        created_at__lt=now - timedelta(hours=UNATTENDED_LEAD_HOURS),
    ).exclude(status__in=TERMINAL_STATUSES)
    if salesperson:
        lead_qs = lead_qs.filter(assigned_salesperson=salesperson)
    lead_qs = lead_qs.filter(created_at__gte=start, created_at__lte=end)

    for lead in lead_qs.select_related("assigned_salesperson"):
        if event_exists(
            salesperson=lead.assigned_salesperson,
            event_type=ScoreEventType.UNATTENDED_LEAD_PENALTY,
            reference_type="lead",
            reference_id=lead.pk,
        ):
            skipped += 1
            continue
        if dry_run:
            details.append(f"Penalidade lead sem contato: {lead.code}")
            created += 1
            continue
        event = record_score_event(
            salesperson=lead.assigned_salesperson,
            event_type=ScoreEventType.UNATTENDED_LEAD_PENALTY,
            reference_type="lead",
            reference_id=lead.pk,
            reference_label=lead.code,
            description=f"Lead sem primeiro contato — {lead.code}",
            skip_if_exists=True,
        )
        if event:
            created += 1
            details.append(f"Penalidade lead sem contato: {lead.code}")
        else:
            skipped += 1

    task_qs = LeadTask.objects.filter(
        due_at__lt=now,
        status__in=[LeadTaskStatus.PENDING, LeadTaskStatus.IN_PROGRESS],
        lead__assigned_salesperson__isnull=False,
        lead__assigned_salesperson__is_active=True,
    ).select_related("lead", "lead__assigned_salesperson")
    if salesperson:
        task_qs = task_qs.filter(lead__assigned_salesperson=salesperson)
    task_qs = task_qs.filter(due_at__gte=start, due_at__lte=end)

    for task in task_qs:
        sp = task.lead.assigned_salesperson
        if event_exists(
            salesperson=sp,
            event_type=ScoreEventType.OVERDUE_FOLLOW_UP_PENALTY,
            reference_type="lead_task",
            reference_id=task.pk,
        ):
            skipped += 1
            continue
        if dry_run:
            details.append(f"Penalidade follow-up vencido: tarefa {task.pk}")
            created += 1
            continue
        event = record_score_event(
            salesperson=sp,
            event_type=ScoreEventType.OVERDUE_FOLLOW_UP_PENALTY,
            reference_type="lead_task",
            reference_id=task.pk,
            reference_label=task.title[:200],
            occurred_at=task.due_at,
            description=f"Follow-up vencido — {task.lead.code}",
            skip_if_exists=True,
        )
        if event:
            created += 1
            details.append(f"Penalidade follow-up vencido: tarefa {task.pk}")
        else:
            skipped += 1

    lost_qs = Lead.objects.filter(
        status__in=LOSS_STATUSES,
        assigned_salesperson__isnull=False,
        assigned_salesperson__is_active=True,
        lost_at__gte=start,
        lost_at__lte=end,
    ).select_related("assigned_salesperson", "loss_reason")
    if salesperson:
        lost_qs = lost_qs.filter(assigned_salesperson=salesperson)

    for lead in lost_qs:
        missing_reason = not lead.loss_reason_id
        weak_reason = (
            lead.loss_reason
            and lead.loss_reason.requires_notes
            and not (lead.loss_notes or "").strip()
        )
        if not missing_reason and not weak_reason:
            skipped += 1
            continue
        if event_exists(
            salesperson=lead.assigned_salesperson,
            event_type=ScoreEventType.LOST_WITHOUT_REASON_PENALTY,
            reference_type="lead",
            reference_id=lead.pk,
        ):
            skipped += 1
            continue
        if dry_run:
            details.append(f"Penalidade perda sem motivo: {lead.code}")
            created += 1
            continue
        event = record_score_event(
            salesperson=lead.assigned_salesperson,
            event_type=ScoreEventType.LOST_WITHOUT_REASON_PENALTY,
            reference_type="lead",
            reference_id=lead.pk,
            reference_label=lead.code,
            occurred_at=lead.lost_at,
            description=f"Perda sem motivo adequado — {lead.code}",
            skip_if_exists=True,
        )
        if event:
            created += 1
            details.append(f"Penalidade perda sem motivo: {lead.code}")
        else:
            skipped += 1

    quote_qs = Quote.objects.filter(
        status=QuoteStatus.EXPIRED,
        salesperson__isnull=False,
        salesperson__is_active=True,
        sent_at__isnull=False,
    ).select_related("salesperson")
    if salesperson:
        quote_qs = quote_qs.filter(salesperson=salesperson)

    for quote in quote_qs:
        ref_type = "quote_expired"
        if event_exists(
            salesperson=quote.salesperson,
            event_type=ScoreEventType.OVERDUE_FOLLOW_UP_PENALTY,
            reference_type=ref_type,
            reference_id=quote.pk,
        ):
            skipped += 1
            continue
        if dry_run:
            details.append(f"Penalidade orçamento expirado: {quote.number}")
            created += 1
            continue
        event = record_score_event(
            salesperson=quote.salesperson,
            event_type=ScoreEventType.OVERDUE_FOLLOW_UP_PENALTY,
            reference_type=ref_type,
            reference_id=quote.pk,
            reference_label=quote.number,
            description=f"Orçamento expirado sem retorno — {quote.number}",
            skip_if_exists=True,
        )
        if event:
            created += 1
            details.append(f"Penalidade orçamento expirado: {quote.number}")
        else:
            skipped += 1

    return {"created": created, "skipped": skipped, "details": details}
