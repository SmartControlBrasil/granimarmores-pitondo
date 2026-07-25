# ruff: noqa: PLR0913
from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render

from access_control.services.authorization import require_permission
from materials.forms import AdditionalServiceForm
from materials.forms import FinishTypeForm
from materials.forms import MaterialCategoryForm
from materials.forms import MaterialForm
from materials.forms import MaterialSlabForm
from materials.models import AdditionalService
from materials.models import FinishType
from materials.models import Material
from materials.models import MaterialCategory
from materials.models import MaterialPriceHistory
from materials.models import MaterialSlab
from materials.services.material_management import save_category
from materials.services.material_management import save_material
from materials.services.material_management import save_priced_model
from materials.services.material_management import set_active


def _list(request, qs, template, title, extra=None):
    search = request.GET.get("q", "").strip()
    if search and hasattr(qs.model, "name"):
        qs = qs.filter(name__icontains=search)
    page_obj = Paginator(qs, 20).get_page(request.GET.get("page"))
    context = {"page_title": title, "page_obj": page_obj, "search": search}
    context.update(extra or {})
    return render(request, template, context)


@require_permission("materials.view")
def material_list(request):
    qs = Material.objects.select_related("category")
    return _list(request, qs, "materials/material_list.html", "Materiais")


@require_permission("materials.view")
def material_detail(request, pk):
    material = get_object_or_404(Material.objects.select_related("category"), pk=pk)
    history = MaterialPriceHistory.objects.filter(material=material)[:20]
    slabs = MaterialSlab.objects.filter(material=material)[:20]
    return render(
        request,
        "materials/material_detail.html",
        {
            "page_title": material.name,
            "material": material,
            "history": history,
            "slabs": slabs,
        },
    )


@require_permission("materials.create")
def material_create(request):
    form = MaterialForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        material = save_material(form=form, actor=request.user, request=request)
        messages.success(request, "Material criado com sucesso.")
        return redirect("materials:detail", pk=material.pk)
    return render(
        request,
        "erp/form.html",
        {"page_title": "Novo material", "form": form, "cancel_url": "materials:list"},
    )


@require_permission("materials.update")
def material_update(request, pk):
    material = get_object_or_404(Material, pk=pk)
    form = MaterialForm(request.POST or None, instance=material)
    if request.method == "POST" and form.is_valid():
        material = save_material(form=form, actor=request.user, request=request)
        messages.success(request, "Material atualizado com sucesso.")
        return redirect("materials:detail", pk=material.pk)
    return render(
        request,
        "erp/form.html",
        {
            "page_title": f"Editar {material.name}",
            "form": form,
            "cancel_url": "materials:list",
        },
    )


@require_permission("materials.deactivate")
def material_deactivate(request, pk):
    material = get_object_or_404(Material, pk=pk)
    if request.method == "POST":
        set_active(
            obj=material,
            is_active=False,
            actor=request.user,
            request=request,
            action_prefix="material",
        )
        messages.success(request, "Material desativado com sucesso.")
        return redirect("materials:detail", pk=material.pk)
    return render(
        request,
        "erp/confirm_action.html",
        {"page_title": "Desativar material", "message": f"Desativar {material.name}?"},
    )


@require_permission("materials.update")
def material_activate(request, pk):
    material = get_object_or_404(Material, pk=pk)
    if request.method == "POST":
        set_active(
            obj=material,
            is_active=True,
            actor=request.user,
            request=request,
            action_prefix="material",
        )
        messages.success(request, "Material ativado com sucesso.")
        return redirect("materials:detail", pk=material.pk)
    return render(
        request,
        "erp/confirm_action.html",
        {"page_title": "Ativar material", "message": f"Ativar {material.name}?"},
    )


@require_permission("materials.view")
def category_list(request):
    return _list(
        request,
        MaterialCategory.objects.all(),
        "materials/category_list.html",
        "Categorias",
    )


@require_permission("materials.create")
def category_create(request):
    form = MaterialCategoryForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        save_category(form=form, actor=request.user, request=request)
        messages.success(request, "Categoria salva com sucesso.")
        return redirect("materials:categories")
    return render(
        request,
        "erp/form.html",
        {
            "page_title": "Nova categoria",
            "form": form,
            "cancel_url": "materials:categories",
        },
    )


@require_permission("materials.update")
def category_update(request, pk):
    category = get_object_or_404(MaterialCategory, pk=pk)
    form = MaterialCategoryForm(request.POST or None, instance=category)
    if request.method == "POST" and form.is_valid():
        save_category(form=form, actor=request.user, request=request)
        messages.success(request, "Categoria atualizada com sucesso.")
        return redirect("materials:categories")
    return render(
        request,
        "erp/form.html",
        {
            "page_title": f"Editar {category.name}",
            "form": form,
            "cancel_url": "materials:categories",
        },
    )


def _priced_list(request, model, template, title):
    return _list(request, model.objects.all(), template, title)


def _priced_form(request, model, form_class, title, list_route, module_action, pk=None):
    obj = get_object_or_404(model, pk=pk) if pk else None
    form = form_class(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        save_priced_model(
            form=form,
            actor=request.user,
            request=request,
            module_action=module_action,
        )
        messages.success(request, "Registro salvo com sucesso.")
        return redirect(list_route)
    return render(
        request,
        "erp/form.html",
        {"page_title": title, "form": form, "cancel_url": list_route},
    )


@require_permission("materials.view")
def finish_list(request):
    return _priced_list(
        request,
        FinishType,
        "materials/finish_list.html",
        "Acabamentos",
    )


@require_permission("materials.create")
def finish_create(request):
    return _priced_form(
        request,
        FinishType,
        FinishTypeForm,
        "Novo acabamento",
        "materials:finishes",
        "finish_saved",
    )


@require_permission("materials.update")
def finish_update(request, pk):
    return _priced_form(
        request,
        FinishType,
        FinishTypeForm,
        "Editar acabamento",
        "materials:finishes",
        "finish_saved",
        pk,
    )


@require_permission("materials.view")
def service_list(request):
    return _priced_list(
        request,
        AdditionalService,
        "materials/service_list.html",
        "Serviços adicionais",
    )


@require_permission("materials.create")
def service_create(request):
    return _priced_form(
        request,
        AdditionalService,
        AdditionalServiceForm,
        "Novo serviço",
        "materials:services",
        "additional_service_saved",
    )


@require_permission("materials.update")
def service_update(request, pk):
    return _priced_form(
        request,
        AdditionalService,
        AdditionalServiceForm,
        "Editar serviço",
        "materials:services",
        "additional_service_saved",
        pk,
    )


@require_permission("materials.view")
def slab_list(request):
    qs = MaterialSlab.objects.select_related("material")
    return _list(request, qs, "materials/slab_list.html", "Chapas")


@require_permission("materials.create")
def slab_create(request):
    form = MaterialSlabForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        slab = form.save(commit=False)
        slab.created_by = request.user
        slab.updated_by = request.user
        slab.save()
        messages.success(request, "Chapa salva com sucesso.")
        return redirect("materials:slabs")
    return render(
        request,
        "erp/form.html",
        {"page_title": "Nova chapa", "form": form, "cancel_url": "materials:slabs"},
    )
