# ruff: noqa: EM101, PLR0913, TRY003
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from access_control.services.authorization import user_has_permission
from after_sales.models import AfterSalesCase
from after_sales.models import CaseType
from after_sales.models import CoverageType
from after_sales.models import HistoryAction
from after_sales.models import WarrantyEligibility
from after_sales.models import WarrantyPolicy
from after_sales.models import WarrantyRecord
from after_sales.models import WarrantyStartsFrom
from after_sales.models import WarrantyStatus
from after_sales.services.cases import _add_history
from after_sales.services.numbering import next_warranty_number
from audit.services import record_audit_event


@transaction.atomic
def create_warranty_record(
    *,
    actor,
    customer,
    sales_order,
    start_date,
    coverage_type,
    end_date=None,
    policy=None,
    installation_schedule=None,
    coverage_description="",
    exclusions="",
    notes="",
    request=None,
):
    if not user_has_permission(actor, "warranties.create"):
        raise PermissionDenied("Sem permissão para criar garantia.")
    if sales_order.customer_id != customer.pk:
        raise ValidationError("Cliente da garantia deve coincidir com o pedido.")
    if end_date and end_date < start_date:
        raise ValidationError("Fim da garantia não pode ser anterior ao início.")

    warranty = WarrantyRecord.objects.create(
        number=next_warranty_number(),
        customer=customer,
        sales_order=sales_order,
        installation_schedule=installation_schedule,
        policy=policy,
        start_date=start_date,
        end_date=end_date,
        status=WarrantyStatus.ACTIVE,
        coverage_type=coverage_type,
        coverage_description=coverage_description,
        exclusions=exclusions,
        notes=notes,
        created_by=actor,
        updated_by=actor,
    )
    record_audit_event(
        request=request,
        user=actor,
        event_type="create",
        module="after_sales",
        action="warranty_created",
        obj=warranty,
    )
    return warranty


def evaluate_warranty_eligibility(*, case, actor):
    if not user_has_permission(actor, "warranties.decide") and not user_has_permission(
        actor,
        "warranties.view",
    ):
        raise PermissionDenied("Sem permissão para avaliar garantia.")

    if not case.sales_order_id:
        return WarrantyEligibility.MANUAL_REVIEW, "Caso sem pedido vinculado."

    warranties = WarrantyRecord.objects.filter(
        sales_order=case.sales_order,
        status=WarrantyStatus.ACTIVE,
    )
    if not warranties.exists():
        return WarrantyEligibility.NOT_ELIGIBLE, "Não há garantia ativa para o pedido."

    today = timezone.localdate()
    active = [w for w in warranties if w.is_within_period(today)]
    if not active:
        return WarrantyEligibility.NOT_ELIGIBLE, "Garantias existentes estão fora da vigência."

    warranty = active[0]
    coverage_map = {
        CaseType.MATERIAL_ISSUE: CoverageType.MATERIAL,
        CaseType.FINISH_ISSUE: CoverageType.WORKMANSHIP,
        CaseType.INSTALLATION_ISSUE: CoverageType.INSTALLATION,
        CaseType.DELIVERY_ISSUE: CoverageType.WORKMANSHIP,
        CaseType.TECHNICAL_ASSISTANCE: None,
        CaseType.WARRANTY_REQUEST: None,
    }
    expected = coverage_map.get(case.case_type)
    if expected and warranty.coverage_type != expected and warranty.coverage_type != CoverageType.CUSTOM:
        return WarrantyEligibility.MANUAL_REVIEW, (
            f"Cobertura da garantia ({warranty.get_coverage_type_display()}) "
            "pode não cobrir o tipo do caso — análise manual."
        )
    if warranty.exclusions and case.case_type in warranty.exclusions:
        return WarrantyEligibility.MANUAL_REVIEW, "Possível exclusão registrada — análise manual."

    return WarrantyEligibility.ELIGIBLE, f"Garantia {warranty.number} vigente."


@transaction.atomic
def decide_warranty_eligibility(*, case, actor, decision, notes, warranty=None, request=None):
    if not user_has_permission(actor, "warranties.decide"):
        raise PermissionDenied("Sem permissão para decidir elegibilidade.")
    if decision not in WarrantyEligibility.values:
        raise ValidationError("Decisão inválida.")
    if not notes.strip():
        raise ValidationError("Justificativa obrigatória.")

    if warranty is None and case.sales_order_id:
        warranty = (
            WarrantyRecord.objects.filter(
                sales_order=case.sales_order,
                status=WarrantyStatus.ACTIVE,
            )
            .order_by("-start_date")
            .first()
        )

    case.warranty = warranty
    case.warranty_eligible = decision
    case.warranty_decision_notes = notes.strip()
    case.updated_by = actor
    case.save()
    _add_history(
        case=case,
        action=HistoryAction.WARRANTY_EVALUATED,
        actor=actor,
        description=f"{decision}: {notes.strip()}",
        old_status=case.status,
        new_status=case.status,
    )
    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="after_sales",
        action="warranty_decided",
        obj=case,
        metadata={"decision": decision},
    )
    return case


@transaction.atomic
def save_warranty_policy(*, form, actor, request=None):
    if not user_has_permission(actor, "warranties.update") and not user_has_permission(
        actor,
        "warranties.create",
    ):
        raise PermissionDenied("Sem permissão para política de garantia.")
    obj = form.save(commit=False)
    if not obj.pk:
        obj.created_by = actor
    obj.updated_by = actor
    obj.save()
    record_audit_event(
        request=request,
        user=actor,
        event_type="update" if form.instance.pk else "create",
        module="after_sales",
        action="warranty_policy_saved",
        obj=obj,
    )
    return obj


def compute_warranty_dates(*, policy, sales_order):
    """Calcula datas a partir da política; não inventa prazo se duration_days for nulo."""
    start = None
    if policy.starts_from == WarrantyStartsFrom.DELIVERY:
        delivery = sales_order.deliveries.filter(status="completed").order_by("-completed_at").first()
        if delivery and delivery.completed_at:
            start = timezone.localdate(delivery.completed_at)
        elif delivery:
            start = delivery.scheduled_date
    elif policy.starts_from == WarrantyStartsFrom.INSTALLATION:
        installation = sales_order.installations.filter(status="completed").order_by("-completed_at").first()
        if installation and installation.completed_at:
            start = timezone.localdate(installation.completed_at)
        elif installation:
            start = installation.scheduled_date
    elif policy.starts_from == WarrantyStartsFrom.ORDER_COMPLETION:
        if sales_order.status == "completed":
            start = timezone.localdate(sales_order.updated_at)
    if start is None:
        return None, None
    end = None
    if policy.duration_days:
        from datetime import timedelta

        end = start + timedelta(days=policy.duration_days)
    return start, end
