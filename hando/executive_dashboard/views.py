# ruff: noqa: PLR0913
import json
from decimal import Decimal
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

from access_control.services.authorization import render_403
from access_control.services.authorization import user_has_permission
from audit.services import record_audit_event
from executive_dashboard.forms import ExecutiveFilterForm
from executive_dashboard.services.aggregation import build_executive_dashboard
from executive_dashboard.services.export import after_sales_csv_rows
from executive_dashboard.services.export import build_csv_response
from executive_dashboard.services.export import production_csv_rows
from executive_dashboard.services.export import risks_csv_rows
from executive_dashboard.services.export import sales_csv_rows
from executive_dashboard.services.export import salespeople_csv_rows
from executive_dashboard.services.export import stock_csv_rows
from executive_dashboard.services.periods import PERIOD_CHOICES
from executive_dashboard.services.periods import parse_executive_period
from executive_dashboard.services.periods import parse_filters


class DecimalEncoder(DjangoJSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        return super().default(o)


EXECUTIVE_ACCESS_CODES = [
    "executive_dashboard.view",
    "executive_dashboard.view_commercial",
    "executive_dashboard.view_production",
    "executive_dashboard.view_stock",
    "executive_dashboard.view_schedule",
    "executive_dashboard.view_after_sales",
    "executive_dashboard.view_quality",
    "executive_dashboard.view_audit",
    "executive_dashboard.view_finance",
    "executive_dashboard.view_purchasing",
]


def can_access_executive(user):
    return any(user_has_permission(user, code) for code in EXECUTIVE_ACCESS_CODES)


def require_executive_access(extra_permission=None):
    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not can_access_executive(request.user):
                return render_403(request)
            if extra_permission and not user_has_permission(request.user, extra_permission):
                if not user_has_permission(request.user, "executive_dashboard.view"):
                    return render_403(request)
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def _build_context(request):
    start, end, period, previous = parse_executive_period(request)
    filters = parse_filters(request)
    for key in (
        "salesperson",
        "commercial_source",
        "project_type",
        "material",
        "production_responsible",
        "production_stage",
    ):
        if filters.get(key) and str(filters[key]).isdigit():
            filters[key] = int(filters[key])
        elif filters.get(key) in ("", None):
            filters[key] = None

    data = build_executive_dashboard(
        user=request.user,
        start=start,
        end=end,
        previous_period=previous,
        filters=filters,
    )
    form = ExecutiveFilterForm(request.GET or None)
    charts_json = json.dumps(data.get("charts") or {}, cls=DecimalEncoder)
    return {
        "page_title": "Painel da Diretoria",
        "period": period,
        "period_choices": PERIOD_CHOICES,
        "start": start,
        "end": end,
        "previous_period": previous,
        "filters": filters,
        "filter_form": form,
        "querystring": request.GET.urlencode(),
        "charts_json": charts_json,
        "generated_at": timezone.now(),
        "can_export": user_has_permission(request.user, "executive_dashboard.export")
        or user_has_permission(request.user, "executive_dashboard.view"),
        "can_print": user_has_permission(request.user, "executive_dashboard.print")
        or user_has_permission(request.user, "executive_dashboard.view"),
        **data,
    }


@require_executive_access()
def dashboard(request):
    try:
        context = _build_context(request)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc))
        return redirect(reverse("executive_dashboard:dashboard") + "?period=30d")

    record_audit_event(
        request=request,
        event_type="view",
        module="executive_dashboard",
        action="view_dashboard",
        description="Acesso ao Painel da Diretoria",
        metadata={"period": context["period"]},
    )
    if context.get("can_view_stock_costs") and context.get("stock"):
        record_audit_event(
            request=request,
            event_type="view",
            module="executive_dashboard",
            action="view_stock_costs",
            description="Consulta de custos de estoque no painel executivo",
        )
    if "audit" in (context.get("domains") or set()) and context.get("governance"):
        record_audit_event(
            request=request,
            event_type="view",
            module="executive_dashboard",
            action="view_audit_summary",
            description="Consulta de governança/auditoria no painel executivo",
        )
    return render(request, "executive_dashboard/dashboard.html", context)


@require_executive_access("executive_dashboard.print")
def report(request):
    try:
        context = _build_context(request)
    except ValidationError as exc:
        messages.error(request, str(exc))
        return redirect("executive_dashboard:dashboard")
    context["page_title"] = "Relatório Executivo"
    record_audit_event(
        request=request,
        event_type="view",
        module="executive_dashboard",
        action="print_report",
        description="Geração de relatório executivo imprimível",
        metadata={"period": context["period"]},
    )
    return render(request, "executive_dashboard/report.html", context)


@require_executive_access("executive_dashboard.export")
def export_csv(request, dataset):
    try:
        context = _build_context(request)
    except ValidationError as exc:
        messages.error(request, str(exc))
        return redirect("executive_dashboard:dashboard")

    mapping = {
        "vendedores": (
            "vendedores.csv",
            lambda: salespeople_csv_rows(context.get("salespeople") or []),
            "commercial",
        ),
        "vendas": (
            "vendas.csv",
            lambda: sales_csv_rows(context.get("commercial") or {}),
            "commercial",
        ),
        "riscos": (
            "pedidos_risco.csv",
            lambda: risks_csv_rows(context.get("risks") or []),
            "production",
        ),
        "producao": (
            "producao.csv",
            lambda: production_csv_rows(context.get("production") or {}),
            "production",
        ),
        "estoque": (
            "estoque.csv",
            lambda: stock_csv_rows(context.get("stock") or {}),
            "stock",
        ),
        "pos-venda": (
            "pos_venda.csv",
            lambda: after_sales_csv_rows(context.get("after_sales") or {}),
            "after_sales",
        ),
    }
    if dataset not in mapping:
        messages.error(request, "Exportação inválida.")
        return redirect("executive_dashboard:dashboard")
    filename, builder, domain = mapping[dataset]
    domains = context.get("domains") or set()
    if domain not in domains and not user_has_permission(request.user, "executive_dashboard.view"):
        return render_403(request)
    headers, rows = builder()
    return build_csv_response(
        filename=filename,
        headers=headers,
        rows=rows,
        request=request,
        export_key=dataset,
    )
