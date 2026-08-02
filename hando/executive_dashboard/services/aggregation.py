# ruff: noqa: PLR0913
import hashlib
import json
from decimal import Decimal

from django.conf import settings
from django.core.cache import cache

from access_control.services.authorization import user_has_permission
from commercial.performance_metrics import safe_rate
from executive_dashboard.selectors.after_sales import after_sales_metrics
from executive_dashboard.selectors.after_sales import media_summary_metrics
from executive_dashboard.selectors.commercial import commercial_metrics
from executive_dashboard.selectors.commercial import salesperson_executive_table
from executive_dashboard.selectors.governance import governance_metrics
from executive_dashboard.selectors.operations import delivery_installation_metrics
from executive_dashboard.selectors.operations import schedule_metrics
from executive_dashboard.selectors.production import production_bottlenecks
from executive_dashboard.selectors.production import production_metrics
from executive_dashboard.selectors.production import quality_metrics
from executive_dashboard.selectors.risks import build_executive_alerts
from executive_dashboard.selectors.risks import orders_at_risk
from executive_dashboard.selectors.stock import stock_metrics


def _dec(value):
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _trend(current, previous):
    current = _dec(current)
    previous = _dec(previous)
    abs_diff = current - previous
    pct = safe_rate(abs_diff, previous) if previous else (Decimal("100") if current else Decimal("0"))
    if previous == 0 and current == 0:
        pct = Decimal("0")
    return {
        "current": current,
        "previous": previous,
        "absolute": abs_diff,
        "percent": pct,
    }


def _cache_key(user, start, end, filters, domains):
    payload = json.dumps(
        {
            "u": user.pk,
            "s": start.isoformat(),
            "e": end.isoformat(),
            "f": filters,
            "d": sorted(domains),
        },
        sort_keys=True,
        default=str,
    )
    return "exec_dash:" + hashlib.sha256(payload.encode()).hexdigest()


def build_executive_dashboard(*, user, start, end, previous_period, filters=None):
    filters = filters or {}
    domains = _allowed_domains(user)
    ttl = int(getattr(settings, "EXECUTIVE_DASHBOARD_CACHE_SECONDS", 60))
    key = _cache_key(user, start, end, filters, domains)
    cached = cache.get(key)
    if cached is not None:
        cached["from_cache"] = True
        return cached

    data = {
        "domains": domains,
        "from_cache": False,
        "filters_applied": filters,
        "trends": {},
        "charts": {},
    }
    prev_start, prev_end = previous_period
    can_values = user_has_permission(user, "executive_dashboard.view_sales_values") or user_has_permission(
        user,
        "executive_dashboard.view",
    )
    data["can_view_sales_values"] = can_values

    if "commercial" in domains:
        commercial = commercial_metrics(start=start, end=end, filters=filters)
        commercial_prev = commercial_metrics(start=prev_start, end=prev_end, filters=filters)
        if not can_values:
            for key in ("potential_value", "approved_value", "ticket_average"):
                commercial[key] = None
                commercial_prev[key] = None
        data["commercial"] = commercial
        data["salespeople"] = salesperson_executive_table(
            start=start,
            end=end,
            filters=filters,
            user=user,
        )
        data["trends"].update(
            {
                "leads": _trend(commercial["leads_received"], commercial_prev["leads_received"]),
                "approved_value": _trend(
                    commercial.get("approved_value") or 0,
                    commercial_prev.get("approved_value") or 0,
                )
                if can_values
                else None,
                "ticket": _trend(
                    commercial.get("ticket_average") or 0,
                    commercial_prev.get("ticket_average") or 0,
                )
                if can_values
                else None,
                "conversion": _trend(commercial["conversion_rate"], commercial_prev["conversion_rate"]),
                "closed_sales": _trend(
                    commercial["quotes_accepted"],
                    commercial_prev["quotes_accepted"],
                ),
            },
        )
        data["charts"].update(
            {
                "funnel": [
                    {"label": r["label"], "value": r["open_count"] or r["count"]}
                    for r in commercial["funnel"]
                ],
                "leads_by_source": [
                    {"label": r["commercial_source__name"] or "Sem origem", "value": r["total"]}
                    for r in commercial["by_source"]
                ],
                "sales_by_salesperson": [
                    {
                        "label": row["salesperson"].display_name,
                        "value": float(row["approved_value"]) if can_values else 0,
                    }
                    for row in data["salespeople"][:10]
                ]
                if can_values
                else [],
                "sales_by_period": commercial.get("sales_by_day") or [],
            },
        )
    else:
        data["commercial"] = {}
        data["salespeople"] = []

    if "production" in domains:
        data["production"] = production_metrics(user=user, start=start, end=end, filters=filters)
        data["bottlenecks"] = production_bottlenecks(user=user, filters=filters)
        data["quality"] = quality_metrics(start=start, end=end)
        prod_prev = production_metrics(user=user, start=prev_start, end=prev_end, filters=filters)
        data["trends"]["overdue"] = _trend(
            data["production"].get("orders_overdue") or data["production"].get("overdue_orders") or 0,
            prod_prev.get("orders_overdue") or prod_prev.get("overdue_orders") or 0,
        )
        data["trends"]["rework"] = _trend(
            data["production"].get("rework_count", 0),
            prod_prev.get("rework_count", 0),
        )
        data["charts"]["production_by_stage"] = [
            {"label": r["stage__name"] or "—", "value": r["total"]}
            for r in data["production"].get("by_stage", [])
        ]
    else:
        data["production"] = {}
        data["bottlenecks"] = {}
        data["quality"] = {}

    if "stock" in domains:
        include_costs = user_has_permission(user, "executive_dashboard.view_stock_costs") or user_has_permission(
            user,
            "stock_costs.view",
        )
        data["stock"] = stock_metrics(
            start=start,
            end=end,
            filters=filters,
            include_costs=include_costs,
        )
        data["can_view_stock_costs"] = include_costs
    else:
        data["stock"] = {}
        data["can_view_stock_costs"] = False

    if "schedule" in domains:
        data["schedule"] = schedule_metrics(user=user, start=start, end=end, filters=filters)
        data["delivery_installation"] = delivery_installation_metrics(
            start=start,
            end=end,
            filters=filters,
        )
    else:
        data["schedule"] = {}
        data["delivery_installation"] = {}

    if "after_sales" in domains:
        data["after_sales"] = after_sales_metrics(user=user, start=start, end=end, filters=filters)
        as_prev = after_sales_metrics(user=user, start=prev_start, end=prev_end, filters=filters)
        data["trends"]["after_sales_open"] = _trend(
            data["after_sales"].get("open_cases", 0),
            as_prev.get("open_cases", 0),
        )
        data["trends"]["satisfaction"] = _trend(
            data["after_sales"].get("avg_satisfaction") or 0,
            as_prev.get("avg_satisfaction") or 0,
        )
        data["charts"]["after_sales_by_type"] = [
            {"label": r["case_type"], "value": r["total"]}
            for r in data["after_sales"].get("by_type", [])
        ]
    else:
        data["after_sales"] = {}

    if "media" in domains:
        data["media"] = media_summary_metrics(user=user, start=start, end=end)
    else:
        data["media"] = {}

    if "audit" in domains:
        data["governance"] = governance_metrics(start=start, end=end)
    else:
        data["governance"] = {}

    data["risks"] = orders_at_risk(filters=filters) if "production" in domains or "commercial" in domains else []
    data["alerts"] = build_executive_alerts(user=user, domains=data)

    # Resumo executivo
    c = data.get("commercial") or {}
    p = data.get("production") or {}
    a = data.get("after_sales") or {}
    data["summary"] = {
        "leads_received": c.get("leads_received", 0),
        "open_opportunities": c.get("open_opportunities", 0),
        "potential_value": c.get("potential_value", Decimal("0")),
        "quotes_sent": c.get("quotes_sent", 0),
        "quotes_accepted": c.get("quotes_accepted", 0),
        "approved_value": c.get("approved_value", Decimal("0")),
        "ticket_average": c.get("ticket_average", Decimal("0")),
        "conversion_rate": c.get("conversion_rate", Decimal("0")),
        "orders_in_production": p.get("production_in_progress", 0),
        "orders_overdue": p.get("orders_overdue") or p.get("overdue_orders") or 0,
        "critical_after_sales": a.get("critical", 0),
        "avg_satisfaction": a.get("avg_satisfaction"),
    }

    if ttl > 0:
        cache.set(key, data, ttl)
    return data


def _allowed_domains(user):
    domains = set()
    if user_has_permission(user, "executive_dashboard.view"):
        domains.update(
            {
                "commercial",
                "production",
                "stock",
                "schedule",
                "after_sales",
                "media",
                "audit",
                "quality",
            },
        )
    if user_has_permission(user, "executive_dashboard.view_commercial"):
        domains.add("commercial")
    if user_has_permission(user, "executive_dashboard.view_production"):
        domains.update({"production", "quality"})
    if user_has_permission(user, "executive_dashboard.view_stock"):
        domains.add("stock")
    if user_has_permission(user, "executive_dashboard.view_schedule"):
        domains.add("schedule")
    if user_has_permission(user, "executive_dashboard.view_after_sales"):
        domains.add("after_sales")
    if user_has_permission(user, "executive_dashboard.view_quality"):
        domains.add("quality")
    if user_has_permission(user, "executive_dashboard.view_audit"):
        domains.add("audit")
    if user_has_permission(user, "media_dashboard.view") or user_has_permission(user, "media_assets.view"):
        if "commercial" in domains or "production" in domains or user_has_permission(
            user,
            "executive_dashboard.view",
        ):
            domains.add("media")
    return domains
