# ruff: noqa: PLR0913
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.forms import formset_factory
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.utils import timezone

from access_control.services.authorization import render_403
from access_control.services.authorization import require_permission
from access_control.services.authorization import user_has_permission
from commercial.models import CommercialPartner
from commissions.export import build_csv_response
from commissions.forms import AdjustmentForm
from commissions.forms import CommissionPolicyForm
from commissions.forms import GeneratePayableForm
from commissions.forms import PaymentForm
from commissions.forms import ReverseForm
from commissions.forms import SettlementForm
from commissions.forms import SimulatorForm
from commissions.forms import TierForm
from commissions.models import CommissionEvent
from commissions.models import CommissionPolicy
from commissions.models import CommissionSettlement
from commissions.periods import PERIOD_CHOICES
from commissions.periods import parse_commission_period
from commissions.selectors import beneficiary_balance
from commissions.selectors import commission_dashboard_metrics
from commissions.selectors import events_queryset_for_user
from commissions.selectors import policies_queryset
from commissions.selectors import settlements_queryset_for_user
from commissions.services.calculation import simulate_commission
from commissions.services.policies import activate_policy
from commissions.services.policies import create_policy
from commissions.services.policies import deactivate_policy
from commissions.services.reversals import create_manual_adjustment
from commissions.services.reversals import reverse_commission_event
from commissions.services.settlement import approve_settlement
from commissions.services.settlement import cancel_settlement
from commissions.services.settlement import create_settlement
from commissions.services.settlement import generate_payable_from_settlement
from commissions.services.settlement import register_commission_payment
from salespeople.models import Salesperson


def _err(request, exc):
    messages.error(request, str(exc))


@require_permission("commission_dashboard.view")
def dashboard(request):
    start, end, period = parse_commission_period(request)
    metrics = commission_dashboard_metrics(user=request.user, start=start, end=end)
    return render(
        request,
        "commissions/dashboard.html",
        {
            "page_title": "Dashboard de Comissões",
            "metrics": metrics,
            "period": period,
            "period_choices": PERIOD_CHOICES,
        },
    )


@login_required
def my_commissions(request):
    if not (
        user_has_permission(request.user, "commission_events.view_own")
        or user_has_permission(request.user, "commission_events.view")
    ):
        return render_403(request)
    sp = getattr(request.user, "salesperson", None)
    if not sp and not user_has_permission(request.user, "commission_events.view"):
        messages.error(request, "Usuário sem vínculo de vendedor.")
        return redirect("/painel/")
    if sp:
        events = events_queryset_for_user(request.user).filter(salesperson=sp)
        balance = beneficiary_balance(salesperson=sp)
        settlements = settlements_queryset_for_user(request.user).filter(salesperson=sp)
    else:
        events = events_queryset_for_user(request.user)
        balance = {}
        settlements = settlements_queryset_for_user(request.user)
    if request.GET.get("export") == "csv":
        rows = [
            [e.number, e.event_type, e.commission_amount, e.status, e.competence_date]
            for e in events[:2000]
        ]
        return build_csv_response(
            filename="minhas_comissoes.csv",
            headers=["Número", "Tipo", "Valor", "Status", "Competência"],
            rows=rows,
            request=request,
            export_key="my_commissions",
        )
    return render(
        request,
        "commissions/my_commissions.html",
        {
            "page_title": "Minhas Comissões",
            "balance": balance,
            "events": events[:100],
            "settlements": settlements[:20],
            "salesperson": sp,
        },
    )


@require_permission("commission_events.view")
def event_list(request):
    qs = events_queryset_for_user(request.user)
    if request.GET.get("status"):
        qs = qs.filter(status=request.GET["status"])
    if request.GET.get("event_type"):
        qs = qs.filter(event_type=request.GET["event_type"])
    if request.GET.get("salesperson"):
        qs = qs.filter(salesperson_id=request.GET["salesperson"])
    if request.GET.get("export") == "csv":
        rows = [
            [
                e.number,
                e.beneficiary_name_snapshot,
                e.event_type,
                e.commission_amount,
                e.status,
                e.policy.name if e.policy else "",
            ]
            for e in qs[:2000]
        ]
        return build_csv_response(
            filename="eventos_comissao.csv",
            headers=["Número", "Beneficiário", "Tipo", "Valor", "Status", "Política"],
            rows=rows,
            request=request,
            export_key="events",
        )
    page = Paginator(qs, 30).get_page(request.GET.get("page"))
    return render(
        request,
        "commissions/event_list.html",
        {"page_title": "Eventos de Comissão", "page_obj": page},
    )


@require_permission("commission_events.reverse")
def event_reverse(request, pk):
    event = get_object_or_404(CommissionEvent, pk=pk)
    form = ReverseForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            reverse_commission_event(
                event=event,
                actor=request.user,
                reason=form.cleaned_data["reason"],
                request=request,
            )
            messages.success(request, "Estorno registrado.")
            return redirect("commissions:event_list")
        except ValidationError as exc:
            _err(request, exc)
    return render(request, "commissions/form.html", {"page_title": f"Estornar {event.number}", "form": form})


@require_permission("commission_events.adjust")
def event_adjust(request):
    form = AdjustmentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            create_manual_adjustment(
                beneficiary_type=form.cleaned_data["beneficiary_type"],
                amount=form.cleaned_data["amount"],
                direction=form.cleaned_data["direction"],
                competence_date=form.cleaned_data["competence_date"],
                reason=form.cleaned_data["reason"],
                actor=request.user,
                salesperson=form.cleaned_data.get("salesperson"),
                commercial_partner=form.cleaned_data.get("commercial_partner"),
                reference=form.cleaned_data.get("reference") or "",
                request=request,
            )
            messages.success(request, "Ajuste registrado.")
            return redirect("commissions:event_list")
        except ValidationError as exc:
            _err(request, exc)
    return render(request, "commissions/form.html", {"page_title": "Ajustar comissão", "form": form})


@require_permission("commission_policies.view")
def policy_list(request):
    qs = policies_queryset()
    if request.GET.get("export") == "csv":
        rows = [[p.name, p.trigger_type, p.valid_from, p.valid_until, p.is_active, p.priority] for p in qs]
        return build_csv_response(
            filename="politicas_comissao.csv",
            headers=["Nome", "Gatilho", "Início", "Fim", "Ativa", "Prioridade"],
            rows=rows,
            request=request,
            export_key="policies",
        )
    return render(request, "commissions/policy_list.html", {"page_title": "Políticas de Comissão", "policies": qs})


@require_permission("commission_policies.create")
def policy_create(request):
    TierFormSet = formset_factory(TierForm, extra=1)
    form = CommissionPolicyForm(request.POST or None, initial={"valid_from": timezone.localdate()})
    formset = TierFormSet(request.POST or None, prefix="tiers")
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        tiers = [f.cleaned_data for f in formset if f.cleaned_data]
        try:
            policy = create_policy(
                data=form.cleaned_data,
                tiers=tiers,
                actor=request.user,
                request=request,
            )
            messages.success(request, f"Política {policy.name} criada.")
            return redirect("commissions:policy_detail", pk=policy.pk)
        except ValidationError as exc:
            _err(request, exc)
    return render(
        request,
        "commissions/policy_form.html",
        {"page_title": "Nova política", "form": form, "formset": formset},
    )


@require_permission("commission_policies.view")
def policy_detail(request, pk):
    policy = get_object_or_404(CommissionPolicy, pk=pk)
    return render(
        request,
        "commissions/policy_detail.html",
        {"page_title": policy.name, "obj": policy, "tiers": policy.tiers.all(), "rules": policy.rules.all()},
    )


@require_permission("commission_policies.update")
def policy_update(request, pk):
    policy = get_object_or_404(CommissionPolicy, pk=pk)
    form = CommissionPolicyForm(request.POST or None, instance=policy)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.updated_by = request.user
        obj.save()
        messages.success(request, "Política atualizada (comissões históricas não são recalculadas).")
        return redirect("commissions:policy_detail", pk=pk)
    return render(request, "commissions/form.html", {"page_title": f"Editar {policy.name}", "form": form})


@require_permission("commission_policies.activate")
def policy_activate(request, pk):
    policy = get_object_or_404(CommissionPolicy, pk=pk)
    if request.method == "POST":
        try:
            activate_policy(policy=policy, actor=request.user, request=request)
            messages.success(request, "Política ativada.")
        except ValidationError as exc:
            _err(request, exc)
    return redirect("commissions:policy_detail", pk=pk)


@require_permission("commission_policies.activate")
def policy_deactivate(request, pk):
    policy = get_object_or_404(CommissionPolicy, pk=pk)
    if request.method == "POST":
        deactivate_policy(policy=policy, actor=request.user, request=request)
        messages.success(request, "Política desativada.")
    return redirect("commissions:policy_detail", pk=pk)


@require_permission("commission_settlements.view")
def settlement_list(request):
    qs = settlements_queryset_for_user(request.user)
    if request.GET.get("export") == "csv":
        rows = [[s.number, s.period_start, s.period_end, s.net_amount, s.status] for s in qs[:2000]]
        return build_csv_response(
            filename="fechamentos_comissao.csv",
            headers=["Número", "Início", "Fim", "Líquido", "Status"],
            rows=rows,
            request=request,
            export_key="settlements",
        )
    page = Paginator(qs, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "commissions/settlement_list.html",
        {"page_title": "Fechamentos", "page_obj": page},
    )


@require_permission("commission_settlements.create")
def settlement_create(request):
    form = SettlementForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            s = create_settlement(
                beneficiary_type=form.cleaned_data["beneficiary_type"],
                period_start=form.cleaned_data["period_start"],
                period_end=form.cleaned_data["period_end"],
                actor=request.user,
                salesperson=form.cleaned_data.get("salesperson"),
                commercial_partner=form.cleaned_data.get("commercial_partner"),
                notes=form.cleaned_data.get("notes") or "",
                request=request,
            )
            messages.success(request, f"Fechamento {s.number} criado.")
            return redirect("commissions:settlement_detail", pk=s.pk)
        except ValidationError as exc:
            _err(request, exc)
    return render(request, "commissions/form.html", {"page_title": "Novo fechamento", "form": form})


@require_permission("commission_settlements.view")
def settlement_detail(request, pk):
    settlement = get_object_or_404(settlements_queryset_for_user(request.user), pk=pk)
    return render(
        request,
        "commissions/settlement_detail.html",
        {
            "page_title": settlement.number,
            "obj": settlement,
            "items": settlement.items.select_related("commission_event"),
            "payments": settlement.payments.all(),
        },
    )


@require_permission("commission_settlements.approve")
def settlement_approve(request, pk):
    settlement = get_object_or_404(CommissionSettlement, pk=pk)
    if request.method == "POST":
        try:
            approve_settlement(settlement=settlement, actor=request.user, request=request)
            messages.success(request, "Fechamento aprovado.")
        except ValidationError as exc:
            _err(request, exc)
    return redirect("commissions:settlement_detail", pk=pk)


@require_permission("commission_settlements.generate_payable")
def settlement_generate_payable(request, pk):
    settlement = get_object_or_404(CommissionSettlement, pk=pk)
    form = GeneratePayableForm(request.POST or None, initial={"due_date": timezone.localdate()})
    if request.method == "POST" and form.is_valid():
        try:
            payable = generate_payable_from_settlement(
                settlement=settlement,
                actor=request.user,
                due_date=form.cleaned_data["due_date"],
                payment_term=form.cleaned_data.get("payment_term"),
                request=request,
            )
            messages.success(request, f"Conta a pagar {payable.number} gerada.")
            return redirect("commissions:settlement_detail", pk=pk)
        except ValidationError as exc:
            _err(request, exc)
    return render(
        request,
        "commissions/form.html",
        {"page_title": f"Gerar conta a pagar — {settlement.number}", "form": form},
    )


@require_permission("commission_settlements.cancel")
def settlement_cancel(request, pk):
    settlement = get_object_or_404(CommissionSettlement, pk=pk)
    form = ReverseForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            cancel_settlement(
                settlement=settlement,
                actor=request.user,
                reason=form.cleaned_data["reason"],
                request=request,
            )
            messages.success(request, "Fechamento cancelado.")
            return redirect("commissions:settlement_list")
        except ValidationError as exc:
            _err(request, exc)
    return render(request, "commissions/form.html", {"page_title": f"Cancelar {settlement.number}", "form": form})


@require_permission("commission_payments.create")
def settlement_pay(request, pk):
    settlement = get_object_or_404(CommissionSettlement, pk=pk)
    form = PaymentForm(
        request.POST or None,
        initial={"amount": settlement.net_amount - settlement.paid_amount},
    )
    if request.method == "POST" and form.is_valid():
        try:
            register_commission_payment(
                settlement=settlement,
                amount=form.cleaned_data["amount"],
                payment_date=form.cleaned_data["payment_date"],
                actor=request.user,
                payment_method=form.cleaned_data.get("payment_method"),
                financial_account=form.cleaned_data.get("financial_account"),
                reference=form.cleaned_data.get("reference") or "",
                notes=form.cleaned_data.get("notes") or "",
                request=request,
            )
            messages.success(request, "Pagamento registrado.")
            return redirect("commissions:settlement_detail", pk=pk)
        except ValidationError as exc:
            _err(request, exc)
    return render(request, "commissions/form.html", {"page_title": f"Pagar {settlement.number}", "form": form})


@require_permission("commission_policies.view")
def simulator(request):
    form = SimulatorForm(request.POST or None)
    result = None
    if request.method == "POST" and form.is_valid():
        result = simulate_commission(
            value=form.cleaned_data["value"],
            trigger_type=form.cleaned_data["trigger_type"],
            target=form.cleaned_data["target"],
            on_date=form.cleaned_data["on_date"],
            salesperson=form.cleaned_data.get("salesperson"),
            partner=form.cleaned_data.get("commercial_partner"),
            margin=form.cleaned_data.get("margin"),
            discount=form.cleaned_data.get("discount"),
        )
    return render(
        request,
        "commissions/simulator.html",
        {"page_title": "Simulador de Comissões", "form": form, "result": result},
    )


@require_permission("commission_events.view")
def salesperson_list(request):
    people = Salesperson.objects.filter(is_active=True).order_by("display_name")
    rows = [{"sp": sp, "balance": beneficiary_balance(salesperson=sp)} for sp in people[:100]]
    return render(
        request,
        "commissions/salesperson_list.html",
        {"page_title": "Comissões por Vendedor", "rows": rows},
    )


@require_permission("commission_partner_values.view")
def partner_detail(request, pk):
    partner = get_object_or_404(CommercialPartner, pk=pk)
    balance = beneficiary_balance(partner=partner)
    events = CommissionEvent.objects.filter(commercial_partner=partner).order_by("-created_at")[:50]
    settlements = CommissionSettlement.objects.filter(commercial_partner=partner).order_by("-created_at")[:20]
    return render(
        request,
        "commissions/partner_detail.html",
        {
            "page_title": f"Comissões — {partner.name}",
            "obj": partner,
            "balance": balance,
            "events": events,
            "settlements": settlements,
        },
    )


@require_permission("commission_partner_values.view")
def partner_list(request):
    partners = CommercialPartner.objects.filter(is_active=True).order_by("name")
    rows = [{"partner": p, "balance": beneficiary_balance(partner=p)} for p in partners[:100]]
    return render(
        request,
        "commissions/partner_list.html",
        {"page_title": "Comissões de Parceiros", "rows": rows},
    )
