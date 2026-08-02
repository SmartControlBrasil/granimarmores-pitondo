# ruff: noqa: PLR0913
from decimal import Decimal

from django.db.models import Avg
from django.db.models import Count
from django.db.models import F
from django.db.models import Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from commercial.lead_models import Lead
from commercial.lead_models import LeadStatus
from commercial.lead_models import LOSS_STATUSES
from commercial.performance_definitions import (
    APPROVED_VALUE_QUOTE_STATUSES,
    CLOSED_SALE_QUOTE_STATUS,
    OPEN_LEAD_STATUSES,
    POTENTIAL_QUOTE_STATUSES,
    QUOTE_SENT_STATUSES,
)
from commercial.performance_metrics import compute_goal_progress
from commercial.performance_metrics import compute_salesperson_metrics
from commercial.performance_metrics import safe_divide
from commercial.performance_metrics import safe_rate
from commercial.performance_models import SalesGoal
from commercial.performance_ranking import build_ranking
from quotes.models import Quote
from quotes.models import QuoteStatus
from salespeople.models import Salesperson


def _apply_lead_filters(qs, filters):
    if filters.get("salesperson"):
        qs = qs.filter(assigned_salesperson_id=filters["salesperson"])
    if filters.get("commercial_source"):
        qs = qs.filter(commercial_source_id=filters["commercial_source"])
    if filters.get("project_type"):
        qs = qs.filter(project_type_id=filters["project_type"])
    if filters.get("city"):
        qs = qs.filter(city__icontains=filters["city"])
    return qs


def _apply_quote_filters(qs, filters):
    if filters.get("salesperson"):
        qs = qs.filter(salesperson_id=filters["salesperson"])
    if filters.get("commercial_source"):
        qs = qs.filter(commercial_source_id=filters["commercial_source"])
    if filters.get("city"):
        qs = qs.filter(customer__addresses__city__icontains=filters["city"]).distinct()
    return qs


def commercial_metrics(*, start, end, filters=None):
    filters = filters or {}
    leads = _apply_lead_filters(Lead.objects.all(), filters)
    period_leads = leads.filter(created_at__gte=start, created_at__lte=end)
    quotes = _apply_quote_filters(Quote.objects.select_related("customer"), filters)

    received = period_leads.count()
    attended = period_leads.filter(first_contact_at__isnull=False).count()
    no_contact = period_leads.filter(first_contact_at__isnull=True).count()
    no_owner = period_leads.filter(assigned_salesperson__isnull=True).count()
    by_status = {
        row["status"]: row["total"]
        for row in period_leads.values("status").annotate(total=Count("id"))
    }
    won = by_status.get(LeadStatus.WON, 0)
    lost = by_status.get(LeadStatus.LOST, 0)

    open_leads = leads.filter(status__in=OPEN_LEAD_STATUSES)
    potential_leads = open_leads.aggregate(total=Sum("estimated_value"))["total"] or Decimal("0")
    potential_quotes = quotes.filter(status__in=POTENTIAL_QUOTE_STATUSES).aggregate(
        total=Sum("grand_total"),
    )["total"] or Decimal("0")
    potential_value = potential_leads + potential_quotes

    closed = quotes.filter(
        status__in=APPROVED_VALUE_QUOTE_STATUSES,
        accepted_at__gte=start,
        accepted_at__lte=end,
    )
    approved_value = closed.aggregate(total=Sum("grand_total"))["total"] or Decimal("0")
    closed_count = closed.count()
    ticket = safe_divide(approved_value, closed_count).quantize(Decimal("0.01"))
    conversion = safe_rate(won, won + lost)

    quotes_sent = quotes.filter(
        status__in=QUOTE_SENT_STATUSES | {QuoteStatus.SENT, QuoteStatus.VIEWED},
        sent_at__gte=start,
        sent_at__lte=end,
    ).count()
    quotes_accepted = closed_count
    quotes_refused = quotes.filter(
        status=QuoteStatus.EXPIRED,
        updated_at__gte=start,
        updated_at__lte=end,
    ).count()
    # Recusado: quotes cancelled after sent or loss linked — use refused/cancelled statuses if exist
    quotes_cancelled = quotes.filter(
        status=QuoteStatus.CANCELLED,
        updated_at__gte=start,
        updated_at__lte=end,
    ).count()
    quotes_expired = quotes.filter(
        status=QuoteStatus.EXPIRED,
        updated_at__gte=start,
        updated_at__lte=end,
    ).count()

    avg_response = period_leads.filter(first_contact_at__isnull=False).aggregate(
        avg=Avg(F("first_contact_at") - F("created_at")),
    )["avg"]
    response_hours = round(avg_response.total_seconds() / 3600, 1) if avg_response else 0

    return {
        "leads_received": received,
        "leads_attended": attended,
        "leads_no_contact": no_contact,
        "leads_no_owner": no_owner,
        "qualified": by_status.get(LeadStatus.QUALIFIED, 0),
        "measurement": by_status.get(LeadStatus.MEASUREMENT_SCHEDULED, 0)
        + by_status.get(LeadStatus.MEASUREMENT_COMPLETED, 0),
        "quoting": by_status.get(LeadStatus.QUOTE_PREPARATION, 0)
        + by_status.get(LeadStatus.QUOTE_SENT, 0),
        "negotiation": by_status.get(LeadStatus.NEGOTIATION, 0),
        "won": won,
        "lost": lost,
        "conversion_rate": conversion,
        "avg_first_response_hours": response_hours,
        "open_opportunities": open_leads.count(),
        "potential_value": potential_value,
        "approved_value": approved_value,
        "ticket_average": ticket,
        "quotes_sent": quotes_sent,
        "quotes_accepted": quotes_accepted,
        "quotes_refused": quotes.filter(
            status=QuoteStatus.REJECTED,
            updated_at__gte=start,
            updated_at__lte=end,
        ).count()
        + quotes_cancelled,
        "quotes_expired": quotes_expired,
        "by_status": by_status,
        "by_source": list(
            period_leads.values("commercial_source__name")
            .annotate(total=Count("id"))
            .order_by("-total")[:10],
        ),
        "by_project_type": list(
            period_leads.values("project_type__name")
            .annotate(total=Count("id"))
            .order_by("-total")[:10],
        ),
        "by_city": list(
            period_leads.exclude(city="")
            .values("city")
            .annotate(total=Count("id"))
            .order_by("-total")[:10],
        ),
        "by_loss_reason": list(
            period_leads.filter(status__in=LOSS_STATUSES)
            .values("loss_reason__name")
            .annotate(total=Count("id"))
            .order_by("-total")[:10],
        ),
        "funnel": _funnel_rows(leads, period_leads),
        "sales_by_day": [
            {
                "label": row["day"].isoformat() if row["day"] else "",
                "value": float(row["total"] or 0),
            }
            for row in closed.annotate(day=TruncDate("accepted_at"))
            .values("day")
            .annotate(total=Sum("grand_total"), count=Count("id"))
            .order_by("day")[:60]
        ],
    }


def _funnel_rows(all_leads, period_leads):
    stages = [
        ("new", "Novos", [LeadStatus.NEW, LeadStatus.TRIAGE, LeadStatus.ASSIGNED]),
        ("contact", "Contato", [LeadStatus.CONTACTED]),
        ("qualified", "Qualificados", [LeadStatus.QUALIFIED]),
        (
            "measurement",
            "Medição",
            [LeadStatus.MEASUREMENT_SCHEDULED, LeadStatus.MEASUREMENT_COMPLETED],
        ),
        (
            "quote",
            "Orçamento",
            [LeadStatus.QUOTE_PREPARATION, LeadStatus.QUOTE_SENT],
        ),
        ("negotiation", "Negociação", [LeadStatus.NEGOTIATION]),
        ("won", "Ganhos", [LeadStatus.WON]),
        ("lost", "Perdidos", [LeadStatus.LOST, LeadStatus.DISQUALIFIED]),
    ]
    rows = []
    for key, label, statuses in stages:
        qs = period_leads.filter(status__in=statuses)
        open_statuses = [s for s in statuses if s in OPEN_LEAD_STATUSES]
        if open_statuses:
            open_qs = all_leads.filter(status__in=open_statuses)
            open_count = open_qs.count()
            value = open_qs.aggregate(total=Sum("estimated_value"))["total"] or Decimal("0")
        else:
            open_count = qs.count()
            value = qs.aggregate(total=Sum("estimated_value"))["total"] or Decimal("0")
        rows.append(
            {
                "key": key,
                "label": label,
                "count": qs.count(),
                "open_count": open_count,
                "estimated_value": value,
                # Tempo médio na etapa exige histórico de transição — não inventar
                "avg_stage_hours": None,
            },
        )
    return rows


def salesperson_executive_table(*, start, end, filters=None, user=None):
    filters = filters or {}
    salespeople = Salesperson.objects.filter(is_active=True)
    if filters.get("salesperson"):
        salespeople = salespeople.filter(pk=filters["salesperson"])
    ranking_data = build_ranking(user=user, start=start, end=end) if user else {"rows": []}
    ranking = {row["salesperson"].pk: row for row in ranking_data.get("rows", [])}
    rows = []
    now = timezone.now()
    for sp in salespeople:
        metrics = compute_salesperson_metrics(salesperson=sp, start=start, end=end)
        goal = (
            SalesGoal.objects.filter(
                salesperson=sp,
                start_date__lte=now.date(),
                end_date__gte=now.date(),
                is_active=True,
            )
            .order_by("-start_date")
            .first()
        )
        goal_progress = compute_goal_progress(goal=goal, metrics=metrics) if goal else None
        rank_row = ranking.get(sp.pk, {})
        rows.append(
            {
                **metrics,
                "position": rank_row.get("position"),
                "goal": goal,
                "goal_progress": goal_progress,
                "alerts": _salesperson_alerts(metrics, goal_progress),
            },
        )
    rows.sort(key=lambda r: r["approved_value"], reverse=True)
    return rows


def _salesperson_alerts(metrics, goal_progress):
    alerts = []
    if metrics["leads_received"] == 0 and metrics["quotes_sent"] == 0:
        alerts.append("Sem atividade no período")
    if metrics["unattended_leads"]:
        alerts.append(f"{metrics['unattended_leads']} lead(s) sem contato")
    if metrics["followups_overdue"]:
        alerts.append(f"{metrics['followups_overdue']} follow-up(s) vencido(s)")
    if goal_progress and goal_progress.get("situation") == "at_risk":
        alerts.append("Meta em risco")
    return alerts
