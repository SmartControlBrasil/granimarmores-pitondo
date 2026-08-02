from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db.models import F

from materials.models import MaterialSlab
from materials.stock_models import SlabReservation


class Command(BaseCommand):
    help = "Audita consistência de estoque de chapas."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--fix", action="store_true")
        parser.add_argument("--material", type=int)
        parser.add_argument("--location", type=int)
        parser.add_argument("--yes", action="store_true", help="Confirma correções com --fix")

    def handle(self, *args, **options):
        dry_run = options["dry_run"] or not options["fix"]
        qs = MaterialSlab.objects.all()
        if options["material"]:
            qs = qs.filter(material_id=options["material"])
        if options["location"]:
            qs = qs.filter(stock_location_id=options["location"])

        issues = []
        for slab in qs.iterator():
            total_parts = (
                slab.available_area + slab.reserved_area + slab.consumed_area + slab.lost_area
            )
            if total_parts > slab.total_area + Decimal("0.0001"):
                issues.append(f"Chapa {slab.slab_code}: soma de áreas excede total")
            if slab.available_area < 0:
                issues.append(f"Chapa {slab.slab_code}: área disponível negativa")
            if slab.status == MaterialSlab.Status.AVAILABLE and slab.consumed_area > 0:
                issues.append(f"Chapa {slab.slab_code}: consumida marcada disponível")
            if slab.status == MaterialSlab.Status.CONSUMED and slab.available_area > 0:
                issues.append(f"Chapa {slab.slab_code}: consumida com saldo disponível")

        orphan = SlabReservation.objects.filter(status=SlabReservation.Status.ACTIVE).exclude(
            production_piece__isnull=False,
        ).count()
        if orphan:
            issues.append(f"{orphan} reserva(s) órfã(s)")

        over_reserved = MaterialSlab.objects.filter(reserved_area__gt=F("total_area")).count()
        if over_reserved:
            issues.append(f"{over_reserved} chapa(s) com reserva acima do total")

        if not issues:
            self.stdout.write(self.style.SUCCESS("Nenhuma inconsistência encontrada."))
            return

        for issue in issues:
            self.stdout.write(self.style.WARNING(issue))

        if dry_run:
            self.stdout.write("Execução em dry-run. Use --fix --yes para correções conservadoras.")
            return

        if not options["yes"]:
            self.stdout.write(self.style.ERROR("Correção exige --yes."))
            return

        fixed = 0
        for slab in qs.filter(available_area__lt=0):
            slab.available_area = Decimal("0.0000")
            slab.save(update_fields=["available_area", "updated_at"])
            fixed += 1

        self.stdout.write(self.style.SUCCESS(f"Correções aplicadas: {fixed}"))
