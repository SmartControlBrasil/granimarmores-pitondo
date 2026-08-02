# ruff: noqa: PLR0913
from datetime import datetime
from datetime import timedelta
from decimal import Decimal

from django.db.models import Count
from django.db.models import Q
from django.db.models import Sum
from django.utils import timezone

from access_control.services.authorization import user_has_permission
from after_sales.models import ConsentStatus
from after_sales.models import MediaUsageConsent
from media_library.models import MediaAsset
from media_library.models import MediaStatus
from media_library.models import MediaType
from media_library.models import MediaVisibility
from media_library.models import PublicationCandidate
from media_library.models import TechnicalReviewStatus
from media_library.services.consent import evaluate_media_consent
from production.models import InstallationSchedule
from production.models import ScheduleStatus


def media_queryset_for_user(user):
    qs = MediaAsset.objects.select_related(
        "category",
        "customer",
        "sales_order",
        "uploaded_by",
        "consent",
    ).exclude(status=MediaStatus.DELETED)
    if user_has_permission(user, "media_assets.view_all"):
        return qs
    if not user_has_permission(user, "media_assets.view"):
        return qs.none()

    filters = Q(uploaded_by=user) | Q(created_by=user)
    salesperson = getattr(user, "salesperson", None)
    if salesperson:
        filters |= Q(customer__assigned_salesperson=salesperson)
        filters |= Q(sales_order__salesperson=salesperson)
        filters |= Q(lead__assigned_salesperson=salesperson)
    qs = qs.filter(filters)
    if not user_has_permission(user, "media_private_files.view"):
        qs = qs.filter(
            Q(visibility=MediaVisibility.PRIVATE, uploaded_by=user)
            | ~Q(visibility=MediaVisibility.PRIVATE),
        )
    return qs.distinct()


def filter_media(qs, params):
    if params.get("q"):
        q = params["q"]
        qs = qs.filter(
            Q(code__icontains=q)
            | Q(title__icontains=q)
            | Q(original_filename__icontains=q)
            | Q(customer__name__icontains=q)
            | Q(sales_order__number__icontains=q),
        )
    for field in ["media_type", "status", "visibility"]:
        if params.get(field):
            qs = qs.filter(**{field: params[field]})
    if params.get("category"):
        qs = qs.filter(category_id=params["category"])
    if params.get("customer"):
        qs = qs.filter(customer_id=params["customer"])
    if params.get("sales_order"):
        qs = qs.filter(sales_order_id=params["sales_order"])
    if params.get("production_order"):
        qs = qs.filter(production_order_id=params["production_order"])
    if params.get("production_piece"):
        qs = qs.filter(production_piece_id=params["production_piece"])
    if params.get("material"):
        qs = qs.filter(material_id=params["material"])
    if params.get("slab"):
        qs = qs.filter(slab_id=params["slab"])
    if params.get("installation"):
        qs = qs.filter(installation_schedule_id=params["installation"])
    if params.get("after_sales"):
        qs = qs.filter(after_sales_case_id=params["after_sales"])
    if params.get("tag"):
        qs = qs.filter(tags__slug=params["tag"])
    if params.get("portfolio") == "1":
        qs = qs.filter(is_portfolio_approved=True)
    if params.get("no_category") == "1":
        qs = qs.filter(category__isnull=True)
    if params.get("no_link") == "1":
        qs = qs.filter(
            customer__isnull=True,
            sales_order__isnull=True,
            production_order__isnull=True,
            material__isnull=True,
            after_sales_case__isnull=True,
        )
    if params.get("uploaded_by"):
        qs = qs.filter(uploaded_by_id=params["uploaded_by"])
    if params.get("start"):
        qs = qs.filter(uploaded_at__date__gte=params["start"])
    if params.get("end"):
        qs = qs.filter(uploaded_at__date__lte=params["end"])
    return qs.distinct()


def parse_period(request):
    period = request.GET.get("period", "30d")
    now = timezone.now()
    today = timezone.localdate()
    if period == "today":
        start = timezone.make_aware(datetime.combine(today, datetime.min.time()))
    elif period == "7d":
        start = now - timedelta(days=7)
    elif period == "month":
        start = timezone.make_aware(datetime.combine(today.replace(day=1), datetime.min.time()))
    else:
        start = now - timedelta(days=30)
    return start, now, period


def build_media_alerts(user):
    alerts = []
    qs = media_queryset_for_user(user)
    no_cat = qs.filter(category__isnull=True).count()
    if no_cat:
        alerts.append({"level": "warning", "message": f"{no_cat} mídia(s) sem categoria"})
    no_link = qs.filter(
        customer__isnull=True,
        sales_order__isnull=True,
        production_order__isnull=True,
        material__isnull=True,
        after_sales_case__isnull=True,
    ).count()
    if no_link:
        alerts.append({"level": "warning", "message": f"{no_link} mídia(s) sem vínculo"})
    dups = qs.filter(duplicate_of__isnull=False).count()
    if dups:
        alerts.append({"level": "info", "message": f"{dups} upload(s) com duplicidade detectada"})
    public_bad = 0
    for asset in qs.filter(visibility=MediaVisibility.PUBLIC_APPROVED)[:100]:
        if evaluate_media_consent(asset) in {"missing", "denied", "revoked", "pending"}:
            public_bad += 1
    if public_bad:
        alerts.append({"level": "danger", "message": f"{public_bad} mídia(s) pública(s) sem consentimento válido"})
    revoked_portfolio = 0
    for asset in qs.filter(is_portfolio_approved=True).select_related("consent")[:100]:
        if evaluate_media_consent(asset) == "revoked":
            revoked_portfolio += 1
    if revoked_portfolio:
        alerts.append(
            {
                "level": "danger",
                "message": f"{revoked_portfolio} mídia(s) no portfólio com consentimento revogado",
            },
        )
    no_alt = qs.filter(is_portfolio_approved=True, alt_text="").count()
    if no_alt:
        alerts.append({"level": "warning", "message": f"{no_alt} candidata(s) a portfólio sem alt text"})
    rejected_pub = PublicationCandidate.objects.filter(
        asset__status=MediaStatus.REJECTED,
    ).exclude(status="cancelled").count()
    if rejected_pub:
        alerts.append(
            {
                "level": "warning",
                "message": f"{rejected_pub} candidata(s) de publicação com mídia rejeitada",
            },
        )
    return alerts


def media_dashboard_metrics(*, user, start=None, end=None):
    qs = media_queryset_for_user(user)
    period_qs = qs
    if start:
        period_qs = period_qs.filter(uploaded_at__gte=start)
    if end:
        period_qs = period_qs.filter(uploaded_at__lte=end)

    space = qs.aggregate(total=Sum("file_size"))["total"] or 0
    pending_consent = MediaUsageConsent.objects.filter(consent_status=ConsentStatus.PENDING).count()
    return {
        "total": qs.count(),
        "uploads_period": period_qs.count(),
        "images": qs.filter(media_type=MediaType.IMAGE).count(),
        "documents": qs.filter(media_type=MediaType.DOCUMENT).count(),
        "no_category": qs.filter(category__isnull=True).count(),
        "no_link": qs.filter(
            customer__isnull=True,
            sales_order__isnull=True,
            production_order__isnull=True,
            material__isnull=True,
        ).count(),
        "under_review": qs.filter(
            Q(status=MediaStatus.UNDER_REVIEW)
            | Q(technical_review_status=TechnicalReviewStatus.PENDING),
        ).count(),
        "pending_consent": pending_consent,
        "denied_consent": MediaUsageConsent.objects.filter(consent_status=ConsentStatus.DENIED).count(),
        "revoked_consent": MediaUsageConsent.objects.filter(consent_status=ConsentStatus.REVOKED).count(),
        "portfolio_approved": qs.filter(is_portfolio_approved=True).count(),
        "rejected": qs.filter(status=MediaStatus.REJECTED).count(),
        "space_bytes": space,
        "space_mb": (Decimal(space) / Decimal(1024 * 1024)).quantize(Decimal("0.01")),
        "by_category": list(
            qs.values("category__name").annotate(total=Count("id")).order_by("-total")[:10],
        ),
        "by_user": list(
            period_qs.values("uploaded_by__username").annotate(total=Count("id")).order_by("-total")[:10],
        ),
        "alerts": build_media_alerts(user),
    }


def main_dashboard_media_summary(user):
    if not (
        user_has_permission(user, "media_dashboard.view")
        or user_has_permission(user, "media_assets.view")
    ):
        return None
    qs = media_queryset_for_user(user)
    return {
        "under_review": qs.filter(
            Q(status=MediaStatus.UNDER_REVIEW)
            | Q(technical_review_status=TechnicalReviewStatus.PENDING, status=MediaStatus.CLASSIFIED),
        ).count(),
        "pending_consent": MediaUsageConsent.objects.filter(consent_status=ConsentStatus.PENDING).count(),
        "portfolio_candidates": qs.filter(
            visibility=MediaVisibility.PORTFOLIO_CANDIDATE,
            is_portfolio_approved=False,
            technical_review_status=TechnicalReviewStatus.APPROVED,
        ).count(),
        "problems": qs.filter(
            Q(category__isnull=True) | Q(status=MediaStatus.REJECTED) | Q(duplicate_of__isnull=False),
        ).count(),
    }


def portfolio_queryset(user):
    return media_queryset_for_user(user).filter(
        is_portfolio_approved=True,
        status=MediaStatus.APPROVED,
        technical_review_status=TechnicalReviewStatus.APPROVED,
    ).exclude(alt_text="")


def review_queues(user):
    qs = media_queryset_for_user(user)
    return {
        "awaiting_classification": qs.filter(status=MediaStatus.UPLOADED),
        "awaiting_technical": qs.filter(
            technical_review_status=TechnicalReviewStatus.PENDING,
        ).exclude(status__in=[MediaStatus.ARCHIVED, MediaStatus.REJECTED]),
        "awaiting_consent": qs.filter(customer__isnull=False, consent__isnull=True),
        "awaiting_portfolio": qs.filter(
            technical_review_status=TechnicalReviewStatus.APPROVED,
            is_portfolio_approved=False,
            category__is_portfolio_eligible=True,
        ),
        "rejected": qs.filter(status=MediaStatus.REJECTED),
        "revoked_consent": qs.filter(
            is_portfolio_approved=True,
            consent__consent_status=ConsentStatus.REVOKED,
        ),
    }
