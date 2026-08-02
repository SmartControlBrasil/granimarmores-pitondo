# ruff: noqa: PLR0913
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.utils import timezone

from access_control.services.authorization import require_permission
from access_control.services.authorization import user_has_permission
from audit.services import record_audit_event
from documents.export import build_csv_response
from documents.forms import AcceptanceForm
from documents.forms import DocumentTemplateForm
from documents.forms import DocumentTypeForm
from documents.forms import FromTemplateForm
from documents.forms import ManagedDocumentForm
from documents.forms import ReasonForm
from documents.forms import RenewForm
from documents.forms import ReviewDecisionForm
from documents.forms import SendRecordForm
from documents.forms import SignatureForm
from documents.forms import VersionContentForm
from documents.forms import ViewRecordForm
from documents.forms import placeholder_help_text
from documents.models import DocumentStatus
from documents.models import DocumentTemplate
from documents.models import DocumentType
from documents.models import ManagedDocument
from documents.models import TemplateStatus
from documents.selectors import document_alerts
from documents.selectors import document_dashboard_metrics
from documents.selectors import documents_queryset_for_user
from documents.services.acceptance import register_document_acceptance
from documents.services.acceptance import register_document_send
from documents.services.acceptance import register_document_signature
from documents.services.acceptance import register_document_view
from documents.services.approvals import approve_document_version
from documents.services.approvals import reject_document_version
from documents.services.approvals import submit_document_for_review
from documents.services.documents import approve_document_template
from documents.services.documents import create_document_from_template
from documents.services.documents import create_document_template
from documents.services.documents import create_document_type
from documents.services.documents import create_managed_document
from documents.services.lifecycle import cancel_document
from documents.services.lifecycle import renew_document
from documents.services.lifecycle import terminate_document
from documents.services.versions import create_version
from documents.services.versions import edit_draft_version


def _err(request, exc):
    messages.error(request, str(exc))


def _doc_or_404(request, pk):
    return get_object_or_404(documents_queryset_for_user(request.user), pk=pk)


@require_permission("document_dashboard.view")
def dashboard(request):
    metrics = document_dashboard_metrics(user=request.user)
    alerts = document_alerts(user=request.user)
    return render(
        request,
        "documents/dashboard.html",
        {"page_title": "Dashboard de Documentos", "metrics": metrics, "alerts": alerts},
    )


@require_permission("documents.view")
def document_list(request):
    qs = documents_queryset_for_user(request.user)
    q = (request.GET.get("q") or "").strip()
    status = request.GET.get("status") or ""
    type_id = request.GET.get("type") or ""
    filter_name = request.GET.get("filter") or ""
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(number__icontains=q))
    if status:
        qs = qs.filter(status=status)
    if type_id:
        qs = qs.filter(document_type_id=type_id)
    today = timezone.localdate()
    if filter_name == "expired":
        qs = qs.filter(status=DocumentStatus.EXPIRED)
    elif filter_name == "expiring":
        qs = qs.filter(status=DocumentStatus.ACTIVE, expiration_date__gte=today)
    elif filter_name == "review":
        qs = qs.filter(status=DocumentStatus.UNDER_REVIEW)
    elif filter_name == "acceptance":
        qs = qs.filter(
            requires_acceptance=True,
            status__in=[DocumentStatus.SENT, DocumentStatus.VIEWED, DocumentStatus.APPROVED],
        )
    for key in (
        "quote",
        "sales_order",
        "purchase_order",
        "after_sales_case",
        "customer",
        "supplier",
    ):
        value = request.GET.get(key)
        if value:
            qs = qs.filter(**{f"{key}_id": value})
    if request.GET.get("export") == "csv":
        if not user_has_permission(request.user, "documents.export"):
            messages.error(request, "Sem permissão para exportar.")
            return redirect("documents:document_list")
        rows = [
            [
                d.number,
                d.title,
                d.document_type.name,
                d.status,
                getattr(d.customer, "name", ""),
                getattr(d.supplier, "name", ""),
                d.expiration_date,
            ]
            for d in qs[:5000]
        ]
        return build_csv_response(
            filename="documentos.csv",
            headers=["Número", "Título", "Tipo", "Status", "Cliente", "Fornecedor", "Vencimento"],
            rows=rows,
            request=request,
            export_key="documents",
        )
    page = Paginator(qs, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "documents/document_list.html",
        {
            "page_title": "Biblioteca de Documentos",
            "page_obj": page,
            "types": DocumentType.objects.filter(is_active=True),
            "statuses": DocumentStatus.choices,
        },
    )


@require_permission("documents.create")
def document_create(request):
    form = ManagedDocumentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            doc = create_managed_document(
                data=form.cleaned_data,
                actor=request.user,
                request=request,
                initial_content=form.cleaned_data.get("initial_content") or "",
            )
            messages.success(request, f"Documento {doc.number} criado.")
            return redirect("documents:document_detail", pk=doc.pk)
        except ValidationError as exc:
            _err(request, exc)
    return render(
        request,
        "documents/form.html",
        {
            "page_title": "Novo Documento",
            "form": form,
            "placeholder_help": placeholder_help_text(),
        },
    )


@require_permission("documents.create")
def document_from_template(request):
    form = FromTemplateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            doc = create_document_from_template(
                template=form.cleaned_data["template"],
                actor=request.user,
                title=form.cleaned_data.get("title") or None,
                context_justification="Criado a partir de modelo",
                request=request,
            )
            messages.success(request, f"Documento {doc.number} gerado do modelo.")
            return redirect("documents:document_detail", pk=doc.pk)
        except ValidationError as exc:
            _err(request, exc)
    return render(
        request,
        "documents/form.html",
        {"page_title": "Novo a partir de modelo", "form": form},
    )


@require_permission("documents.view")
def document_detail(request, pk):
    doc = _doc_or_404(request, pk)
    return render(
        request,
        "documents/document_detail.html",
        {
            "page_title": doc.number,
            "obj": doc,
            "versions": doc.versions.all()[:20],
            "reviews": doc.current_version.reviews.all()[:20] if doc.current_version_id else [],
            "sends": doc.send_records.all()[:20],
            "acceptances": doc.acceptances.all()[:20],
            "signatures": doc.signatures.all()[:20],
            "attachments": doc.attachments.select_related("media_asset")[:50],
            "relationships": doc.relationships_from.select_related("to_document")[:20],
        },
    )


@require_permission("documents.print")
def document_print(request, pk):
    doc = _doc_or_404(request, pk)
    record_audit_event(
        request=request,
        user=request.user,
        event_type="export",
        module="documents",
        action="print_document",
        obj=doc,
    )
    return render(
        request,
        "documents/document_print.html",
        {"obj": doc, "version": doc.current_version},
    )


@require_permission("documents.submit_review")
def document_submit_review(request, pk):
    doc = _doc_or_404(request, pk)
    if request.method == "POST":
        try:
            submit_document_for_review(document=doc, actor=request.user, request=request)
            messages.success(request, "Documento enviado para revisão.")
        except ValidationError as exc:
            _err(request, exc)
    return redirect("documents:document_detail", pk=pk)


@require_permission("documents.approve")
def document_approve(request, pk):
    doc = _doc_or_404(request, pk)
    form = ReviewDecisionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            approve_document_version(
                version=doc.current_version,
                actor=request.user,
                comments=form.cleaned_data.get("comments") or "",
                request=request,
            )
            messages.success(request, "Versão aprovada.")
            return redirect("documents:document_detail", pk=pk)
        except ValidationError as exc:
            _err(request, exc)
    return render(request, "documents/form.html", {"page_title": f"Aprovar {doc.number}", "form": form})


@require_permission("documents.reject")
def document_reject(request, pk):
    doc = _doc_or_404(request, pk)
    form = ReviewDecisionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            reject_document_version(
                version=doc.current_version,
                actor=request.user,
                reason=form.cleaned_data.get("reason") or form.cleaned_data.get("comments") or "",
                request=request,
            )
            messages.success(request, "Versão rejeitada.")
            return redirect("documents:document_detail", pk=pk)
        except ValidationError as exc:
            _err(request, exc)
    return render(request, "documents/form.html", {"page_title": f"Rejeitar {doc.number}", "form": form})


@require_permission("documents.update")
def document_new_version(request, pk):
    doc = _doc_or_404(request, pk)
    form = VersionContentForm(
        request.POST or None,
        initial={"content": doc.current_version.rendered_content if doc.current_version else ""},
    )
    if request.method == "POST" and form.is_valid():
        try:
            create_version(
                document=doc,
                actor=request.user,
                content=form.cleaned_data["content"],
                change_summary=form.cleaned_data.get("change_summary") or "",
                request=request,
            )
            messages.success(request, "Nova versão criada.")
            return redirect("documents:document_detail", pk=pk)
        except ValidationError as exc:
            _err(request, exc)
    return render(
        request,
        "documents/form.html",
        {"page_title": f"Nova versão — {doc.number}", "form": form, "placeholder_help": placeholder_help_text()},
    )


@require_permission("documents.update")
def document_edit_version(request, pk):
    doc = _doc_or_404(request, pk)
    version = doc.current_version
    form = VersionContentForm(request.POST or None, initial={"content": version.content if version else ""})
    if request.method == "POST" and form.is_valid():
        try:
            edit_draft_version(
                version=version,
                content=form.cleaned_data["content"],
                actor=request.user,
                request=request,
            )
            messages.success(request, "Versão atualizada.")
            return redirect("documents:document_detail", pk=pk)
        except ValidationError as exc:
            _err(request, exc)
    return render(request, "documents/form.html", {"page_title": "Editar rascunho", "form": form})


@require_permission("documents.send")
def document_send(request, pk):
    doc = _doc_or_404(request, pk)
    form = SendRecordForm(request.POST or None, initial={"sent_at": timezone.now()})
    if request.method == "POST" and form.is_valid():
        try:
            register_document_send(
                document=doc,
                actor=request.user,
                data=form.cleaned_data,
                request=request,
            )
            messages.success(request, "Envio registrado (manual).")
            return redirect("documents:document_detail", pk=pk)
        except ValidationError as exc:
            _err(request, exc)
    return render(request, "documents/form.html", {"page_title": "Registrar envio", "form": form})


@require_permission("documents.update")
def document_view_record(request, pk):
    doc = _doc_or_404(request, pk)
    form = ViewRecordForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            register_document_view(
                document=doc,
                actor=request.user,
                data=form.cleaned_data,
                request=request,
            )
            messages.success(request, "Visualização registrada.")
            return redirect("documents:document_detail", pk=pk)
        except ValidationError as exc:
            _err(request, exc)
    return render(request, "documents/form.html", {"page_title": "Registrar visualização", "form": form})


@require_permission("documents.accept")
def document_accept(request, pk):
    doc = _doc_or_404(request, pk)
    form = AcceptanceForm(request.POST or None, initial={"accepted": True})
    if request.method == "POST" and form.is_valid():
        try:
            register_document_acceptance(
                document=doc,
                actor=request.user,
                data=form.cleaned_data,
                request=request,
            )
            messages.success(request, "Aceite registrado.")
            return redirect("documents:document_detail", pk=pk)
        except ValidationError as exc:
            _err(request, exc)
    return render(request, "documents/form.html", {"page_title": "Registrar aceite", "form": form})


@require_permission("documents.register_signature")
def document_signature(request, pk):
    doc = _doc_or_404(request, pk)
    form = SignatureForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            register_document_signature(
                document=doc,
                actor=request.user,
                data=form.cleaned_data,
                request=request,
            )
            messages.success(request, "Assinatura registrada (registro operacional).")
            return redirect("documents:document_detail", pk=pk)
        except ValidationError as exc:
            _err(request, exc)
    return render(request, "documents/form.html", {"page_title": "Registrar assinatura", "form": form})


@require_permission("documents.cancel")
def document_cancel(request, pk):
    doc = _doc_or_404(request, pk)
    form = ReasonForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            cancel_document(
                document=doc,
                actor=request.user,
                reason=form.cleaned_data["reason"],
                request=request,
            )
            messages.success(request, "Documento cancelado.")
            return redirect("documents:document_detail", pk=pk)
        except ValidationError as exc:
            _err(request, exc)
    return render(request, "documents/form.html", {"page_title": "Cancelar documento", "form": form})


@require_permission("documents.terminate")
def document_terminate(request, pk):
    doc = _doc_or_404(request, pk)
    form = ReasonForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            terminate_document(
                document=doc,
                actor=request.user,
                reason=form.cleaned_data["reason"],
                request=request,
            )
            messages.success(request, "Documento encerrado.")
            return redirect("documents:document_detail", pk=pk)
        except ValidationError as exc:
            _err(request, exc)
    return render(request, "documents/form.html", {"page_title": "Encerrar documento", "form": form})


@require_permission("documents.renew")
def document_renew(request, pk):
    doc = _doc_or_404(request, pk)
    form = RenewForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            new_doc = renew_document(
                document=doc,
                actor=request.user,
                expiration_date=form.cleaned_data.get("expiration_date"),
                request=request,
            )
            messages.success(request, f"Renovação criada: {new_doc.number}")
            return redirect("documents:document_detail", pk=new_doc.pk)
        except ValidationError as exc:
            _err(request, exc)
    return render(request, "documents/form.html", {"page_title": "Renovar documento", "form": form})


@require_permission("document_templates.view")
def template_list(request):
    qs = DocumentTemplate.objects.select_related("document_type").order_by("name")
    return render(
        request,
        "documents/template_list.html",
        {"page_title": "Modelos documentais", "templates": qs},
    )


@require_permission("document_templates.create")
def template_create(request):
    form = DocumentTemplateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            tpl = create_document_template(
                data=form.cleaned_data,
                actor=request.user,
                request=request,
            )
            messages.success(request, "Modelo criado.")
            return redirect("documents:template_list")
        except ValidationError as exc:
            _err(request, exc)
    return render(
        request,
        "documents/form.html",
        {
            "page_title": "Novo modelo",
            "form": form,
            "placeholder_help": placeholder_help_text(),
        },
    )


@require_permission("document_templates.approve")
def template_approve(request, pk):
    tpl = get_object_or_404(DocumentTemplate, pk=pk)
    if request.method == "POST":
        approve_document_template(template=tpl, actor=request.user, request=request)
        messages.success(request, "Modelo aprovado.")
    return redirect("documents:template_list")


@require_permission("document_types.view")
def type_list(request):
    return render(
        request,
        "documents/type_list.html",
        {"page_title": "Tipos de documento", "types": DocumentType.objects.all()},
    )


@require_permission("document_types.create")
def type_create(request):
    form = DocumentTypeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            create_document_type(data=form.cleaned_data, actor=request.user, request=request)
            messages.success(request, "Tipo criado.")
            return redirect("documents:type_list")
        except ValidationError as exc:
            _err(request, exc)
    return render(request, "documents/form.html", {"page_title": "Novo tipo", "form": form})


@require_permission("documents.view")
def review_queue(request):
    qs = documents_queryset_for_user(request.user).filter(status=DocumentStatus.UNDER_REVIEW)
    page = Paginator(qs, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "documents/document_list.html",
        {"page_title": "Revisões pendentes", "page_obj": page, "types": [], "statuses": []},
    )


@require_permission("documents.approve")
def approval_queue(request):
    qs = documents_queryset_for_user(request.user).filter(status=DocumentStatus.UNDER_REVIEW)
    page = Paginator(qs, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "documents/document_list.html",
        {"page_title": "Aprovações pendentes", "page_obj": page, "types": [], "statuses": []},
    )


@require_permission("documents.view")
def acceptance_queue(request):
    qs = documents_queryset_for_user(request.user).filter(
        requires_acceptance=True,
        status__in=[DocumentStatus.SENT, DocumentStatus.VIEWED, DocumentStatus.APPROVED],
    )
    page = Paginator(qs, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "documents/document_list.html",
        {"page_title": "Aguardando aceite", "page_obj": page, "types": [], "statuses": []},
    )


@require_permission("documents.view")
def expiration_list(request):
    qs = documents_queryset_for_user(request.user).filter(
        expiration_date__isnull=False,
    ).order_by("expiration_date")
    page = Paginator(qs, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "documents/document_list.html",
        {"page_title": "Vencimentos", "page_obj": page, "types": [], "statuses": []},
    )
