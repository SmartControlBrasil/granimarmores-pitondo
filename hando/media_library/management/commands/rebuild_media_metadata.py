from pathlib import Path

from django.core.management.base import BaseCommand
from django.core.management.base import CommandError

from media_library.models import MediaAsset
from media_library.models import MediaType
from media_library.services.validation import compute_checksum
from media_library.services.validation import sniff_mime


class Command(BaseCommand):
    help = "Recalcula metadados de mídia (dimensões, tamanho, MIME, checksum)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--fix", action="store_true")
        parser.add_argument("--confirm", action="store_true", help="Obrigatório com --fix")

    def handle(self, *args, **options):
        dry_run = options["dry_run"] or not options["fix"]
        if options["fix"] and not options["confirm"]:
            raise CommandError("Use --fix --confirm para gravar alterações.")

        updated = 0
        for asset in MediaAsset.objects.exclude(file="").iterator():
            path = Path(asset.file.path)
            if not path.exists():
                self.stdout.write(f"Ausente: {asset.code}")
                continue
            with path.open("rb") as fh:
                checksum = compute_checksum(fh)
                mime = sniff_mime(fh, asset.original_filename or path.name)
            size = path.stat().st_size
            width = height = None
            if asset.media_type == MediaType.IMAGE:
                try:
                    from PIL import Image

                    with Image.open(path) as img:
                        width, height = img.size
                except Exception:
                    pass
            changes = []
            if asset.checksum != checksum:
                changes.append("checksum")
            if asset.mime_type != mime:
                changes.append("mime")
            if asset.file_size != size:
                changes.append("size")
            if width and (asset.width != width or asset.height != height):
                changes.append("dims")
            if not changes:
                continue
            self.stdout.write(f"{asset.code}: {', '.join(changes)}")
            if not dry_run:
                asset.checksum = checksum
                asset.mime_type = mime
                asset.file_size = size
                if width:
                    asset.width = width
                    asset.height = height
                asset.save(
                    update_fields=["checksum", "mime_type", "file_size", "width", "height", "updated_at"],
                )
            updated += 1
        mode = "dry-run" if dry_run else "aplicado"
        self.stdout.write(self.style.SUCCESS(f"Metadados ({mode}): {updated} arquivo(s)."))
