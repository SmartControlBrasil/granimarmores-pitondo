# ruff: noqa: PLR0913
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render

from access_control.services.authorization import require_permission
from access_control.services.authorization import user_has_permission
from materials.models import Material
from materials.models import MaterialSlab
from materials.stock_forms import MaterialSlabEditForm
from materials.stock_forms import MaterialSupplierForm
from materials.stock_forms import SlabAdjustForm
from materials.stock_forms import SlabBlockForm
from materials.stock_forms import SlabConsumptionForm
from materials.stock_forms import SlabLossForm
from materials.stock_forms import SlabReceiveForm
from materials.stock_forms import SlabReservationForm
from materials.stock_forms import SlabTransferForm
from materials.stock_forms import StockInventoryForm
from materials.stock_forms import StockInventoryItemForm
from materials.stock_forms import StockLocationForm
from materials.stock_models import MaterialSupplier
from materials.stock_models import SlabReservation
from materials.stock_models import StockInventory
from materials.stock_models import StockInventoryItem
from materials.stock_models import StockLocation
from materials.stock_models import StockMovement
from materials.stock_selectors import parse_stock_period
from materials.stock_selectors import stock_dashboard_metrics
from materials.services.stock_operations import adjust_slab_area
from materials.services.stock_operations import block_slab
from materials.services.stock_operations import complete_inventory
from materials.services.stock_operations import consume_slab_reservation
from materials.services.stock_operations import discard_remnant
from materials.services.stock_operations import next_inventory_number
from materials.services.stock_operations import receive_slab
from materials.services.stock_operations import register_slab_loss
from materials.services.stock_operations import release_slab_reservation
from materials.services.stock_operations import reserve_slab_for_piece
from materials.services.stock_operations import start_inventory
from materials.services.stock_operations import transfer_slab
from materials.services.stock_operations import unblock_slab
from production.models import ProductionPiece


def _can_view_cost(user):
    return user_has_permission(user, "stock_costs.view")


@require_permission("stock_dashboard.view")
def stock_dashboard(request):
    start, end, period = parse_stock_period(request)
    metrics = stock_dashboard_metrics(
        request=request,
        start=start,
        end=end,
        material_id=request.GET.get("material") or None,
        location_id=request.GET.get("location") or None,
        supplier_id=request.GET.get("supplier") or None,
        status=request.GET.get("status") or None,
    )
    return render(
        request,
        "materials/stock/dashboard.html",
        {
            "page_title": "Dashboard de Estoque",
            "metrics": metrics,
            "period": period,
            "materials": Material.objects.filter(is_active=True),
            "locations": StockLocation.objects.filter(is_active=True),
            "suppliers": MaterialSupplier.objects.filter(is_active=True),
            "status_choices": MaterialSlab.Status.choices,
            "can_view_cost": _can_view_cost(request.user),
        },
    )


def _filter_slabs(request):
    qs = MaterialSlab.objects.select_related(
        "material",
        "stock_location",
        "supplier_ref",
    ).filter(is_active=True)
    material = request.GET.get("material")
    supplier = request.GET.get("supplier")
    location = request.GET.get("location")
    status = request.GET.get("status")
    if material:
        qs = qs.filter(material_id=material)
    if supplier:
        qs = qs.filter(supplier_ref_id=supplier)
    if location:
        qs = qs.filter(stock_location_id=location)
    if status:
        qs = qs.filter(status=status)
    if request.GET.get("available") == "1":
        qs = qs.filter(available_area__gt=0)
    if request.GET.get("reserved") == "1":
        qs = qs.filter(reserved_area__gt=0)
    if request.GET.get("blocked") == "1":
        qs = qs.filter(status=MaterialSlab.Status.BLOCKED)
    if request.GET.get("no_location") == "1":
        qs = qs.filter(stock_location__isnull=True, location_text="")
    if request.GET.get("remnants") == "1":
        qs = qs.filter(is_remnant=True)
    search = request.GET.get("q", "").strip()
    if search:
        qs = qs.filter(
            Q(slab_code__icontains=search)
            | Q(external_code__icontains=search)
            | Q(lot_number__icontains=search),
        )
    return qs.order_by("-received_at", "slab_code")


@require_permission("slabs.view")
def slab_list(request):
    page_obj = Paginator(_filter_slabs(request), 25).get_page(request.GET.get("page"))
    return render(
        request,
        "materials/stock/slab_list.html",
        {
            "page_title": "Chapas",
            "page_obj": page_obj,
            "materials": Material.objects.filter(is_active=True),
            "locations": StockLocation.objects.filter(is_active=True),
            "suppliers": MaterialSupplier.objects.filter(is_active=True),
            "status_choices": MaterialSlab.Status.choices,
            "can_view_cost": _can_view_cost(request.user),
        },
    )


@require_permission("slabs.create")
def slab_receive(request):
    form = SlabReceiveForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        slab = receive_slab(
            material=data["material"],
            width=data["width"],
            height=data["height"],
            thickness=data["thickness"],
            supplier=data.get("supplier"),
            location=data.get("location"),
            cost_value=data["cost_value"],
            actor=request.user,
            external_code=data.get("external_code", ""),
            batch=data.get("batch", ""),
            bundle=data.get("bundle", ""),
            serial_number=data.get("serial_number", ""),
            lot_number=data.get("lot_number", ""),
            rack=data.get("rack", ""),
            position=data.get("position", ""),
            notes=data.get("notes", ""),
            request=request,
        )
        messages.success(request, f"Chapa {slab.slab_code} registrada com sucesso.")
        return redirect("stock:slab_detail", pk=slab.pk)
    return render(
        request,
        "erp/form.html",
        {"page_title": "Entrada de chapa", "form": form, "cancel_url": "stock:slab_list"},
    )


@require_permission("slabs.view")
def slab_detail(request, pk):
    slab = get_object_or_404(
        MaterialSlab.objects.select_related(
            "material",
            "stock_location",
            "supplier_ref",
            "parent_slab",
        ),
        pk=pk,
    )
    return render(
        request,
        "materials/stock/slab_detail.html",
        {
            "page_title": slab.slab_code,
            "slab": slab,
            "reservations": slab.reservations.select_related(
                "production_piece",
                "production_order",
            )[:50],
            "movements": slab.movements.select_related(
                "created_by",
                "source_location",
                "destination_location",
            )[:50],
            "losses": slab.losses.select_related("production_piece")[:20],
            "remnants": slab.remnants.all()[:20],
            "can_view_cost": _can_view_cost(request.user),
            "can_transfer": user_has_permission(request.user, "slabs.transfer"),
            "can_block": user_has_permission(request.user, "slabs.block"),
            "can_adjust": user_has_permission(request.user, "stock_adjustments.execute"),
        },
    )


@require_permission("slabs.update")
def slab_edit(request, pk):
    slab = get_object_or_404(MaterialSlab, pk=pk)
    form = MaterialSlabEditForm(request.POST or None, instance=slab)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.updated_by = request.user
        obj.save()
        messages.success(request, "Chapa atualizada.")
        return redirect("stock:slab_detail", pk=slab.pk)
    return render(
        request,
        "erp/form.html",
        {"page_title": f"Editar {slab.slab_code}", "form": form, "cancel_url": "stock:slab_detail", "object_pk": pk},
    )


@require_permission("slabs.transfer")
def slab_transfer(request, pk):
    slab = get_object_or_404(MaterialSlab, pk=pk)
    form = SlabTransferForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        transfer_slab(
            slab=slab,
            destination=form.cleaned_data["destination"],
            actor=request.user,
            notes=form.cleaned_data.get("notes", ""),
            request=request,
        )
        messages.success(request, "Transferência registrada.")
        return redirect("stock:slab_detail", pk=pk)
    return render(
        request,
        "erp/form.html",
        {"page_title": "Transferir chapa", "form": form, "cancel_url": "stock:slab_detail", "object_pk": pk},
    )


@require_permission("slabs.block")
def slab_block(request, pk):
    slab = get_object_or_404(MaterialSlab, pk=pk)
    form = SlabBlockForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        block_slab(slab=slab, reason=form.cleaned_data["reason"], actor=request.user, request=request)
        messages.success(request, "Chapa bloqueada.")
        return redirect("stock:slab_detail", pk=pk)
    return render(
        request,
        "erp/form.html",
        {"page_title": "Bloquear chapa", "form": form, "cancel_url": "stock:slab_detail", "object_pk": pk},
    )


@require_permission("slabs.unblock")
def slab_unblock(request, pk):
    slab = get_object_or_404(MaterialSlab, pk=pk)
    if request.method == "POST":
        unblock_slab(slab=slab, actor=request.user, request=request)
        messages.success(request, "Chapa desbloqueada.")
        return redirect("stock:slab_detail", pk=pk)
    return render(
        request,
        "erp/confirm_action.html",
        {"page_title": "Desbloquear chapa", "message": f"Desbloquear {slab.slab_code}?"},
    )


@require_permission("stock_adjustments.execute")
def slab_adjust(request, pk):
    slab = get_object_or_404(MaterialSlab, pk=pk)
    form = SlabAdjustForm(request.POST or None, initial={"new_available_area": slab.available_area})
    if request.method == "POST" and form.is_valid():
        adjust_slab_area(
            slab=slab,
            new_available_area=form.cleaned_data["new_available_area"],
            reason=form.cleaned_data["reason"],
            actor=request.user,
            request=request,
        )
        messages.success(request, "Ajuste registrado.")
        return redirect("stock:slab_detail", pk=pk)
    return render(
        request,
        "erp/form.html",
        {"page_title": "Ajustar estoque", "form": form, "cancel_url": "stock:slab_detail", "object_pk": pk},
    )


@require_permission("slab_reservations.view")
def reservation_list(request):
    qs = SlabReservation.objects.select_related(
        "slab",
        "production_piece",
        "production_order",
    ).order_by("-reserved_at")
    status = request.GET.get("status")
    if status:
        qs = qs.filter(status=status)
    page_obj = Paginator(qs, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "materials/stock/reservation_list.html",
        {"page_title": "Reservas", "page_obj": page_obj, "status_choices": SlabReservation.Status.choices},
    )


@require_permission("slab_remnants.view")
def remnant_list(request):
    qs = MaterialSlab.objects.filter(is_remnant=True, is_active=True).select_related("material", "stock_location", "parent_slab")
    page_obj = Paginator(qs, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "materials/stock/remnant_list.html",
        {"page_title": "Sobras", "page_obj": page_obj},
    )


@require_permission("stock_movements.view")
def movement_list(request):
    qs = StockMovement.objects.select_related("slab", "created_by").order_by("-occurred_at")
    page_obj = Paginator(qs, 30).get_page(request.GET.get("page"))
    return render(
        request,
        "materials/stock/movement_list.html",
        {"page_title": "Movimentações", "page_obj": page_obj},
    )


@require_permission("stock_locations.view")
def location_list(request):
    qs = StockLocation.objects.select_related("parent").order_by("display_order", "name")
    return render(
        request,
        "materials/stock/location_list.html",
        {"page_title": "Localizações", "locations": qs},
    )


@require_permission("stock_locations.create")
def location_create(request):
    form = StockLocationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.created_by = request.user
        obj.updated_by = request.user
        obj.save()
        messages.success(request, "Localização criada.")
        return redirect("stock:location_list")
    return render(
        request,
        "erp/form.html",
        {"page_title": "Nova localização", "form": form, "cancel_url": "stock:location_list"},
    )


@require_permission("stock_locations.update")
def location_update(request, pk):
    location = get_object_or_404(StockLocation, pk=pk)
    form = StockLocationForm(request.POST or None, instance=location)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.updated_by = request.user
        obj.save()
        messages.success(request, "Localização atualizada.")
        return redirect("stock:location_list")
    return render(
        request,
        "erp/form.html",
        {"page_title": f"Editar {location.name}", "form": form, "cancel_url": "stock:location_list"},
    )


@require_permission("material_suppliers.view")
def supplier_list(request):
    qs = MaterialSupplier.objects.order_by("name")
    return render(
        request,
        "materials/stock/supplier_list.html",
        {"page_title": "Fornecedores", "suppliers": qs},
    )


@require_permission("material_suppliers.create")
def supplier_create(request):
    form = MaterialSupplierForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.created_by = request.user
        obj.updated_by = request.user
        obj.save()
        messages.success(request, "Fornecedor criado.")
        return redirect("stock:supplier_list")
    return render(
        request,
        "erp/form.html",
        {"page_title": "Novo fornecedor", "form": form, "cancel_url": "stock:supplier_list"},
    )


@require_permission("material_suppliers.update")
def supplier_update(request, pk):
    supplier = get_object_or_404(MaterialSupplier, pk=pk)
    form = MaterialSupplierForm(request.POST or None, instance=supplier)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.updated_by = request.user
        obj.save()
        messages.success(request, "Fornecedor atualizado.")
        return redirect("stock:supplier_list")
    return render(
        request,
        "erp/form.html",
        {"page_title": f"Editar {supplier.name}", "form": form, "cancel_url": "stock:supplier_list"},
    )


@require_permission("stock_inventory.view")
def inventory_list(request):
    qs = StockInventory.objects.select_related("location", "created_by").order_by("-created_at")
    page_obj = Paginator(qs, 20).get_page(request.GET.get("page"))
    return render(
        request,
        "materials/stock/inventory_list.html",
        {"page_title": "Inventários", "page_obj": page_obj},
    )


@require_permission("stock_inventory.create")
def inventory_create(request):
    form = StockInventoryForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        inv = form.save(commit=False)
        inv.number = next_inventory_number()
        inv.created_by = request.user
        inv.updated_by = request.user
        inv.save()
        messages.success(request, f"Inventário {inv.number} criado.")
        return redirect("stock:inventory_detail", pk=inv.pk)
    return render(
        request,
        "erp/form.html",
        {"page_title": "Novo inventário", "form": form, "cancel_url": "stock:inventory_list"},
    )


@require_permission("stock_inventory.view")
def inventory_detail(request, pk):
    inventory = get_object_or_404(
        StockInventory.objects.select_related("location"),
        pk=pk,
    )
    items = inventory.items.select_related("slab", "counted_by")
    return render(
        request,
        "materials/stock/inventory_detail.html",
        {
            "page_title": inventory.number,
            "inventory": inventory,
            "items": items,
            "can_inventory": user_has_permission(request.user, "stock_inventory.inventory"),
            "can_approve": user_has_permission(request.user, "stock_inventory.approve_inventory"),
        },
    )


@require_permission("stock_inventory.inventory")
def inventory_start(request, pk):
    inventory = get_object_or_404(StockInventory, pk=pk)
    if request.method == "POST":
        start_inventory(inventory=inventory, actor=request.user, request=request)
        messages.success(request, "Inventário iniciado.")
        return redirect("stock:inventory_detail", pk=pk)
    return render(
        request,
        "erp/confirm_action.html",
        {"page_title": "Iniciar inventário", "message": f"Iniciar {inventory.number}?"},
    )


@require_permission("stock_inventory.inventory")
def inventory_count_item(request, pk, item_pk):
    inventory = get_object_or_404(StockInventory, pk=pk)
    item = get_object_or_404(StockInventoryItem, pk=item_pk, inventory=inventory)
    form = StockInventoryItemForm(request.POST or None, initial={"counted_area": item.expected_area})
    if request.method == "POST" and form.is_valid():
        from django.utils import timezone

        item.counted_area = form.cleaned_data["counted_area"]
        item.notes = form.cleaned_data.get("notes", "")
        item.counted_by = request.user
        item.counted_at = timezone.now()
        item.status = StockInventoryItem.ItemStatus.COUNTED
        item.save()
        messages.success(request, "Contagem registrada.")
        return redirect("stock:inventory_detail", pk=pk)
    return render(
        request,
        "erp/form.html",
        {"page_title": f"Contar {item.slab.slab_code}", "form": form, "cancel_url": "stock:inventory_detail", "object_pk": pk},
    )


@require_permission("stock_inventory.approve_inventory")
def inventory_complete(request, pk):
    inventory = get_object_or_404(StockInventory, pk=pk)
    apply = request.POST.get("apply_adjustments") == "1"
    if request.method == "POST":
        complete_inventory(
            inventory=inventory,
            actor=request.user,
            apply_adjustments=apply,
            request=request,
        )
        messages.success(request, "Inventário concluído.")
        return redirect("stock:inventory_detail", pk=pk)
    return render(
        request,
        "materials/stock/inventory_complete.html",
        {"page_title": "Concluir inventário", "inventory": inventory},
    )


@require_permission("slab_reservations.reserve")
def piece_reserve_slab(request, pk):
    piece = get_object_or_404(
        ProductionPiece.objects.select_related("material", "production_order"),
        pk=pk,
    )
    form = SlabReservationForm(request.POST or None, piece=piece)
    if request.method == "POST" and form.is_valid():
        reserve_slab_for_piece(
            slab=form.cleaned_data["slab"],
            production_piece=piece,
            reserved_area=form.cleaned_data["reserved_area"],
            actor=request.user,
            notes=form.cleaned_data.get("notes", ""),
            request=request,
        )
        messages.success(request, "Chapa reservada.")
        return redirect("producao:piece_detail", pk=pk)
    from materials.services.stock_operations import compatible_slabs_for_piece

    suggestions = compatible_slabs_for_piece(piece=piece)[:10]
    return render(
        request,
        "materials/stock/piece_reserve.html",
        {
            "page_title": f"Reservar chapa — {piece.code}",
            "form": form,
            "piece": piece,
            "suggestions": suggestions,
            "can_view_cost": _can_view_cost(request.user),
        },
    )


@require_permission("slab_reservations.release")
def reservation_release(request, pk):
    reservation = get_object_or_404(SlabReservation, pk=pk)
    if request.method == "POST":
        release_slab_reservation(reservation=reservation, actor=request.user, request=request)
        messages.success(request, "Reserva liberada.")
        return redirect("stock:reservation_list")
    return render(
        request,
        "erp/confirm_action.html",
        {"page_title": "Liberar reserva", "message": f"Liberar reserva de {reservation.slab}?"},
    )


@require_permission("slab_consumption.consume")
def reservation_consume(request, pk):
    reservation = get_object_or_404(SlabReservation.objects.select_related("slab"), pk=pk)
    form = SlabConsumptionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        consume_slab_reservation(
            reservation=reservation,
            consumed_area=form.cleaned_data["consumed_area"],
            lost_area=form.cleaned_data.get("lost_area") or 0,
            actor=request.user,
            notes=form.cleaned_data.get("notes", ""),
            remnant_width=form.cleaned_data.get("remnant_width"),
            remnant_height=form.cleaned_data.get("remnant_height"),
            request=request,
        )
        messages.success(request, "Consumo registrado.")
        return redirect("stock:reservation_list")
    return render(
        request,
        "erp/form.html",
        {"page_title": "Registrar consumo", "form": form, "cancel_url": "stock:reservation_list"},
    )


@require_permission("slab_losses.create")
def slab_register_loss(request, pk):
    slab = get_object_or_404(MaterialSlab, pk=pk)
    form = SlabLossForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        register_slab_loss(
            slab=slab,
            area=form.cleaned_data["area"],
            loss_reason=form.cleaned_data["loss_reason"],
            description=form.cleaned_data.get("description", ""),
            actor=request.user,
            request=request,
        )
        messages.success(request, "Perda registrada.")
        return redirect("stock:slab_detail", pk=pk)
    return render(
        request,
        "erp/form.html",
        {"page_title": "Registrar perda", "form": form, "cancel_url": "stock:slab_detail", "object_pk": pk},
    )


@require_permission("slab_remnants.update")
def remnant_discard(request, pk):
    remnant = get_object_or_404(MaterialSlab, pk=pk, is_remnant=True)
    if request.method == "POST":
        reason = request.POST.get("reason", "").strip()
        discard_remnant(remnant=remnant, reason=reason, actor=request.user, request=request)
        messages.success(request, "Sobra descartada.")
        return redirect("stock:remnant_list")
    return render(
        request,
        "erp/confirm_action.html",
        {"page_title": "Descartar sobra", "message": f"Descartar {remnant.slab_code}? Informe motivo no POST."},
    )
