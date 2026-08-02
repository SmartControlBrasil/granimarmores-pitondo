from after_sales.models import CaseSeverity
from after_sales.models import CaseStatus
from after_sales.models import OPEN_CASE_STATUSES
from after_sales.selectors import after_sales_dashboard_metrics
from media_library.selectors import media_dashboard_metrics


def after_sales_metrics(*, user, start, end, filters=None):
    filters = filters or {}
    metrics = after_sales_dashboard_metrics(
        user=user,
        start=start,
        end=end,
        assigned_user=filters.get("production_responsible"),
        status=filters.get("after_sales_status"),
    )
    metrics["critical_open"] = metrics.get("critical", 0)
    return metrics


def media_summary_metrics(*, user, start, end):
    return media_dashboard_metrics(user=user, start=start, end=end)
