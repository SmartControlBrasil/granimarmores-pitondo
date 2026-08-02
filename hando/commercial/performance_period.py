from datetime import datetime
from datetime import timedelta

from django.utils import timezone


def parse_performance_period(request, *, default="30d"):
    """Interpreta filtros de período comuns a ranking, metas e dashboards."""
    period = request.GET.get("period", default)
    now = timezone.now()
    today = timezone.localdate()

    if period == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return start, now, period

    if period == "week":
        start_date = today - timedelta(days=today.weekday())
        start = timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
        return start, now, period

    if period == "7d":
        return now - timedelta(days=7), now, period

    if period == "month":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return start, now, period

    if period == "quarter":
        quarter_month = ((today.month - 1) // 3) * 3 + 1
        start_date = today.replace(month=quarter_month, day=1)
        start = timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
        return start, now, period

    if period == "year":
        start_date = today.replace(month=1, day=1)
        start = timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
        return start, now, period

    if period == "custom":
        from django.utils.dateparse import parse_date

        start_date = parse_date(request.GET.get("start", "") or "")
        end_date = parse_date(request.GET.get("end", "") or "")
        if start_date and end_date:
            start = timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
            end = timezone.make_aware(datetime.combine(end_date, datetime.max.time()))
            return start, end, period
        return now - timedelta(days=30), now, "30d"

    # default 30d
    return now - timedelta(days=30), now, "30d"


PERIOD_CHOICES = [
    ("today", "Hoje"),
    ("week", "Semana atual"),
    ("7d", "Últimos 7 dias"),
    ("30d", "Últimos 30 dias"),
    ("month", "Mês atual"),
    ("quarter", "Trimestre"),
    ("year", "Ano"),
    ("custom", "Personalizado"),
]
