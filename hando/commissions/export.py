import csv
import io
from decimal import Decimal

from django.http import HttpResponse

from audit.services import record_audit_event


def sanitize_csv_cell(value):
    if value is None:
        return ""
    if isinstance(value, Decimal):
        text = format(value, "f")
    else:
        text = str(value)
    if text and text[0] in {"=", "+", "-", "@", "\t", "\r"}:
        return "'" + text
    return text


def build_csv_response(*, filename, headers, rows, request=None, export_key=""):
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", lineterminator="\n")
    writer.writerow([sanitize_csv_cell(h) for h in headers])
    for row in rows:
        writer.writerow([sanitize_csv_cell(c) for c in row])
    response = HttpResponse("\ufeff" + buffer.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    if request is not None:
        record_audit_event(
            request=request,
            event_type="export",
            module="commissions",
            action="export_csv",
            description=f"Exportação comissões: {export_key or filename}",
            metadata={"filename": filename, "rows": len(rows)},
        )
    return response
