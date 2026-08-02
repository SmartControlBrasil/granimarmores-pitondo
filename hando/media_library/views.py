# ruff: noqa: PLR0913
import mimetypes

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import FileResponse
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render

from access_control.services.authorization import require_permission
from access_control.services.authorization import user_has_permission
from after_sales.models import AfterSalesAttachment
from after_sales.models import AfterSalesCase
from customers.models import Customer
from materials.models import Material
from media_library.forms import BeforeAfterForm
from media_library.forms import ClassifyForm
from media_library.forms import CollectionForm
from media_library.forms import CollectionItemForm
from media_library.forms import MediaMultiUploadForm
from media_library.forms import MediaUploadForm
from media_library.forms import NotesForm
from media_library.forms import PublicationCandidateForm
from media_library.forms import ReasonForm
from media_library.forms import ReviewForm
from media_library.models import BeforeAfterPair
from media_library.models import MediaAsset
from media_library.models import MediaCategory
from media_library.models import MediaCollection
from media_library.models import MediaStatus
from media_library.models import MediaType
from media_library.models import MediaVisibility
from media_library.models import PublicationCandidate
from media_library.selectors import filter_media
from media_library.selectors import media_dashboard_metrics
from media_library.selectors import media_queryset_for_user
from media_library.selectors import parse_period
from media_library.selectors import portfolio_queryset
from media_library.selectors import review_queues
from media_library.services.classification import classify_media_asset
from media_library.services.classification import review_media_asset
from media_library.services.consent import evaluate_media_consent
from media_library.services.lifecycle import archive_media_asset
from media_library.services.lifecycle import request_media_deletion
from media_library.services.portfolio import add_asset_to_collection
from media_library.services.portfolio import approve_for_portfolio
from media_library.services.portfolio import create_before_after_pair
from media_library.services.portfolio import create_collection
from media_library.services.portfolio import create_publication_candidate
from media_library.services.portfolio import remove_from_portfolio
from media_library.services.uploads import upload_media_asset
from media_library.services.uploads import upload_multiple_media_assets
from production.models import InstallationSchedule
from production.models import ProductionOrder
from production.models import ProductionPiece
from production.models import SalesOrder
from audit.services import record_audit_event


def _asset_or_403(request, pk):
    return get_object_or_404(media_queryset_for_user(request.user), pk=pk)


def _handle(request, exc):
    messages.error(request, str(exc))


def _context_from_form(cleaned):
    keys = [
        "customer",
        "lead",
        "quote",
        "sales_order",
        "production_order",
        "production_piece",
        "production_stage",
        "material",
        "slab",
        "delivery_schedule",
        "installation_schedule",
        "after_sales_case",
        "warranty",
        "consent",
        "category",
        "tags",
        "capture_date",
        "title",
        "description",
        "alt_text",
        "reuse_duplicate",
    ]
    return {k: cleaned.get(k) for k in keys if k in cleaned}


@require_permission("media_dashboard.view")
def dashboard(request):
    start, end, period = parse_period(request)
    metrics = media_dashboard_metrics(user=request.user, start=start, end=end)
    return render(
        request,
        "media_library/dashboard.html",
        {"page_title": "Dashboard de Mídia", "metrics": metrics, "period": period},
    )


@require_permission("media_assets.view")
def library_list(request):
    qs = filter_media(media_queryset_for_user(request.user), request.GET)
    page_obj = Paginator(qs, 24).get_page(request.GET.get("page"))
    return render(
        request,
        "media_library/library.html",
        {
            "page_title": "Biblioteca de mídia",
            "page_obj": page_obj,
            "categories": MediaCategory.objects.filter(is_active=True),
            "status_choices": MediaStatus.choices,
            "type_choices": MediaType.choices,
            "visibility_choices": MediaVisibility.choices,
            "view_mode": request.GET.get("view", "grid"),
        },
    )


@require_permission("media_assets.upload")
def upload(request):
    form = MediaUploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        data = _context_from_form(form.cleaned_data)
        try:
            asset, is_dup = upload_media_asset(
                actor=request.user,
                uploaded_file=form.cleaned_data["file"],
                request=request,
                **data,
            )
        except (ValidationError, PermissionDenied) as exc:
            _handle(request, exc)
        else:
            msg = f"Mídia {asset.code} enviada."
            if is_dup:
                msg += " Duplicidade detectada."
            messages.success(request, msg)
            return redirect("media_library:asset_detail", pk=asset.pk)
    return render(
        request,
        "media_library/simple_form.html",
        {"page_title": "Upload de mídia", "form": form, "cancel_url": "media_library:library"},
    )


@require_permission("media_assets.upload")
def upload_multiple(request):
    form = MediaMultiUploadForm(request.POST or None, request.FILES or None)
    results = None
    if request.method == "POST" and form.is_valid():
        files = request.FILES.getlist("files")
        common = {
            "category": form.cleaned_data.get("category"),
            "tags": form.cleaned_data.get("tags"),
            "customer": form.cleaned_data.get("customer"),
            "sales_order": form.cleaned_data.get("sales_order"),
            "production_order": form.cleaned_data.get("production_order"),
            "installation_schedule": form.cleaned_data.get("installation_schedule"),
            "after_sales_case": form.cleaned_data.get("after_sales_case"),
            "material": form.cleaned_data.get("material"),
        }
        try:
            results = upload_multiple_media_assets(
                actor=request.user,
                files=files,
                common_context=common,
                request=request,
                reuse_duplicate=bool(form.cleaned_data.get("reuse_duplicate")),
            )
        except (ValidationError, PermissionDenied) as exc:
            _handle(request, exc)
        else:
            ok = sum(1 for r in results if r["ok"])
            messages.info(request, f"Processados {len(results)} arquivo(s); {ok} com sucesso.")
    return render(
        request,
        "media_library/upload_multiple.html",
        {"page_title": "Upload múltiplo", "form": form, "results": results},
    )


@require_permission("media_assets.view")
def asset_detail(request, pk):
    asset = _asset_or_403(request, pk)
    return render(
        request,
        "media_library/asset_detail.html",
        {
            "page_title": asset.code,
            "asset": asset,
            "consent_status": evaluate_media_consent(asset),
            "history": asset.history.all()[:40],
            "links": asset.links.all(),
            "reviews": asset.reviews.all()[:20],
            "classify_form": ClassifyForm(
                initial={
                    "category": asset.category_id,
                    "title": asset.title,
                    "description": asset.description,
                    "alt_text": asset.alt_text,
                },
            ),
            "review_form": ReviewForm(),
            "notes_form": NotesForm(),
            "reason_form": ReasonForm(),
            "can_review": user_has_permission(request.user, "media_assets.review"),
            "can_portfolio": user_has_permission(request.user, "media_portfolio.approve"),
        },
    )


@require_permission("media_assets.view")
def asset_file(request, pk):
    asset = _asset_or_403(request, pk)
    if asset.visibility == MediaVisibility.PRIVATE and not (
        user_has_permission(request.user, "media_private_files.view")
        or asset.uploaded_by_id == request.user.pk
        or user_has_permission(request.user, "media_assets.view_all")
    ):
        raise PermissionDenied("Arquivo privado.")
    if not asset.file:
        raise Http404("Arquivo ausente.")
    record_audit_event(
        request=request,
        user=request.user,
        event_type="read",
        module="media_library",
        action="media_private_download",
        obj=asset,
    )
    content_type = asset.mime_type or mimetypes.guess_type(asset.original_filename)[0] or "application/octet-stream"
    response = FileResponse(asset.file.open("rb"), content_type=content_type)
    disposition = "inline" if asset.media_type == MediaType.IMAGE else "attachment"
    response["Content-Disposition"] = f'{disposition}; filename="{asset.original_filename or asset.stored_filename}"'
    return response


@require_permission("media_assets.classify")
def asset_classify(request, pk):
    asset = _asset_or_403(request, pk)
    form = ClassifyForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            classify_media_asset(asset=asset, actor=request.user, request=request, **form.cleaned_data)
        except (ValidationError, PermissionDenied) as exc:
            _handle(request, exc)
        else:
            messages.success(request, "Mídia classificada.")
    return redirect("media_library:asset_detail", pk=pk)


@require_permission("media_assets.review")
def asset_review(request, pk):
    asset = _asset_or_403(request, pk)
    form = ReviewForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            review_media_asset(asset=asset, actor=request.user, request=request, **form.cleaned_data)
        except (ValidationError, PermissionDenied) as exc:
            _handle(request, exc)
        else:
            messages.success(request, "Revisão registrada.")
    return redirect("media_library:asset_detail", pk=pk)


@require_permission("media_portfolio.approve")
def asset_portfolio_approve(request, pk):
    asset = _asset_or_403(request, pk)
    form = NotesForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            approve_for_portfolio(
                asset=asset,
                actor=request.user,
                notes=form.cleaned_data.get("notes") or "",
                request=request,
            )
        except (ValidationError, PermissionDenied) as exc:
            _handle(request, exc)
        else:
            messages.success(request, "Aprovado para portfólio.")
    return redirect("media_library:asset_detail", pk=pk)


@require_permission("media_portfolio.approve")
def asset_portfolio_remove(request, pk):
    asset = _asset_or_403(request, pk)
    if request.method == "POST":
        try:
            remove_from_portfolio(asset=asset, actor=request.user, request=request)
        except (ValidationError, PermissionDenied) as exc:
            _handle(request, exc)
        else:
            messages.success(request, "Removido do portfólio.")
    return redirect("media_library:asset_detail", pk=pk)


@require_permission("media_assets.archive")
def asset_archive(request, pk):
    asset = _asset_or_403(request, pk)
    form = ReasonForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            archive_media_asset(
                asset=asset,
                actor=request.user,
                reason=form.cleaned_data["reason"],
                request=request,
            )
        except (ValidationError, PermissionDenied) as exc:
            _handle(request, exc)
        else:
            messages.success(request, "Mídia arquivada.")
    return redirect("media_library:library")


@require_permission("media_assets.request_delete")
def asset_request_delete(request, pk):
    asset = _asset_or_403(request, pk)
    form = ReasonForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            request_media_deletion(
                asset=asset,
                actor=request.user,
                reason=form.cleaned_data["reason"],
                request=request,
            )
        except (ValidationError, PermissionDenied) as exc:
            _handle(request, exc)
        else:
            messages.success(request, "Exclusão lógica solicitada.")
    return redirect("media_library:library")


@require_permission("media_assets.review")
def review_queue(request):
    queues = review_queues(request.user)
    return render(
        request,
        "media_library/review_queue.html",
        {"page_title": "Revisão de mídia", "queues": queues},
    )


@require_permission("media_collections.view")
def collection_list(request):
    qs = MediaCollection.objects.select_related("customer", "sales_order").order_by("-created_at")
    page_obj = Paginator(qs, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "media_library/collection_list.html",
        {"page_title": "Coleções", "page_obj": page_obj},
    )


@require_permission("media_collections.create")
def collection_create(request):
    form = CollectionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            collection = create_collection(actor=request.user, **data)
        except (ValidationError, PermissionDenied) as exc:
            _handle(request, exc)
        else:
            messages.success(request, f"Coleção {collection.code} criada.")
            return redirect("media_library:collection_detail", pk=collection.pk)
    return render(
        request,
        "media_library/simple_form.html",
        {"page_title": "Nova coleção", "form": form, "cancel_url": "media_library:collection_list"},
    )


@require_permission("media_collections.view")
def collection_detail(request, pk):
    collection = get_object_or_404(MediaCollection, pk=pk)
    form = CollectionItemForm(request.POST or None)
    if request.method == "POST" and form.is_valid() and user_has_permission(
        request.user,
        "media_collections.update",
    ):
        try:
            add_asset_to_collection(
                collection=collection,
                asset=form.cleaned_data["asset"],
                actor=request.user,
                caption=form.cleaned_data.get("caption") or "",
                is_cover=bool(form.cleaned_data.get("is_cover")),
                display_order=form.cleaned_data.get("display_order") or 0,
            )
        except (ValidationError, PermissionDenied) as exc:
            _handle(request, exc)
        else:
            messages.success(request, "Mídia adicionada à coleção.")
            return redirect("media_library:collection_detail", pk=pk)
    return render(
        request,
        "media_library/collection_detail.html",
        {
            "page_title": collection.code,
            "collection": collection,
            "items": collection.items.select_related("asset"),
            "form": form,
        },
    )


@require_permission("media_collections.view")
def before_after_list(request):
    qs = BeforeAfterPair.objects.select_related("before_asset", "after_asset", "customer")
    page_obj = Paginator(qs, 20).get_page(request.GET.get("page"))
    return render(
        request,
        "media_library/before_after_list.html",
        {"page_title": "Antes e depois", "page_obj": page_obj},
    )


@require_permission("media_collections.create")
def before_after_create(request):
    form = BeforeAfterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            pair = create_before_after_pair(actor=request.user, request=request, **data)
        except (ValidationError, PermissionDenied) as exc:
            _handle(request, exc)
        else:
            messages.success(request, "Par antes/depois criado.")
            return redirect("media_library:before_after_list")
    return render(
        request,
        "media_library/simple_form.html",
        {"page_title": "Novo antes e depois", "form": form, "cancel_url": "media_library:before_after_list"},
    )


@require_permission("media_assets.view")
def materials_gallery(request):
    qs = media_queryset_for_user(request.user).filter(material__isnull=False)
    material_id = request.GET.get("material")
    if material_id:
        qs = qs.filter(material_id=material_id)
    page_obj = Paginator(qs, 24).get_page(request.GET.get("page"))
    return render(
        request,
        "media_library/materials_gallery.html",
        {
            "page_title": "Mídias de materiais",
            "page_obj": page_obj,
            "materials": Material.objects.filter(is_active=True),
        },
    )


@require_permission("media_portfolio.view")
def portfolio(request):
    qs = portfolio_queryset(request.user)
    if request.GET.get("material"):
        qs = qs.filter(material_id=request.GET["material"])
    if request.GET.get("category"):
        qs = qs.filter(category_id=request.GET["category"])
    page_obj = Paginator(qs, 24).get_page(request.GET.get("page"))
    return render(
        request,
        "media_library/portfolio.html",
        {
            "page_title": "Portfólio interno",
            "page_obj": page_obj,
            "categories": MediaCategory.objects.filter(is_active=True, is_portfolio_eligible=True),
        },
    )


@require_permission("media_publication_candidates.view")
def publication_list(request):
    qs = PublicationCandidate.objects.select_related("asset").order_by("-created_at")
    page_obj = Paginator(qs, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "media_library/publication_list.html",
        {"page_title": "Publicação futura", "page_obj": page_obj},
    )


@require_permission("media_publication_candidates.create")
def publication_create(request):
    form = PublicationCandidateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            create_publication_candidate(actor=request.user, request=request, **data)
        except (ValidationError, PermissionDenied) as exc:
            _handle(request, exc)
        else:
            messages.success(request, "Candidato registrado (sem publicação automática).")
            return redirect("media_library:publication_list")
    return render(
        request,
        "media_library/simple_form.html",
        {"page_title": "Novo candidato de publicação", "form": form, "cancel_url": "media_library:publication_list"},
    )


def _upload_context(request, initial, page_title):
    form = MediaUploadForm(request.POST or None, request.FILES or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        data = _context_from_form(form.cleaned_data)
        for key, value in initial.items():
            data.setdefault(key, value)
        try:
            asset, is_dup = upload_media_asset(
                actor=request.user,
                uploaded_file=form.cleaned_data["file"],
                request=request,
                **data,
            )
        except (ValidationError, PermissionDenied) as exc:
            _handle(request, exc)
        else:
            messages.success(request, f"{asset.code} enviado." + (" Duplicidade." if is_dup else ""))
            return redirect("media_library:asset_detail", pk=asset.pk)
    return render(
        request,
        "media_library/simple_form.html",
        {"page_title": page_title, "form": form, "cancel_url": "media_library:library"},
    )


@require_permission("media_assets.upload")
def upload_from_production(request, pk):
    production = get_object_or_404(ProductionOrder, pk=pk)
    return _upload_context(
        request,
        {
            "production_order": production,
            "sales_order": production.sales_order,
            "customer": production.sales_order.customer,
        },
        f"Adicionar mídia — {production.number}",
    )


@require_permission("media_assets.upload")
def upload_from_piece(request, pk):
    piece = get_object_or_404(ProductionPiece.objects.select_related("production_order__sales_order"), pk=pk)
    return _upload_context(
        request,
        {
            "production_piece": piece,
            "production_order": piece.production_order,
            "sales_order": piece.production_order.sales_order,
            "customer": piece.production_order.sales_order.customer,
            "material": piece.material,
        },
        f"Adicionar mídia — {piece.code}",
    )


@require_permission("media_assets.upload")
def upload_from_installation(request, pk):
    installation = get_object_or_404(
        InstallationSchedule.objects.select_related("sales_order"),
        pk=pk,
    )
    return _upload_context(
        request,
        {
            "installation_schedule": installation,
            "sales_order": installation.sales_order,
            "customer": installation.sales_order.customer,
        },
        "Fotos de instalação",
    )


@require_permission("media_assets.upload")
def upload_from_after_sales(request, pk):
    case = get_object_or_404(AfterSalesCase, pk=pk)
    form = MediaUploadForm(
        request.POST or None,
        request.FILES or None,
        initial={
            "after_sales_case": case,
            "customer": case.customer,
            "sales_order": case.sales_order,
        },
    )
    if request.method == "POST" and form.is_valid():
        data = _context_from_form(form.cleaned_data)
        data.setdefault("after_sales_case", case)
        data.setdefault("customer", case.customer)
        data.setdefault("sales_order", case.sales_order)
        try:
            asset, _ = upload_media_asset(
                actor=request.user,
                uploaded_file=form.cleaned_data["file"],
                request=request,
                **data,
            )
            AfterSalesAttachment.objects.create(
                case=case,
                media_asset=asset,
                attachment_type="photo" if asset.media_type == MediaType.IMAGE else "document",
                description=asset.title,
                uploaded_by=request.user,
            )
        except (ValidationError, PermissionDenied) as exc:
            _handle(request, exc)
            return redirect("media_library:upload_after_sales", pk=pk)
        messages.success(request, f"Anexo de pós-venda vinculado a {asset.code}.")
        return redirect("media_library:asset_detail", pk=asset.pk)
    return render(
        request,
        "media_library/simple_form.html",
        {
            "page_title": f"Mídia — {case.code}",
            "form": form,
            "cancel_url": "after_sales:case_detail",
        },
    )


@require_permission("media_assets.view")
def customer_gallery(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    qs = media_queryset_for_user(request.user).filter(customer=customer)
    page_obj = Paginator(qs, 24).get_page(request.GET.get("page"))
    return render(
        request,
        "media_library/gallery.html",
        {"page_title": f"Galeria — {customer}", "page_obj": page_obj},
    )


@require_permission("media_assets.view")
def order_gallery(request, pk):
    order = get_object_or_404(SalesOrder, pk=pk)
    qs = media_queryset_for_user(request.user).filter(sales_order=order).order_by("uploaded_at")
    page_obj = Paginator(qs, 24).get_page(request.GET.get("page"))
    return render(
        request,
        "media_library/gallery.html",
        {"page_title": f"Galeria — {order.number}", "page_obj": page_obj},
    )
