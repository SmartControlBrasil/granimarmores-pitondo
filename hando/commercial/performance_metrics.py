from datetime import datetime
from datetime import timedelta
from decimal import Decimal

from django.db.models import Avg
from django.db.models import Count
from django.db.models import F
from django.db.models import Q
from django.db.models import Sum
from django.utils import timezone

from access_control.services.authorization import user_has_permission
from commercial.lead_models import Lead
from commercial.lead_models import LeadStatus
from commercial.lead_models import LeadTask
from commercial.lead_models import LeadTaskStatus
from commercial.lead_models import LOSS_STATUSES
from commercial.lead_queries import leads_queryset_for_user
from commercial.performance_definitions import (
    CLOSED_SALE_QUOTE_STATUS,
    OPEN_LEAD_STATUSES,
    POTENTIAL_QUOTE_STATUSES,
    QUOTE_SENT_STATUSES,
)
from commercial.performance_models import SalesGoal
from commercial.performance_models import SalesScoreEvent
from quotes.models import Quote
from quotes.models import QuoteStatus
from salespeople.models import Salesperson


def safe_rate(numerator, denominator, *, decimals=1):
    if not denominator:
        return Decimal("0")
    return round(Decimal(numerator) / Decimal(denominator) * 100, decimals)


def safe_divide(numerator, denominator):
    if not denominator:
        return Decimal("0")
    return Decimal(numerator) / Decimal(denominator)


def salespersons_for_scope(*, user, include_inactive=False):
    qs = Salesperson.objects.all()
    if not include_inactive:
        qs = qs.filter(is_active=True)
    if user_has_permission(user, "sales_performance.view_all"):
        return qs
    salesperson = getattr(user, "salesperson", None)
    if salesperson:
        team_ids = list(
            qs.filter(Q(pk=salesperson.pk) | Q(manager=salesperson)).values_list("pk", flat=True),
        )
        return qs.filter(pk__in=team_ids)
    return qs.none()


def leads_for_salesperson(*, salesperson, start, end, user=None):
    qs = Lead.objects.filter(assigned_salesperson=salesperson)
    if user:
        qs = qs.filter(pk__in=leads_queryset_for_user(user).values("pk"))
    return qs.filter(created_at__gte=start, created_at__lte=end)


def quotes_for_salesperson(*, salesperson, start, end):
    return Quote.objects.filter(salesperson=salesperson).filter(
        Q(created_at__gte=start, created_at__lte=end)
        | Q(sent_at__gte=start, sent_at__lte=end)
        | Q(accepted_at__gte=start, accepted_at__lte=end),
    )


def compute_salesperson_metrics(*, salesperson, start, end):
    leads = Lead.objects.filter(
        assigned_salesperson=salesperson,
        created_at__gte=start,
        created_at__lte=end,
    )
    all_assigned = Lead.objects.filter(assigned_salesperson=salesperson)
    now = timezone.now()

    received = leads.count()
    attended = leads.filter(first_contact_at__isnull=False).count()
    qualified = leads.filter(status=LeadStatus.QUALIFIED).count()
    converted = leads.filter(converted_customer__isnull=False).count()
    won = leads.filter(status=LeadStatus.WON).count()
    lost = leads.filter(status=LeadStatus.LOST).count()
    disqualified = leads.filter(status=LeadStatus.DISQUALIFIED).count()

    quotes = Quote.objects.filter(salesperson=salesperson)
    quotes_created = quotes.filter(created_at__gte=start, created_at__lte=end).count()
    quotes_sent = quotes.filter(
        status__in=QUOTE_SENT_STATUSES | {QuoteStatus.SENT, QuoteStatus.VIEWED},
        sent_at__gte=start,
        sent_at__lte=end,
    ).count()
    closed_sales = quotes.filter(
        status=CLOSED_SALE_QUOTE_STATUS,
        accepted_at__gte=start,
        accepted_at__lte=end,
    )
    closed_sales_count = closed_sales.count()

    potential_leads_value = all_assigned.filter(
        status__in=OPEN_LEAD_STATUSES,
    ).aggregate(total=Sum("estimated_value"))["total"] or Decimal("0")
    potential_quotes_value = quotes.filter(
        status__in=POTENTIAL_QUOTE_STATUSES,
    ).aggregate(total=Sum("grand_total"))["total"] or Decimal("0")
    potential_value = potential_leads_value + potential_quotes_value

    approved_value = closed_sales.aggregate(total=Sum("grand_total"))["total"] or Decimal("0")
    ticket_avg = safe_divide(approved_value, closed_sales_count or won or 1)
    if closed_sales_count == 0 and won == 0:
        ticket_avg = Decimal("0")
    elif closed_sales_count == 0:
        ticket_avg = safe_divide(
            leads.filter(status=LeadStatus.WON).aggregate(total=Sum("estimated_value"))["total"]
            or Decimal("0"),
            won,
        )

    conversion_rate = safe_rate(won, won + lost)
    avg_response = leads.filter(first_contact_at__isnull=False).aggregate(
        avg=Avg(F("first_contact_at") - F("created_at")),
    )["avg"]
    response_minutes = int(avg_response.total_seconds() / 60) if avg_response else 0

    tasks = LeadTask.objects.filter(
        lead__assigned_salesperson=salesperson,
        created_at__gte=start,
        created_at__lte=end,
    )
    followups_created = tasks.count()
    followups_completed = tasks.filter(status=LeadTaskStatus.COMPLETED).count()
    followups_overdue = tasks.filter(
        due_at__lt=now,
        status__in=[LeadTaskStatus.PENDING, LeadTaskStatus.IN_PROGRESS],
    ).count()
    on_time = tasks.filter(
        status=LeadTaskStatus.COMPLETED,
        completed_at__isnull=False,
        completed_at__lte=F("due_at"),
    ).count()
    follow_up_compliance = safe_rate(on_time, followups_completed)

    score_data = SalesScoreEvent.objects.filter(
        salesperson=salesperson,
        occurred_at__gte=start,
        occurred_at__lte=end,
    ).aggregate(
        total=Sum("points"),
        penalties=Sum("points", filter=Q(points__lt=0)),
    )
    total_score = score_data["total"] or 0
    penalties = abs(score_data["penalties"] or 0)

    unattended = all_assigned.filter(
        first_contact_at__isnull=True,
        status__in=OPEN_LEAD_STATUSES,
        created_at__lt=now - timedelta(hours=48),
    ).count()
    negotiations = all_assigned.filter(status=LeadStatus.NEGOTIATION).count()

    return {
        "salesperson": salesperson,
        "leads_received": received,
        "leads_attended": attended,
        "leads_qualified": qualified,
        "leads_converted": converted,
        "leads_won": won,
        "leads_lost": lost,
        "leads_disqualified": disqualified,
        "quotes_created": quotes_created,
        "quotes_sent": quotes_sent,
        "closed_sales": closed_sales_count,
        "potential_value": potential_value,
        "approved_value": approved_value,
        "ticket_average": ticket_avg.quantize(Decimal("0.01")),
        "conversion_rate": conversion_rate,
        "response_minutes": response_minutes,
        "followups_created": followups_created,
        "followups_completed": followups_completed,
        "followups_overdue": followups_overdue,
        "follow_up_compliance": follow_up_compliance,
        "tasks_completed": followups_completed,
        "total_score": total_score,
        "penalties": penalties,
        "unattended_leads": unattended,
        "negotiations_open": negotiations,
    }


def compute_goal_progress(*, goal, metrics=None):
    if metrics is None:
        start = timezone.make_aware(datetime.combine(goal.start_date, datetime.min.time()))
        end = timezone.make_aware(datetime.combine(goal.end_date, datetime.max.time()))
        metrics = compute_salesperson_metrics(
            salesperson=goal.salesperson,
            start=start,
            end=end,
        )

    today = timezone.localdate()
    if today > goal.end_date:
        situation = "closed"
    elif not metrics["leads_received"] and not metrics["quotes_sent"]:
        situation = "no_data"
    else:
        situation = "on_track"

    def pct(actual, target):
        if not target:
            return None
        return round(float(actual) / float(target) * 100, 1)

    progress = {
        "lead_goal": pct(metrics["leads_received"], goal.lead_goal),
        "contact_goal": pct(metrics["leads_attended"], goal.contact_goal),
        "quote_goal": pct(metrics["quotes_sent"], goal.quote_goal),
        "won_lead_goal": pct(metrics["leads_won"], goal.won_lead_goal),
        "sales_value_goal": pct(metrics["approved_value"], goal.sales_value_goal),
        "conversion_goal": pct(metrics["conversion_rate"], goal.conversion_goal),
        "response_time_goal": (
            pct(goal.response_time_goal_minutes, metrics["response_minutes"])
            if metrics["response_minutes"] and goal.response_time_goal_minutes
            else None
        ),
        "follow_up_compliance_goal": pct(
            metrics["follow_up_compliance"],
            goal.follow_up_compliance_goal,
        ),
    }

    tracked = [v for v in progress.values() if v is not None]
    if tracked:
        avg_progress = sum(tracked) / len(tracked)
        if avg_progress >= 100:
            situation = "achieved"
        elif avg_progress < 60 and today <= goal.end_date:
            situation = "at_risk"

    elapsed_days = max((min(today, goal.end_date) - goal.start_date).days + 1, 1)
    total_days = max((goal.end_date - goal.start_date).days + 1, 1)
    projection_factor = total_days / elapsed_days

    return {
        "metrics": metrics,
        "progress": progress,
        "situation": situation,
        "situation_label": {
            "achieved": "Atingida",
            "on_track": "No ritmo",
            "at_risk": "Em risco",
            "no_data": "Sem dados",
            "closed": "Encerrada",
        }[situation],
        "projection": {
            "leads": round(metrics["leads_received"] * projection_factor),
            "won": round(metrics["leads_won"] * projection_factor),
            "approved_value": (metrics["approved_value"] * Decimal(str(projection_factor))).quantize(
                Decimal("0.01"),
            ),
        },
    }


def active_goal_for_salesperson(*, salesperson, at_date=None):
    at_date = at_date or timezone.localdate()
    return (
        SalesGoal.objects.filter(
            salesperson=salesperson,
            is_active=True,
            start_date__lte=at_date,
            end_date__gte=at_date,
        )
        .order_by("-start_date")
        .first()
    )


def team_summary(*, user, start, end):
    salespersons = salespersons_for_scope(user=user)
    rows = [compute_salesperson_metrics(salesperson=sp, start=start, end=end) for sp in salespersons]
    return {
        "total_score": sum(r["total_score"] for r in rows),
        "total_received": sum(r["leads_received"] for r in rows),
        "total_won": sum(r["leads_won"] for r in rows),
        "total_approved_value": sum(r["approved_value"] for r in rows),
        "rows": rows,
        "inactive_count": salespersons.filter(
            pk__in=[r["salesperson"].pk for r in rows if r["leads_received"] == 0],
        ).count(),
        "goals_at_risk": sum(
            1
            for sp in salespersons
            for goal in SalesGoal.objects.filter(
                salesperson=sp,
                is_active=True,
                start_date__lte=timezone.localdate(),
                end_date__gte=timezone.localdate(),
            )
            if compute_goal_progress(goal=goal)["situation"] == "at_risk"
        ),
    }
