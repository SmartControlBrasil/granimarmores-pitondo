# ruff: noqa: PLR0913
from decimal import Decimal

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.forms import formset_factory
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

from access_control.services.authorization import require_permission
from access_control.services.authorization import user_has_permission
from materials.models import MaterialSlab
from materials.stock_models import MaterialSupplier
from production.models import ProductionOrder
from production.models import ProductionPiece
from purchasing.export import build_csv_response
from purchasing.export import sanitize_csv_cell
from purchasing.forms import CancelForm
from purchasing.forms import GeneratePayableForm
from purchasing.forms import PurchaseOrderEditForm
from purchasing.forms import PurchaseRequestForm
from purchasing.forms import PurchaseRequestItemForm
from purchasing.forms import QuotationForm
from purchasing.forms import QuotationItemForm
from purchasing.forms import ReceiptCreateForm
from purchasing.forms import ReceiptItemForm
from purchasing.forms import RejectForm
from purchasing.forms import ReturnForm
from purchasing.forms import SelectionForm
from purchasing.models import PurchaseOrder
from purchasing.models import PurchaseOrderItem
from purchasing.models import PurchaseReceipt
from purchasing.models import PurchaseReceiptDivergence
from purchasing.models import PurchaseReceiptItem
from purchasing.models import PurchaseRequest
from purchasing.models import PurchaseRequestItem
from purchasing.models import PurchaseReturn
from purchasing.models import SupplierQuotation
from purchasing.periods import PERIOD_CHOICES
from purchasing.periods import parse_purchasing_period
from purchasing.selectors import active_suppliers
from purchasing.selectors import filter_purchase_orders
from purchasing.selectors import filter_purchase_requests
from purchasing.selectors import purchase_orders_queryset_for_user
from purchasing.selectors import purchase_requests_queryset_for_user
from purchasing.selectors import purchasing_alerts
from purchasing.selectors import purchasing_dashboard_metrics
from purchasing.selectors import quotations_queryset_for_user
from purchasing.selectors import receipts_queryset_for_user
from purchasing.selectors import supplier_history
from purchasing.services.payables_integration import generate_payable_from_purchase_order
from purchasing.services.purchase_orders import approve_purchase_order
from purchasing.services.purchase_orders import approve_purchase_selection
from purchasing.services.purchase_orders import cancel_purchase_order
from purchasing.services.quotations import compare_quotations
from purchasing.services.quotations import create_quotation
from purchasing.services.receiving import accept_receipt
from purchasing.services.receiving import create_and_complete_return
from purchasing.services.receiving import create_receipt
from purchasing.services.receiving import reject_receipt
from purchasing.services.requests import approve_purchase_request
from purchasing.services.requests import cancel_purchase_request
from purchasing.services.requests import create_purchase_request
from purchasing.services.requests import reject_purchase_request
from purchasing.services.requests import submit_purchase_request
from purchasing.services.supplier_performance import supplier_performance


def _handle(request, exc):
    messages.error(request, str(exc))


@require_permission("purchasing_dashboard.view")
def dashboard(request):
    start, end, period = parse_purchasing_period(request)
    metrics = purchasing_dashboard_metrics(user=request.user, start=start, end=end)
    alerts = purchasing_alerts(user=request.user)
    return render(
        request,
        "purchasing/dashboard.html",
        {
            "page_title": "Dashboard de Compras",
            "metrics": metrics,
            "alerts": alerts,
            "period": period,
            "period_choices": PERIOD_CHOICES,
            "start": start,
            "end": end,
        },
    )


@require_permission("purchase_requests.view")
def request_list(request):
    qs = filter_purchase_requests(purchase_requests_queryset_for_user(request.user), request.GET)
    if request.GET.get("export") == "csv":
        if not user_has_permission(request.user, "purchasing_dashboard.view") and not user_has_permission(
            request.user,
            "purchase_requests.view",
        ):
            messages.error(request, "Sem permissão para exportar.")
            return redirect("purchasing:request_list")
        rows = [
            [
                r.number,
                r.get_request_type_display(),
                r.requested_by.get_username(),
                r.get_priority_display(),
                r.required_date,
                r.get_status_display(),
            ]
            for r in qs[:2000]
        ]
        return build_csv_response(
            filename="solicitacoes.csv",
            headers=["Número", "Tipo", "Solicitante", "Prioridade", "Necessário em", "Status"],
            rows=rows,
            request=request,
            export_key="requests",
        )
    page = Paginator(qs, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "purchasing/request_list.html",
        {"page_title": "Solicitações de Compra", "page_obj": page, "q": request.GET.get("q", "")},
    )


@require_permission("purchase_requests.create")
def request_create(request):
    ItemFormSet = formset_factory(PurchaseRequestItemForm, extra=1, can_delete=False)
    piece = None
    production_order = None
    if request.GET.get("piece"):
        piece = get_object_or_404(ProductionPiece, pk=request.GET["piece"])
    if request.GET.get("production_order"):
        production_order = get_object_or_404(ProductionOrder, pk=request.GET["production_order"])

    initial = {}
    if piece:
        initial = {
            "request_type": "slab",
            "justification": f"Necessidade de chapa para peça #{piece.pk}",
            "source_type": "production_piece",
        }
    elif production_order:
        initial = {
            "justification": f"Necessidade de material para OP {production_order.number}",
            "source_type": "production_order",
        }

    form = PurchaseRequestForm(request.POST or None, initial=initial)
    formset = ItemFormSet(request.POST or None, prefix="items")
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        items = []
        for f in formset:
            if not f.cleaned_data:
                continue
            items.append(
                {
                    "item_type": f.cleaned_data["item_type"],
                    "material": f.cleaned_data.get("material"),
                    "description": f.cleaned_data["description"],
                    "quantity": f.cleaned_data["quantity"],
                    "unit": f.cleaned_data["unit"],
                    "estimated_unit_cost": f.cleaned_data.get("estimated_unit_cost") or Decimal("0"),
                    "technical_specification": f.cleaned_data.get("technical_specification") or "",
                    "preferred_supplier": f.cleaned_data.get("preferred_supplier"),
                },
            )
        try:
            data = form.cleaned_data.copy()
            if piece:
                data["production_piece"] = piece
                data["production_order"] = piece.production_order
                data["source_id"] = piece.pk
            if production_order:
                data["production_order"] = production_order
                data["source_id"] = production_order.pk
            pr = create_purchase_request(data=data, items=items, actor=request.user, request=request)
            messages.success(request, f"Solicitação {pr.number} criada.")
            return redirect("purchasing:request_detail", pk=pr.pk)
        except ValidationError as exc:
            _handle(request, exc)
    return render(
        request,
        "purchasing/request_form.html",
        {
            "page_title": "Nova solicitação",
            "form": form,
            "formset": formset,
            "piece": piece,
            "production_order": production_order,
        },
    )


@require_permission("purchase_requests.view")
def request_detail(request, pk):
    pr = get_object_or_404(purchase_requests_queryset_for_user(request.user), pk=pk)
    return render(
        request,
        "purchasing/request_detail.html",
        {
            "page_title": pr.number,
            "obj": pr,
            "items": pr.items.select_related("material", "preferred_supplier"),
            "quotations": pr.quotations.select_related("supplier"),
            "orders": pr.purchase_orders.select_related("supplier"),
        },
    )


@require_permission("purchase_requests.update")
def request_update(request, pk):
    pr = get_object_or_404(PurchaseRequest, pk=pk)
    if pr.status not in {"draft", "submitted", "under_review"}:
        messages.error(request, "Solicitação não pode ser editada neste status.")
        return redirect("purchasing:request_detail", pk=pk)
    form = PurchaseRequestForm(request.POST or None, instance=pr)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.updated_by = request.user
        obj.save()
        messages.success(request, "Solicitação atualizada.")
        return redirect("purchasing:request_detail", pk=pk)
    return render(
        request,
        "purchasing/form.html",
        {"page_title": f"Editar {pr.number}", "form": form},
    )


@require_permission("purchase_requests.submit")
def request_submit(request, pk):
    pr = get_object_or_404(PurchaseRequest, pk=pk)
    if request.method == "POST":
        try:
            submit_purchase_request(purchase_request=pr, actor=request.user, request=request)
            messages.success(request, "Solicitação enviada.")
        except ValidationError as exc:
            _handle(request, exc)
    return redirect("purchasing:request_detail", pk=pk)


@require_permission("purchase_requests.approve")
def request_approve(request, pk):
    pr = get_object_or_404(PurchaseRequest, pk=pk)
    if request.method == "POST":
        try:
            approve_purchase_request(purchase_request=pr, actor=request.user, request=request)
            messages.success(request, "Solicitação aprovada.")
        except ValidationError as exc:
            _handle(request, exc)
    return redirect("purchasing:request_detail", pk=pk)


@require_permission("purchase_requests.reject")
def request_reject(request, pk):
    pr = get_object_or_404(PurchaseRequest, pk=pk)
    form = RejectForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            reject_purchase_request(
                purchase_request=pr,
                actor=request.user,
                reason=form.cleaned_data["reason"],
                request=request,
            )
            messages.success(request, "Solicitação rejeitada.")
            return redirect("purchasing:request_detail", pk=pk)
        except ValidationError as exc:
            _handle(request, exc)
    return render(
        request,
        "purchasing/form.html",
        {"page_title": f"Rejeitar {pr.number}", "form": form},
    )


@require_permission("purchase_requests.cancel")
def request_cancel(request, pk):
    pr = get_object_or_404(PurchaseRequest, pk=pk)
    form = CancelForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            cancel_purchase_request(
                purchase_request=pr,
                actor=request.user,
                reason=form.cleaned_data["reason"],
                request=request,
            )
            messages.success(request, "Solicitação cancelada.")
            return redirect("purchasing:request_detail", pk=pk)
        except ValidationError as exc:
            _handle(request, exc)
    return render(
        request,
        "purchasing/form.html",
        {"page_title": f"Cancelar {pr.number}", "form": form},
    )


@require_permission("supplier_quotations.view")
def request_compare(request, pk):
    pr = get_object_or_404(PurchaseRequest, pk=pk)
    comparison = compare_quotations(purchase_request=pr)
    choices = []
    for row in comparison["rows"]:
        for offer in row["offers"]:
            label = (
                f"{row['request_item'].description} | {offer['supplier'].name} | "
                f"R$ {offer['unit_price']} | {offer['delivery_days']}d"
            )
            choices.append((offer["item"].pk, label))
    form = SelectionForm(request.POST or None, choices=choices)
    if request.method == "POST" and form.is_valid():
        if not user_has_permission(request.user, "purchase_orders.approve") and not user_has_permission(
            request.user,
            "purchase_requests.approve",
        ):
            messages.error(request, "Sem permissão para aprovar seleção.")
            return redirect("purchasing:request_compare", pk=pk)
        try:
            orders = approve_purchase_selection(
                purchase_request=pr,
                selections=[{"quotation_item_id": i} for i in form.cleaned_data["quotation_item_ids"]],
                actor=request.user,
                justification=form.cleaned_data.get("justification") or "",
                request=request,
            )
            messages.success(request, f"Gerados {len(orders)} pedido(s) de compra.")
            return redirect("purchasing:order_list")
        except ValidationError as exc:
            _handle(request, exc)
    return render(
        request,
        "purchasing/compare.html",
        {
            "page_title": f"Comparar cotações — {pr.number}",
            "obj": pr,
            "comparison": comparison,
            "form": form,
        },
    )


@require_permission("supplier_quotations.view")
def quotation_list(request):
    qs = quotations_queryset_for_user(request.user)
    if request.GET.get("export") == "csv":
        rows = [[q.number, q.supplier.name, q.purchase_request.number, q.total_amount, q.status] for q in qs[:2000]]
        return build_csv_response(
            filename="cotacoes.csv",
            headers=["Número", "Fornecedor", "Solicitação", "Total", "Status"],
            rows=rows,
            request=request,
            export_key="quotations",
        )
    page = Paginator(qs, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "purchasing/quotation_list.html",
        {"page_title": "Cotações", "page_obj": page},
    )


@require_permission("supplier_quotations.create")
def quotation_create(request):
    ItemFormSet = formset_factory(QuotationItemForm, extra=1)
    form = QuotationForm(request.POST or None)
    formset = ItemFormSet(request.POST or None, prefix="items")
    if request.GET.get("request"):
        form.fields["purchase_request"].initial = request.GET["request"]
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        items = []
        for f in formset:
            if not f.cleaned_data:
                continue
            req_item = None
            if f.cleaned_data.get("request_item_id"):
                req_item = PurchaseRequestItem.objects.filter(
                    pk=f.cleaned_data["request_item_id"],
                    purchase_request=form.cleaned_data["purchase_request"],
                ).first()
            items.append(
                {
                    "request_item": req_item,
                    "description": f.cleaned_data["description"],
                    "quantity": f.cleaned_data["quantity"],
                    "unit": f.cleaned_data["unit"],
                    "unit_price": f.cleaned_data["unit_price"],
                    "delivery_days": f.cleaned_data.get("delivery_days") or 0,
                },
            )
        try:
            q = create_quotation(
                purchase_request=form.cleaned_data["purchase_request"],
                supplier=form.cleaned_data["supplier"],
                data=form.cleaned_data,
                items=items,
                actor=request.user,
                request=request,
            )
            messages.success(request, f"Cotação {q.number} registrada.")
            return redirect("purchasing:quotation_detail", pk=q.pk)
        except ValidationError as exc:
            _handle(request, exc)
    return render(
        request,
        "purchasing/quotation_form.html",
        {"page_title": "Nova cotação", "form": form, "formset": formset},
    )


@require_permission("supplier_quotations.view")
def quotation_detail(request, pk):
    q = get_object_or_404(quotations_queryset_for_user(request.user), pk=pk)
    return render(
        request,
        "purchasing/quotation_detail.html",
        {"page_title": q.number, "obj": q, "items": q.items.select_related("request_item")},
    )


@require_permission("supplier_quotations.update")
def quotation_update(request, pk):
    q = get_object_or_404(SupplierQuotation, pk=pk)
    if q.status in {"selected", "cancelled"}:
        messages.error(request, "Cotação não editável.")
        return redirect("purchasing:quotation_detail", pk=pk)
    form = QuotationForm(request.POST or None, instance=q)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.updated_by = request.user
        obj.save()
        messages.success(request, "Cotação atualizada.")
        return redirect("purchasing:quotation_detail", pk=pk)
    return render(request, "purchasing/form.html", {"page_title": f"Editar {q.number}", "form": form})


@require_permission("purchase_orders.view")
def order_list(request):
    qs = filter_purchase_orders(purchase_orders_queryset_for_user(request.user), request.GET)
    if request.GET.get("export") == "csv":
        rows = [
            [o.number, o.supplier.name, o.order_date, o.total_amount, o.status, bool(o.payable_id)]
            for o in qs[:2000]
        ]
        return build_csv_response(
            filename="pedidos_compra.csv",
            headers=["Número", "Fornecedor", "Data", "Total", "Status", "Financeiro"],
            rows=rows,
            request=request,
            export_key="orders",
        )
    page = Paginator(qs, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "purchasing/order_list.html",
        {"page_title": "Pedidos de Compra", "page_obj": page},
    )


@require_permission("purchase_orders.view")
def order_detail(request, pk):
    order = get_object_or_404(purchase_orders_queryset_for_user(request.user), pk=pk)
    return render(
        request,
        "purchasing/order_detail.html",
        {
            "page_title": order.number,
            "obj": order,
            "items": order.items.select_related("material"),
            "receipts": order.receipts.all(),
            "can_generate_payable": user_has_permission(request.user, "purchasing_generate_payable"),
        },
    )


@require_permission("purchase_orders.update")
def order_update(request, pk):
    order = get_object_or_404(PurchaseOrder, pk=pk)
    if order.receipts.exists():
        messages.error(request, "Pedido com recebimento não pode ter valores recalculados; só metadados.")
    form = PurchaseOrderEditForm(request.POST or None, instance=order)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.updated_by = request.user
        obj.save()
        messages.success(request, "Pedido atualizado.")
        return redirect("purchasing:order_detail", pk=pk)
    return render(request, "purchasing/form.html", {"page_title": f"Editar {order.number}", "form": form})


@require_permission("purchase_orders.approve")
def order_approve(request, pk):
    order = get_object_or_404(PurchaseOrder, pk=pk)
    if request.method == "POST":
        try:
            approve_purchase_order(purchase_order=order, actor=request.user, request=request)
            messages.success(request, "Pedido aprovado.")
        except ValidationError as exc:
            _handle(request, exc)
    return redirect("purchasing:order_detail", pk=pk)


@require_permission("purchase_orders.cancel")
def order_cancel(request, pk):
    order = get_object_or_404(PurchaseOrder, pk=pk)
    form = CancelForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            cancel_purchase_order(
                purchase_order=order,
                actor=request.user,
                reason=form.cleaned_data["reason"],
                request=request,
            )
            messages.success(request, "Pedido cancelado.")
            return redirect("purchasing:order_detail", pk=pk)
        except ValidationError as exc:
            _handle(request, exc)
    return render(request, "purchasing/form.html", {"page_title": f"Cancelar {order.number}", "form": form})


@require_permission("purchasing_generate_payable")
def order_generate_payable(request, pk):
    order = get_object_or_404(PurchaseOrder, pk=pk)
    form = GeneratePayableForm(request.POST or None, initial={"due_date": timezone.localdate()})
    if request.method == "POST" and form.is_valid():
        try:
            payable = generate_payable_from_purchase_order(
                purchase_order=order,
                actor=request.user,
                due_date=form.cleaned_data["due_date"],
                payment_term=form.cleaned_data.get("payment_term"),
                request=request,
            )
            messages.success(request, f"Conta a pagar {payable.number} gerada.")
            return redirect("purchasing:order_detail", pk=pk)
        except ValidationError as exc:
            _handle(request, exc)
    return render(
        request,
        "purchasing/form.html",
        {"page_title": f"Gerar conta a pagar — {order.number}", "form": form},
    )


@require_permission("purchase_receipts.view")
def receipt_list(request):
    qs = receipts_queryset_for_user(request.user)
    if request.GET.get("export") == "csv":
        rows = [[r.number, r.purchase_order.number, r.received_at, r.status] for r in qs[:2000]]
        return build_csv_response(
            filename="recebimentos.csv",
            headers=["Número", "Pedido", "Data", "Status"],
            rows=rows,
            request=request,
            export_key="receipts",
        )
    page = Paginator(qs, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "purchasing/receipt_list.html",
        {"page_title": "Recebimentos", "page_obj": page},
    )


@require_permission("purchase_receipts.create")
def receipt_create(request):
    order = None
    if request.GET.get("order") or request.POST.get("order_id"):
        order = get_object_or_404(
            PurchaseOrder,
            pk=request.GET.get("order") or request.POST.get("order_id"),
        )
    ItemFormSet = formset_factory(ReceiptItemForm, extra=0)
    initial_items = []
    if order:
        for poi in order.items.all():
            if poi.outstanding_quantity > 0:
                initial_items.append(
                    {
                        "purchase_order_item_id": poi.pk,
                        "received_quantity": poi.outstanding_quantity,
                        "accepted_quantity": poi.outstanding_quantity,
                        "rejected_quantity": Decimal("0"),
                        "actual_unit_cost": poi.unit_price,
                        "width": poi.width,
                        "height": poi.height,
                        "thickness": poi.thickness,
                    },
                )
    form = ReceiptCreateForm(request.POST or None)
    formset = ItemFormSet(request.POST or None, prefix="items", initial=initial_items)
    if request.method == "POST" and order and form.is_valid() and formset.is_valid():
        items = []
        for f in formset:
            cd = f.cleaned_data
            if not cd or not cd.get("received_quantity"):
                continue
            poi = get_object_or_404(PurchaseOrderItem, pk=cd["purchase_order_item_id"])
            items.append(
                {
                    "purchase_order_item": poi,
                    "received_quantity": cd["received_quantity"],
                    "accepted_quantity": cd["accepted_quantity"],
                    "rejected_quantity": cd.get("rejected_quantity") or Decimal("0"),
                    "actual_unit_cost": cd.get("actual_unit_cost") or poi.unit_price,
                    "width": cd.get("width"),
                    "height": cd.get("height"),
                    "thickness": cd.get("thickness"),
                    "batch": cd.get("batch") or "",
                    "condition": cd.get("condition"),
                    "divergence_notes": cd.get("divergence_notes") or "",
                },
            )
        try:
            receipt = create_receipt(
                purchase_order=order,
                items=items,
                actor=request.user,
                data={
                    "delivery_document": form.cleaned_data.get("delivery_document"),
                    "supplier_document": form.cleaned_data.get("supplier_document"),
                    "stock_location": form.cleaned_data.get("stock_location"),
                    "notes": form.cleaned_data.get("notes"),
                },
                allow_excess=bool(form.cleaned_data.get("allow_excess"))
                and user_has_permission(request.user, "purchase_receipts.override_quantity"),
                request=request,
            )
            messages.success(request, f"Recebimento {receipt.number} criado.")
            return redirect("purchasing:receipt_detail", pk=receipt.pk)
        except ValidationError as exc:
            _handle(request, exc)
    return render(
        request,
        "purchasing/receipt_form.html",
        {
            "page_title": "Novo recebimento",
            "form": form,
            "formset": formset,
            "order": order,
            "orders": PurchaseOrder.objects.exclude(status__in=["draft", "cancelled", "rejected"])[:100],
        },
    )


@require_permission("purchase_receipts.view")
def receipt_detail(request, pk):
    receipt = get_object_or_404(receipts_queryset_for_user(request.user), pk=pk)
    return render(
        request,
        "purchasing/receipt_detail.html",
        {
            "page_title": receipt.number,
            "obj": receipt,
            "items": receipt.items.select_related("purchase_order_item"),
            "divergences": receipt.divergences.all(),
        },
    )


@require_permission("purchase_receipts.inspect")
def receipt_inspect(request, pk):
    receipt = get_object_or_404(PurchaseReceipt, pk=pk)
    return redirect("purchasing:receipt_detail", pk=receipt.pk)


@require_permission("purchase_receipts.accept")
def receipt_accept(request, pk):
    receipt = get_object_or_404(PurchaseReceipt, pk=pk)
    if request.method == "POST":
        try:
            accept_receipt(receipt=receipt, actor=request.user, request=request)
            messages.success(request, "Recebimento aceito.")
        except ValidationError as exc:
            _handle(request, exc)
    return redirect("purchasing:receipt_detail", pk=pk)


@require_permission("purchase_receipts.reject")
def receipt_reject(request, pk):
    receipt = get_object_or_404(PurchaseReceipt, pk=pk)
    form = RejectForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            reject_receipt(
                receipt=receipt,
                actor=request.user,
                reason=form.cleaned_data["reason"],
                request=request,
            )
            messages.success(request, "Recebimento rejeitado.")
            return redirect("purchasing:receipt_detail", pk=pk)
        except ValidationError as exc:
            _handle(request, exc)
    return render(request, "purchasing/form.html", {"page_title": f"Rejeitar {receipt.number}", "form": form})


@require_permission("purchase_divergences.view")
def divergence_list(request):
    qs = PurchaseReceiptDivergence.objects.select_related("receipt", "receipt__purchase_order").order_by(
        "-created_at",
    )
    if request.GET.get("export") == "csv":
        rows = [[d.receipt.number, d.divergence_type, d.severity, d.status, d.description] for d in qs[:2000]]
        return build_csv_response(
            filename="divergencias.csv",
            headers=["Recebimento", "Tipo", "Severidade", "Status", "Descrição"],
            rows=rows,
            request=request,
            export_key="divergences",
        )
    page = Paginator(qs, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "purchasing/divergence_list.html",
        {"page_title": "Divergências", "page_obj": page},
    )


@require_permission("purchase_returns.view")
def return_list(request):
    qs = PurchaseReturn.objects.select_related("supplier", "purchase_order").order_by("-created_at")
    page = Paginator(qs, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "purchasing/return_list.html",
        {"page_title": "Devoluções", "page_obj": page},
    )


@require_permission("purchase_returns.create")
def return_create(request):
    form = ReturnForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        receipt_item = get_object_or_404(PurchaseReceiptItem, pk=form.cleaned_data["receipt_item_id"])
        slab = None
        if form.cleaned_data.get("slab_id"):
            slab = get_object_or_404(MaterialSlab, pk=form.cleaned_data["slab_id"])
        try:
            ret = create_and_complete_return(
                supplier=receipt_item.receipt.purchase_order.supplier,
                receipt=receipt_item.receipt,
                items=[
                    {
                        "receipt_item": receipt_item,
                        "quantity": form.cleaned_data["quantity"],
                        "slab": slab,
                    },
                ],
                actor=request.user,
                reason=form.cleaned_data["reason"],
                notes=form.cleaned_data.get("notes") or "",
                request=request,
            )
            messages.success(request, f"Devolução {ret.number} concluída.")
            return redirect("purchasing:return_list")
        except ValidationError as exc:
            _handle(request, exc)
    return render(request, "purchasing/form.html", {"page_title": "Nova devolução", "form": form})


@require_permission("material_suppliers.view")
def supplier_list(request):
    qs = active_suppliers()
    if request.GET.get("export") == "csv":
        rows = [[s.name, s.document, s.city, s.state, s.phone] for s in qs[:2000]]
        return build_csv_response(
            filename="fornecedores_compras.csv",
            headers=["Nome", "Documento", "Cidade", "UF", "Telefone"],
            rows=rows,
            request=request,
            export_key="suppliers",
        )
    page = Paginator(qs, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "purchasing/supplier_list.html",
        {"page_title": "Fornecedores", "page_obj": page},
    )


@require_permission("material_suppliers.view")
def supplier_detail(request, pk):
    supplier = get_object_or_404(MaterialSupplier, pk=pk)
    history = supplier_history(supplier=supplier)
    start, end, _ = parse_purchasing_period(request)
    performance = supplier_performance(supplier=supplier, start=start, end=end)
    return render(
        request,
        "purchasing/supplier_detail.html",
        {
            "page_title": supplier.name,
            "obj": supplier,
            "history": history,
            "performance": performance,
        },
    )


@require_permission("purchasing_dashboard.view")
def comparison_hub(request):
    qs = PurchaseRequest.objects.filter(
        status__in=["approved", "quoted", "partially_quoted"],
    ).order_by("-created_at")[:50]
    return render(
        request,
        "purchasing/comparison_hub.html",
        {"page_title": "Comparação de cotações", "requests": qs},
    )


# silence unused import warning for sanitize in tests via re-export
__all__ = ["sanitize_csv_cell"]
