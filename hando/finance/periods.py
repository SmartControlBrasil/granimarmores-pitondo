from calendar import monthrange
from datetime import datetime
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.dateparse import parse_date


PERIOD_CHOICES = [
    ("today", "Hoje"),
    ("7d", "Últimos 7 dias"),
    ("30d", "Últimos 30 dias"),
    ("month", "Mês atual"),
    ("previous_month", "Mês anterior"),
    ("year", "Ano atual"),
    ("custom", "Personalizado"),
]


def _aware(date_obj, end=False):
    time = datetime.max.time() if end else datetime.min.time()
    return timezone.make_aware(datetime.combine(date_obj, time))


def parse_finance_period(request, *, default="30d"):
    period = request.GET.get("period", default)
    now = timezone.now()
    today = timezone.localdate()
    if period == "today":
        start, end = today, today
    elif period == "7d":
        start, end = today - timedelta(days=7), today
    elif period == "month":
        start, end = today.replace(day=1), today
    elif period == "previous_month":
        first = today.replace(day=1)
        prev_last = first - timedelta(days=1)
        start, end = prev_last.replace(day=1), prev_last
    elif period == "year":
        start, end = today.replace(month=1, day=1), today
    elif period == "custom":
        start = parse_date(request.GET.get("start") or "")
        end = parse_date(request.GET.get("end") or "")
        if not start or not end:
            raise ValidationError("Período personalizado exige datas.")
        if end < start:
            raise ValidationError("Data fim inválida.")
        if (end - start).days > 732:
            raise ValidationError("Período máximo de 732 dias.")
    else:
        period = "30d"
        start, end = today - timedelta(days=30), today
    return start, end, period
