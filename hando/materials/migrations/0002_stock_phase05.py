# Generated manually for Fase Admin 05

import django.db.models.deletion
import django.utils.timezone
import materials.models
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


def migrate_slab_data(apps, schema_editor):
    MaterialSlab = apps.get_model("materials", "MaterialSlab")
    status_map = {
        "available": "available",
        "reserved": "partially_reserved",
        "used": "consumed",
        "damaged": "damaged",
        "discarded": "discarded",
    }
    for slab in MaterialSlab.objects.all():
        area = getattr(slab, "total_area", None) or getattr(slab, "area_m2", None) or Decimal("0")
        if not slab.total_area:
            slab.total_area = area
        if not slab.available_area:
            if slab.status in {"reserved", "used", "consumed"}:
                slab.available_area = Decimal("0.0000")
            else:
                slab.available_area = area
        if slab.status in status_map:
            slab.status = status_map[slab.status]
        slab.save()


class Migration(migrations.Migration):

    dependencies = [
        ("materials", "0001_initial"),
        ("production", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="MaterialSupplier",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_active", models.BooleanField(default=True)),
                ("deactivated_at", models.DateTimeField(blank=True, null=True)),
                ("name", models.CharField(max_length=180)),
                ("trade_name", models.CharField(blank=True, max_length=180)),
                ("document", models.CharField(blank=True, max_length=20)),
                ("contact_name", models.CharField(blank=True, max_length=120)),
                ("phone", models.CharField(blank=True, max_length=40)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("city", models.CharField(blank=True, max_length=80)),
                ("state", models.CharField(blank=True, max_length=2)),
                ("notes", models.TextField(blank=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_%(class)s_set", to=settings.AUTH_USER_MODEL)),
                ("deactivated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="deactivated_%(class)s_set", to=settings.AUTH_USER_MODEL)),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="updated_%(class)s_set", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "fornecedor de material",
                "verbose_name_plural": "fornecedores de material",
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="SlabSequence",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("year", models.PositiveIntegerField(unique=True)),
                ("last_number", models.PositiveIntegerField(default=0)),
            ],
            options={
                "verbose_name": "sequência de chapas",
                "verbose_name_plural": "sequências de chapas",
            },
        ),
        migrations.CreateModel(
            name="StockLocation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_active", models.BooleanField(default=True)),
                ("deactivated_at", models.DateTimeField(blank=True, null=True)),
                ("name", models.CharField(max_length=160)),
                ("code", models.CharField(max_length=40, unique=True)),
                ("description", models.TextField(blank=True)),
                ("location_type", models.CharField(choices=[("warehouse", "Galpão"), ("yard", "Pátio"), ("rack", "Cavalete"), ("shelf", "Prateleira"), ("production_area", "Área de produção"), ("quarantine", "Quarentena"), ("scrap", "Sucata"), ("other", "Outro")], default="warehouse", max_length=30)),
                ("display_order", models.PositiveIntegerField(default=0)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_%(class)s_set", to=settings.AUTH_USER_MODEL)),
                ("deactivated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="deactivated_%(class)s_set", to=settings.AUTH_USER_MODEL)),
                ("parent", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="children", to="materials.stocklocation")),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="updated_%(class)s_set", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "localização de estoque",
                "verbose_name_plural": "localizações de estoque",
                "ordering": ["display_order", "name"],
            },
        ),
        migrations.RenameField(
            model_name="materialslab",
            old_name="supplier",
            new_name="supplier_name",
        ),
        migrations.RenameField(
            model_name="materialslab",
            old_name="location",
            new_name="location_text",
        ),
        migrations.RenameField(
            model_name="materialslab",
            old_name="area_m2",
            new_name="total_area",
        ),
        migrations.AddField(
            model_name="materialslab",
            name="available_area",
            field=models.DecimalField(decimal_places=4, default=Decimal("0.0000"), max_digits=10),
        ),
        migrations.AddField(
            model_name="materialslab",
            name="reserved_area",
            field=models.DecimalField(decimal_places=4, default=Decimal("0.0000"), max_digits=10),
        ),
        migrations.AddField(
            model_name="materialslab",
            name="consumed_area",
            field=models.DecimalField(decimal_places=4, default=Decimal("0.0000"), max_digits=10),
        ),
        migrations.AddField(
            model_name="materialslab",
            name="lost_area",
            field=models.DecimalField(decimal_places=4, default=Decimal("0.0000"), max_digits=10),
        ),
        migrations.AddField(
            model_name="materialslab",
            name="external_code",
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name="materialslab",
            name="batch",
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name="materialslab",
            name="bundle",
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name="materialslab",
            name="serial_number",
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name="materialslab",
            name="is_remnant",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="materialslab",
            name="rack",
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name="materialslab",
            name="position",
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name="materialslab",
            name="received_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="materialslab",
            name="block_reason",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="materialslab",
            name="parent_slab",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="remnants", to="materials.materialslab"),
        ),
        migrations.AddField(
            model_name="materialslab",
            name="supplier_ref",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="slabs", to="materials.materialsupplier"),
        ),
        migrations.AddField(
            model_name="materialslab",
            name="stock_location",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="slabs", to="materials.stocklocation"),
        ),
        migrations.AlterField(
            model_name="materialslab",
            name="status",
            field=models.CharField(choices=[("available", "Disponível"), ("partially_reserved", "Parcialmente reservada"), ("fully_reserved", "Totalmente reservada"), ("in_use", "Em uso"), ("partially_consumed", "Parcialmente consumida"), ("consumed", "Consumida"), ("blocked", "Bloqueada"), ("damaged", "Danificada"), ("discarded", "Descartada"), ("inventory_adjustment", "Ajuste de inventário"), ("reserved", "Reservada (legado)"), ("used", "Utilizada (legado)")], default="available", max_length=30),
        ),
        migrations.RunPython(migrate_slab_data, migrations.RunPython.noop),
        migrations.CreateModel(
            name="SlabReservation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("reserved_area", models.DecimalField(decimal_places=4, max_digits=10, validators=[materials.models.validate_non_negative])),
                ("consumed_area", models.DecimalField(decimal_places=4, default=Decimal("0.0000"), max_digits=10, validators=[materials.models.validate_non_negative])),
                ("lost_area", models.DecimalField(decimal_places=4, default=Decimal("0.0000"), max_digits=10, validators=[materials.models.validate_non_negative])),
                ("status", models.CharField(choices=[("active", "Ativa"), ("released", "Liberada"), ("partially_consumed", "Parcialmente consumida"), ("consumed", "Consumida"), ("cancelled", "Cancelada")], default="active", max_length=30)),
                ("reserved_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("released_at", models.DateTimeField(blank=True, null=True)),
                ("consumed_at", models.DateTimeField(blank=True, null=True)),
                ("notes", models.TextField(blank=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_%(class)s_set", to=settings.AUTH_USER_MODEL)),
                ("production_order", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="slab_reservations", to="production.productionorder")),
                ("production_piece", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="slab_reservations", to="production.productionpiece")),
                ("released_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="slab_reservations_released", to=settings.AUTH_USER_MODEL)),
                ("slab", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="reservations", to="materials.materialslab")),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="updated_%(class)s_set", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-reserved_at"]},
        ),
        migrations.CreateModel(
            name="StockInventory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("number", models.CharField(max_length=30, unique=True)),
                ("status", models.CharField(choices=[("draft", "Rascunho"), ("in_progress", "Em andamento"), ("completed", "Concluído"), ("cancelled", "Cancelado")], default="draft", max_length=20)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("notes", models.TextField(blank=True)),
                ("completed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="stock_inventories_completed", to=settings.AUTH_USER_MODEL)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_%(class)s_set", to=settings.AUTH_USER_MODEL)),
                ("location", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="inventories", to="materials.stocklocation")),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="updated_%(class)s_set", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "inventário de estoque",
                "verbose_name_plural": "inventários de estoque",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="StockMovement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("movement_type", models.CharField(choices=[("entry", "Entrada"), ("transfer", "Transferência"), ("reservation", "Reserva"), ("reservation_release", "Liberação de reserva"), ("consumption", "Consumo"), ("loss", "Perda"), ("scrap", "Descarte"), ("inventory_increase", "Ajuste inventário (+)"), ("inventory_decrease", "Ajuste inventário (-)"), ("return_to_stock", "Retorno ao estoque"), ("block", "Bloqueio"), ("unblock", "Desbloqueio")], max_length=30)),
                ("quantity_area", models.DecimalField(decimal_places=4, max_digits=10)),
                ("previous_available_area", models.DecimalField(decimal_places=4, max_digits=10)),
                ("new_available_area", models.DecimalField(decimal_places=4, max_digits=10)),
                ("reference_type", models.CharField(blank=True, max_length=60)),
                ("reference_id", models.CharField(blank=True, max_length=60)),
                ("description", models.TextField(blank=True)),
                ("occurred_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="stock_movements_created", to=settings.AUTH_USER_MODEL)),
                ("destination_location", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="movements_to", to="materials.stocklocation")),
                ("slab", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="movements", to="materials.materialslab")),
                ("source_location", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="movements_from", to="materials.stocklocation")),
            ],
            options={"ordering": ["-occurred_at", "-pk"]},
        ),
        migrations.CreateModel(
            name="SlabLoss",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("area", models.DecimalField(decimal_places=4, max_digits=10, validators=[materials.models.validate_non_negative])),
                ("loss_reason", models.CharField(choices=[("cutting_loss", "Perda de corte"), ("breakage", "Quebra"), ("defect", "Defeito"), ("measurement_error", "Erro de medição"), ("handling_damage", "Avaria no manuseio"), ("quality_rejection", "Reprovação de qualidade"), ("unusable_remnant", "Sobra inutilizável"), ("other", "Outro")], max_length=40)),
                ("description", models.TextField(blank=True)),
                ("occurred_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="slab_losses_created", to=settings.AUTH_USER_MODEL)),
                ("production_piece", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="slab_losses", to="production.productionpiece")),
                ("reservation", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="losses", to="materials.slabreservation")),
                ("slab", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="losses", to="materials.materialslab")),
            ],
            options={"ordering": ["-occurred_at"]},
        ),
        migrations.CreateModel(
            name="StockInventoryItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("expected_area", models.DecimalField(decimal_places=4, max_digits=10)),
                ("counted_area", models.DecimalField(blank=True, decimal_places=4, max_digits=10, null=True)),
                ("difference_area", models.DecimalField(blank=True, decimal_places=4, max_digits=10, null=True)),
                ("status", models.CharField(choices=[("pending", "Pendente"), ("counted", "Contado"), ("adjusted", "Ajustado"), ("skipped", "Ignorado")], default="pending", max_length=20)),
                ("notes", models.TextField(blank=True)),
                ("counted_at", models.DateTimeField(blank=True, null=True)),
                ("counted_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="inventory_items_counted", to=settings.AUTH_USER_MODEL)),
                ("inventory", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="materials.stockinventory")),
                ("slab", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="inventory_items", to="materials.materialslab")),
            ],
            options={"ordering": ["slab__slab_code"]},
        ),
        migrations.AddIndex(
            model_name="stockmovement",
            index=models.Index(fields=["reference_type", "reference_id"], name="materials_s_referen_6a0fbd_idx"),
        ),
        migrations.AddIndex(
            model_name="stockmovement",
            index=models.Index(fields=["slab", "movement_type"], name="materials_s_slab_id_8ea0d1_idx"),
        ),
        migrations.AddConstraint(
            model_name="stockmovement",
            constraint=models.UniqueConstraint(condition=models.Q(("reference_type__gt", "")), fields=("movement_type", "reference_type", "reference_id"), name="unique_stock_movement_reference"),
        ),
        migrations.AddConstraint(
            model_name="slabreservation",
            constraint=models.UniqueConstraint(condition=models.Q(("status", "active")), fields=("slab", "production_piece"), name="unique_active_slab_piece_reservation"),
        ),
        migrations.AddConstraint(
            model_name="stockinventoryitem",
            constraint=models.UniqueConstraint(fields=("inventory", "slab"), name="unique_inventory_slab"),
        ),
    ]
