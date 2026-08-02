# ruff: noqa: EM101, TRY003
import hashlib
import imghdr
import mimetypes
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.text import get_valid_filename


BANNED_EXTENSIONS = {
    ".exe",
    ".sh",
    ".php",
    ".py",
    ".js",
    ".bat",
    ".cmd",
    ".jar",
    ".scr",
    ".com",
    ".msi",
    ".dll",
    ".vbs",
    ".ps1",
}

IMAGE_SIGNATURES = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"RIFF": "image/webp",  # refined below
    b"%PDF": "application/pdf",
}


def _max_image_bytes():
    return int(getattr(settings, "MEDIA_LIBRARY_MAX_IMAGE_SIZE_MB", 10)) * 1024 * 1024


def _max_document_bytes():
    return int(getattr(settings, "MEDIA_LIBRARY_MAX_DOCUMENT_SIZE_MB", 20)) * 1024 * 1024


def allowed_image_types():
    return set(
        getattr(
            settings,
            "MEDIA_LIBRARY_ALLOWED_IMAGE_TYPES",
            ["image/jpeg", "image/png", "image/webp"],
        ),
    )


def allowed_document_types():
    return set(
        getattr(
            settings,
            "MEDIA_LIBRARY_ALLOWED_DOCUMENT_TYPES",
            ["application/pdf"],
        ),
    )


def safe_filename(name: str) -> str:
    base = get_valid_filename(Path(name).name)
    if not base:
        base = "arquivo"
    return base[:180]


def compute_checksum(file_obj) -> str:
    digest = hashlib.sha256()
    pos = file_obj.tell() if hasattr(file_obj, "tell") else None
    file_obj.seek(0)
    for chunk in iter(lambda: file_obj.read(1024 * 1024), b""):
        digest.update(chunk)
    if pos is not None:
        file_obj.seek(pos)
    else:
        file_obj.seek(0)
    return digest.hexdigest()


def sniff_mime(file_obj, filename: str) -> str:
    file_obj.seek(0)
    head = file_obj.read(32)
    file_obj.seek(0)
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith(b"RIFF") and b"WEBP" in head[:16]:
        return "image/webp"
    if head.startswith(b"%PDF"):
        return "application/pdf"
    guessed, _ = mimetypes.guess_type(filename)
    return guessed or "application/octet-stream"


def validate_upload_file(uploaded_file):
    original = uploaded_file.name or "arquivo"
    stored = safe_filename(original)
    ext = Path(stored).suffix.lower()
    if ext in BANNED_EXTENSIONS:
        raise ValidationError("Tipo de arquivo não permitido.")

    mime = sniff_mime(uploaded_file, stored)
    size = getattr(uploaded_file, "size", 0) or 0
    media_type = "other"
    width = height = None

    if mime in allowed_image_types() or ext in {".jpg", ".jpeg", ".png", ".webp"}:
        if mime not in allowed_image_types():
            raise ValidationError("MIME de imagem não permitido.")
        if size > _max_image_bytes():
            raise ValidationError("Imagem excede o tamanho máximo configurado.")
        uploaded_file.seek(0)
        kind = imghdr.what(None, h=uploaded_file.read(512))
        uploaded_file.seek(0)
        if kind not in {"jpeg", "png", "webp"} and mime != "image/webp":
            # imghdr may not detect webp; Pillow validates below
            if mime not in allowed_image_types():
                raise ValidationError("Arquivo de imagem inválido.")
        try:
            from PIL import Image

            uploaded_file.seek(0)
            with Image.open(uploaded_file) as img:
                img.verify()
            uploaded_file.seek(0)
            with Image.open(uploaded_file) as img:
                width, height = img.size
            uploaded_file.seek(0)
        except Exception as exc:
            raise ValidationError("Imagem inválida ou corrompida.") from exc
        media_type = "image"
    elif mime in allowed_document_types() or ext == ".pdf":
        if mime not in allowed_document_types():
            raise ValidationError("MIME de documento não permitido.")
        if size > _max_document_bytes():
            raise ValidationError("Documento excede o tamanho máximo configurado.")
        uploaded_file.seek(0)
        if not uploaded_file.read(4).startswith(b"%PDF"):
            raise ValidationError("PDF inválido.")
        uploaded_file.seek(0)
        media_type = "document"
    else:
        raise ValidationError("Tipo de arquivo não suportado nesta fase.")

    checksum = compute_checksum(uploaded_file)
    uploaded_file.seek(0)
    return {
        "original_filename": original[:255],
        "stored_filename": stored,
        "mime_type": mime,
        "file_size": size,
        "checksum": checksum,
        "media_type": media_type,
        "width": width,
        "height": height,
    }


def generate_thumbnail_bytes(uploaded_file, max_size=(480, 480)):
    try:
        from PIL import Image

        uploaded_file.seek(0)
        with Image.open(uploaded_file) as img:
            img = img.convert("RGB") if img.mode not in ("RGB", "L") else img
            img.thumbnail(max_size)
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=85)
            buf.seek(0)
            uploaded_file.seek(0)
            return buf
    except Exception:
        if hasattr(uploaded_file, "seek"):
            uploaded_file.seek(0)
        return None
