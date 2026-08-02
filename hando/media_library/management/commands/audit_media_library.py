from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_date

from media_library.models import MediaAsset
from media_library.models import MediaStatus
from media_library.models import MediaVisibility
from media_library.services.consent import evaluate_media_consent
from media_library.services.validation import compute_checksum


class Command(BaseCommand):
    help = "Audita inconsistências da biblioteca de mídia (somente relatório)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", default=True)
        parser.add_argument("--status", type=str, default="")
        parser.add_argument("--customer", type=int, default=0)
        parser.add_argument("--older-than", type=str, default="")

    def handle(self, *args, **options):
        qs = MediaAsset.objects.all()
        if options["status"]:
            qs = qs.filter(status=options["status"])
        if options["customer"]:
            qs = qs.filter(customer_id=options["customer"])
        if options["older_than"]:
            qs = qs.filter(uploaded_at__date__lte=parse_date(options["older_than"]))

        findings = []
        missing_files = orphan_meta = checksum_mismatch = 0
        public_bad = revoked_portfolio = no_category = no_link = invalid_mime = 0
        dups = qs.filter(duplicate_of__isnull=False).count()

        for asset in qs.iterator():
            path = Path(asset.file.path) if asset.file else None
            if not path or not path.exists():
                missing_files += 1
                continue
            if asset.file_size and path.stat().st_size != asset.file_size:
                orphan_meta += 1
            try:
                with path.open("rb") as fh:
                    digest = compute_checksum(fh)
                if asset.checksum and digest != asset.checksum:
                    checksum_mismatch += 1
            except Exception:
                invalid_mime += 1
            if not asset.category_id and asset.status != MediaStatus.DELETED:
                no_category += 1
            if not any(
                [
                    asset.customer_id,
                    asset.sales_order_id,
                    asset.production_order_id,
                    asset.material_id,
                    asset.after_sales_case_id,
                ],
            ):
                no_link += 1
            if asset.visibility == MediaVisibility.PUBLIC_APPROVED:
                if evaluate_media_consent(asset) in {"missing", "denied", "revoked", "pending"}:
                    public_bad += 1
            if asset.is_portfolio_approved and evaluate_media_consent(asset) == "revoked":
                revoked_portfolio += 1

        for label, value in [
            ("arquivos ausentes", missing_files),
            ("metadados de tamanho divergentes", orphan_meta),
            ("checksum divergente", checksum_mismatch),
            ("MIME/leitura inválida", invalid_mime),
            ("sem categoria", no_category),
            ("sem vínculo", no_link),
            ("públicas sem consentimento", public_bad),
            ("portfólio com consentimento revogado", revoked_portfolio),
            ("duplicidades registradas", dups),
        ]:
            if value:
                findings.append(f"{value} {label}")

        if not findings:
            self.stdout.write(self.style.SUCCESS("Nenhuma inconsistência encontrada."))
            return
        self.stdout.write(self.style.WARNING("Auditoria de mídia (dry-run — sem correção):"))
        for item in findings:
            self.stdout.write(f" - {item}")
