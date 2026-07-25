# ruff: noqa: E501, PERF401
import hashlib

from django.core.files.base import ContentFile

from audit.services import record_audit_event


def br_money(value):
    number = f"{value:,.2f}"
    return "R$ " + number.replace(",", "X").replace(".", ",").replace("X", ".")


def _escape_pdf_text(text):
    return (
        str(text).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")[:1000]
    )


def _pdf_bytes(lines):
    content = ["BT", "/F1 10 Tf", "50 800 Td"]
    first = True
    for line in lines:
        if not first:
            content.append("0 -16 Td")
        content.append(f"({_escape_pdf_text(line)}) Tj")
        first = False
    content.append("ET")
    stream = "\n".join(content).encode("latin-1", errors="replace")
    objects = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj",
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj",
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj",
        b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj",
        b"5 0 obj << /Length "
        + str(len(stream)).encode()
        + b" >> stream\n"
        + stream
        + b"\nendstream endobj",
    ]
    data = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(data))
        data.extend(obj + b"\n")
    xref = len(data)
    data.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        data.extend(f"{offset:010d} 00000 n \n".encode())
    data.extend(
        f"trailer << /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode(),
    )
    return bytes(data)


def generate_quote_pdf(*, version, actor=None, request=None):
    snapshot = version.snapshot
    lines = [
        "Granimármores Pitondo",
        f"Orçamento {snapshot.get('number')} - Versão {version.version_number}",
        f"Cliente: {snapshot.get('customer')}",
        f"Vendedor: {snapshot.get('salesperson')}",
        f"Validade: {snapshot.get('valid_until')}",
        "Itens:",
    ]
    for item in snapshot.get("items", []):
        lines.append(
            f"- {item.get('material_name') or item.get('description')} | {item.get('quantity')} {item.get('unit')} | {item.get('subtotal')}",
        )
    lines.extend(
        [
            f"Subtotal: {br_money(version.subtotal)}",
            f"Desconto: {br_money(version.discount_total)}",
            f"Impostos: {br_money(version.tax_total)}",
            f"Total: {br_money(version.grand_total)}",
            f"Condições: {snapshot.get('payment_terms')}",
            f"Observações: {snapshot.get('customer_notes')}",
            "PDF gerado a partir de snapshot imutável da versão.",
        ],
    )
    data = _pdf_bytes(lines)
    digest = hashlib.sha256(data).hexdigest()
    filename = f"{snapshot.get('number')}-v{version.version_number}.pdf"
    version.pdf_file.save(filename, ContentFile(data), save=False)
    version.pdf_hash = digest
    version.save_base(raw=True, update_fields=["pdf_file", "pdf_hash"])
    record_audit_event(
        request=request,
        user=actor,
        event_type="print",
        module="quotes",
        action="quote_pdf_generated",
        obj=version.quote,
        metadata={
            "quote_number": version.quote.number,
            "version": version.version_number,
            "pdf_hash": digest,
        },
    )
    return version


def record_pdf_download(*, version, actor=None, request=None):
    record_audit_event(
        request=request,
        user=actor,
        event_type="print",
        module="quotes",
        action="quote_pdf_downloaded",
        obj=version.quote,
        metadata={
            "quote_number": version.quote.number,
            "version": version.version_number,
        },
    )
