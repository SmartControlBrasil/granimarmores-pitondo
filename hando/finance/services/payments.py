# ruff: noqa: PLR0913
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from audit.services import record_audit_event
from finance.models import FinancialMovement
from finance.models import MovementType
from finance.models import PayablePayment
from finance.models import PaymentStatus
from finance.models import ReceivablePayment
from finance.models import TERMINAL_INSTALLMENT_STATUSES
from finance.services.balances import recalculate_installment_status
from finance.services.balances import recalculate_title_from_installments
from finance.services.numbering import next_movement_number
from finance.services.numbering import next_payable_payment_number
from finance.services.numbering import next_receivable_payment_number


def _create_movement(
    *,
    movement_type,
    account,
    amount,
    movement_date,
    description,
    actor,
    category=None,
    cost_center=None,
    reference_type="",
    reference_id=None,
    source_receivable_payment=None,
    source_payable_payment=None,
    reversal_of=None,
    transfer_group="",
):
    mov = FinancialMovement(
        number=next_movement_number(),
        movement_type=movement_type,
        financial_account=account,
        category=category,
        cost_center=cost_center,
        amount=amount,
        movement_date=movement_date,
        description=description,
        reference_type=reference_type,
        reference_id=reference_id,
        source_receivable_payment=source_receivable_payment,
        source_payable_payment=source_payable_payment,
        reversal_of=reversal_of,
        transfer_group=transfer_group,
        created_by=actor,
    )
    mov.save()
    return mov


@transaction.atomic
def register_receivable_payment(
    *,
    installment,
    amount,
    payment_date,
    payment_method,
    financial_account,
    actor,
    reference="",
    notes="",
    allow_overpay=False,
    request=None,
):
    if amount <= 0:
        raise ValidationError("Valor do recebimento deve ser positivo.")
    if installment.status in TERMINAL_INSTALLMENT_STATUSES:
        raise ValidationError("Parcela não está aberta para recebimento.")
    if amount > installment.outstanding_amount and not allow_overpay:
        raise ValidationError("Valor supera o saldo da parcela.")
    if reference:
        dup = ReceivablePayment.objects.filter(
            installment=installment,
            reference=reference,
            status=PaymentStatus.CONFIRMED,
        ).exists()
        if dup:
            raise ValidationError("Recebimento duplicado para a mesma referência.")

    payment = ReceivablePayment(
        number=next_receivable_payment_number(),
        installment=installment,
        payment_date=payment_date,
        amount=amount,
        payment_method=payment_method,
        financial_account=financial_account,
        reference=reference or "",
        notes=notes or "",
        status=PaymentStatus.CONFIRMED,
        created_by=actor,
        updated_by=actor,
    )
    payment.save()

    installment.paid_amount += amount
    installment.outstanding_amount = max(installment.original_amount - installment.paid_amount, Decimal("0.00"))
    # net of installment = original for simplicity (discount/interest handled on title)
    installment.outstanding_amount = max(
        installment.original_amount
        - installment.discount_amount
        + installment.interest_amount
        + installment.penalty_amount
        - installment.paid_amount,
        Decimal("0.00"),
    )
    recalculate_installment_status(installment)
    installment.save(
        update_fields=["paid_amount", "outstanding_amount", "status", "updated_at"],
    )

    title = installment.receivable
    recalculate_title_from_installments(title)
    title.updated_by = actor
    title.save(update_fields=["paid_amount", "outstanding_amount", "status", "updated_by", "updated_at"])

    _create_movement(
        movement_type=MovementType.INCOME,
        account=financial_account,
        amount=amount,
        movement_date=payment_date,
        description=f"Recebimento {payment.number} — {title.number}",
        actor=actor,
        category=title.category,
        cost_center=title.cost_center,
        reference_type="receivable_payment",
        reference_id=payment.pk,
        source_receivable_payment=payment,
    )

    if not financial_account.initial_balance_locked:
        financial_account.initial_balance_locked = True
        financial_account.save(update_fields=["initial_balance_locked", "updated_at"])

    record_audit_event(
        request=request,
        user=actor,
        event_type="create",
        module="finance",
        action="receive_payment",
        obj=payment,
        description=f"Recebimento {payment.number} de {amount}",
    )
    try:
        from commissions.services.provisioning import release_commission_for_receivable_payment

        release_commission_for_receivable_payment(payment=payment, actor=actor, request=request)
    except Exception:
        pass
    return payment


@transaction.atomic
def reverse_receivable_payment(*, payment, actor, reason, request=None):
    if not reason:
        raise ValidationError("Motivo do estorno é obrigatório.")
    if payment.status != PaymentStatus.CONFIRMED:
        raise ValidationError("Somente recebimentos confirmados podem ser estornados.")
    payment.status = PaymentStatus.REVERSED
    payment.reverse_reason = reason
    payment.reversed_at = timezone.now()
    payment.reversed_by = actor
    payment.updated_by = actor
    payment.save(
        update_fields=[
            "status",
            "reverse_reason",
            "reversed_at",
            "reversed_by",
            "updated_by",
            "updated_at",
        ],
    )

    installment = payment.installment
    installment.paid_amount = max(installment.paid_amount - payment.amount, Decimal("0.00"))
    installment.outstanding_amount = max(
        installment.original_amount
        - installment.discount_amount
        + installment.interest_amount
        + installment.penalty_amount
        - installment.paid_amount,
        Decimal("0.00"),
    )
    recalculate_installment_status(installment)
    installment.save(update_fields=["paid_amount", "outstanding_amount", "status", "updated_at"])

    title = installment.receivable
    recalculate_title_from_installments(title)
    title.updated_by = actor
    title.save(update_fields=["paid_amount", "outstanding_amount", "status", "updated_by", "updated_at"])

    original = payment.movements.filter(movement_type=MovementType.INCOME).first()
    _create_movement(
        movement_type=MovementType.REVERSAL,
        account=payment.financial_account,
        amount=payment.amount,
        movement_date=timezone.localdate(),
        description=f"Estorno {payment.number}: {reason}",
        actor=actor,
        category=title.category,
        cost_center=title.cost_center,
        reference_type="receivable_payment_reversal",
        reference_id=payment.pk,
        source_receivable_payment=payment,
        reversal_of=original,
    )
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="finance",
        action="reverse_receivable_payment",
        obj=payment,
        description=f"Estornou recebimento {payment.number}",
        metadata={"reason": reason},
    )
    try:
        from commissions.services.reversals import reverse_releases_for_receivable_payment

        reverse_releases_for_receivable_payment(
            payment=payment,
            actor=actor,
            reason=reason,
            request=request,
        )
    except Exception:
        pass
    return payment


@transaction.atomic
def register_payable_payment(
    *,
    installment,
    amount,
    payment_date,
    payment_method,
    financial_account,
    actor,
    reference="",
    notes="",
    allow_overpay=False,
    request=None,
):
    if amount <= 0:
        raise ValidationError("Valor do pagamento deve ser positivo.")
    if installment.status in TERMINAL_INSTALLMENT_STATUSES:
        raise ValidationError("Parcela não está aberta para pagamento.")
    if amount > installment.outstanding_amount and not allow_overpay:
        raise ValidationError("Valor supera o saldo da parcela.")

    payment = PayablePayment(
        number=next_payable_payment_number(),
        installment=installment,
        payment_date=payment_date,
        amount=amount,
        payment_method=payment_method,
        financial_account=financial_account,
        reference=reference or "",
        notes=notes or "",
        status=PaymentStatus.CONFIRMED,
        created_by=actor,
        updated_by=actor,
    )
    payment.save()

    installment.paid_amount += amount
    installment.outstanding_amount = max(
        installment.original_amount
        - installment.discount_amount
        + installment.interest_amount
        + installment.penalty_amount
        - installment.paid_amount,
        Decimal("0.00"),
    )
    recalculate_installment_status(installment)
    installment.save(update_fields=["paid_amount", "outstanding_amount", "status", "updated_at"])

    title = installment.payable
    recalculate_title_from_installments(title)
    title.updated_by = actor
    title.save(update_fields=["paid_amount", "outstanding_amount", "status", "updated_by", "updated_at"])

    _create_movement(
        movement_type=MovementType.EXPENSE,
        account=financial_account,
        amount=amount,
        movement_date=payment_date,
        description=f"Pagamento {payment.number} — {title.number}",
        actor=actor,
        category=title.category,
        cost_center=title.cost_center,
        reference_type="payable_payment",
        reference_id=payment.pk,
        source_payable_payment=payment,
    )
    if not financial_account.initial_balance_locked:
        financial_account.initial_balance_locked = True
        financial_account.save(update_fields=["initial_balance_locked", "updated_at"])

    record_audit_event(
        request=request,
        user=actor,
        event_type="create",
        module="finance",
        action="pay_expense",
        obj=payment,
        description=f"Pagamento {payment.number} de {amount}",
    )
    return payment


@transaction.atomic
def reverse_payable_payment(*, payment, actor, reason, request=None):
    if not reason:
        raise ValidationError("Motivo do estorno é obrigatório.")
    if payment.status != PaymentStatus.CONFIRMED:
        raise ValidationError("Somente pagamentos confirmados podem ser estornados.")
    payment.status = PaymentStatus.REVERSED
    payment.reverse_reason = reason
    payment.reversed_at = timezone.now()
    payment.reversed_by = actor
    payment.updated_by = actor
    payment.save(
        update_fields=[
            "status",
            "reverse_reason",
            "reversed_at",
            "reversed_by",
            "updated_by",
            "updated_at",
        ],
    )

    installment = payment.installment
    installment.paid_amount = max(installment.paid_amount - payment.amount, Decimal("0.00"))
    installment.outstanding_amount = max(
        installment.original_amount
        - installment.discount_amount
        + installment.interest_amount
        + installment.penalty_amount
        - installment.paid_amount,
        Decimal("0.00"),
    )
    recalculate_installment_status(installment)
    installment.save(update_fields=["paid_amount", "outstanding_amount", "status", "updated_at"])

    title = installment.payable
    recalculate_title_from_installments(title)
    title.updated_by = actor
    title.save(update_fields=["paid_amount", "outstanding_amount", "status", "updated_by", "updated_at"])

    original = payment.movements.filter(movement_type=MovementType.EXPENSE).first()
    _create_movement(
        movement_type=MovementType.REVERSAL,
        account=payment.financial_account,
        amount=payment.amount,
        movement_date=timezone.localdate(),
        description=f"Estorno {payment.number}: {reason}",
        actor=actor,
        category=title.category,
        cost_center=title.cost_center,
        reference_type="payable_payment_reversal",
        reference_id=payment.pk,
        source_payable_payment=payment,
        reversal_of=original,
    )
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="finance",
        action="reverse_payable_payment",
        obj=payment,
        description=f"Estornou pagamento {payment.number}",
        metadata={"reason": reason},
    )
    return payment
