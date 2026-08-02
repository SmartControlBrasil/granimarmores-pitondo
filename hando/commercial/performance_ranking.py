from commercial.performance_definitions import RANKING_METRICS
from commercial.performance_metrics import compute_salesperson_metrics
from commercial.performance_metrics import salespersons_for_scope


def _sort_key(row, metric):
    if metric == "score":
        return (-row["total_score"], -row["leads_won"], row["salesperson"].display_name)
    if metric == "approved_value":
        return (-float(row["approved_value"]), -row["total_score"], row["salesperson"].display_name)
    if metric == "conversion_rate":
        return (-float(row["conversion_rate"]), -row["leads_won"], row["salesperson"].display_name)
    if metric == "response_time":
        if row["response_minutes"] == 0:
            return (999999, row["salesperson"].display_name)
        return (row["response_minutes"], row["salesperson"].display_name)
    if metric == "follow_up_compliance":
        return (-float(row["follow_up_compliance"]), -row["total_score"], row["salesperson"].display_name)
    if metric == "won_leads":
        return (-row["leads_won"], -row["total_score"], row["salesperson"].display_name)
    if metric == "quotes_sent":
        return (-row["quotes_sent"], -row["total_score"], row["salesperson"].display_name)
    return (-row["total_score"], row["salesperson"].display_name)


def build_ranking(*, user, start, end, metric="score", include_inactive=False):
    salespersons = salespersons_for_scope(user=user, include_inactive=include_inactive)
    rows = [
        compute_salesperson_metrics(salesperson=sp, start=start, end=end)
        for sp in salespersons
    ]
    rows.sort(key=lambda row: _sort_key(row, metric))
    for index, row in enumerate(rows, start=1):
        row["position"] = index
    metric_label = dict(RANKING_METRICS).get(metric, "Score total")
    return {
        "rows": rows,
        "metric": metric,
        "metric_label": metric_label,
        "metrics": RANKING_METRICS,
    }
