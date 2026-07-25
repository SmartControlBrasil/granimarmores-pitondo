# ruff: noqa: EM101, TRY003

from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from access_control.services.authorization import user_has_permission
from audit.services import record_audit_event
from quotes.models import CommercialPolicy
from quotes.models import QuoteStatus
from quotes.services.calculation import calculate_quote
from quotes.services.versioning import create_version

VALID_TRANSITIONS = {
    QuoteStatus.DRAFT: {QuoteStatus.UNDER_REVIEW, QuoteStatus.CANCELLED},
    QuoteStatus.UNDER_REVIEW: {QuoteStatus.PENDING_APPROVAL, QuoteStatus.CANCELLED},
    QuoteStatus.PENDING_APPROVAL: {
        QuoteStatus.APPROVED,
        QuoteStatus.REJECTED,
        QuoteStatus.CANCELLED,
    },
    QuoteStatus.APPROVED: {QuoteStatus.SENT, QuoteStatus.CANCELLED},
    QuoteStatus.SENT: {QuoteStatus.VIEWED, QuoteStatus.ACCEPTED, QuoteStatus.EXPIRED},
}


def active_policy():
    policy = CommercialPolicy.objects.filter(is_active=True).first()
    if policy:
        return policy
    return CommercialPolicy.objects.create()


def approval_reasons(quote, *, manual=False):
    policy = active_policy()
    reasons = []
    if manual:
        reasons.append("Aprovação manual solicitada.")
    if (
        quote.discount_type == "percentage"
        and quote.discount_value > policy.salesperson_max_discount_percentage
    ):
        reasons.append("Desconto acima do limite do vendedor.")
    if quote.gross_margin_percentage < policy.minimum_margin_percentage:
        reasons.append("Margem abaixo da política comercial.")
    if quote.grand_total > policy.approval_required_above:
        reasons.append("Valor total acima do limite configurado.")
    if quote.items.filter(needs_price_approval=True).exists():
        reasons.append("Há item abaixo do preço mínimo.")
    return reasons


def assert_transition(quote, target_status):
    if target_status not in VALID_TRANSITIONS.get(quote.status, set()):
        message = f"Transição inválida: {quote.status} -> {target_status}."
        raise ValidationError(message)


def change_status(*, quote, target_status, actor, request=None, metadata=None):
    old_status = quote.status
    assert_transition(quote, target_status)
    quote.status = target_status
    now = timezone.now()
    if target_status == QuoteStatus.APPROVED:
        quote.approved_at = now
        quote.approved_by = actor
    elif target_status == QuoteStatus.SENT:
        quote.sent_at = now
        quote.sent_by = actor
    elif target_status == QuoteStatus.CANCELLED:
        quote.cancelled_at = now
        quote.cancelled_by = actor
    quote.updated_by = actor
    quote.save()
    data = {
        "quote_number": quote.number,
        "status_from": old_status,
        "status_to": target_status,
    }
    data.update(metadata or {})
    record_audit_event(
        request=request,
        user=actor,
        event_type="configuration",
        module="quotes",
        action=f"quote_{target_status}",
        obj=quote,
        metadata=data,
    )
    return quote


@transaction.atomic
def submit_for_approval(*, quote, actor, request=None, manual=False):
    calculate_quote(quote)
    reasons = approval_reasons(quote, manual=manual)
    quote.requires_approval = bool(reasons)
    quote.approval_reasons = reasons
    quote.save()
    if quote.status == QuoteStatus.DRAFT:
        change_status(
            quote=quote,
            target_status=QuoteStatus.UNDER_REVIEW,
            actor=actor,
            request=request,
        )
    if quote.status == QuoteStatus.UNDER_REVIEW:
        change_status(
            quote=quote,
            target_status=QuoteStatus.PENDING_APPROVAL,
            actor=actor,
            request=request,
            metadata={"reasons": reasons},
        )
    return quote


@transaction.atomic
def approve_quote(*, quote, actor, request=None, note=""):
    if not user_has_permission(actor, "quotes.approve"):
        raise PermissionDenied("Usuário sem permissão para aprovar orçamento.")
    if quote.created_by_id == actor.id and not actor.is_superuser:
        raise PermissionDenied("Autor não pode aprovar o próprio orçamento.")
    calculate_quote(quote)
    change_status(
        quote=quote,
        target_status=QuoteStatus.APPROVED,
        actor=actor,
        request=request,
        metadata={"note": note[:120]},
    )
    return create_version(
        quote=quote,
        actor=actor,
        request=request,
        status=QuoteStatus.APPROVED,
    )


@transaction.atomic
def reject_quote(*, quote, actor, reason, request=None):
    if not reason:
        raise ValidationError("Motivo da rejeição é obrigatório.")
    if not user_has_permission(actor, "quotes.approve"):
        raise PermissionDenied("Usuário sem permissão para rejeitar orçamento.")
    quote.rejected_at = timezone.now()
    quote.rejected_by = actor
    quote.rejection_reason = reason
    quote.save()
    return change_status(
        quote=quote,
        target_status=QuoteStatus.REJECTED,
        actor=actor,
        request=request,
        metadata={"reason": reason[:120]},
    )


@transaction.atomic
def cancel_quote(*, quote, actor, reason, request=None):
    if not reason:
        raise ValidationError("Motivo do cancelamento é obrigatório.")
    quote.cancellation_reason = reason
    quote.save(update_fields=["cancellation_reason", "updated_at"])
    return change_status(
        quote=quote,
        target_status=QuoteStatus.CANCELLED,
        actor=actor,
        request=request,
        metadata={"reason": reason[:120]},
    )
