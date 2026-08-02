from datetime import timedelta
from decimal import Decimal

from django.db.models import Count
from django.db.models import Q
from django.utils import timezone

from access_control.services.authorization import user_has_permission
from documents.models import AcceptanceStatus
from documents.models import Confidentiality
from documents.models import DocumentStatus
from documents.models import DocumentType
from documents.models import ManagedDocument
from documents.models import ReviewStatus
from documents.models import VersionStatus
from documents.services.lifecycle import warning_days


def _salesperson_for_user(user):
    return getattr(user, "salesperson", None)


def can_view_confidential(user):
    return user_has_permission(user, "document_confidential.view") or user_has_permission(
        user,
        "documents.view_all",
    )


def documents_queryset_for_user(user):
    qs = ManagedDocument.objects.select_related(
        "document_type",
        "customer",
        "supplier",
        "quote",
        "sales_order",
        "purchase_order",
        "current_version",
        "responsible_user",
        "owner",
    )
    if not can_view_confidential(user):
        qs = qs.exclude(confidentiality=Confidentiality.CONFIDENTIAL)

    if user_has_permission(user, "documents.view_all"):
        return qs
    if not user_has_permission(user, "documents.view"):
        return qs.none()

    sp = _salesperson_for_user(user)
    filters = Q(owner=user) | Q(responsible_user=user) | Q(created_by=user)
    if sp:
        filters |= Q(customer__assigned_salesperson=sp) | Q(quote__salesperson=sp) | Q(
            sales_order__salesperson=sp,
        ) | Q(lead__assigned_salesperson=sp)
    if user_has_permission(user, "purchase_orders.view"):
        filters |= Q(purchase_order__isnull=False) | Q(supplier__isnull=False)
    if user_has_permission(user, "after_sales_cases.view"):
        filters |= Q(after_sales_case__isnull=False) | Q(warranty__isnull=False)
    return qs.filter(filters).distinct()


def document_types_queryset():
    return DocumentType.objects.filter(is_active=True)


def document_dashboard_metrics(*, user):
    qs = documents_queryset_for_user(user)
    today = timezone.localdate()
    warn = today + timedelta(days=warning_days())
    return {
        "active": qs.filter(status=DocumentStatus.ACTIVE).count(),
        "draft": qs.filter(status=DocumentStatus.DRAFT).count(),
        "under_review": qs.filter(status=DocumentStatus.UNDER_REVIEW).count(),
        "approved": qs.filter(status=DocumentStatus.APPROVED).count(),
        "awaiting_send": qs.filter(status=DocumentStatus.APPROVED).count(),
        "awaiting_acceptance": qs.filter(
            requires_acceptance=True,
            status__in=[DocumentStatus.SENT, DocumentStatus.VIEWED, DocumentStatus.APPROVED],
        ).count(),
        "awaiting_signature": qs.filter(
            requires_signature=True,
            status__in=[DocumentStatus.ACCEPTED, DocumentStatus.SENT, DocumentStatus.VIEWED],
        ).count(),
        "expiring": qs.filter(
            status=DocumentStatus.ACTIVE,
            expiration_date__gte=today,
            expiration_date__lte=warn,
        ).count(),
        "expired": qs.filter(status=DocumentStatus.EXPIRED).count(),
        "rejected": qs.filter(status=DocumentStatus.REJECTED).count(),
        "cancelled": qs.filter(status=DocumentStatus.CANCELLED).count(),
        "renewed": qs.filter(renewed_from__isnull=False).count(),
        "without_responsible": qs.filter(responsible_user__isnull=True).count(),
        "without_file": qs.filter(
            current_version__isnull=False,
            current_version__media_asset__isnull=True,
            current_version__content="",
        ).count(),
        "pending_versions": qs.filter(
            current_version__status__in=[VersionStatus.DRAFT, VersionStatus.UNDER_REVIEW],
        ).count(),
        "by_type": list(
            qs.values("document_type__name").annotate(total=Count("id")).order_by("-total")[:10],
        ),
    }


def document_alerts(*, user):
    qs = documents_queryset_for_user(user)
    today = timezone.localdate()
    warn = today + timedelta(days=warning_days())
    alerts = []
    for doc in qs.filter(status=DocumentStatus.ACTIVE, expiration_date__lt=today)[:20]:
        alerts.append({"level": "danger", "text": f"{doc.number} vencido em {doc.expiration_date}"})
    for doc in qs.filter(
        status=DocumentStatus.ACTIVE,
        expiration_date__gte=today,
        expiration_date__lte=warn,
    )[:20]:
        alerts.append({"level": "warning", "text": f"{doc.number} vence em {doc.expiration_date}"})
    for doc in qs.filter(responsible_user__isnull=True).exclude(
        status__in=[DocumentStatus.CANCELLED, DocumentStatus.TERMINATED, DocumentStatus.ARCHIVED],
    )[:10]:
        alerts.append({"level": "warning", "text": f"{doc.number} sem responsável"})
    for doc in qs.filter(status=DocumentStatus.APPROVED)[:10]:
        alerts.append({"level": "info", "text": f"{doc.number} aprovado e não enviado"})
    for doc in qs.filter(
        status__in=[DocumentStatus.SENT, DocumentStatus.VIEWED],
        requires_acceptance=True,
    )[:10]:
        alerts.append({"level": "info", "text": f"{doc.number} aguardando aceite"})
    return alerts


def main_dashboard_documents_summary(user):
    if not (
        user_has_permission(user, "document_dashboard.view")
        or user_has_permission(user, "documents.view")
        or user_has_permission(user, "documents.view_all")
    ):
        return None
    qs = documents_queryset_for_user(user)
    today = timezone.localdate()
    warn = today + timedelta(days=warning_days())
    return {
        "awaiting_approval": qs.filter(status=DocumentStatus.UNDER_REVIEW).count(),
        "expiring": qs.filter(
            status=DocumentStatus.ACTIVE,
            expiration_date__gte=today,
            expiration_date__lte=warn,
        ).count(),
        "awaiting_acceptance": qs.filter(
            requires_acceptance=True,
            status__in=[DocumentStatus.SENT, DocumentStatus.VIEWED, DocumentStatus.APPROVED],
        ).count(),
    }


def executive_document_metrics(*, user, start=None, end=None):
    if not (
        user_has_permission(user, "executive_dashboard.view_documents")
        or user_has_permission(user, "executive_dashboard.view")
        or user_has_permission(user, "document_dashboard.view")
    ):
        return {}
    qs = documents_queryset_for_user(user)
    today = timezone.localdate()
    warn = today + timedelta(days=warning_days())
    return {
        "active_contracts": qs.filter(
            status=DocumentStatus.ACTIVE,
            document_type__category="contract",
        ).count(),
        "expiring": qs.filter(
            status=DocumentStatus.ACTIVE,
            expiration_date__gte=today,
            expiration_date__lte=warn,
        ).count(),
        "awaiting_acceptance": qs.filter(
            requires_acceptance=True,
            status__in=[DocumentStatus.SENT, DocumentStatus.VIEWED, DocumentStatus.APPROVED],
        ).count(),
        "expired": qs.filter(status=DocumentStatus.EXPIRED).count(),
        "supplier_expired": qs.filter(
            status=DocumentStatus.EXPIRED,
            supplier__isnull=False,
        ).count(),
    }
