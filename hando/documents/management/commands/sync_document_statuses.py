from django.core.management.base import BaseCommand

from documents.services.lifecycle import sync_document_statuses


class Command(BaseCommand):
    help = "Sincroniza status operacionais de documentos (expiração). Idempotente."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        dry = options["dry_run"]
        report = sync_document_statuses(dry_run=dry)
        prefix = "Dry-run: " if dry else ""
        self.stdout.write(f"{prefix}a expirar agora: {len(report['to_expire'])}")
        self.stdout.write(f"{prefix}vencendo em breve: {len(report['expiring_soon'])}")
        for number in report["to_expire"][:50]:
            self.stdout.write(f"  - {number}")
        if dry:
            self.stdout.write(self.style.WARNING("Dry-run: nenhum status alterado."))
        else:
            self.stdout.write(
                self.style.SUCCESS(f"Atualizados para expired: {report['updated']}"),
            )
