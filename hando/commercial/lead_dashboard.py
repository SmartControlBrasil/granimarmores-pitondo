from datetime import datetime
from datetime import timedelta

from django.db.models import Avg
from django.db.models import Count
from django.db.models import F
from django.db.models import Q
from django.db.models import Sum
from django.utils import timezone

from commercial.lead_models import Lead
from commercial.lead_models import LeadStatus
from commercial.lead_models import LeadTask
from commercial.lead_models import LeadTaskStatus
from commercial.lead_models import LOSS_STATUSES
from commercial.lead_models import TERMINAL_STATUSES
from commercial.lead_queries import leads_queryset_for_user


OPEN_STATUSES = [
    s for s, _ in LeadStatus.choices if s not in TERMINAL_STATUSES
]


def _parse_period(request):
    period = request.GET.get("period", "30d")
    now = timezone.now()
    if period == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "7d":
        start = now - timedelta(days=7)
    elif period == "month":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif period == "custom":
        from django.utils.dateparse import parse_date

        start_date = parse_date(request.GET.get("start", "") or "")
        end_date = parse_date(request.GET.get("end", "") or "")
        if start_date and end_date:
            start = timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
            end = timezone.make_aware(datetime.combine(end_date, datetime.max.time()))
            return start, end
        start = now - timedelta(days=30)
    else:
        start = now - timedelta(days=30)
    return start, now


def build_commercial_dashboard_context(*, user, request):
    start, end = _parse_period(request)
    qs = leads_queryset_for_user(user).filter(created_at__gte=start, created_at__lte=end)
    all_leads = leads_queryset_for_user(user)
    now = timezone.now()

    won = qs.filter(status=LeadStatus.WON).count()
    lost = qs.filter(status__in=LOSS_STATUSES).count()
    received = qs.count()
    converted = qs.filter(converted_customer__isnull=False).count()

    def safe_rate(numerator, denominator):
        if not denominator:
            return 0
        return round((numerator / denominator) * 100, 1)

    open_qs = all_leads.filter(status__in=OPEN_STATUSES)
    overdue_followups = all_leads.filter(
        next_follow_up_at__lt=now,
        status__in=OPEN_STATUSES,
    ).count()
    overdue_tasks = LeadTask.objects.filter(
        lead__in=all_leads,
        due_at__lt=now,
        status__in=[LeadTaskStatus.PENDING, LeadTaskStatus.IN_PROGRESS],
    ).count()

    avg_first_contact = qs.filter(first_contact_at__isnull=False).aggregate(
        avg=Avg(F("first_contact_at") - F("created_at")),
    )["avg"]

    cards = [
        ("Leads recebidos", received),
        ("Novos", qs.filter(status=LeadStatus.NEW).count()),
        ("Sem responsável", all_leads.filter(assigned_salesperson__isnull=True, status__in=OPEN_STATUSES).count()),
        ("Primeiro contato pendente", all_leads.filter(first_contact_at__isnull=True, status__in=OPEN_STATUSES).exclude(status=LeadStatus.NEW).count()),
        ("Qualificados", all_leads.filter(status=LeadStatus.QUALIFIED).count()),
        ("Em medição", all_leads.filter(status__in=[LeadStatus.MEASUREMENT_SCHEDULED, LeadStatus.MEASUREMENT_COMPLETED]).count()),
        ("Em orçamento", all_leads.filter(status__in=[LeadStatus.QUOTE_PREPARATION, LeadStatus.QUOTE_SENT]).count()),
        ("Em negociação", all_leads.filter(status=LeadStatus.NEGOTIATION).count()),
        ("Ganhos", won),
        ("Perdidos", lost),
        ("Desqualificados", qs.filter(status=LeadStatus.DISQUALIFIED).count()),
        ("Conversão em cliente", f"{safe_rate(converted, received)}%"),
        ("Taxa de ganho", f"{safe_rate(won, won + lost)}%"),
        ("Valor estimado aberto", open_qs.aggregate(total=Sum("estimated_value"))["total"] or 0),
        ("Valor estimado ganho", qs.filter(status=LeadStatus.WON).aggregate(total=Sum("estimated_value"))["total"] or 0),
        ("Follow-ups vencidos", overdue_followups),
        ("Tarefas vencidas", overdue_tasks),
    ]

    by_source = (
        qs.values("commercial_source__name")
        .annotate(total=Count("id"))
        .order_by("-total")[:8]
    )
    by_salesperson = (
        qs.values("assigned_salesperson__display_name")
        .annotate(total=Count("id"))
        .order_by("-total")[:8]
    )
    by_project = (
        qs.values("project_type__name")
        .annotate(total=Count("id"))
        .order_by("-total")[:8]
    )
    by_loss = (
        qs.filter(status__in=LOSS_STATUSES)
        .values("loss_reason__name")
        .annotate(total=Count("id"))
        .order_by("-total")[:8]
    )
    by_city = qs.values("city").annotate(total=Count("id")).order_by("-total")[:8]

    return {
        "period": request.GET.get("period", "30d"),
        "cards": cards,
        "by_source": by_source,
        "by_salesperson": by_salesperson,
        "by_project": by_project,
        "by_loss": by_loss,
        "by_city": by_city,
        "avg_first_contact": avg_first_contact,
    }


FUNNEL_COLUMNS = [
    ("new", "Novos", [LeadStatus.NEW]),
    ("triage", "Triagem", [LeadStatus.TRIAGE]),
    ("assigned", "Atribuídos", [LeadStatus.ASSIGNED]),
    ("contact", "Contato", [LeadStatus.CONTACTED]),
    ("qualified", "Qualificados", [LeadStatus.QUALIFIED]),
    ("measurement", "Medição", [LeadStatus.MEASUREMENT_SCHEDULED, LeadStatus.MEASUREMENT_COMPLETED]),
    ("quote", "Orçamento", [LeadStatus.QUOTE_PREPARATION, LeadStatus.QUOTE_SENT]),
    ("negotiation", "Negociação", [LeadStatus.NEGOTIATION]),
    ("won", "Ganhos", [LeadStatus.WON]),
    ("lost", "Perdidos", [LeadStatus.LOST, LeadStatus.DISQUALIFIED]),
]


def build_funnel_context(*, user, limit=8):
    now = timezone.now()
    cutoff = now - timedelta(days=30)
    columns = []
    qs_base = leads_queryset_for_user(user)
    for key, label, statuses in FUNNEL_COLUMNS:
        qs = qs_base.filter(status__in=statuses)
        if key in {"won", "lost"}:
            qs = qs.filter(
                Q(won_at__gte=cutoff) | Q(lost_at__gte=cutoff) | Q(updated_at__gte=cutoff),
            )
        total = qs.count()
        value = qs.aggregate(total=Sum("estimated_value"))["total"] or 0
        columns.append(
            {
                "key": key,
                "label": label,
                "total": total,
                "value": value,
                "leads": qs.select_related("assigned_salesperson", "project_type")[:limit],
            },
        )
    return {"columns": columns}
