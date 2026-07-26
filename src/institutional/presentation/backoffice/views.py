from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count
from django.db.models import Sum
from django.db.models import Q
from django.http import FileResponse
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from src.institutional.application.services.access_policy import backoffice_required
from src.institutional.application.services.access_policy import can_add_note
from src.institutional.application.services.access_policy import can_assign_lead
from src.institutional.application.services.access_policy import can_change_lead
from src.institutional.application.services.access_policy import can_view_audit
from src.institutional.application.services.access_policy import can_view_all_leads
from src.institutional.application.services.access_policy import can_change_opportunity
from src.institutional.application.services.access_policy import can_convert_lead_to_opportunity
from src.institutional.application.services.access_policy import get_visible_opportunities
from src.institutional.application.services.access_policy import get_visible_quotes
from src.institutional.application.services.access_policy import get_visible_contact_requests
from src.institutional.application.services.access_policy import user_role_label
from src.institutional.application.services.lead_management import add_contact_note
from src.institutional.application.services.lead_management import assign_contact_request
from src.institutional.application.services.lead_management import change_contact_status
from src.institutional.application.services.opportunity_management import EDITABLE_QUOTE_STATUSES
from src.institutional.application.services.opportunity_management import change_opportunity_stage
from src.institutional.application.services.opportunity_management import change_quote_status
from src.institutional.application.services.opportunity_management import create_opportunity_from_lead
from src.institutional.application.services.opportunity_management import create_quote
from src.institutional.application.services.opportunity_management import create_quote_revision
from src.institutional.application.services.opportunity_management import update_quote_financials
from src.institutional.application.services.quote_documents import generate_quote_document
from src.institutional.application.services.quote_documents import render_quote_preview_html
from src.institutional.application.services.quote_documents import send_quote_by_email
from src.institutional.application.services.quote_documents import void_quote_document
from src.institutional.infrastructure.django.models import ContactRequest
from src.institutional.infrastructure.django.models import Opportunity
from src.institutional.infrastructure.django.models import Quote
from src.institutional.infrastructure.django.models import QuoteDocument
from src.institutional.presentation.backoffice.forms import LeadAssignForm
from src.institutional.presentation.backoffice.forms import LeadConvertForm
from src.institutional.presentation.backoffice.forms import LeadNoteForm
from src.institutional.presentation.backoffice.forms import LeadStatusForm
from src.institutional.presentation.backoffice.forms import OpportunityStageForm
from src.institutional.presentation.backoffice.forms import QuoteForm
from src.institutional.presentation.backoffice.forms import QuoteItemFormSet
from src.institutional.presentation.backoffice.forms import QuoteStatusForm
from src.institutional.presentation.backoffice.forms import QuoteSendForm


def _permission_denied_message(request):
    messages.error(request, "Você não tem permissão para executar esta ação.")


def _visible_lead_or_404(user, pk):
    return get_object_or_404(get_visible_contact_requests(user), pk=pk)


@backoffice_required
def dashboard(request):
    visible_qs = get_visible_contact_requests(request.user)
    opportunities = get_visible_opportunities(request.user)
    today = timezone.localdate()
    month_start = today.replace(day=1)
    last_7_days = timezone.now() - timedelta(days=7)
    status_counts = {item["status"]: item["total"] for item in visible_qs.values("status").annotate(total=Count("id"))}
    stage_counts = {item["stage"]: item["total"] for item in opportunities.values("stage").annotate(total=Count("id"))}
    open_stages = [
        Opportunity.Stage.QUALIFICATION,
        Opportunity.Stage.QUOTATION,
        Opportunity.Stage.QUOTATION_SENT,
        Opportunity.Stage.NEGOTIATION,
    ]
    cards = [
        {"label": "Novo", "value": status_counts.get(ContactRequest.Status.NEW, 0)},
        {"label": "Oportunidades abertas", "value": opportunities.filter(stage__in=open_stages).count()},
        {"label": "Em qualificação", "value": stage_counts.get(Opportunity.Stage.QUALIFICATION, 0)},
        {"label": "Orçamento", "value": stage_counts.get(Opportunity.Stage.QUOTATION, 0)},
        {"label": "Orçamento enviado", "value": stage_counts.get(Opportunity.Stage.QUOTATION_SENT, 0)},
        {"label": "Negociação", "value": stage_counts.get(Opportunity.Stage.NEGOTIATION, 0)},
        {"label": "Ganhos", "value": stage_counts.get(Opportunity.Stage.WON, 0)},
        {"label": "Perdidos", "value": stage_counts.get(Opportunity.Stage.LOST, 0)},
        {"label": "Valor em pipeline", "value": opportunities.filter(stage__in=open_stages).aggregate(total=Sum("estimated_value"))["total"] or 0},
        {"label": "Valor ganho no mês", "value": opportunities.filter(stage=Opportunity.Stage.WON, updated_at__date__gte=month_start).aggregate(total=Sum("estimated_value"))["total"] or 0},
        {"label": "Recebidos nos últimos 7 dias", "value": visible_qs.filter(created_at__gte=last_7_days).count()},
        {"label": "Recebidos no mês atual", "value": visible_qs.filter(created_at__date__gte=month_start).count()},
    ]
    return render(request, "backoffice/dashboard.html", {"cards": cards})


@backoffice_required
def lead_list(request):
    qs = get_visible_contact_requests(request.user).order_by("-created_at")
    search = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    assigned_to = request.GET.get("assigned_to", "").strip()
    cidade = request.GET.get("cidade", "").strip()
    start = request.GET.get("start", "").strip()
    end = request.GET.get("end", "").strip()

    if search:
        qs = qs.filter(
            Q(nome__icontains=search)
            | Q(telefone__icontains=search)
            | Q(email__icontains=search),
        )
    if status:
        qs = qs.filter(status=status)
    if assigned_to and can_view_all_leads(request.user):
        qs = qs.filter(assigned_to_id=assigned_to)
    if cidade:
        qs = qs.filter(cidade__icontains=cidade)
    if start:
        qs = qs.filter(created_at__date__gte=start)
    if end:
        qs = qs.filter(created_at__date__lte=end)

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get("page"))
    query_params = request.GET.copy()
    query_params.pop("page", None)
    context = {
        "page_obj": page_obj,
        "statuses": ContactRequest.Status.choices,
        "users": get_user_model().objects.filter(is_active=True).order_by("first_name", "username")
        if can_view_all_leads(request.user)
        else [],
        "can_filter_assigned_to": can_view_all_leads(request.user),
        "filters": {
            "q": search,
            "status": status,
            "assigned_to": assigned_to,
            "cidade": cidade,
            "start": start,
            "end": end,
        },
        "querystring": query_params.urlencode(),
    }
    return render(request, "backoffice/leads/list.html", context)


@backoffice_required
def lead_detail(request, pk):
    lead = _visible_lead_or_404(request.user, pk)
    context = {
        "lead": lead,
        "status_form": LeadStatusForm(initial={"status": lead.status}),
        "assign_form": LeadAssignForm(initial={"assigned_to": lead.assigned_to_id}),
        "note_form": LeadNoteForm(),
        "notes": lead.notes.select_related("author"),
        "audit_logs": lead.audit_logs.select_related("actor") if can_view_audit(request.user, lead) else [],
        "can_change_lead": can_change_lead(request.user, lead),
        "can_assign_lead": can_assign_lead(request.user, lead),
        "can_add_note": can_add_note(request.user, lead),
        "can_view_audit": can_view_audit(request.user, lead),
        "can_convert_lead": can_convert_lead_to_opportunity(request.user, lead),
        "convert_form": LeadConvertForm(require_assigned=lead.assigned_to_id is None),
        "opportunity": getattr(lead, "opportunity", None),
    }
    return render(request, "backoffice/leads/detail.html", context)


@backoffice_required
@require_POST
def lead_status(request, pk):
    try:
        _visible_lead_or_404(request.user, pk)
    except Http404:
        raise
    form = LeadStatusForm(request.POST)
    if form.is_valid():
        try:
            change_contact_status(
                contact_request_id=pk,
                status=form.cleaned_data["status"],
                actor=request.user,
            )
            messages.success(request, "Status atualizado com sucesso.")
        except ValidationError as exc:
            messages.error(request, exc.message)
        except PermissionDenied:
            _permission_denied_message(request)
    else:
        messages.error(request, "Status inválido.")
    return redirect(reverse("backoffice:lead_detail", args=[pk]))


@backoffice_required
@require_POST
def lead_assign(request, pk):
    try:
        _visible_lead_or_404(request.user, pk)
    except Http404:
        raise
    form = LeadAssignForm(request.POST)
    if form.is_valid():
        assigned_to = form.cleaned_data["assigned_to"]
        try:
            assign_contact_request(
                contact_request_id=pk,
                assigned_to_id=assigned_to.pk if assigned_to else None,
                actor=request.user,
            )
            messages.success(request, "Responsável atualizado com sucesso.")
        except ValidationError as exc:
            messages.error(request, exc.message)
        except PermissionDenied:
            _permission_denied_message(request)
    else:
        messages.error(request, "Responsável inválido.")
    return redirect(reverse("backoffice:lead_detail", args=[pk]))


@backoffice_required
@require_POST
def lead_note(request, pk):
    try:
        _visible_lead_or_404(request.user, pk)
    except Http404:
        raise
    form = LeadNoteForm(request.POST)
    if form.is_valid():
        try:
            add_contact_note(
                contact_request_id=pk,
                content=form.cleaned_data["content"],
                actor=request.user,
            )
            messages.success(request, "Observação adicionada com sucesso.")
        except ValidationError as exc:
            messages.error(request, exc.message)
        except PermissionDenied:
            _permission_denied_message(request)
    else:
        messages.error(request, "Informe uma observação.")
    return redirect(reverse("backoffice:lead_detail", args=[pk]))


@backoffice_required
@require_POST
def lead_convert(request, pk):
    lead = _visible_lead_or_404(request.user, pk)
    form = LeadConvertForm(request.POST, require_assigned=lead.assigned_to_id is None)
    if form.is_valid():
        try:
            opportunity = create_opportunity_from_lead(
                contact_request_id=pk,
                actor=request.user,
                assigned_to=form.cleaned_data["assigned_to"],
            )
            messages.success(request, "Lead convertido em oportunidade.")
            return redirect(reverse("backoffice:opportunity_detail", args=[opportunity.pk]))
        except ValidationError as exc:
            messages.error(request, exc.message)
        except PermissionDenied:
            _permission_denied_message(request)
    else:
        messages.error(request, "Responsável inválido para conversão.")
    return redirect(reverse("backoffice:lead_detail", args=[pk]))


def _filter_opportunities(request, qs):
    search = request.GET.get("q", "").strip()
    stage = request.GET.get("stage", "").strip()
    assigned_to = request.GET.get("assigned_to", "").strip()
    cidade = request.GET.get("cidade", "").strip()
    start = request.GET.get("start", "").strip()
    end = request.GET.get("end", "").strip()
    result = qs
    if search:
        result = result.filter(Q(customer_name__icontains=search) | Q(customer_email__icontains=search) | Q(customer_phone__icontains=search) | Q(title__icontains=search))
    if stage:
        result = result.filter(stage=stage)
    if assigned_to and can_view_all_leads(request.user):
        result = result.filter(assigned_to_id=assigned_to)
    if cidade:
        result = result.filter(city__icontains=cidade)
    if start:
        result = result.filter(created_at__date__gte=start)
    if end:
        result = result.filter(created_at__date__lte=end)
    return result, {"q": search, "stage": stage, "assigned_to": assigned_to, "cidade": cidade, "start": start, "end": end}


@backoffice_required
def opportunity_pipeline(request):
    qs, filters = _filter_opportunities(request, get_visible_opportunities(request.user).order_by("-updated_at"))
    grouped = []
    for stage, label in Opportunity.Stage.choices:
        grouped.append({"stage": stage, "label": label, "items": qs.filter(stage=stage)[:50]})
    return render(request, "backoffice/opportunities/pipeline.html", {"grouped": grouped, "stages": Opportunity.Stage.choices, "filters": filters})


@backoffice_required
def opportunity_list(request):
    qs, filters = _filter_opportunities(request, get_visible_opportunities(request.user).order_by("-updated_at"))
    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get("page"))
    query_params = request.GET.copy()
    query_params.pop("page", None)
    return render(request, "backoffice/opportunities/list.html", {"page_obj": page_obj, "stages": Opportunity.Stage.choices, "users": get_user_model().objects.filter(is_active=True).order_by("first_name", "username") if can_view_all_leads(request.user) else [], "can_filter_assigned_to": can_view_all_leads(request.user), "filters": filters, "querystring": query_params.urlencode()})


@backoffice_required
def opportunity_detail(request, pk):
    opportunity = get_object_or_404(get_visible_opportunities(request.user), pk=pk)
    return render(request, "backoffice/opportunities/detail.html", {"opportunity": opportunity, "quotes": opportunity.quotes.select_related("created_by").order_by("-created_at", "-revision"), "audit_logs": opportunity.audit_logs.select_related("actor"), "stage_form": OpportunityStageForm(initial={"stage": opportunity.stage}), "can_change_opportunity": can_change_opportunity(request.user, opportunity)})


@backoffice_required
@require_POST
def opportunity_stage(request, pk):
    get_object_or_404(get_visible_opportunities(request.user), pk=pk)
    form = OpportunityStageForm(request.POST)
    if form.is_valid():
        try:
            change_opportunity_stage(opportunity_id=pk, stage=form.cleaned_data["stage"], actor=request.user, lost_reason=form.cleaned_data["lost_reason"], lost_notes=form.cleaned_data["lost_notes"])
            messages.success(request, "Etapa atualizada com sucesso.")
        except ValidationError as exc:
            messages.error(request, exc.message)
        except PermissionDenied:
            _permission_denied_message(request)
    else:
        messages.error(request, "Etapa inválida.")
    return redirect(reverse("backoffice:opportunity_detail", args=[pk]))


@backoffice_required
def quote_new(request, opportunity_id):
    opportunity = get_object_or_404(get_visible_opportunities(request.user), pk=opportunity_id)
    if not can_change_opportunity(request.user, opportunity):
        raise PermissionDenied("Você não tem permissão para criar orçamento nesta oportunidade.")
    form = QuoteForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            quote = create_quote(opportunity_id=opportunity.pk, actor=request.user, validity_date=form.cleaned_data["validity_date"], notes=form.cleaned_data["notes"])
            messages.success(request, "Orçamento criado com sucesso.")
            return redirect(reverse("backoffice:quote_detail", args=[quote.pk]))
        except ValidationError as exc:
            messages.error(request, exc.message)
        except PermissionDenied:
            _permission_denied_message(request)
    return render(request, "backoffice/quotes/form.html", {"form": form, "opportunity": opportunity})


def _quote_items_initial(quote):
    return [{"id": item.pk, "description": item.description, "quantity": item.quantity, "unit": item.unit, "unit_price": item.unit_price} for item in quote.items.all()]


@backoffice_required
def quote_detail(request, pk):
    quote = get_object_or_404(get_visible_quotes(request.user).prefetch_related("items"), pk=pk)
    can_change_quote = can_change_opportunity(request.user, quote.opportunity)
    editable = can_change_quote and quote.status in EDITABLE_QUOTE_STATUSES
    if request.method == "POST":
        if not editable:
            raise PermissionDenied("Este orçamento não permite edição financeira.")
        form = QuoteForm(request.POST)
        formset = QuoteItemFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            try:
                update_quote_financials(quote_id=quote.pk, actor=request.user, discount_amount=form.cleaned_data["discount_amount"] or 0, validity_date=form.cleaned_data["validity_date"], notes=form.cleaned_data["notes"], items_data=formset.cleaned_data)
                messages.success(request, "Orçamento atualizado com sucesso.")
                return redirect(reverse("backoffice:quote_detail", args=[quote.pk]))
            except ValidationError as exc:
                messages.error(request, exc.message)
            except PermissionDenied:
                _permission_denied_message(request)
        else:
            messages.error(request, "Revise os itens do orçamento.")
    else:
        form = QuoteForm(initial={"validity_date": quote.validity_date, "discount_amount": quote.discount_amount, "notes": quote.notes})
        formset = QuoteItemFormSet(initial=_quote_items_initial(quote))
    return render(
        request,
        "backoffice/quotes/detail.html",
        {
            "quote": quote,
            "form": form,
            "formset": formset,
            "status_form": QuoteStatusForm(initial={"status": quote.status}),
            "send_form": QuoteSendForm(initial={"recipient": quote.opportunity.customer_email}),
            "documents": quote.documents.select_related("generated_by"),
            "deliveries": quote.deliveries.select_related("document", "requested_by"),
            "editable": editable,
            "can_change_quote": can_change_quote,
        },
    )


@backoffice_required
def quote_preview(request, pk):
    quote = get_object_or_404(get_visible_quotes(request.user), pk=pk)
    html = render_quote_preview_html(quote=quote)
    return render(request, "backoffice/quotes/preview.html", {"quote": quote, "preview_html": html})


@backoffice_required
@require_POST
def quote_generate_document(request, pk):
    get_object_or_404(get_visible_quotes(request.user), pk=pk)
    try:
        document = generate_quote_document(quote_id=pk, actor=request.user)
        messages.success(request, f"PDF {document.document_number} disponível.")
    except ValidationError as exc:
        messages.error(request, exc.message)
    except PermissionDenied:
        _permission_denied_message(request)
    return redirect(reverse("backoffice:quote_detail", args=[pk]))


@backoffice_required
def quote_document_download(request, pk, document_id):
    quote = get_object_or_404(get_visible_quotes(request.user), pk=pk)
    document = get_object_or_404(quote.documents, pk=document_id)
    if not document.file:
        raise Http404("Documento sem arquivo.")
    return FileResponse(document.file.open("rb"), as_attachment=True, filename=document.file.name.rsplit("/", 1)[-1])


@backoffice_required
@require_POST
def quote_send(request, pk, document_id):
    quote = get_object_or_404(get_visible_quotes(request.user), pk=pk)
    get_object_or_404(quote.documents, pk=document_id)
    form = QuoteSendForm(request.POST)
    if form.is_valid():
        try:
            delivery = send_quote_by_email(
                quote_id=pk,
                document_id=document_id,
                recipient=form.cleaned_data["recipient"],
                actor=request.user,
                allow_resend=form.cleaned_data["allow_resend"],
            )
            if delivery.status == delivery.Status.SENT:
                messages.success(request, "Orçamento enviado por e-mail.")
            else:
                messages.error(request, "Falha ao enviar orçamento. O status não foi alterado.")
        except ValidationError as exc:
            messages.error(request, exc.message)
        except PermissionDenied:
            _permission_denied_message(request)
    else:
        messages.error(request, "Destinatário inválido.")
    return redirect(reverse("backoffice:quote_detail", args=[pk]))


@backoffice_required
@require_POST
def quote_document_void(request, pk, document_id):
    quote = get_object_or_404(get_visible_quotes(request.user), pk=pk)
    get_object_or_404(quote.documents, pk=document_id)
    try:
        void_quote_document(document_id=document_id, actor=request.user)
        messages.success(request, "Documento anulado.")
    except ValidationError as exc:
        messages.error(request, exc.message)
    except PermissionDenied:
        _permission_denied_message(request)
    return redirect(reverse("backoffice:quote_detail", args=[pk]))


@backoffice_required
@require_POST
def quote_status(request, pk):
    quote = get_object_or_404(get_visible_quotes(request.user), pk=pk)
    form = QuoteStatusForm(request.POST)
    if form.is_valid():
        try:
            change_quote_status(quote_id=quote.pk, status=form.cleaned_data["status"], actor=request.user)
            messages.success(request, "Status do orçamento atualizado.")
        except ValidationError as exc:
            messages.error(request, exc.message)
        except PermissionDenied:
            _permission_denied_message(request)
    else:
        messages.error(request, "Status inválido.")
    return redirect(reverse("backoffice:quote_detail", args=[quote.pk]))


@backoffice_required
@require_POST
def quote_revision(request, pk):
    quote = get_object_or_404(get_visible_quotes(request.user), pk=pk)
    try:
        revision = create_quote_revision(quote_id=quote.pk, actor=request.user)
        messages.success(request, "Revisão criada com sucesso.")
        return redirect(reverse("backoffice:quote_detail", args=[revision.pk]))
    except ValidationError as exc:
        messages.error(request, exc.message)
    except PermissionDenied:
        _permission_denied_message(request)
    return redirect(reverse("backoffice:quote_detail", args=[quote.pk]))


@backoffice_required
def profile(request):
    return render(
        request,
        "backoffice/profile.html",
        {"role_label": user_role_label(request.user)},
    )
