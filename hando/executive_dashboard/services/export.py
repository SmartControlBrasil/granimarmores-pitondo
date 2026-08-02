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
        writer.writerow([sanitize_csv_cell(cell) for cell in row])
    content = "\ufeff" + buffer.getvalue()
    response = HttpResponse(content, content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    if request is not None:
        record_audit_event(
            request=request,
            event_type="export",
            module="executive_dashboard",
            action="export_csv",
            description=f"Exportação CSV executiva: {export_key or filename}",
            metadata={"filename": filename, "rows": len(rows)},
        )
    return response


def salespeople_csv_rows(rows):
    headers = [
        "Vendedor",
        "Leads recebidos",
        "Leads atendidos",
        "Orçamentos enviados",
        "Vendas aceitas",
        "Valor aprovado",
        "Ticket médio",
        "Conversão %",
        "Score",
        "Posição",
    ]
    data = []
    for row in rows:
        data.append(
            [
                row["salesperson"].display_name,
                row["leads_received"],
                row["leads_attended"],
                row["quotes_sent"],
                row["closed_sales"],
                row["approved_value"],
                row["ticket_average"],
                row["conversion_rate"],
                row["total_score"],
                row.get("position") or "",
            ],
        )
    return headers, data


def risks_csv_rows(rows):
    headers = ["Pedido", "Cliente", "Nível", "Score", "Motivos"]
    data = [
        [
            row["order"].number,
            row["order"].customer.name if row["order"].customer_id else "",
            row["level"],
            row["score"],
            "; ".join(row["reasons"]),
        ]
        for row in rows
    ]
    return headers, data


def production_csv_rows(metrics):
    headers = ["Indicador", "Valor"]
    keys = [
        ("orders_technical_review", "Aguardando revisão"),
        ("orders_awaiting_measurement", "Aguardando medição"),
        ("orders_ready_for_production", "Prontos para produção"),
        ("production_open", "Ordens abertas"),
        ("production_in_progress", "Em andamento"),
        ("production_on_hold", "Pausadas"),
        ("orders_overdue", "Pedidos atrasados"),
        ("rework_count", "Retrabalhos"),
        ("ready_for_delivery", "Prontos para entrega"),
        ("completed_in_period", "Concluídos no período"),
    ]
    data = [[label, metrics.get(key, 0)] for key, label in keys]
    return headers, data


def stock_csv_rows(metrics):
    headers = ["Indicador", "Valor"]
    keys = [
        ("available_slabs", "Chapas disponíveis"),
        ("total_available_area", "Área disponível"),
        ("total_reserved_area", "Área reservada"),
        ("total_consumed_area", "Área consumida"),
        ("total_lost_area", "Área perdida"),
        ("active_reservations", "Reservas ativas"),
        ("blocked_slabs", "Chapas bloqueadas"),
        ("no_location", "Sem localização"),
        ("consumed_period", "Consumo no período"),
        ("lost_period", "Perdas no período"),
    ]
    data = [[label, metrics.get(key, 0)] for key, label in keys]
    return headers, data


def after_sales_csv_rows(metrics):
    headers = ["Indicador", "Valor"]
    keys = [
        ("open_cases", "Casos abertos"),
        ("new_period", "Novos no período"),
        ("critical", "Críticos"),
        ("no_owner", "Sem responsável"),
        ("resolved", "Resolvidos"),
        ("closed", "Fechados"),
        ("avg_satisfaction", "Satisfação média"),
        ("overdue_pending", "Pendências vencidas"),
    ]
    data = [[label, metrics.get(key, 0)] for key, label in keys]
    return headers, data


def sales_csv_rows(commercial):
    headers = ["Indicador", "Valor"]
    keys = [
        ("leads_received", "Leads recebidos"),
        ("quotes_sent", "Orçamentos enviados"),
        ("quotes_accepted", "Vendas aceitas"),
        ("approved_value", "Valor aprovado"),
        ("potential_value", "Valor potencial"),
        ("ticket_average", "Ticket médio"),
        ("conversion_rate", "Conversão %"),
        ("quotes_refused", "Orçamentos recusados"),
        ("quotes_expired", "Orçamentos expirados"),
    ]
    data = [[label, commercial.get(key, 0)] for key, label in keys]
    return headers, data
