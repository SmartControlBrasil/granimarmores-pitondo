# ruff: noqa: EM101
from after_sales.models import ConsentScope
from after_sales.models import ConsentStatus
from after_sales.models import MediaUsageConsent
from media_library.models import MediaVisibility


def evaluate_media_consent(asset):
    """Avalia consentimento reutilizando MediaUsageConsent do pós-venda."""
    category = asset.category
    requires = bool(category and category.requires_consent)
    identifiable = bool(asset.customer_id or asset.sales_order_id or asset.installation_schedule_id)

    if not identifiable and not requires:
        return "not_required"

    consent = asset.consent
    if consent is None and asset.customer_id:
        consent = (
            MediaUsageConsent.objects.filter(customer_id=asset.customer_id)
            .order_by("-created_at")
            .first()
        )

    if consent is None:
        return "missing" if (identifiable or requires) else "not_required"

    if consent.consent_status == ConsentStatus.PENDING:
        return "pending"
    if consent.consent_status == ConsentStatus.DENIED:
        return "denied"
    if consent.consent_status == ConsentStatus.REVOKED:
        return "revoked"
    if consent.consent_status == ConsentStatus.GRANTED:
        return "granted"
    return "missing"


def consent_allows_scope(asset, scope: str) -> bool:
    result = evaluate_media_consent(asset)
    if result == "not_required":
        return True
    if result != "granted":
        return False
    consent = asset.consent
    if consent is None and asset.customer_id:
        consent = (
            MediaUsageConsent.objects.filter(
                customer_id=asset.customer_id,
                consent_status=ConsentStatus.GRANTED,
            )
            .order_by("-created_at")
            .first()
        )
    if consent is None:
        return False
    if consent.consent_scope == ConsentScope.ALL:
        return True
    if consent.consent_scope == scope:
        return True
    # Portfólio não implica publicidade automaticamente
    if scope == ConsentScope.PORTFOLIO and consent.consent_scope in {
        ConsentScope.PORTFOLIO,
        ConsentScope.WEBSITE,
        ConsentScope.ALL,
    }:
        return True
    return False


def assert_public_visibility_allowed(asset):
    if asset.visibility != MediaVisibility.PUBLIC_APPROVED:
        return
    result = evaluate_media_consent(asset)
    if result in {"denied", "revoked", "pending", "missing"}:
        from django.core.exceptions import ValidationError

        raise ValidationError(
            f"Visibilidade pública bloqueada: consentimento={result}.",
        )
