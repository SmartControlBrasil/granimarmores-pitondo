from datetime import timedelta

from django.utils import timezone

PERIOD_CHOICES = [
    ("today", "Hoje"),
    ("7d", "7 dias"),
    ("30d", "30 dias"),
    ("month", "Mês atual"),
    ("prev_month", "Mês anterior"),
    ("year", "Ano"),
    ("custom", "Personalizado"),
]


def parse_commission_period(request):
    period = request.GET.get("period") or "30d"
    today = timezone.localdate()
    start = today - timedelta(days=29)
    end = today
    if period == "today":
        start = today
    elif period == "7d":
        start = today - timedelta(days=6)
    elif period == "30d":
        start = today - timedelta(days=29)
    elif period == "month":
        start = today.replace(day=1)
    elif period == "prev_month":
        first = today.replace(day=1)
        end = first - timedelta(days=1)
        start = end.replace(day=1)
    elif period == "year":
        start = today.replace(month=1, day=1)
    elif period == "custom":
        try:
            if request.GET.get("start"):
                start = timezone.datetime.fromisoformat(request.GET["start"]).date()
            if request.GET.get("end"):
                end = timezone.datetime.fromisoformat(request.GET["end"]).date()
        except ValueError:
            pass
    return start, end, period
