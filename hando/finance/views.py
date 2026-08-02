# ruff: noqa: PLR0913
import json
from decimal import Decimal

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.core.serializers.json import DjangoJSONEncoder
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

from access_control.services.authorization import require_permission
from access_control.services.authorization import user_has_permission
from finance.export import build_csv_response
from finance.forms import AdjustmentForm
from finance.forms import CancelForm
from finance.forms import CostCenterForm
from finance.forms import FinancialAccountForm
from finance.forms import FinancialCategoryForm
from finance.forms import GenerateReceivableForm
from finance.forms import PayExpenseForm
from finance.forms import PaymentMethodForm
from finance.forms import PaymentTermForm
from finance.forms import PayableForm
from finance.forms import ReceivePaymentForm
from finance.forms import ReceivableForm
from finance.forms import ReversePaymentForm
from finance.forms import TransferForm
from finance.models import AccountsPayable
from finance.models import AccountsReceivable
from finance.models import CostCenter
from finance.models import FinancialAccount
from finance.models import FinancialCategory
from finance.models import FinancialMovement
from finance.models import PaymentMethod
from finance.models import PaymentTerm
from finance.models import PayablePayment
from finance.models import ReceivablePayment
from finance.models import TitleStatus
from finance.periods import PERIOD_CHOICES
from finance.periods import parse_finance_period
from finance.selectors import filter_payables
from finance.selectors import filter_receivables
from finance.selectors import finance_dashboard_metrics
from finance.selectors import overdue_buckets
from finance.selectors import overdue_receivable_installments
from finance.selectors import payables_queryset_for_user
from finance.selectors import receivables_queryset_for_user
from finance.services.cash_flow import daily_cash_flow
from finance.services.payables import cancel_payable
from finance.services.payables import create_payable
from finance.services.payments import register_payable_payment
from finance.services.payments import register_receivable_payment
from finance.services.payments import reverse_payable_payment
from finance.services.payments import reverse_receivable_payment
from finance.services.receivables import cancel_receivable
from finance.services.receivables import create_manual_receivable
from finance.services.receivables import generate_receivable_from_order
from finance.services.reconciliation import create_financial_account
from finance.services.reconciliation import create_manual_adjustment
from finance.services.reconciliation import transfer_between_accounts
from production.models import SalesOrder


class DecimalEncoder(DjangoJSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        return super().default(o)


def _handle(request, exc):
    messages.error(request, str(exc))


@require_permission("finance_dashboard.view")
def dashboard(request):
    try:
        start, end, period = parse_finance_period(request)
    except ValidationError as exc:
        messages.error(request, str(exc))
        start, end, period = parse_finance_period(type("R", (), {"GET": {"period": "30d"}})())
    metrics = finance_dashboard_metrics(user=request.user, start=start, end=end)
    charts = {
        "income": [
            {"label": r["category__name"] or "Sem categoria", "value": float(r["total"] or 0)}
            for r in metrics.get("income_by_category", [])
        ],
        "expense": [
            {"label": r["category__name"] or "Sem categoria", "value": float(r["total"] or 0)}
            for r in metrics.get("expense_by_category", [])
        ],
    }
    return render(
        request,
        "finance/dashboard.html",
        {
            "page_title": "Dashboard Financeiro",
            "metrics": metrics,
            "period": period,
            "period_choices": PERIOD_CHOICES,
            "start": start,
            "end": end,
            "charts_json": json.dumps(charts, cls=DecimalEncoder),
            "can_values": user_has_permission(request.user, "finance_values.view"),
        },
    )


@require_permission("accounts_receivable.view")
def receivable_list(request):
    qs = filter_receivables(receivables_queryset_for_user(request.user), request.GET)
    page_obj = Paginator(qs, 25).get_page(request.GET.get("page"))
    if request.GET.get("export") == "1" and user_has_permission(request.user, "finance_export"):
        rows = [
            [
                r.number,
                r.customer.name,
                r.sales_order.number if r.sales_order_id else "",
                r.issue_date,
                r.due_date,
                r.original_amount,
                r.paid_amount,
                r.outstanding_amount,
                r.status,
            ]
            for r in qs[:5000]
        ]
        return build_csv_response(
            filename="contas_receber.csv",
            headers=[
                "Número",
                "Cliente",
                "Pedido",
                "Emissão",
                "Vencimento",
                "Valor",
                "Recebido",
                "Saldo",
                "Status",
            ],
            rows=rows,
            request=request,
            export_key="receivables",
        )
    return render(
        request,
        "finance/receivable_list.html",
        {
            "page_title": "Contas a Receber",
            "page_obj": page_obj,
            "statuses": TitleStatus.choices,
            "querystring": request.GET.urlencode(),
        },
    )


@require_permission("accounts_receivable.create")
def receivable_create(request):
    form = ReceivableForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            obj = create_manual_receivable(
                data=form.cleaned_data,
                actor=request.user,
                request=request,
            )
            messages.success(request, f"Recebível {obj.number} criado.")
            return redirect("finance:receivable_detail", pk=obj.pk)
        except ValidationError as exc:
            _handle(request, exc)
    return render(
        request,
        "finance/form.html",
        {"page_title": "Novo recebível", "form": form},
    )


@require_permission("accounts_receivable.view")
def receivable_detail(request, pk):
    obj = get_object_or_404(receivables_queryset_for_user(request.user), pk=pk)
    return render(
        request,
        "finance/receivable_detail.html",
        {
            "page_title": obj.number,
            "receivable": obj,
            "installments": obj.installments.all(),
            "payments": ReceivablePayment.objects.filter(installment__receivable=obj).select_related(
                "payment_method",
                "financial_account",
                "installment",
            ),
        },
    )


@require_permission("accounts_receivable.update")
def receivable_update(request, pk):
    obj = get_object_or_404(receivables_queryset_for_user(request.user), pk=pk)
    if obj.paid_amount > 0:
        messages.error(request, "Título com recebimentos não pode ser editado livremente.")
        return redirect("finance:receivable_detail", pk=pk)
    form = ReceivableForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.instance.updated_by = request.user
        form.save()
        messages.success(request, "Recebível atualizado.")
        return redirect("finance:receivable_detail", pk=pk)
    return render(request, "finance/form.html", {"page_title": f"Editar {obj.number}", "form": form})


@require_permission("accounts_receivable.receive")
def receivable_receive(request, pk):
    obj = get_object_or_404(receivables_queryset_for_user(request.user), pk=pk)
    form = ReceivePaymentForm(request.POST or None, receivable=obj)
    if request.method == "POST" and form.is_valid():
        try:
            payment = register_receivable_payment(
                installment=form.cleaned_data["installment"],
                amount=form.cleaned_data["amount"],
                payment_date=form.cleaned_data["payment_date"],
                payment_method=form.cleaned_data["payment_method"],
                financial_account=form.cleaned_data["financial_account"],
                actor=request.user,
                reference=form.cleaned_data.get("reference") or "",
                notes=form.cleaned_data.get("notes") or "",
                request=request,
            )
            messages.success(request, f"Recebimento {payment.number} confirmado.")
            return redirect("finance:receivable_detail", pk=pk)
        except ValidationError as exc:
            _handle(request, exc)
    return render(
        request,
        "finance/receive_form.html",
        {"page_title": f"Receber {obj.number}", "form": form, "receivable": obj},
    )


@require_permission("accounts_receivable.cancel")
def receivable_cancel(request, pk):
    obj = get_object_or_404(receivables_queryset_for_user(request.user), pk=pk)
    form = CancelForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            cancel_receivable(
                receivable=obj,
                actor=request.user,
                reason=form.cleaned_data["reason"],
                request=request,
            )
            messages.success(request, "Recebível cancelado.")
            return redirect("finance:receivable_detail", pk=pk)
        except ValidationError as exc:
            _handle(request, exc)
    return render(
        request,
        "finance/form.html",
        {"page_title": f"Cancelar {obj.number}", "form": form},
    )


@require_permission("accounts_receivable.reverse_payment")
def receivable_payment_reverse(request, pk):
    payment = get_object_or_404(
        ReceivablePayment.objects.select_related("installment__receivable"),
        pk=pk,
    )
    form = ReversePaymentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            reverse_receivable_payment(
                payment=payment,
                actor=request.user,
                reason=form.cleaned_data["reason"],
                request=request,
            )
            messages.success(request, "Recebimento estornado.")
            return redirect("finance:receivable_detail", pk=payment.installment.receivable_id)
        except ValidationError as exc:
            _handle(request, exc)
    return render(
        request,
        "finance/form.html",
        {"page_title": f"Estornar {payment.number}", "form": form},
    )


@require_permission("accounts_receivable.create")
def generate_from_order(request, order_id):
    order = get_object_or_404(SalesOrder.objects.select_related("quote", "customer"), pk=order_id)
    form = GenerateReceivableForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            receivable = generate_receivable_from_order(
                sales_order=order,
                payment_term=form.cleaned_data["payment_term"],
                actor=request.user,
                first_due_date=form.cleaned_data.get("first_due_date"),
                category=form.cleaned_data.get("category"),
                cost_center=form.cleaned_data.get("cost_center"),
                request=request,
            )
            messages.success(request, f"Recebível {receivable.number} gerado.")
            return redirect("finance:receivable_detail", pk=receivable.pk)
        except ValidationError as exc:
            _handle(request, exc)
    return render(
        request,
        "finance/generate_receivable.html",
        {"page_title": f"Gerar contas a receber — {order.number}", "form": form, "order": order},
    )


@require_permission("accounts_payable.view")
def payable_list(request):
    qs = filter_payables(payables_queryset_for_user(request.user), request.GET)
    page_obj = Paginator(qs, 25).get_page(request.GET.get("page"))
    if request.GET.get("export") == "1" and user_has_permission(request.user, "finance_export"):
        rows = [
            [
                p.number,
                p.supplier_name,
                p.due_date,
                p.original_amount,
                p.paid_amount,
                p.outstanding_amount,
                p.status,
            ]
            for p in qs[:5000]
        ]
        return build_csv_response(
            filename="contas_pagar.csv",
            headers=["Número", "Fornecedor", "Vencimento", "Valor", "Pago", "Saldo", "Status"],
            rows=rows,
            request=request,
            export_key="payables",
        )
    return render(
        request,
        "finance/payable_list.html",
        {"page_title": "Contas a Pagar", "page_obj": page_obj, "statuses": TitleStatus.choices},
    )


@require_permission("accounts_payable.create")
def payable_create(request):
    form = PayableForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            obj = create_payable(data=form.cleaned_data, actor=request.user, request=request)
            messages.success(request, f"Conta a pagar {obj.number} criada.")
            return redirect("finance:payable_detail", pk=obj.pk)
        except ValidationError as exc:
            _handle(request, exc)
    return render(request, "finance/form.html", {"page_title": "Nova conta a pagar", "form": form})


@require_permission("accounts_payable.view")
def payable_detail(request, pk):
    obj = get_object_or_404(payables_queryset_for_user(request.user), pk=pk)
    return render(
        request,
        "finance/payable_detail.html",
        {
            "page_title": obj.number,
            "payable": obj,
            "installments": obj.installments.all(),
            "payments": PayablePayment.objects.filter(installment__payable=obj),
        },
    )


@require_permission("accounts_payable.update")
def payable_update(request, pk):
    obj = get_object_or_404(payables_queryset_for_user(request.user), pk=pk)
    if obj.paid_amount > 0:
        messages.error(request, "Título com pagamentos não pode ser editado livremente.")
        return redirect("finance:payable_detail", pk=pk)
    form = PayableForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.instance.updated_by = request.user
        form.save()
        messages.success(request, "Conta a pagar atualizada.")
        return redirect("finance:payable_detail", pk=pk)
    return render(request, "finance/form.html", {"page_title": f"Editar {obj.number}", "form": form})


@require_permission("accounts_payable.pay")
def payable_pay(request, pk):
    obj = get_object_or_404(payables_queryset_for_user(request.user), pk=pk)
    form = PayExpenseForm(request.POST or None, payable=obj)
    if request.method == "POST" and form.is_valid():
        try:
            payment = register_payable_payment(
                installment=form.cleaned_data["installment"],
                amount=form.cleaned_data["amount"],
                payment_date=form.cleaned_data["payment_date"],
                payment_method=form.cleaned_data["payment_method"],
                financial_account=form.cleaned_data["financial_account"],
                actor=request.user,
                reference=form.cleaned_data.get("reference") or "",
                notes=form.cleaned_data.get("notes") or "",
                request=request,
            )
            messages.success(request, f"Pagamento {payment.number} confirmado.")
            return redirect("finance:payable_detail", pk=pk)
        except ValidationError as exc:
            _handle(request, exc)
    return render(
        request,
        "finance/pay_form.html",
        {"page_title": f"Pagar {obj.number}", "form": form, "payable": obj},
    )


@require_permission("accounts_payable.cancel")
def payable_cancel(request, pk):
    obj = get_object_or_404(payables_queryset_for_user(request.user), pk=pk)
    form = CancelForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            cancel_payable(
                payable=obj,
                actor=request.user,
                reason=form.cleaned_data["reason"],
                request=request,
            )
            messages.success(request, "Conta a pagar cancelada.")
            return redirect("finance:payable_detail", pk=pk)
        except ValidationError as exc:
            _handle(request, exc)
    return render(request, "finance/form.html", {"page_title": f"Cancelar {obj.number}", "form": form})


@require_permission("accounts_payable.reverse_payment")
def payable_payment_reverse(request, pk):
    payment = get_object_or_404(PayablePayment.objects.select_related("installment__payable"), pk=pk)
    form = ReversePaymentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            reverse_payable_payment(
                payment=payment,
                actor=request.user,
                reason=form.cleaned_data["reason"],
                request=request,
            )
            messages.success(request, "Pagamento estornado.")
            return redirect("finance:payable_detail", pk=payment.installment.payable_id)
        except ValidationError as exc:
            _handle(request, exc)
    return render(request, "finance/form.html", {"page_title": f"Estornar {payment.number}", "form": form})


@require_permission("finance_cash_flow.view")
def cash_flow_view(request):
    try:
        start, end, period = parse_finance_period(request, default="month")
    except ValidationError as exc:
        messages.error(request, str(exc))
        start, end, period = parse_finance_period(type("R", (), {"GET": {"period": "month"}})())
    account_id = request.GET.get("account") or None
    account = FinancialAccount.objects.filter(pk=account_id).first() if account_id else None
    data = daily_cash_flow(start=start, end=end, account=account)
    if request.GET.get("export") == "1" and user_has_permission(request.user, "finance_export"):
        rows = [
            [
                r["date"],
                r["opening"],
                r["forecast_in"],
                r["forecast_out"],
                r["realized_in"],
                r["realized_out"],
                r["realized_balance"],
                r["projected_balance"],
            ]
            for r in data["rows"]
        ]
        return build_csv_response(
            filename="fluxo_caixa.csv",
            headers=[
                "Data",
                "Saldo inicial",
                "Entradas previstas",
                "Saídas previstas",
                "Entradas realizadas",
                "Saídas realizadas",
                "Saldo realizado",
                "Saldo projetado",
            ],
            rows=rows,
            request=request,
            export_key="cash_flow",
        )
    chart = {
        "labels": [r["date"].isoformat() for r in data["rows"]],
        "realized": [float(r["realized_balance"]) for r in data["rows"]],
        "projected": [float(r["projected_balance"]) for r in data["rows"]],
    }
    return render(
        request,
        "finance/cash_flow.html",
        {
            "page_title": "Fluxo de Caixa",
            "summary": data["summary"],
            "rows": data["rows"],
            "period": period,
            "period_choices": PERIOD_CHOICES,
            "accounts": FinancialAccount.objects.filter(is_active=True),
            "selected_account": account,
            "charts_json": json.dumps(chart),
            "querystring": request.GET.urlencode(),
        },
    )


@require_permission("financial_movements.view")
def movement_list(request):
    qs = FinancialMovement.objects.select_related(
        "financial_account",
        "category",
        "cost_center",
        "created_by",
    )
    if request.GET.get("account"):
        qs = qs.filter(financial_account_id=request.GET["account"])
    if request.GET.get("type"):
        qs = qs.filter(movement_type=request.GET["type"])
    page_obj = Paginator(qs, 40).get_page(request.GET.get("page"))
    if request.GET.get("export") == "1" and user_has_permission(request.user, "finance_export"):
        rows = [
            [m.number, m.movement_date, m.movement_type, m.financial_account.name, m.description, m.amount]
            for m in qs[:5000]
        ]
        return build_csv_response(
            filename="movimentacoes.csv",
            headers=["Número", "Data", "Tipo", "Conta", "Descrição", "Valor"],
            rows=rows,
            request=request,
            export_key="movements",
        )
    return render(
        request,
        "finance/movement_list.html",
        {
            "page_title": "Movimentações",
            "page_obj": page_obj,
            "accounts": FinancialAccount.objects.filter(is_active=True),
        },
    )


@require_permission("finance_overdue.view")
def overdue_list(request):
    qs = overdue_receivable_installments()
    scoped = receivables_queryset_for_user(request.user)
    qs = qs.filter(receivable__in=scoped)
    if request.GET.get("export") == "1" and user_has_permission(request.user, "finance_export"):
        today = timezone.localdate()
        rows = [
            [
                i.receivable.number,
                i.receivable.customer.name,
                i.sequence,
                i.due_date,
                (today - i.due_date).days,
                i.outstanding_amount,
            ]
            for i in qs[:5000]
        ]
        return build_csv_response(
            filename="inadimplencia.csv",
            headers=["Título", "Cliente", "Parcela", "Vencimento", "Dias", "Saldo"],
            rows=rows,
            request=request,
            export_key="overdue",
        )
    return render(
        request,
        "finance/overdue_list.html",
        {
            "page_title": "Inadimplência",
            "installments": qs[:200],
            "buckets": overdue_buckets(qs[:500]),
        },
    )


def _crud_list(request, model, template, title, perm):
    @require_permission(perm)
    def _view(request):
        return render(
            request,
            template,
            {"page_title": title, "objects": model.objects.all()},
        )

    return _view(request)


@require_permission("financial_categories.view")
def category_list(request):
    return render(
        request,
        "finance/master_list.html",
        {
            "page_title": "Categorias financeiras",
            "objects": FinancialCategory.objects.all(),
            "create_url": "finance:category_create",
            "columns": ["code", "name", "category_type", "is_active"],
        },
    )


@require_permission("financial_categories.create")
def category_create(request):
    form = FinancialCategoryForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.created_by = request.user
        obj.updated_by = request.user
        obj.save()
        messages.success(request, "Categoria criada.")
        return redirect("finance:category_list")
    return render(request, "finance/form.html", {"page_title": "Nova categoria", "form": form})


@require_permission("cost_centers.view")
def cost_center_list(request):
    return render(
        request,
        "finance/master_list.html",
        {
            "page_title": "Centros de custo",
            "objects": CostCenter.objects.all(),
            "create_url": "finance:cost_center_create",
            "columns": ["code", "name", "is_active"],
        },
    )


@require_permission("cost_centers.create")
def cost_center_create(request):
    form = CostCenterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.created_by = request.user
        obj.save()
        messages.success(request, "Centro de custo criado.")
        return redirect("finance:cost_center_list")
    return render(request, "finance/form.html", {"page_title": "Novo centro de custo", "form": form})


@require_permission("payment_methods.view")
def payment_method_list(request):
    return render(
        request,
        "finance/master_list.html",
        {
            "page_title": "Formas de pagamento",
            "objects": PaymentMethod.objects.all(),
            "create_url": "finance:payment_method_create",
            "columns": ["code", "name", "method_type", "is_active"],
        },
    )


@require_permission("payment_methods.create")
def payment_method_create(request):
    form = PaymentMethodForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.created_by = request.user
        obj.save()
        messages.success(request, "Forma de pagamento criada.")
        return redirect("finance:payment_method_list")
    return render(request, "finance/form.html", {"page_title": "Nova forma de pagamento", "form": form})


@require_permission("payment_terms.view")
def payment_term_list(request):
    return render(
        request,
        "finance/master_list.html",
        {
            "page_title": "Condições de pagamento",
            "objects": PaymentTerm.objects.all(),
            "create_url": "finance:payment_term_create",
            "columns": ["name", "installment_count", "down_payment_percent", "is_active"],
        },
    )


@require_permission("payment_terms.create")
def payment_term_create(request):
    form = PaymentTermForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.created_by = request.user
        obj.save()
        messages.success(request, "Condição criada.")
        return redirect("finance:payment_term_list")
    return render(request, "finance/form.html", {"page_title": "Nova condição", "form": form})


@require_permission("financial_accounts.view")
def account_list(request):
    from finance.services.balances import account_balance

    accounts = []
    for acc in FinancialAccount.objects.filter(is_active=True):
        accounts.append({"obj": acc, "balance": account_balance(account=acc)})
    return render(
        request,
        "finance/account_list.html",
        {"page_title": "Contas financeiras", "accounts": accounts},
    )


@require_permission("financial_accounts.create")
def account_create(request):
    form = FinancialAccountForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            obj = create_financial_account(
                data=form.cleaned_data,
                actor=request.user,
                request=request,
            )
            messages.success(request, f"Conta {obj.name} criada.")
            return redirect("finance:account_list")
        except ValidationError as exc:
            _handle(request, exc)
    return render(request, "finance/form.html", {"page_title": "Nova conta financeira", "form": form})


@require_permission("financial_movements.transfer")
def transfer_view(request):
    form = TransferForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            transfer_between_accounts(
                source_account=form.cleaned_data["source_account"],
                destination_account=form.cleaned_data["destination_account"],
                amount=form.cleaned_data["amount"],
                movement_date=form.cleaned_data["movement_date"],
                actor=request.user,
                notes=form.cleaned_data.get("notes") or "",
                request=request,
            )
            messages.success(request, "Transferência registrada.")
            return redirect("finance:movement_list")
        except ValidationError as exc:
            _handle(request, exc)
    return render(request, "finance/form.html", {"page_title": "Transferência entre contas", "form": form})


@require_permission("financial_movements.adjust")
def adjustment_view(request):
    form = AdjustmentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            create_manual_adjustment(
                account=form.cleaned_data["account"],
                direction=form.cleaned_data["direction"],
                amount=form.cleaned_data["amount"],
                movement_date=form.cleaned_data["movement_date"],
                reason=form.cleaned_data["reason"],
                actor=request.user,
                category=form.cleaned_data.get("category"),
                cost_center=form.cleaned_data.get("cost_center"),
                request=request,
            )
            messages.success(request, "Ajuste registrado.")
            return redirect("finance:movement_list")
        except ValidationError as exc:
            _handle(request, exc)
    return render(request, "finance/form.html", {"page_title": "Ajuste financeiro", "form": form})
