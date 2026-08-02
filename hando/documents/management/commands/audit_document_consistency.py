import hashlib

from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_date
from django.utils import timezone

from documents.models import AcceptanceStatus
from documents.models import DocumentStatus
from documents.models import ManagedDocument
from documents.models import TemplateStatus
from documents.models import VersionStatus


class Command(BaseCommand):
    help = "Audita consistência documental (somente relatório)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--start", type=str, default="")
        parser.add_argument("--end", type=str, default="")
        parser.add_argument("--status", type=str, default="")
        parser.add_argument("--type", type=str, default="")

    def handle(self, *args, **options):
        qs = ManagedDocument.objects.select_related(
            "current_version",
            "template",
            "document_type",
        ).prefetch_related("versions", "acceptances", "signatures", "renewals")
        if options["start"]:
            qs = qs.filter(created_at__date__gte=parse_date(options["start"]))
        if options["end"]:
            qs = qs.filter(created_at__date__lte=parse_date(options["end"]))
        if options["status"]:
            qs = qs.filter(status=options["status"])
        if options["type"]:
            qs = qs.filter(document_type__code=options["type"])

        issues = []
        today = timezone.localdate()
        seen_renewals = set()

        for doc in qs.iterator(chunk_size=100):
            version = doc.current_version
            if doc.status == DocumentStatus.ACTIVE:
                if not version or version.status != VersionStatus.APPROVED:
                    issues.append(f"{doc.number}: ativo sem versão aprovada")
                if doc.expiration_date and doc.expiration_date < today:
                    issues.append(f"{doc.number}: ativo com vencimento passado")

            for acc in doc.acceptances.all():
                if acc.status == AcceptanceStatus.ACCEPTED:
                    if acc.document_version.status != VersionStatus.APPROVED:
                        issues.append(f"{doc.number}: aceite em versão não aprovada")
                if (
                    acc.status == AcceptanceStatus.REVOKED
                    and doc.status == DocumentStatus.ACTIVE
                ):
                    issues.append(f"{doc.number}: aceite revogado com documento ativo")

            for sig in doc.signatures.all():
                if not sig.document_version_id:
                    issues.append(f"{doc.number}: assinatura sem versão")

            if version:
                approved_ids = list(
                    doc.versions.filter(status=VersionStatus.APPROVED)
                    .order_by("-version_number")
                    .values_list("id", flat=True)[:1],
                )
                if approved_ids and version.status == VersionStatus.APPROVED:
                    if version.id != approved_ids[0] and doc.status not in {
                        DocumentStatus.DRAFT,
                        DocumentStatus.UNDER_REVIEW,
                    }:
                        issues.append(f"{doc.number}: versão atual divergente")
                content = version.rendered_content or version.content or ""
                if content:
                    expected = hashlib.sha256(content.encode("utf-8")).hexdigest()
                    if version.checksum and version.checksum != expected:
                        if not version.media_asset_id:
                            issues.append(f"{doc.number}: checksum divergente")
                if version.media_asset_id:
                    asset = version.media_asset
                    if asset and getattr(asset, "file", None):
                        try:
                            if not asset.file or not asset.file.name:
                                issues.append(f"{doc.number}: arquivo ausente")
                        except Exception:
                            issues.append(f"{doc.number}: arquivo ausente")

            if doc.template_id and doc.template:
                if not doc.template.is_active or doc.template.status == TemplateStatus.INACTIVE:
                    issues.append(f"{doc.number}: modelo inativo em uso")

            if doc.renewed_from_id:
                chain = []
                current = doc
                while current and current.renewed_from_id:
                    if current.pk in chain:
                        issues.append(f"{doc.number}: renovação circular")
                        break
                    chain.append(current.pk)
                    if current.pk in seen_renewals:
                        break
                    seen_renewals.add(current.pk)
                    current = current.renewed_from

        self.stdout.write(f"Auditoria documental — {timezone.now():%Y-%m-%d %H:%M}")
        self.stdout.write(f"Documentos analisados: {qs.count()}")
        if options["dry_run"]:
            self.stdout.write("Dry-run: nenhuma correção automática.")
        if not issues:
            self.stdout.write(self.style.SUCCESS("Nenhuma inconsistência encontrada."))
        else:
            self.stdout.write(self.style.WARNING(f"{len(issues)} inconsistência(s):"))
            for issue in issues[:200]:
                self.stdout.write(f"- {issue}")
