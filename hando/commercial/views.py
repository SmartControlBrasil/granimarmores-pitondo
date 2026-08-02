# ruff: noqa: PLR0913
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import F
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render

from access_control.services.authorization import require_permission
from access_control.services.authorization import user_has_permission
from audit.models import AuditEvent
from commercial.forms import CommercialPartnerForm
from commercial.forms import CommercialSourceForm
from commercial.forms import ContactChannelForm
from commercial.forms import LossReasonForm
from commercial.forms import ProjectTypeForm
from commercial.forms import ServiceRegionForm
from commercial.models import ChannelGroup
from commercial.models import CommercialPartner
from commercial.models import CommercialSource
from commercial.models import ContactChannel
from commercial.models import LossCategory
from commercial.models import LossReason
from commercial.models import PartnerType
from commercial.models import ProjectType
from commercial.models import ServiceRegion
from commercial.services import save_commercial_partner
from commercial.services import save_commercial_source
from commercial.services import save_contact_channel
from commercial.services import save_loss_reason
from commercial.services import save_project_type
from commercial.services import save_service_region
from commercial.services import set_master_active
from customers.models import Customer
from materials.models import AdditionalService
from materials.models import FinishType
from materials.models import Material
from materials.models import MaterialSlab
from salespeople.models import Salesperson


def _paginated_list(request, qs, template, title, extra=None):
    page_obj = Paginator(qs, 20).get_page(request.GET.get("page"))
    context = {
        "page_title": title,
        "page_obj": page_obj,
        "search": request.GET.get("q", "").strip(),
    }
    context.update(extra or {})
    return render(request, template, context)


def _apply_active_filter(qs, request):
    active = request.GET.get("active", "").strip()
    if active == "1":
        return qs.filter(is_active=True)
    if active == "0":
        return qs.filter(is_active=False)
    return qs


@require_permission("commercial_sources.view")
def source_list(request):
    qs = CommercialSource.objects.all()
    search = request.GET.get("q", "").strip()
    group = request.GET.get("group", "").strip()
    if search:
        qs = qs.filter(name__icontains=search)
    if group:
        qs = qs.filter(channel_group=group)
    qs = _apply_active_filter(qs, request)
    return _paginated_list(
        request,
        qs,
        "commercial/source_list.html",
        "Origens comerciais",
        {"groups": ChannelGroup.choices, "selected_group": group},
    )


@require_permission("commercial_sources.create")
def source_create(request):
    form = CommercialSourceForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = save_commercial_source(form=form, actor=request.user, request=request)
        messages.success(request, "Origem comercial salva com sucesso.")
        return redirect("commercial:source_update", pk=obj.pk)
    return render(
        request,
        "erp/form.html",
        {
            "page_title": "Nova origem comercial",
            "form": form,
            "cancel_url": "commercial:sources",
        },
    )


@require_permission("commercial_sources.update")
def source_update(request, pk):
    obj = get_object_or_404(CommercialSource, pk=pk)
    form = CommercialSourceForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        save_commercial_source(form=form, actor=request.user, request=request)
        messages.success(request, "Origem comercial atualizada com sucesso.")
        return redirect("commercial:source_update", pk=obj.pk)
    return render(
        request,
        "erp/form.html",
        {
            "page_title": f"Editar {obj.name}",
            "form": form,
            "cancel_url": "commercial:sources",
        },
    )


@require_permission("project_types.view")
def project_type_list(request):
    qs = ProjectType.objects.all()
    search = request.GET.get("q", "").strip()
    if search:
        qs = qs.filter(name__icontains=search)
    qs = _apply_active_filter(qs, request)
    return _paginated_list(
        request,
        qs,
        "commercial/project_type_list.html",
        "Tipos de projeto",
    )


@require_permission("project_types.create")
def project_type_create(request):
    form = ProjectTypeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = save_project_type(form=form, actor=request.user, request=request)
        messages.success(request, "Tipo de projeto salvo com sucesso.")
        return redirect("commercial:project_type_update", pk=obj.pk)
    return render(
        request,
        "erp/form.html",
        {
            "page_title": "Novo tipo de projeto",
            "form": form,
            "cancel_url": "commercial:project_types",
        },
    )


@require_permission("project_types.update")
def project_type_update(request, pk):
    obj = get_object_or_404(ProjectType, pk=pk)
    form = ProjectTypeForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        save_project_type(form=form, actor=request.user, request=request)
        messages.success(request, "Tipo de projeto atualizado com sucesso.")
        return redirect("commercial:project_type_update", pk=obj.pk)
    return render(
        request,
        "erp/form.html",
        {
            "page_title": f"Editar {obj.name}",
            "form": form,
            "cancel_url": "commercial:project_types",
        },
    )


@require_permission("commercial_partners.view")
def partner_list(request):
    qs = CommercialPartner.objects.select_related("assigned_salesperson")
    search = request.GET.get("q", "").strip()
    partner_type = request.GET.get("partner_type", "").strip()
    city = request.GET.get("city", "").strip()
    state = request.GET.get("state", "").strip()
    salesperson_id = request.GET.get("salesperson", "").strip()
    if search:
        qs = qs.filter(
            Q(name__icontains=search)
            | Q(contact_name__icontains=search)
            | Q(phone__icontains=search)
            | Q(mobile_phone__icontains=search)
            | Q(document__icontains=search),
        )
    if partner_type:
        qs = qs.filter(partner_type=partner_type)
    if city:
        qs = qs.filter(city__icontains=city)
    if state:
        qs = qs.filter(state__iexact=state)
    if salesperson_id.isdigit():
        qs = qs.filter(assigned_salesperson_id=int(salesperson_id))
    qs = _apply_active_filter(qs, request)
    return _paginated_list(
        request,
        qs,
        "commercial/partner_list.html",
        "Parceiros comerciais",
        {
            "partner_types": PartnerType.choices,
            "selected_type": partner_type,
            "selected_city": city,
            "selected_state": state,
            "salespeople": Salesperson.objects.filter(is_active=True).order_by("display_name"),
            "selected_salesperson": salesperson_id,
        },
    )


@require_permission("commercial_partners.view")
def partner_detail(request, pk):
    partner = get_object_or_404(
        CommercialPartner.objects.select_related("assigned_salesperson"),
        pk=pk,
    )
    recent_events = AuditEvent.objects.filter(
        object_type="CommercialPartner",
        object_id=str(partner.pk),
    )[:10]
    return render(
        request,
        "commercial/partner_detail.html",
        {
            "page_title": partner.name,
            "partner": partner,
            "recent_events": recent_events,
        },
    )


@require_permission("commercial_partners.create")
def partner_create(request):
    form = CommercialPartnerForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        partner = save_commercial_partner(form=form, actor=request.user, request=request)
        messages.success(request, "Parceiro comercial criado com sucesso.")
        return redirect("commercial:partner_detail", pk=partner.pk)
    return render(
        request,
        "commercial/partner_form.html",
        {"page_title": "Novo parceiro comercial", "form": form},
    )


@require_permission("commercial_partners.update")
def partner_update(request, pk):
    partner = get_object_or_404(CommercialPartner, pk=pk)
    form = CommercialPartnerForm(request.POST or None, instance=partner)
    if request.method == "POST" and form.is_valid():
        partner = save_commercial_partner(form=form, actor=request.user, request=request)
        messages.success(request, "Parceiro comercial atualizado com sucesso.")
        return redirect("commercial:partner_detail", pk=partner.pk)
    return render(
        request,
        "commercial/partner_form.html",
        {
            "page_title": f"Editar {partner.name}",
            "form": form,
            "partner": partner,
        },
    )


@require_permission("commercial_partners.deactivate")
def partner_deactivate(request, pk):
    partner = get_object_or_404(CommercialPartner, pk=pk)
    if request.method == "POST":
        set_master_active(
            obj=partner,
            is_active=False,
            actor=request.user,
            request=request,
            action_prefix="commercial_partner",
        )
        messages.success(request, "Parceiro desativado com sucesso.")
        return redirect("commercial:partner_detail", pk=partner.pk)
    return render(
        request,
        "erp/confirm_action.html",
        {"page_title": "Desativar parceiro", "message": f"Desativar {partner.name}?"},
    )


@require_permission("commercial_partners.update")
def partner_activate(request, pk):
    partner = get_object_or_404(CommercialPartner, pk=pk)
    if request.method == "POST":
        set_master_active(
            obj=partner,
            is_active=True,
            actor=request.user,
            request=request,
            action_prefix="commercial_partner",
        )
        messages.success(request, "Parceiro reativado com sucesso.")
        return redirect("commercial:partner_detail", pk=partner.pk)
    return render(
        request,
        "erp/confirm_action.html",
        {"page_title": "Reativar parceiro", "message": f"Reativar {partner.name}?"},
    )


@require_permission("loss_reasons.view")
def loss_reason_list(request):
    qs = LossReason.objects.all()
    search = request.GET.get("q", "").strip()
    category = request.GET.get("category", "").strip()
    if search:
        qs = qs.filter(name__icontains=search)
    if category:
        qs = qs.filter(category=category)
    qs = _apply_active_filter(qs, request)
    return _paginated_list(
        request,
        qs,
        "commercial/loss_reason_list.html",
        "Motivos de perda",
        {"categories": LossCategory.choices, "selected_category": category},
    )


@require_permission("loss_reasons.create")
def loss_reason_create(request):
    form = LossReasonForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = save_loss_reason(form=form, actor=request.user, request=request)
        messages.success(request, "Motivo de perda salvo com sucesso.")
        return redirect("commercial:loss_reason_update", pk=obj.pk)
    return render(
        request,
        "erp/form.html",
        {
            "page_title": "Novo motivo de perda",
            "form": form,
            "cancel_url": "commercial:loss_reasons",
        },
    )


@require_permission("loss_reasons.update")
def loss_reason_update(request, pk):
    obj = get_object_or_404(LossReason, pk=pk)
    form = LossReasonForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        save_loss_reason(form=form, actor=request.user, request=request)
        messages.success(request, "Motivo de perda atualizado com sucesso.")
        return redirect("commercial:loss_reason_update", pk=obj.pk)
    return render(
        request,
        "erp/form.html",
        {
            "page_title": f"Editar {obj.name}",
            "form": form,
            "cancel_url": "commercial:loss_reasons",
        },
    )


@require_permission("service_regions.view")
def region_list(request):
    qs = ServiceRegion.objects.all()
    search = request.GET.get("q", "").strip()
    city = request.GET.get("city", "").strip()
    state = request.GET.get("state", "").strip()
    service = request.GET.get("service", "").strip()
    if search:
        qs = qs.filter(name__icontains=search)
    if city:
        qs = qs.filter(city__icontains=city)
    if state:
        qs = qs.filter(state__iexact=state)
    if service == "1":
        qs = qs.filter(service_enabled=True, is_active=True)
    elif service == "0":
        qs = qs.filter(service_enabled=False)
    qs = _apply_active_filter(qs, request)
    return _paginated_list(
        request,
        qs,
        "commercial/region_list.html",
        "Regiões de atendimento",
        {"selected_city": city, "selected_state": state, "selected_service": service},
    )


@require_permission("service_regions.create")
def region_create(request):
    form = ServiceRegionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = save_service_region(form=form, actor=request.user, request=request)
        messages.success(request, "Região de atendimento salva com sucesso.")
        return redirect("commercial:region_update", pk=obj.pk)
    return render(
        request,
        "erp/form.html",
        {
            "page_title": "Nova região de atendimento",
            "form": form,
            "cancel_url": "commercial:regions",
        },
    )


@require_permission("service_regions.update")
def region_update(request, pk):
    obj = get_object_or_404(ServiceRegion, pk=pk)
    form = ServiceRegionForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        save_service_region(form=form, actor=request.user, request=request)
        messages.success(request, "Região de atendimento atualizada com sucesso.")
        return redirect("commercial:region_update", pk=obj.pk)
    return render(
        request,
        "erp/form.html",
        {
            "page_title": f"Editar {obj.name}",
            "form": form,
            "cancel_url": "commercial:regions",
        },
    )


@require_permission("contact_channels.view")
def channel_list(request):
    qs = ContactChannel.objects.all()
    search = request.GET.get("q", "").strip()
    if search:
        qs = qs.filter(name__icontains=search)
    qs = _apply_active_filter(qs, request)
    return _paginated_list(
        request,
        qs,
        "commercial/channel_list.html",
        "Canais de contato",
    )


@require_permission("contact_channels.create")
def channel_create(request):
    form = ContactChannelForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = save_contact_channel(form=form, actor=request.user, request=request)
        messages.success(request, "Canal de contato salvo com sucesso.")
        return redirect("commercial:channel_update", pk=obj.pk)
    return render(
        request,
        "erp/form.html",
        {
            "page_title": "Novo canal de contato",
            "form": form,
            "cancel_url": "commercial:channels",
        },
    )


@require_permission("contact_channels.update")
def channel_update(request, pk):
    obj = get_object_or_404(ContactChannel, pk=pk)
    form = ContactChannelForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        save_contact_channel(form=form, actor=request.user, request=request)
        messages.success(request, "Canal de contato atualizado com sucesso.")
        return redirect("commercial:channel_update", pk=obj.pk)
    return render(
        request,
        "erp/form.html",
        {
            "page_title": f"Editar {obj.name}",
            "form": form,
            "cancel_url": "commercial:channels",
        },
    )



@login_required
def master_data_summary(request):
    user = request.user
    cards = []
    alerts = []

    card_specs = [
        ("Clientes ativos", "customers.view", Customer.objects.filter(is_active=True).count(), "users", "customers:list"),
        ("Vendedores ativos", "salespeople.view", Salesperson.objects.filter(is_active=True).count(), "user-check", "salespeople:list"),
        ("Parceiros ativos", "commercial_partners.view", CommercialPartner.objects.filter(is_active=True).count(), "briefcase", "commercial:partners"),
        ("Origens ativas", "commercial_sources.view", CommercialSource.objects.filter(is_active=True).count(), "compass", "commercial:sources"),
        ("Tipos de projeto ativos", "project_types.view", ProjectType.objects.filter(is_active=True).count(), "grid", "commercial:project_types"),
        ("Canais ativos", "contact_channels.view", ContactChannel.objects.filter(is_active=True).count(), "message-circle", "commercial:channels"),
        ("Regiões atendidas", "service_regions.view", ServiceRegion.objects.filter(is_active=True, service_enabled=True).count(), "map-pin", "commercial:regions"),
        ("Materiais ativos", "materials.view", Material.objects.filter(is_active=True).count(), "layers", "materials:list"),
        ("Chapas disponíveis", "materials.view", MaterialSlab.objects.filter(is_active=True, status="available").count(), "copy", "materials:slabs"),
        ("Serviços ativos", "materials.view", AdditionalService.objects.filter(is_active=True).count(), "tool", "materials:services"),
        ("Acabamentos ativos", "materials.view", FinishType.objects.filter(is_active=True).count(), "sliders", "materials:finishes"),
    ]
    for label, permission, value, icon, url_name in card_specs:
        if user_has_permission(user, permission):
            cards.append({"label": label, "value": value, "icon": icon, "url_name": url_name})

    if user_has_permission(user, "customers.view"):
        no_salesperson = Customer.objects.filter(is_active=True, assigned_salesperson__isnull=True).count()
        if no_salesperson:
            alerts.append({
                "label": f"{no_salesperson} cliente(s) sem vendedor",
                "url_name": "customers:list",
                "query": "",
            })
        no_contact = Customer.objects.filter(
            is_active=True,
            email="",
            phone="",
            mobile_phone="",
        ).count()
        if no_contact:
            alerts.append({
                "label": f"{no_contact} cliente(s) sem telefone e e-mail",
                "url_name": "customers:list",
                "query": "",
            })

    if user_has_permission(user, "commercial_partners.view"):
        partners_no_contact = CommercialPartner.objects.filter(
            is_active=True,
            email="",
            phone="",
            mobile_phone="",
        ).count()
        if partners_no_contact:
            alerts.append({
                "label": f"{partners_no_contact} parceiro(s) sem contato",
                "url_name": "commercial:partners",
                "query": "q=",
            })

    if user_has_permission(user, "materials.view"):
        no_sale_price = Material.objects.filter(is_active=True, sale_price=Decimal("0.00")).count()
        if no_sale_price:
            alerts.append({
                "label": f"{no_sale_price} material(is) sem preço de venda",
                "url_name": "materials:list",
                "query": "",
            })
        below_minimum = Material.objects.filter(
            is_active=True,
            minimum_sale_price__gt=F("sale_price"),
        ).count()
        if below_minimum:
            alerts.append({
                "label": f"{below_minimum} material(is) com preço abaixo do mínimo",
                "url_name": "materials:list",
                "query": "",
            })
        slabs_no_location = MaterialSlab.objects.filter(is_active=True, location="").count()
        if slabs_no_location:
            alerts.append({
                "label": f"{slabs_no_location} chapa(s) sem localização",
                "url_name": "materials:slabs",
                "query": "",
            })

    if user_has_permission(user, "service_regions.view"):
        regions_no_city = ServiceRegion.objects.filter(is_active=True, city="").count()
        if regions_no_city:
            alerts.append({
                "label": f"{regions_no_city} região(ões) sem cidade",
                "url_name": "commercial:regions",
                "query": "",
            })

    if user_has_permission(user, "commercial_sources.view"):
        inactive_sources = CommercialSource.objects.filter(is_active=False).filter(
            Q(customers__isnull=False) | Q(quotes__isnull=False),
        ).distinct().count()
        if inactive_sources:
            alerts.append({
                "label": f"{inactive_sources} origem(ns) inativa(s) ainda referenciada(s)",
                "url_name": "commercial:sources",
                "query": "active=0",
            })

    return render(
        request,
        "commercial/summary.html",
        {"page_title": "Resumo de Cadastros", "cards": cards, "alerts": alerts},
    )
