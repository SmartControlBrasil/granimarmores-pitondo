from datetime import datetime
from datetime import timedelta
from calendar import monthrange

from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.dateparse import parse_date


PERIOD_CHOICES = [
    ("today", "Hoje"),
    ("7d", "Últimos 7 dias"),
    ("30d", "Últimos 30 dias"),
    ("month", "Mês atual"),
    ("previous_month", "Mês anterior"),
    ("quarter", "Trimestre atual"),
    ("year", "Ano atual"),
    ("custom", "Período personalizado"),
]

MAX_PERIOD_DAYS = 732  # ~2 anos


def _aware(date_obj, end=False):
    time = datetime.max.time() if end else datetime.min.time()
    return timezone.make_aware(datetime.combine(date_obj, time))


def parse_executive_period(request, *, default="30d"):
    period = request.GET.get("period", default)
    now = timezone.now()
    today = timezone.localdate()

    if period == "today":
        start, end = _aware(today), now
    elif period == "7d":
        start, end = now - timedelta(days=7), now
    elif period == "month":
        start, end = _aware(today.replace(day=1)), now
    elif period == "previous_month":
        first = today.replace(day=1)
        prev_last = first - timedelta(days=1)
        prev_first = prev_last.replace(day=1)
        start, end = _aware(prev_first), _aware(prev_last, end=True)
    elif period == "quarter":
        qm = ((today.month - 1) // 3) * 3 + 1
        start, end = _aware(today.replace(month=qm, day=1)), now
    elif period == "year":
        start, end = _aware(today.replace(month=1, day=1)), now
    elif period == "custom":
        start_date = parse_date(request.GET.get("start", "") or "")
        end_date = parse_date(request.GET.get("end", "") or "")
        if not start_date or not end_date:
            raise ValidationError("Período personalizado exige datas início e fim.")
        if end_date < start_date:
            raise ValidationError("Data fim não pode ser anterior ao início.")
        if (end_date - start_date).days > MAX_PERIOD_DAYS:
            raise ValidationError(f"Período máximo de {MAX_PERIOD_DAYS} dias.")
        start, end = _aware(start_date), _aware(end_date, end=True)
    else:
        period = "30d"
        start, end = now - timedelta(days=30), now

    previous = previous_equivalent_period(start, end)
    return start, end, period, previous


def previous_equivalent_period(start, end):
    delta = end - start
    prev_end = start - timedelta(microseconds=1)
    prev_start = prev_end - delta
    return prev_start, prev_end


def parse_filters(request):
    return {
        "salesperson": request.GET.get("salesperson") or None,
        "commercial_source": request.GET.get("commercial_source") or None,
        "project_type": request.GET.get("project_type") or None,
        "city": (request.GET.get("city") or "").strip() or None,
        "material": request.GET.get("material") or None,
        "production_responsible": request.GET.get("production_responsible") or None,
        "production_stage": request.GET.get("production_stage") or None,
        "order_status": request.GET.get("order_status") or None,
        "after_sales_status": request.GET.get("after_sales_status") or None,
    }
