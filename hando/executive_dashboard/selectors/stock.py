from materials.stock_selectors import stock_dashboard_metrics


def stock_metrics(*, start, end, filters=None, include_costs=False):
    filters = filters or {}
    metrics = stock_dashboard_metrics(
        start=start,
        end=end,
        material_id=filters.get("material"),
    )
    if not include_costs:
        metrics.pop("total_cost", None)
        metrics.pop("cost_by_material", None)
        for key in list(metrics.keys()):
            if "cost" in key.lower():
                metrics.pop(key, None)
    return metrics
