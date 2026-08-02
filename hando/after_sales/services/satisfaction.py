# ruff: noqa: EM101, PLR0913, TRY003
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from access_control.services.authorization import user_has_permission
from after_sales.models import ConsentStatus
from after_sales.models import CustomerReferral
from after_sales.models import CustomerSatisfactionSurvey
from after_sales.models import MediaUsageConsent
from after_sales.models import ReferralStatus
from after_sales.models import ReviewRequest
from after_sales.models import ReviewRequestStatus
from after_sales.models import SurveyStatus
from audit.services import record_audit_event


@transaction.atomic
def create_satisfaction_survey(*, actor, customer, survey_type, sales_order=None, after_sales_case=None, request=None):
    if not user_has_permission(actor, "customer_satisfaction.create"):
        raise PermissionDenied("Sem permissão para criar pesquisa.")
    if not sales_order and not after_sales_case:
        raise ValidationError("Pesquisa deve vincular pedido ou caso.")
    survey = CustomerSatisfactionSurvey.objects.create(
        customer=customer,
        sales_order=sales_order,
        after_sales_case=after_sales_case,
        survey_type=survey_type,
        status=SurveyStatus.PENDING,
        created_by=actor,
        updated_by=actor,
    )
    record_audit_event(request=request, user=actor, event_type="create", module="after_sales", action="survey_created", obj=survey)
    return survey


@transaction.atomic
def register_survey_response(
    *,
    survey,
    actor,
    overall_score=None,
    service_score=None,
    quality_score=None,
    delivery_score=None,
    installation_score=None,
    comments="",
    would_recommend=None,
    request=None,
):
    if not user_has_permission(actor, "customer_satisfaction.update"):
        raise PermissionDenied("Sem permissão para registrar resposta.")
    for score in [overall_score, service_score, quality_score, delivery_score, installation_score]:
        if score is not None and (score < 1 or score > 5):
            raise ValidationError("Notas devem estar entre 1 e 5.")
    survey.overall_score = overall_score
    survey.service_score = service_score
    survey.quality_score = quality_score
    survey.delivery_score = delivery_score
    survey.installation_score = installation_score
    survey.comments = comments
    survey.would_recommend = would_recommend
    survey.status = SurveyStatus.RESPONDED
    survey.responded_at = timezone.now()
    survey.updated_by = actor
    survey.full_clean()
    survey.save()
    record_audit_event(request=request, user=actor, event_type="update", module="after_sales", action="survey_responded", obj=survey)
    return survey


@transaction.atomic
def create_review_request(*, actor, customer, sales_order=None, channel="", notes="", request=None):
    if not user_has_permission(actor, "review_requests.create"):
        raise PermissionDenied("Sem permissão.")
    obj = ReviewRequest.objects.create(
        customer=customer,
        sales_order=sales_order,
        channel=channel,
        notes=notes,
        status=ReviewRequestStatus.REQUESTED,
        created_by=actor,
        updated_by=actor,
    )
    record_audit_event(request=request, user=actor, event_type="create", module="after_sales", action="review_requested", obj=obj)
    return obj


@transaction.atomic
def complete_review_request(*, review_request, actor, request=None):
    if not user_has_permission(actor, "review_requests.update"):
        raise PermissionDenied("Sem permissão.")
    review_request.status = ReviewRequestStatus.COMPLETED
    review_request.updated_by = actor
    review_request.save()
    record_audit_event(request=request, user=actor, event_type="update", module="after_sales", action="review_completed", obj=review_request)
    return review_request


@transaction.atomic
def record_media_consent(
    *,
    actor,
    customer,
    consent_status,
    consent_scope,
    sales_order=None,
    authorized_by_name="",
    notes="",
    request=None,
):
    if not user_has_permission(actor, "media_usage_consents.create"):
        raise PermissionDenied("Sem permissão.")
    obj = MediaUsageConsent.objects.create(
        customer=customer,
        sales_order=sales_order,
        consent_status=consent_status,
        consent_scope=consent_scope,
        authorized_by_name=authorized_by_name,
        notes=notes,
        recorded_by=actor,
        authorized_at=timezone.now() if consent_status == ConsentStatus.GRANTED else None,
        created_by=actor,
        updated_by=actor,
    )
    record_audit_event(request=request, user=actor, event_type="create", module="after_sales", action="media_consent_recorded", obj=obj)
    return obj


@transaction.atomic
def revoke_media_consent(*, consent, actor, notes="", request=None):
    if not user_has_permission(actor, "media_usage_consents.update"):
        raise PermissionDenied("Sem permissão.")
    consent.consent_status = ConsentStatus.REVOKED
    consent.revoked_at = timezone.now()
    if notes:
        consent.notes = notes
    consent.updated_by = actor
    consent.save()
    record_audit_event(request=request, user=actor, event_type="update", module="after_sales", action="media_consent_revoked", obj=consent)
    return consent


@transaction.atomic
def create_referral(*, actor, referring_customer, referred_name, sales_order=None, referred_phone="", referred_email="", notes="", request=None):
    if not user_has_permission(actor, "customer_referrals.create"):
        raise PermissionDenied("Sem permissão.")
    if not referred_name.strip():
        raise ValidationError("Nome do indicado obrigatório.")
    obj = CustomerReferral.objects.create(
        referring_customer=referring_customer,
        sales_order=sales_order,
        referred_name=referred_name.strip(),
        referred_phone=referred_phone,
        referred_email=referred_email,
        notes=notes,
        created_by=actor,
        updated_by=actor,
    )
    record_audit_event(request=request, user=actor, event_type="create", module="after_sales", action="referral_created", obj=obj)
    return obj


@transaction.atomic
def convert_referral_to_lead(*, referral, actor, request=None):
    if not (
        user_has_permission(actor, "customer_referrals.convert")
        or user_has_permission(actor, "customer_referrals.update")
    ):
        raise PermissionDenied("Sem permissão para converter indicação.")
    if referral.converted_lead_id:
        raise ValidationError("Indicação já convertida em lead.")
    if referral.status == ReferralStatus.CONVERTED:
        raise ValidationError("Indicação já convertida.")

    from commercial.lead_models import Lead
    from commercial.lead_models import LeadStatus
    from commercial.lead_numbering import next_lead_code
    from commercial.models import CommercialSource

    source = CommercialSource.objects.filter(
        channel_group="referral",
        is_active=True,
    ).order_by("display_order").first()
    if source is None:
        source = CommercialSource.objects.filter(slug="indicacao", is_active=True).first()

    from django.db.models import Q

    dup_q = Q(name__iexact=referral.referred_name)
    if referral.referred_phone:
        dup_q &= Q(phone=referral.referred_phone) | Q(whatsapp=referral.referred_phone)
    if Lead.objects.filter(dup_q).exists():
        raise ValidationError("Já existe lead semelhante para esta indicação.")

    lead = Lead.objects.create(
        code=next_lead_code(),
        name=referral.referred_name,
        phone=referral.referred_phone,
        email=referral.referred_email,
        commercial_source=source,
        status=LeadStatus.NEW,
        project_description=f"Indicação de {referral.referring_customer}",
        created_by=actor,
        updated_by=actor,
    )
    referral.converted_lead = lead
    referral.status = ReferralStatus.CONVERTED
    referral.updated_by = actor
    referral.save()
    record_audit_event(
        request=request,
        user=actor,
        event_type="create",
        module="after_sales",
        action="referral_converted_to_lead",
        obj=referral,
        metadata={"lead": lead.code},
    )
    return lead
