# ruff: noqa: PLR0913
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render

from access_control.services.authorization import require_permission
from audit.models import AuditEvent
from commercial.models import CommercialPartner
from commercial.models import CommercialSource
from commercial.models import ProjectType
from production.forms import AcceptQuoteForm
from production.forms import RefuseQuoteForm
from production.models import SalesOrder
from production.models import SalesOrderStatus
from quotes.forms import CommercialPolicyForm
from quotes.forms import QuoteApprovalForm
from quotes.forms import QuoteCancellationForm
from quotes.forms import QuoteForm
from quotes.forms import QuoteItemFinishForm
from quotes.forms import QuoteItemForm
from quotes.forms import QuoteItemMeasurementForm
from quotes.forms import QuoteRejectionForm
from quotes.forms import QuoteSendForm
from quotes.forms import QuoteServiceForm
from quotes.forms import QuoteSubmitForApprovalForm
from quotes.models import Quote
from quotes.models import QuoteDelivery
from quotes.models import QuoteItem
from quotes.models import QuoteStatus
from quotes.models import QuoteVersion
from quotes.services.delivery import send_quote
from quotes.services.pdf import generate_quote_pdf
from quotes.services.pdf import record_pdf_download
from quotes.services.query import can_access_quote
from quotes.services.query import quote_queryset_for_user
from quotes.services.quote_management import remove_quote_item
from quotes.services.quote_management import save_item_finish
from quotes.services.quote_management import save_measurement
from quotes.services.quote_management import save_quote
from quotes.services.quote_management import save_quote_item
from quotes.services.quote_management import save_quote_service
from quotes.services.versioning import create_version
from quotes.services.acceptance import accept_quote
from quotes.services.acceptance import refuse_quote
from quotes.services.workflow import active_policy
from quotes.services.workflow import approve_quote
from quotes.services.workflow import cancel_quote
from quotes.services.workflow import reject_quote
from quotes.services.workflow import submit_for_approval


def _quote_or_403(request, pk):
    quote = get_object_or_404(
        Quote.objects.select_related("customer", "salesperson", "lead"),
        pk=pk,
    )
    if not can_access_quote(request.user, quote):
        message = "Você não tem acesso a este orçamento."
        raise PermissionDenied(message)
    return quote


@require_permission("quotes.view")
def quote_list(request):
    qs = quote_queryset_for_user(request.user).select_related(
        "customer",
        "project_type",
        "commercial_source",
        "partner",
    ).order_by("-created_at")
    search = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    source_id = request.GET.get("source", "").strip()
    project_type_id = request.GET.get("project_type", "").strip()
    partner_id = request.GET.get("partner", "").strip()
    if search:
        qs = qs.filter(number__icontains=search)
    if status:
        qs = qs.filter(status=status)
    if source_id.isdigit():
        qs = qs.filter(commercial_source_id=int(source_id))
    if project_type_id.isdigit():
        qs = qs.filter(project_type_id=int(project_type_id))
    if partner_id.isdigit():
        qs = qs.filter(partner_id=int(partner_id))
    page_obj = Paginator(qs, 20).get_page(request.GET.get("page"))
    return render(
        request,
        "quotes/quote_list.html",
        {
            "page_title": "Orçamentos",
            "page_obj": page_obj,
            "search": search,
            "status": status,
            "statuses": QuoteStatus.choices,
            "sources": CommercialSource.objects.filter(is_active=True).order_by("name"),
            "project_types": ProjectType.objects.filter(is_active=True).order_by("name"),
            "partners": CommercialPartner.objects.filter(is_active=True).order_by("name"),
            "selected_source": source_id,
            "selected_project_type": project_type_id,
            "selected_partner": partner_id,
        },
    )


@require_permission("quotes.view")
def quote_detail(request, pk):
    quote = _quote_or_403(request, pk)
    sales_order = SalesOrder.objects.filter(quote=quote).exclude(
        status=SalesOrderStatus.CANCELLED,
    ).first()
    current_acceptance = quote.acceptances.filter(is_current=True).first()
    accept_form = AcceptQuoteForm(
        initial={"customer_name": quote.customer.name},
    )
    refuse_form = RefuseQuoteForm()
    return render(
        request,
        "quotes/quote_detail.html",
        {
            "page_title": quote.number,
            "quote": quote,
            "sales_order": sales_order,
            "acceptances": quote.acceptances.select_related("contact_channel", "loss_reason", "recorded_by"),
            "current_acceptance": current_acceptance,
            "accept_form": accept_form,
            "refuse_form": refuse_form,
        },
    )


@require_permission("quotes.accept")
def quote_accept(request, pk):
    quote = _quote_or_403(request, pk)
    form = AcceptQuoteForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            result = accept_quote(
                quote=quote,
                actor=request.user,
                request=request,
                customer_name=form.cleaned_data["customer_name"],
                customer_document=form.cleaned_data.get("customer_document", ""),
                acceptance_notes=form.cleaned_data.get("acceptance_notes", ""),
                acceptance_channel=form.cleaned_data.get("acceptance_channel"),
            )
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, str(exc))
        else:
            if isinstance(result, SalesOrder):
                messages.success(request, f"Orçamento aceito. Pedido {result.number} criado.")
            else:
                messages.success(request, "Orçamento aceito.")
            return redirect("quotes:detail", pk=quote.pk)
    messages.error(request, "Dados inválidos para aceite.")
    return redirect("quotes:detail", pk=pk)


@require_permission("quotes.refuse")
def quote_refuse(request, pk):
    quote = _quote_or_403(request, pk)
    form = RefuseQuoteForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            refuse_quote(
                quote=quote,
                actor=request.user,
                request=request,
                loss_reason=form.cleaned_data["loss_reason"],
                notes=form.cleaned_data.get("notes", ""),
                acceptance_channel=form.cleaned_data.get("acceptance_channel"),
            )
        except (ValidationError, PermissionDenied) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Recusa registrada.")
            return redirect("quotes:detail", pk=quote.pk)
    messages.error(request, "Dados inválidos para recusa.")
    return redirect("quotes:detail", pk=pk)


@require_permission("quotes.create")
def quote_create(request):
    form = QuoteForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        quote = save_quote(form=form, actor=request.user, request=request)
        messages.success(request, "Orçamento criado com sucesso.")
        return redirect("quotes:detail", pk=quote.pk)
    return render(
        request,
        "erp/form.html",
        {"page_title": "Novo orçamento", "form": form, "cancel_url": "quotes:list"},
    )


@require_permission("quotes.update")
def quote_update(request, pk):
    quote = _quote_or_403(request, pk)
    form = QuoteForm(request.POST or None, instance=quote)
    if request.method == "POST" and form.is_valid():
        try:
            quote = save_quote(form=form, actor=request.user, request=request)
        except PermissionDenied as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Orçamento atualizado com sucesso.")
            return redirect("quotes:detail", pk=quote.pk)
    return render(
        request,
        "erp/form.html",
        {
            "page_title": f"Editar {quote.number}",
            "form": form,
            "cancel_url": "quotes:list",
        },
    )


@require_permission("quotes.update")
def quote_items(request, pk):
    quote = _quote_or_403(request, pk)
    items = quote.items.select_related("material").prefetch_related(
        "measurements",
        "finishes",
    )
    services = quote.services.select_related("service")
    return render(
        request,
        "quotes/quote_items.html",
        {
            "page_title": f"Itens de {quote.number}",
            "quote": quote,
            "items": items,
            "services": services,
        },
    )


@require_permission("quotes.update")
def quote_item_create(request, pk):
    quote = _quote_or_403(request, pk)
    form = QuoteItemForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            item = save_quote_item(
                quote=quote,
                form=form,
                actor=request.user,
                request=request,
            )
        except (PermissionDenied, ValidationError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Item salvo com sucesso.")
            return redirect("quotes:item_detail", pk=quote.pk, item_pk=item.pk)
    return render(
        request,
        "erp/form.html",
        {"page_title": "Novo item", "form": form, "cancel_url": "quotes:items"},
    )


@require_permission("quotes.update")
def quote_item_detail(request, pk, item_pk):
    quote = _quote_or_403(request, pk)
    item = get_object_or_404(
        QuoteItem.objects.prefetch_related("measurements", "finishes"),
        pk=item_pk,
        quote=quote,
    )
    return render(
        request,
        "quotes/quote_item_detail.html",
        {"page_title": str(item), "quote": quote, "item": item},
    )


@require_permission("quotes.update")
def quote_item_update(request, pk, item_pk):
    quote = _quote_or_403(request, pk)
    item = get_object_or_404(QuoteItem, pk=item_pk, quote=quote)
    form = QuoteItemForm(request.POST or None, instance=item)
    if request.method == "POST" and form.is_valid():
        try:
            save_quote_item(quote=quote, form=form, actor=request.user, request=request)
        except (PermissionDenied, ValidationError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Item atualizado com sucesso.")
            return redirect("quotes:items", pk=quote.pk)
    return render(
        request,
        "erp/form.html",
        {"page_title": "Editar item", "form": form, "cancel_url": "quotes:items"},
    )


@require_permission("quotes.update")
def quote_item_remove(request, pk, item_pk):
    quote = _quote_or_403(request, pk)
    item = get_object_or_404(QuoteItem, pk=item_pk, quote=quote)
    if request.method == "POST":
        remove_quote_item(item=item, actor=request.user, request=request)
        messages.success(request, "Item removido com sucesso.")
        return redirect("quotes:items", pk=quote.pk)
    return render(
        request,
        "erp/confirm_action.html",
        {"page_title": "Remover item", "message": f"Remover {item}?"},
    )


@require_permission("quotes.update")
def measurement_create(request, pk, item_pk):
    quote = _quote_or_403(request, pk)
    item = get_object_or_404(QuoteItem, pk=item_pk, quote=quote)
    form = QuoteItemMeasurementForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        save_measurement(item=item, form=form, actor=request.user, request=request)
        messages.success(request, "Medida salva com sucesso.")
        return redirect("quotes:item_detail", pk=quote.pk, item_pk=item.pk)
    return render(
        request,
        "erp/form.html",
        {"page_title": "Nova medida", "form": form, "cancel_url": "quotes:items"},
    )


@require_permission("quotes.update")
def finish_create(request, pk, item_pk):
    quote = _quote_or_403(request, pk)
    item = get_object_or_404(QuoteItem, pk=item_pk, quote=quote)
    form = QuoteItemFinishForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        save_item_finish(item=item, form=form, actor=request.user, request=request)
        messages.success(request, "Acabamento salvo com sucesso.")
        return redirect("quotes:item_detail", pk=quote.pk, item_pk=item.pk)
    return render(
        request,
        "erp/form.html",
        {
            "page_title": "Novo acabamento do item",
            "form": form,
            "cancel_url": "quotes:items",
        },
    )


@require_permission("quotes.update")
def service_create(request, pk):
    quote = _quote_or_403(request, pk)
    form = QuoteServiceForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        save_quote_service(quote=quote, form=form, actor=request.user, request=request)
        messages.success(request, "Serviço salvo com sucesso.")
        return redirect("quotes:items", pk=quote.pk)
    return render(
        request,
        "erp/form.html",
        {
            "page_title": "Novo serviço do orçamento",
            "form": form,
            "cancel_url": "quotes:items",
        },
    )


@require_permission("quotes.update")
def quote_review(request, pk):
    quote = _quote_or_403(request, pk)
    form = QuoteSubmitForApprovalForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        submit_for_approval(
            quote=quote,
            actor=request.user,
            request=request,
            manual=form.cleaned_data["manual_approval"],
        )
        messages.success(
            request,
            "Orçamento revisado e encaminhado no fluxo comercial.",
        )
        return redirect("quotes:detail", pk=quote.pk)
    return render(
        request,
        "quotes/quote_review.html",
        {"page_title": f"Revisar {quote.number}", "quote": quote, "form": form},
    )


@require_permission("quotes.approve")
def quote_approve(request, pk):
    quote = _quote_or_403(request, pk)
    form = QuoteApprovalForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            approve_quote(
                quote=quote,
                actor=request.user,
                request=request,
                note=form.cleaned_data["note"],
            )
        except (PermissionDenied, ValidationError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Orçamento aprovado com sucesso.")
            return redirect("quotes:detail", pk=quote.pk)
    return render(
        request,
        "erp/form.html",
        {"page_title": "Aprovar orçamento", "form": form, "cancel_url": "quotes:list"},
    )


@require_permission("quotes.approve")
def quote_reject(request, pk):
    quote = _quote_or_403(request, pk)
    form = QuoteRejectionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        reject_quote(
            quote=quote,
            actor=request.user,
            request=request,
            reason=form.cleaned_data["reason"],
        )
        messages.success(request, "Orçamento rejeitado.")
        return redirect("quotes:detail", pk=quote.pk)
    return render(
        request,
        "erp/form.html",
        {"page_title": "Rejeitar orçamento", "form": form, "cancel_url": "quotes:list"},
    )


@require_permission("quotes.cancel")
def quote_cancel(request, pk):
    quote = _quote_or_403(request, pk)
    form = QuoteCancellationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        cancel_quote(
            quote=quote,
            actor=request.user,
            request=request,
            reason=form.cleaned_data["reason"],
        )
        messages.success(request, "Orçamento cancelado.")
        return redirect("quotes:detail", pk=quote.pk)
    return render(
        request,
        "erp/form.html",
        {"page_title": "Cancelar orçamento", "form": form, "cancel_url": "quotes:list"},
    )


@require_permission("quotes.view")
def quote_versions(request, pk):
    quote = _quote_or_403(request, pk)
    return render(
        request,
        "quotes/version_list.html",
        {
            "page_title": f"Versões de {quote.number}",
            "quote": quote,
            "versions": quote.versions.all(),
        },
    )


@require_permission("quotes.send")
def quote_send(request, pk):
    quote = _quote_or_403(request, pk)
    version = quote.versions.order_by("-version_number").first() or create_version(
        quote=quote,
        actor=request.user,
        request=request,
    )
    initial = {
        "recipient": quote.customer.email,
        "subject": f"Orçamento {quote.number}",
        "message": "Segue orçamento em anexo.",
        "channel": QuoteDelivery.Channel.EMAIL,
    }
    form = QuoteSendForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        try:
            send_quote(
                quote=quote,
                version=version,
                actor=request.user,
                request=request,
                **form.cleaned_data,
            )
        except (ValidationError, Exception) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Orçamento enviado com sucesso.")
            return redirect("quotes:detail", pk=quote.pk)
    return render(
        request,
        "erp/form.html",
        {"page_title": "Enviar orçamento", "form": form, "cancel_url": "quotes:list"},
    )


@require_permission("quotes.view")
def quote_delivery_history(request, pk):
    quote = _quote_or_403(request, pk)
    return render(
        request,
        "quotes/delivery_history.html",
        {
            "page_title": f"Histórico de envios {quote.number}",
            "quote": quote,
            "deliveries": quote.deliveries.all(),
        },
    )


@require_permission("quotes.view")
def quote_history(request, pk):
    quote = _quote_or_403(request, pk)
    events = AuditEvent.objects.filter(object_type="Quote", object_id=str(quote.pk))
    return render(
        request,
        "quotes/quote_history.html",
        {"page_title": f"Histórico {quote.number}", "quote": quote, "events": events},
    )


@require_permission("quotes.view")
def quote_pdf(request, pk, version):
    quote = _quote_or_403(request, pk)
    quote_version = get_object_or_404(QuoteVersion, quote=quote, version_number=version)
    if not quote_version.pdf_file:
        generate_quote_pdf(version=quote_version, actor=request.user, request=request)
    record_pdf_download(version=quote_version, actor=request.user, request=request)
    return FileResponse(
        quote_version.pdf_file.open("rb"),
        content_type="application/pdf",
    )


@require_permission("quotes.manage_policy")
def policy_update(request):
    policy = active_policy()
    form = CommercialPolicyForm(request.POST or None, instance=policy)
    if request.method == "POST" and form.is_valid():
        policy = form.save(commit=False)
        policy.updated_by = request.user
        policy.save()
        messages.success(request, "Política comercial atualizada.")
        return redirect("quotes:policy")
    return render(
        request,
        "erp/form.html",
        {"page_title": "Política comercial", "form": form, "cancel_url": "quotes:list"},
    )
