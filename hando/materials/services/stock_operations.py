# ruff: noqa: EM101, PLR0913, TRY003
from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from access_control.services.authorization import user_has_permission
from audit.services import record_audit_event
from materials.models import MaterialSlab
from materials.stock_models import SlabLoss
from materials.stock_models import SlabReservation
from materials.stock_models import SlabSequence
from materials.stock_models import StockInventory
from materials.stock_models import StockInventoryItem
from materials.stock_models import StockMovement

RESERVABLE_STATUSES = {
    MaterialSlab.Status.AVAILABLE,
    MaterialSlab.Status.PARTIALLY_RESERVED,
    MaterialSlab.Status.PARTIALLY_CONSUMED,
}

BLOCKED_STATUSES = {
    MaterialSlab.Status.BLOCKED,
    MaterialSlab.Status.DAMAGED,
    MaterialSlab.Status.DISCARDED,
    MaterialSlab.Status.CONSUMED,
}

CUT_STAGE_SLUG = "corte"


def calculate_area(*, width_mm, height_mm):
    if width_mm <= 0 or height_mm <= 0:
        raise ValidationError("Largura e altura devem ser positivas.")
    return (width_mm * height_mm / Decimal("1000000")).quantize(Decimal("0.0001"))


@transaction.atomic
def next_slab_code(*, year=None):
    year = year or timezone.now().year
    seq, _ = SlabSequence.objects.select_for_update().get_or_create(
        year=year,
        defaults={"last_number": 0},
    )
    seq.last_number += 1
    seq.save(update_fields=["last_number"])
    return f"CHP-{year}-{seq.last_number:06d}"


def _refresh_slab_status(slab):
    if slab.status in {MaterialSlab.Status.BLOCKED, MaterialSlab.Status.DISCARDED}:
        return
    if slab.available_area <= 0 and slab.reserved_area <= 0:
        if slab.consumed_area >= slab.total_area:
            slab.status = MaterialSlab.Status.CONSUMED
        return
    if slab.consumed_area > 0 and slab.available_area > 0:
        slab.status = MaterialSlab.Status.PARTIALLY_CONSUMED
    elif slab.reserved_area >= slab.total_area:
        slab.status = MaterialSlab.Status.FULLY_RESERVED
    elif slab.reserved_area > 0:
        slab.status = MaterialSlab.Status.PARTIALLY_RESERVED
    elif slab.available_area > 0:
        slab.status = MaterialSlab.Status.AVAILABLE


def _create_movement(
    *,
    slab,
    movement_type,
    quantity_area,
    actor,
    previous_available,
    new_available,
    source_location=None,
    destination_location=None,
    reference_type="",
    reference_id="",
    description="",
    occurred_at=None,
):
    return StockMovement.objects.create(
        slab=slab,
        movement_type=movement_type,
        quantity_area=quantity_area,
        previous_available_area=previous_available,
        new_available_area=new_available,
        source_location=source_location,
        destination_location=destination_location,
        reference_type=reference_type,
        reference_id=str(reference_id) if reference_id else "",
        description=description,
        occurred_at=occurred_at or timezone.now(),
        created_by=actor,
    )


def _lock_slab(slab_id):
    return MaterialSlab.objects.select_for_update().get(pk=slab_id)


@transaction.atomic
def receive_slab(
    *,
    material,
    width,
    height,
    thickness,
    supplier,
    location,
    cost_value,
    actor,
    external_code="",
    batch="",
    bundle="",
    serial_number="",
    lot_number="",
    rack="",
    position="",
    notes="",
    request=None,
):
    if not user_has_permission(actor, "slabs.create"):
        raise PermissionDenied("Sem permissão para registrar entrada de chapa.")

    total_area = calculate_area(width_mm=width, height_mm=height)
    code = next_slab_code()
    now = timezone.now()

    slab = MaterialSlab.objects.create(
        material=material,
        slab_code=code,
        external_code=external_code,
        lot_number=lot_number,
        batch=batch,
        bundle=bundle,
        serial_number=serial_number,
        supplier_ref=supplier,
        width_mm=width,
        height_mm=height,
        thickness_mm=thickness,
        total_area=total_area,
        available_area=total_area,
        reserved_area=Decimal("0.0000"),
        consumed_area=Decimal("0.0000"),
        lost_area=Decimal("0.0000"),
        cost_value=cost_value,
        stock_location=location,
        rack=rack,
        position=position,
        received_at=now,
        status=MaterialSlab.Status.AVAILABLE,
        notes=notes,
        created_by=actor,
        updated_by=actor,
    )

    _create_movement(
        slab=slab,
        movement_type=StockMovement.MovementType.ENTRY,
        quantity_area=total_area,
        previous_available=Decimal("0.0000"),
        new_available=total_area,
        destination_location=location,
        reference_type="slab_entry",
        reference_id=slab.pk,
        description=notes or "Entrada de chapa",
        actor=actor,
        occurred_at=now,
    )

    record_audit_event(
        request=request,
        user=actor,
        event_type="create",
        module="materials",
        action="slab_received",
        obj=slab,
        metadata={"code": code, "area": str(total_area)},
    )
    return slab


@transaction.atomic
def reserve_slab_for_piece(
    *,
    slab,
    production_piece,
    reserved_area,
    actor,
    notes="",
    request=None,
):
    if not user_has_permission(actor, "slab_reservations.reserve"):
        raise PermissionDenied("Sem permissão para reservar chapa.")

    if reserved_area <= 0:
        raise ValidationError("Área reservada deve ser positiva.")

    slab = _lock_slab(slab.pk)
    if slab.status in BLOCKED_STATUSES:
        raise ValidationError("Chapa bloqueada ou indisponível não pode ser reservada.")
    if slab.available_area < reserved_area:
        raise ValidationError("Área disponível insuficiente para reserva.")

    duplicate = SlabReservation.objects.filter(
        slab=slab,
        production_piece=production_piece,
        status=SlabReservation.Status.ACTIVE,
    ).exists()
    if duplicate:
        raise ValidationError("Já existe reserva ativa desta chapa para esta peça.")

    prev_available = slab.available_area
    slab.available_area = (slab.available_area - reserved_area).quantize(Decimal("0.0001"))
    slab.reserved_area = (slab.reserved_area + reserved_area).quantize(Decimal("0.0001"))
    _refresh_slab_status(slab)
    slab.updated_by = actor
    slab.save()

    reservation = SlabReservation.objects.create(
        slab=slab,
        production_order=production_piece.production_order,
        production_piece=production_piece,
        reserved_area=reserved_area,
        status=SlabReservation.Status.ACTIVE,
        notes=notes,
        created_by=actor,
        updated_by=actor,
    )

    production_piece.slab = slab
    production_piece.save(update_fields=["slab", "updated_at"])

    _create_movement(
        slab=slab,
        movement_type=StockMovement.MovementType.RESERVATION,
        quantity_area=reserved_area,
        previous_available=prev_available,
        new_available=slab.available_area,
        reference_type="slab_reservation",
        reference_id=reservation.pk,
        description=notes or f"Reserva peça {production_piece.code}",
        actor=actor,
    )

    record_audit_event(
        request=request,
        user=actor,
        event_type="create",
        module="materials",
        action="slab_reserved",
        obj=reservation,
        metadata={"area": str(reserved_area)},
    )
    return reservation


@transaction.atomic
def release_slab_reservation(*, reservation, actor, notes="", request=None):
    if not user_has_permission(actor, "slab_reservations.release"):
        raise PermissionDenied("Sem permissão para liberar reserva.")

    reservation = (
        SlabReservation.objects.select_for_update()
        .select_related("slab", "production_piece")
        .get(pk=reservation.pk)
    )
    if reservation.status not in {
        SlabReservation.Status.ACTIVE,
        SlabReservation.Status.PARTIALLY_CONSUMED,
    }:
        raise ValidationError("Somente reservas ativas podem ser liberadas.")

    remaining = reservation.reserved_area - reservation.consumed_area - reservation.lost_area
    if remaining <= 0:
        raise ValidationError("Reserva sem área restante para liberar.")

    slab = _lock_slab(reservation.slab_id)
    prev_available = slab.available_area
    slab.available_area = (slab.available_area + remaining).quantize(Decimal("0.0001"))
    slab.reserved_area = (slab.reserved_area - remaining).quantize(Decimal("0.0001"))
    _refresh_slab_status(slab)
    slab.updated_by = actor
    slab.save()

    now = timezone.now()
    reservation.status = SlabReservation.Status.RELEASED
    reservation.released_at = now
    reservation.released_by = actor
    reservation.updated_by = actor
    if notes:
        reservation.notes = notes
    reservation.save()

    _create_movement(
        slab=slab,
        movement_type=StockMovement.MovementType.RESERVATION_RELEASE,
        quantity_area=remaining,
        previous_available=prev_available,
        new_available=slab.available_area,
        reference_type="slab_reservation",
        reference_id=reservation.pk,
        description=notes or "Liberação de reserva",
        actor=actor,
    )

    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="materials",
        action="slab_reservation_released",
        obj=reservation,
    )
    return reservation


@transaction.atomic
def consume_slab_reservation(
    *,
    reservation,
    consumed_area,
    lost_area=Decimal("0.0000"),
    actor,
    notes="",
    remnant_width=None,
    remnant_height=None,
    remnant_location=None,
    request=None,
):
    if not user_has_permission(actor, "slab_consumption.consume"):
        raise PermissionDenied("Sem permissão para consumir chapa.")

    if consumed_area <= 0:
        raise ValidationError("Consumo deve ser positivo.")
    if lost_area < 0:
        raise ValidationError("Perda não pode ser negativa.")

    reservation = (
        SlabReservation.objects.select_for_update()
        .select_related("slab", "production_piece", "production_order")
        .get(pk=reservation.pk)
    )
    if reservation.status not in {
        SlabReservation.Status.ACTIVE,
        SlabReservation.Status.PARTIALLY_CONSUMED,
    }:
        raise ValidationError("Reserva não está ativa para consumo.")

    pending = reservation.reserved_area - reservation.consumed_area - reservation.lost_area
    if consumed_area + lost_area > pending:
        raise ValidationError("Consumo e perda excedem área reservada pendente.")

    slab = _lock_slab(reservation.slab_id)
    prev_available = slab.available_area

    reservation.consumed_area = (reservation.consumed_area + consumed_area).quantize(
        Decimal("0.0001"),
    )
    reservation.lost_area = (reservation.lost_area + lost_area).quantize(Decimal("0.0001"))
    slab.consumed_area = (slab.consumed_area + consumed_area).quantize(Decimal("0.0001"))
    slab.lost_area = (slab.lost_area + lost_area).quantize(Decimal("0.0001"))
    slab.reserved_area = (slab.reserved_area - consumed_area - lost_area).quantize(
        Decimal("0.0001"),
    )

    pending_after = reservation.reserved_area - reservation.consumed_area - reservation.lost_area
    now = timezone.now()
    if pending_after <= 0:
        reservation.status = SlabReservation.Status.CONSUMED
        reservation.consumed_at = now
    else:
        reservation.status = SlabReservation.Status.PARTIALLY_CONSUMED
    reservation.updated_by = actor
    reservation.save()

    _refresh_slab_status(slab)
    slab.updated_by = actor
    slab.save()

    _create_movement(
        slab=slab,
        movement_type=StockMovement.MovementType.CONSUMPTION,
        quantity_area=consumed_area,
        previous_available=prev_available,
        new_available=slab.available_area,
        reference_type="slab_reservation",
        reference_id=reservation.pk,
        description=notes or "Consumo de chapa",
        actor=actor,
    )

    if lost_area > 0:
        _create_movement(
            slab=slab,
            movement_type=StockMovement.MovementType.LOSS,
            quantity_area=lost_area,
            previous_available=slab.available_area,
            new_available=slab.available_area,
            reference_type="slab_reservation",
            reference_id=reservation.pk,
            description=notes or "Perda no consumo",
            actor=actor,
        )

    remnant = None
    if remnant_width and remnant_height and remnant_width > 0 and remnant_height > 0:
        remnant = create_slab_remnant(
            origin_slab=slab,
            origin_reservation=reservation,
            width=remnant_width,
            height=remnant_height,
            thickness=slab.thickness_mm,
            location=remnant_location or slab.stock_location,
            actor=actor,
            request=request,
        )

    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="materials",
        action="slab_consumed",
        obj=reservation,
        metadata={"consumed": str(consumed_area), "lost": str(lost_area)},
    )
    return reservation, remnant


@transaction.atomic
def register_slab_loss(
    *,
    slab,
    area,
    loss_reason,
    actor,
    production_piece=None,
    reservation=None,
    description="",
    occurred_at=None,
    request=None,
):
    if not user_has_permission(actor, "slab_losses.create"):
        raise PermissionDenied("Sem permissão para registrar perda.")

    if area <= 0:
        raise ValidationError("Área de perda deve ser positiva.")
    if loss_reason == SlabLoss.LossReason.OTHER and not description.strip():
        raise ValidationError("Descrição obrigatória para motivo 'Outro'.")

    slab = _lock_slab(slab.pk)
    prev_available = slab.available_area

    if reservation:
        reservation = SlabReservation.objects.select_for_update().get(pk=reservation.pk)
        pending = reservation.reserved_area - reservation.consumed_area - reservation.lost_area
        if area > pending:
            raise ValidationError("Perda excede área reservada pendente.")
        reservation.lost_area = (reservation.lost_area + area).quantize(Decimal("0.0001"))
        slab.reserved_area = (slab.reserved_area - area).quantize(Decimal("0.0001"))
        reservation.updated_by = actor
        reservation.save()
    elif area > slab.available_area:
        raise ValidationError("Perda excede área disponível.")
    else:
        slab.available_area = (slab.available_area - area).quantize(Decimal("0.0001"))

    slab.lost_area = (slab.lost_area + area).quantize(Decimal("0.0001"))
    _refresh_slab_status(slab)
    slab.updated_by = actor
    slab.save()

    loss = SlabLoss.objects.create(
        slab=slab,
        production_piece=production_piece,
        reservation=reservation,
        area=area,
        loss_reason=loss_reason,
        description=description,
        occurred_at=occurred_at or timezone.now(),
        created_by=actor,
    )

    _create_movement(
        slab=slab,
        movement_type=StockMovement.MovementType.LOSS,
        quantity_area=area,
        previous_available=prev_available,
        new_available=slab.available_area,
        reference_type="slab_loss",
        reference_id=loss.pk,
        description=description or loss.get_loss_reason_display(),
        actor=actor,
        occurred_at=occurred_at,
    )

    record_audit_event(
        request=request,
        user=actor,
        event_type="create",
        module="materials",
        action="slab_loss_registered",
        obj=loss,
    )
    return loss


@transaction.atomic
def transfer_slab(*, slab, destination, actor, notes="", request=None):
    if not user_has_permission(actor, "slabs.transfer"):
        raise PermissionDenied("Sem permissão para transferir chapa.")

    if destination is None:
        raise ValidationError("Destino obrigatório.")
    if not destination.is_active:
        raise ValidationError("Destino inativo.")
    if slab.status in {MaterialSlab.Status.CONSUMED, MaterialSlab.Status.DISCARDED}:
        raise ValidationError("Chapa consumida ou descartada não pode ser transferida.")

    slab = _lock_slab(slab.pk)
    origin = slab.stock_location
    if origin and origin.pk == destination.pk:
        raise ValidationError("Origem e destino devem ser diferentes.")

    prev_available = slab.available_area
    slab.stock_location = destination
    slab.updated_by = actor
    slab.save(update_fields=["stock_location", "updated_by", "updated_at"])

    _create_movement(
        slab=slab,
        movement_type=StockMovement.MovementType.TRANSFER,
        quantity_area=Decimal("0.0000"),
        previous_available=prev_available,
        new_available=slab.available_area,
        source_location=origin,
        destination_location=destination,
        reference_type="slab_transfer",
        reference_id=slab.pk,
        description=notes or "Transferência de localização",
        actor=actor,
    )

    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="materials",
        action="slab_transferred",
        obj=slab,
        metadata={"destination": destination.code},
    )
    return slab


@transaction.atomic
def block_slab(*, slab, reason, actor, request=None):
    if not user_has_permission(actor, "slabs.block"):
        raise PermissionDenied("Sem permissão para bloquear chapa.")
    if not reason.strip():
        raise ValidationError("Motivo obrigatório para bloqueio.")

    slab = _lock_slab(slab.pk)
    if slab.status == MaterialSlab.Status.BLOCKED:
        raise ValidationError("Chapa já está bloqueada.")

    prev_available = slab.available_area
    slab.status = MaterialSlab.Status.BLOCKED
    slab.block_reason = reason.strip()
    slab.updated_by = actor
    slab.save()

    _create_movement(
        slab=slab,
        movement_type=StockMovement.MovementType.BLOCK,
        quantity_area=Decimal("0.0000"),
        previous_available=prev_available,
        new_available=slab.available_area,
        reference_type="slab_block",
        reference_id=slab.pk,
        description=reason.strip(),
        actor=actor,
    )

    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="materials",
        action="slab_blocked",
        obj=slab,
        metadata={"reason": reason[:500]},
    )
    return slab


@transaction.atomic
def unblock_slab(*, slab, actor, notes="", request=None):
    if not user_has_permission(actor, "slabs.unblock"):
        raise PermissionDenied("Sem permissão para desbloquear chapa.")

    slab = _lock_slab(slab.pk)
    if slab.status != MaterialSlab.Status.BLOCKED:
        raise ValidationError("Chapa não está bloqueada.")

    prev_available = slab.available_area
    slab.block_reason = ""
    _refresh_slab_status(slab)
    if slab.status == MaterialSlab.Status.BLOCKED:
        slab.status = MaterialSlab.Status.AVAILABLE
    slab.updated_by = actor
    slab.save()

    _create_movement(
        slab=slab,
        movement_type=StockMovement.MovementType.UNBLOCK,
        quantity_area=Decimal("0.0000"),
        previous_available=prev_available,
        new_available=slab.available_area,
        reference_type="slab_unblock",
        reference_id=slab.pk,
        description=notes or "Desbloqueio de chapa",
        actor=actor,
    )

    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="materials",
        action="slab_unblocked",
        obj=slab,
    )
    return slab


@transaction.atomic
def adjust_slab_area(*, slab, new_available_area, reason, actor, request=None):
    if not user_has_permission(actor, "stock_adjustments.execute"):
        raise PermissionDenied("Sem permissão para ajustar estoque.")
    if not reason.strip():
        raise ValidationError("Justificativa obrigatória para ajuste.")
    if new_available_area < 0:
        raise ValidationError("Área disponível não pode ser negativa.")

    slab = _lock_slab(slab.pk)
    if new_available_area + slab.reserved_area + slab.consumed_area + slab.lost_area > slab.total_area:
        raise ValidationError("Ajuste resultaria em áreas inconsistentes.")

    prev = slab.available_area
    diff = new_available_area - prev
    slab.available_area = new_available_area
    _refresh_slab_status(slab)
    slab.updated_by = actor
    slab.save()

    movement_type = (
        StockMovement.MovementType.INVENTORY_INCREASE
        if diff >= 0
        else StockMovement.MovementType.INVENTORY_DECREASE
    )
    _create_movement(
        slab=slab,
        movement_type=movement_type,
        quantity_area=abs(diff),
        previous_available=prev,
        new_available=new_available_area,
        reference_type="slab_adjustment",
        reference_id=slab.pk,
        description=reason.strip(),
        actor=actor,
    )

    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="materials",
        action="slab_adjusted",
        obj=slab,
        metadata={"new_available": str(new_available_area), "reason": reason[:500]},
    )
    return slab


@transaction.atomic
def create_slab_remnant(
    *,
    origin_slab,
    origin_reservation=None,
    width,
    height,
    thickness,
    location,
    actor,
    notes="",
    request=None,
):
    if not user_has_permission(actor, "slab_remnants.create"):
        raise PermissionDenied("Sem permissão para registrar sobra.")

    area = calculate_area(width_mm=width, height_mm=height)
    code = next_slab_code()
    now = timezone.now()

    remnant = MaterialSlab.objects.create(
        material=origin_slab.material,
        slab_code=code,
        parent_slab=origin_slab,
        is_remnant=True,
        width_mm=width,
        height_mm=height,
        thickness_mm=thickness,
        total_area=area,
        available_area=area,
        supplier_ref=origin_slab.supplier_ref,
        supplier_name=origin_slab.supplier_name,
        stock_location=location,
        received_at=now,
        status=MaterialSlab.Status.AVAILABLE,
        notes=notes or f"Sobra de {origin_slab.slab_code}",
        created_by=actor,
        updated_by=actor,
    )

    _create_movement(
        slab=remnant,
        movement_type=StockMovement.MovementType.ENTRY,
        quantity_area=area,
        previous_available=Decimal("0.0000"),
        new_available=area,
        destination_location=location,
        reference_type="slab_remnant",
        reference_id=remnant.pk,
        description=notes or f"Sobra originada de {origin_slab.slab_code}",
        actor=actor,
    )

    record_audit_event(
        request=request,
        user=actor,
        event_type="create",
        module="materials",
        action="slab_remnant_created",
        obj=remnant,
        metadata={
            "origin": origin_slab.slab_code,
            "reservation": origin_reservation.pk if origin_reservation else None,
        },
    )
    return remnant


@transaction.atomic
def discard_remnant(*, remnant, reason, actor, request=None):
    if not user_has_permission(actor, "slab_remnants.update"):
        raise PermissionDenied("Sem permissão para descartar sobra.")
    if not reason.strip():
        raise ValidationError("Motivo obrigatório para descarte.")

    remnant = _lock_slab(remnant.pk)
    if not remnant.is_remnant:
        raise ValidationError("Registro não é uma sobra.")

    prev = remnant.available_area
    area = remnant.available_area
    remnant.available_area = Decimal("0.0000")
    remnant.status = MaterialSlab.Status.DISCARDED
    remnant.updated_by = actor
    remnant.save()

    _create_movement(
        slab=remnant,
        movement_type=StockMovement.MovementType.SCRAP,
        quantity_area=area,
        previous_available=prev,
        new_available=Decimal("0.0000"),
        reference_type="slab_remnant_discard",
        reference_id=remnant.pk,
        description=reason.strip(),
        actor=actor,
    )

    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="materials",
        action="slab_remnant_discarded",
        obj=remnant,
    )
    return remnant


@transaction.atomic
def start_inventory(*, inventory, actor, request=None):
    if not user_has_permission(actor, "stock_inventory.inventory"):
        raise PermissionDenied("Sem permissão para inventário.")

    if inventory.status != StockInventory.Status.DRAFT:
        raise ValidationError("Inventário não está em rascunho.")

    slabs = MaterialSlab.objects.filter(
        stock_location=inventory.location,
        is_active=True,
    ).exclude(status=MaterialSlab.Status.DISCARDED)

    for slab in slabs:
        StockInventoryItem.objects.get_or_create(
            inventory=inventory,
            slab=slab,
            defaults={"expected_area": slab.available_area},
        )

    inventory.status = StockInventory.Status.IN_PROGRESS
    inventory.started_at = timezone.now()
    inventory.updated_by = actor
    inventory.save()

    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="materials",
        action="stock_inventory_started",
        obj=inventory,
    )
    return inventory


@transaction.atomic
def complete_inventory(*, inventory, actor, apply_adjustments=False, request=None):
    if apply_adjustments and not user_has_permission(actor, "stock_inventory.approve_inventory"):
        raise PermissionDenied("Sem permissão para aprovar ajustes de inventário.")
    if inventory.status != StockInventory.Status.IN_PROGRESS:
        raise ValidationError("Inventário não está em andamento.")

    for item in inventory.items.select_related("slab"):
        if item.counted_area is None:
            continue
        item.difference_area = (item.counted_area - item.expected_area).quantize(
            Decimal("0.0001"),
        )
        item.status = StockInventoryItem.ItemStatus.COUNTED
        item.save(update_fields=["difference_area", "status"])

        if apply_adjustments and item.difference_area != 0:
            adjust_slab_area(
                slab=item.slab,
                new_available_area=item.counted_area,
                reason=f"Inventário {inventory.number}",
                actor=actor,
                request=request,
            )
            item.status = StockInventoryItem.ItemStatus.ADJUSTED
            item.save(update_fields=["status"])

    inventory.status = StockInventory.Status.COMPLETED
    inventory.completed_at = timezone.now()
    inventory.completed_by = actor
    inventory.updated_by = actor
    inventory.save()

    record_audit_event(
        request=request,
        user=actor,
        event_type="update",
        module="materials",
        action="stock_inventory_completed",
        obj=inventory,
        metadata={"adjustments": apply_adjustments},
    )
    return inventory


def next_inventory_number(*, year=None):
    year = year or timezone.now().year
    prefix = f"INV-{year}-"
    last = (
        StockInventory.objects.filter(number__startswith=prefix)
        .order_by("-number")
        .values_list("number", flat=True)
        .first()
    )
    if last:
        seq = int(last.split("-")[-1]) + 1
    else:
        seq = 1
    return f"{prefix}{seq:04d}"


def compatible_slabs_for_piece(*, piece, include_cost=False):
    qs = MaterialSlab.objects.filter(
        material=piece.material,
        is_active=True,
        available_area__gt=0,
    ).exclude(status__in=BLOCKED_STATUSES)

    if piece.material and piece.material.thickness_mm:
        qs = qs.filter(thickness_mm=piece.material.thickness_mm)

    qs = qs.select_related("material", "stock_location", "supplier_ref").order_by(
        "available_area",
        "slab_code",
    )
    return qs
