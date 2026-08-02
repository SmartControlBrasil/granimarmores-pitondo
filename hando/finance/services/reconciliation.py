# ruff: noqa: PLR0913
import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from audit.services import record_audit_event
from finance.models import FinancialAccount
from finance.models import MovementType
from finance.services.balances import account_balance
from finance.services.payments import _create_movement


@transaction.atomic
def create_financial_account(*, data, actor, request=None):
    account = FinancialAccount(
        name=data["name"],
        account_type=data["account_type"],
        bank_name=data.get("bank_name") or "",
        branch=data.get("branch") or "",
        account_reference=data.get("account_reference") or "",
        initial_balance=data.get("initial_balance") or Decimal("0.00"),
        notes=data.get("notes") or "",
        created_by=actor,
        updated_by=actor,
    )
    account.save()
    if account.initial_balance and account.initial_balance != 0:
        if account.initial_balance < 0:
            raise ValidationError("Saldo inicial negativo deve ser registrado via ajuste.")
        _create_movement(
            movement_type=MovementType.OPENING_BALANCE,
            account=account,
            amount=account.initial_balance,
            movement_date=timezone.localdate(),
            description=f"Saldo inicial — {account.name}",
            actor=actor,
            reference_type="financial_account",
            reference_id=account.pk,
        )
        account.initial_balance_locked = True
        account.save(update_fields=["initial_balance_locked", "updated_at"])
    record_audit_event(
        request=request,
        user=actor,
        event_type="create",
        module="finance",
        action="create_financial_account",
        obj=account,
        description=f"Criou conta financeira {account.name}",
    )
    return account


@transaction.atomic
def transfer_between_accounts(
    *,
    source_account,
    destination_account,
    amount,
    movement_date,
    actor,
    notes="",
    request=None,
    prevent_negative=True,
):
    if source_account.pk == destination_account.pk:
        raise ValidationError("Contas de origem e destino devem ser diferentes.")
    if amount <= 0:
        raise ValidationError("Valor da transferência deve ser positivo.")
    if prevent_negative:
        bal = account_balance(account=source_account, until_date=movement_date)
        if bal < amount:
            raise ValidationError("Saldo insuficiente na conta de origem.")

    group = uuid.uuid4().hex[:16]
    out_mov = _create_movement(
        movement_type=MovementType.TRANSFER_OUT,
        account=source_account,
        amount=amount,
        movement_date=movement_date,
        description=notes or f"Transferência para {destination_account.name}",
        actor=actor,
        reference_type="transfer",
        transfer_group=group,
    )
    in_mov = _create_movement(
        movement_type=MovementType.TRANSFER_IN,
        account=destination_account,
        amount=amount,
        movement_date=movement_date,
        description=notes or f"Transferência de {source_account.name}",
        actor=actor,
        reference_type="transfer",
        transfer_group=group,
    )
    record_audit_event(
        request=request,
        user=actor,
        event_type="create",
        module="finance",
        action="transfer_between_accounts",
        description=f"Transferência {amount} de {source_account} para {destination_account}",
        metadata={"group": group, "out": out_mov.pk, "in": in_mov.pk},
    )
    return out_mov, in_mov


@transaction.atomic
def create_manual_adjustment(
    *,
    account,
    direction,
    amount,
    movement_date,
    reason,
    actor,
    category=None,
    cost_center=None,
    request=None,
):
    if not reason:
        raise ValidationError("Justificativa do ajuste é obrigatória.")
    if amount <= 0:
        raise ValidationError("Valor do ajuste deve ser positivo.")
    if direction not in {"in", "out"}:
        raise ValidationError("Direção inválida.")
    movement_type = MovementType.ADJUSTMENT_IN if direction == "in" else MovementType.ADJUSTMENT_OUT
    mov = _create_movement(
        movement_type=movement_type,
        account=account,
        amount=amount,
        movement_date=movement_date,
        description=reason,
        actor=actor,
        category=category,
        cost_center=cost_center,
        reference_type="manual_adjustment",
    )
    record_audit_event(
        request=request,
        user=actor,
        event_type="create",
        module="finance",
        action="financial_adjustment",
        obj=mov,
        description=f"Ajuste {direction} de {amount}: {reason}",
    )
    return mov
