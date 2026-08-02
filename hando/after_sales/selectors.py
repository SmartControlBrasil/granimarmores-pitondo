# ruff: noqa: PLR0913
from datetime import datetime
from datetime import timedelta
from decimal import Decimal

from django.db.models import Avg
from django.db.models import Count
from django.db.models import Q
from django.utils import timezone

from access_control.services.authorization import user_has_permission
from after_sales.models import AfterSalesCase
from after_sales.models import CaseSeverity
from after_sales.models import CaseStatus
from after_sales.models import ConsentStatus
from after_sales.models import CustomerReferral
from after_sales.models import CustomerSatisfactionSurvey
from after_sales.models import InstallationPendingItem
from after_sales.models import MediaUsageConsent
from after_sales.models import OPEN_CASE_STATUSES
from after_sales.models import PendingStatus
from after_sales.models import ReviewRequest
from after_sales.models import SurveyStatus
from after_sales.models import WarrantyRecord


def cases_queryset_for_user(user):
    qs = AfterSalesCase.objects.select_related(
        "customer",
        "sales_order",
        "assigned_user",
        "assigned_salesperson",
        "warranty",
    )
    if user_has_permission(user, "after_sales_cases.view_all"):
        return qs
    if not user_has_permission(user, "after_sales_cases.view"):
        return qs.none()
    salesperson = getattr(user, "salesperson", None)
    filters = Q(assigned_user=user) | Q(created_by=user)
    if salesperson:
        filters |= Q(assigned_salesperson=salesperson) | Q(sales_order__salesperson=salesperson)
        filters |= Q(customer__assigned_salesperson=salesperson)
    return qs.filter(filters)


def filter_cases(qs, params):
    if params.get("q"):
        q = params["q"]
        qs = qs.filter(
            Q(code__icontains=q)
            | Q(subject__icontains=q)
            | Q(customer__name__icontains=q)
            | Q(sales_order__number__icontains=q),
        )
    for field in ["status", "case_type", "priority", "severity"]:
        if params.get(field):
            qs = qs.filter(**{field: params[field]})
    if params.get("assigned_user"):
        qs = qs.filter(assigned_user_id=params["assigned_user"])
    if params.get("salesperson"):
        qs = qs.filter(assigned_salesperson_id=params["salesperson"])
    if params.get("customer"):
        qs = qs.filter(customer_id=params["customer"])
    if params.get("warranty") == "1":
        qs = qs.filter(warranty__isnull=False)
    if params.get("critical") == "1":
        qs = qs.filter(severity=CaseSeverity.CRITICAL)
    if params.get("open") == "1":
        qs = qs.filter(status__in=OPEN_CASE_STATUSES)
    if params.get("no_owner") == "1":
        qs = qs.filter(assigned_user__isnull=True, assigned_salesperson__isnull=True)
    if params.get("overdue") == "1":
        qs = qs.filter(next_action_at__lt=timezone.now()).exclude(
            status__in=[CaseStatus.CLOSED, CaseStatus.CANCELLED, CaseStatus.REJECTED],
        )
    if params.get("start"):
        qs = qs.filter(opened_at__date__gte=params["start"])
    if params.get("end"):
        qs = qs.filter(opened_at__date__lte=params["end"])
    return qs


def parse_period(request):
    period = request.GET.get("period", "30d")
    now = timezone.now()
    today = timezone.localdate()
    if period == "today":
        start = timezone.make_aware(datetime.combine(today, datetime.min.time()))
        end = now
    elif period == "7d":
        start = now - timedelta(days=7)
        end = now
    elif period == "month":
        start = timezone.make_aware(datetime.combine(today.replace(day=1), datetime.min.time()))
        end = now
    elif period == "custom":
        start_s = request.GET.get("start")
        end_s = request.GET.get("end")
        start = timezone.make_aware(datetime.fromisoformat(start_s)) if start_s else now - timedelta(days=30)
        end = timezone.make_aware(datetime.fromisoformat(end_s)) if end_s else now
    else:
        start = now - timedelta(days=30)
        end = now
    return start, end, period


def _safe_rate(part, total):
    if not total:
        return Decimal("0.0")
    return (Decimal(part) / Decimal(total) * Decimal("100")).quantize(Decimal("0.1"))


def after_sales_dashboard_metrics(*, user, start=None, end=None, **filters):
    qs = cases_queryset_for_user(user)
    period_qs = qs
    if start:
        period_qs = period_qs.filter(opened_at__gte=start)
    if end:
        period_qs = period_qs.filter(opened_at__lte=end)
    if filters.get("assigned_user"):
        period_qs = period_qs.filter(assigned_user_id=filters["assigned_user"])
    if filters.get("case_type"):
        period_qs = period_qs.filter(case_type=filters["case_type"])
    if filters.get("status"):
        period_qs = period_qs.filter(status=filters["status"])

    open_qs = qs.filter(status__in=OPEN_CASE_STATUSES)
    resolved = period_qs.filter(status__in=[CaseStatus.RESOLVED, CaseStatus.CLOSED]).count()
    closed = period_qs.filter(status=CaseStatus.CLOSED).count()
    reopened = period_qs.filter(history__action="reopened").distinct().count()
    total_period = period_qs.count() or 0

    first_responses = [
        (c.first_response_at - c.opened_at).total_seconds() / 3600
        for c in period_qs.exclude(first_response_at__isnull=True)[:200]
        if c.first_response_at and c.opened_at
    ]
    resolutions = [
        (c.resolved_at - c.opened_at).total_seconds() / 3600
        for c in period_qs.exclude(resolved_at__isnull=True)[:200]
        if c.resolved_at and c.opened_at
    ]

    surveys = CustomerSatisfactionSurvey.objects.filter(status=SurveyStatus.RESPONDED)
    if start:
        surveys = surveys.filter(responded_at__gte=start)
    avg_satisfaction = surveys.aggregate(avg=Avg("overall_score"))["avg"]

    pending = InstallationPendingItem.objects.filter(
        status__in=[PendingStatus.OPEN, PendingStatus.SCHEDULED, PendingStatus.IN_PROGRESS],
    )
    overdue_pending = pending.filter(due_date__lt=timezone.localdate()).count()

    today = timezone.localdate()
    from scheduling.models import EventType
    from scheduling.models import OperationalEvent

    visits_today = OperationalEvent.objects.filter(
        event_type=EventType.TECHNICAL_ASSISTANCE,
        start_at__date=today,
        after_sales_case__isnull=False,
    ).count()

    return {
        "open_cases": open_qs.count(),
        "new_period": period_qs.filter(status=CaseStatus.NEW).count(),
        "critical": open_qs.filter(severity=CaseSeverity.CRITICAL).count(),
        "no_owner": open_qs.filter(assigned_user__isnull=True, assigned_salesperson__isnull=True).count(),
        "awaiting_customer": qs.filter(status=CaseStatus.AWAITING_CUSTOMER).count(),
        "visit_scheduled": qs.filter(status=CaseStatus.VISIT_SCHEDULED).count(),
        "in_warranty": qs.filter(warranty_eligible="eligible").count(),
        "out_of_warranty": qs.filter(warranty_eligible="not_eligible").count(),
        "resolved": resolved,
        "closed": closed,
        "reopened": reopened,
        "avg_first_response_hours": round(sum(first_responses) / len(first_responses), 1) if first_responses else 0,
        "avg_resolution_hours": round(sum(resolutions) / len(resolutions), 1) if resolutions else 0,
        "resolution_rate": _safe_rate(resolved, total_period),
        "reopen_rate": _safe_rate(reopened, closed or 1),
        "by_type": list(period_qs.values("case_type").annotate(total=Count("id")).order_by("-total")[:10]),
        "by_root_cause": list(
            period_qs.exclude(root_cause="")
            .values("root_cause")
            .annotate(total=Count("id"))
            .order_by("-total")[:10],
        ),
        "by_responsibility": list(
            period_qs.exclude(responsibility="")
            .values("responsibility")
            .annotate(total=Count("id"))
            .order_by("-total"),
        ),
        "open_pending": pending.count(),
        "overdue_pending": overdue_pending,
        "avg_satisfaction": round(avg_satisfaction, 2) if avg_satisfaction else None,
        "would_recommend": surveys.filter(would_recommend=True).count(),
        "review_requests": ReviewRequest.objects.count(),
        "media_granted": MediaUsageConsent.objects.filter(consent_status=ConsentStatus.GRANTED).count(),
        "referrals": CustomerReferral.objects.count(),
        "visits_today": visits_today,
        "alerts": build_after_sales_alerts(user),
    }


def build_after_sales_alerts(user):
    alerts = []
    qs = cases_queryset_for_user(user).exclude(
        status__in=[CaseStatus.CLOSED, CaseStatus.CANCELLED, CaseStatus.REJECTED],
    )
    now = timezone.now()

    critical_no_owner = qs.filter(
        severity=CaseSeverity.CRITICAL,
        assigned_user__isnull=True,
        assigned_salesperson__isnull=True,
    ).count()
    if critical_no_owner:
        alerts.append({"level": "danger", "message": f"{critical_no_owner} caso(s) crítico(s) sem responsável"})

    no_contact = qs.filter(first_response_at__isnull=True, opened_at__lt=now - timedelta(hours=24)).count()
    if no_contact:
        alerts.append({"level": "warning", "message": f"{no_contact} caso(s) sem primeiro contato"})

    overdue = qs.filter(next_action_at__lt=now).count()
    if overdue:
        alerts.append({"level": "warning", "message": f"{overdue} próxima(s) ação(ões) vencida(s)"})

    resolved_open = cases_queryset_for_user(user).filter(status=CaseStatus.RESOLVED).count()
    if resolved_open:
        alerts.append({"level": "info", "message": f"{resolved_open} caso(s) resolvido(s) não fechado(s)"})

    no_root = qs.filter(case_type__in=[
        "technical_assistance",
        "warranty_request",
        "material_issue",
        "installation_issue",
    ], root_cause="").count()
    if no_root:
        alerts.append({"level": "warning", "message": f"{no_root} caso(s) técnico(s) sem causa raiz"})

    overdue_pending = InstallationPendingItem.objects.filter(
        status__in=[PendingStatus.OPEN, PendingStatus.SCHEDULED],
        due_date__lt=timezone.localdate(),
    ).count()
    if overdue_pending:
        alerts.append({"level": "danger", "message": f"{overdue_pending} pendência(s) de instalação vencida(s)"})

    low_sat = CustomerSatisfactionSurvey.objects.filter(
        status=SurveyStatus.RESPONDED,
        overall_score__lte=2,
    ).count()
    if low_sat:
        alerts.append({"level": "warning", "message": f"{low_sat} pesquisa(s) com satisfação baixa"})

    return alerts


def main_dashboard_after_sales_summary(user):
    if not (
        user_has_permission(user, "after_sales_dashboard.view")
        or user_has_permission(user, "after_sales_cases.view")
    ):
        return None
    qs = cases_queryset_for_user(user)
    today = timezone.localdate()
    from scheduling.models import EventType
    from scheduling.models import OperationalEvent

    surveys = CustomerSatisfactionSurvey.objects.filter(
        status=SurveyStatus.RESPONDED,
        responded_at__gte=timezone.now() - timedelta(days=30),
    )
    avg = surveys.aggregate(avg=Avg("overall_score"))["avg"]
    return {
        "open_cases": qs.filter(status__in=OPEN_CASE_STATUSES).count(),
        "critical": qs.filter(
            status__in=OPEN_CASE_STATUSES,
            severity=CaseSeverity.CRITICAL,
        ).count(),
        "overdue_pending": InstallationPendingItem.objects.filter(
            status__in=[PendingStatus.OPEN, PendingStatus.SCHEDULED],
            due_date__lt=today,
        ).count(),
        "visits_today": OperationalEvent.objects.filter(
            event_type=EventType.TECHNICAL_ASSISTANCE,
            start_at__date=today,
            after_sales_case__isnull=False,
        ).count(),
        "avg_satisfaction": round(avg, 2) if avg else None,
    }
