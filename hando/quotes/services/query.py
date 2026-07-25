from django.db.models import Q

from access_control.models import DataScope
from access_control.services.authorization import get_user_scope
from quotes.models import Quote


def quote_queryset_for_user(user):
    qs = Quote.objects.select_related(
        "customer",
        "salesperson",
        "salesperson__user",
        "created_by",
    )
    scope = get_user_scope(user, "quote")
    if user.is_superuser or scope == DataScope.ALL:
        return qs
    if scope == DataScope.TEAM:
        salesperson = getattr(user, "salesperson", None)
        if salesperson:
            return qs.filter(
                Q(salesperson=salesperson) | Q(salesperson__manager=salesperson),
            )
        return qs.filter(created_by=user)
    if scope == DataScope.OWN:
        return qs.filter(Q(salesperson__user=user) | Q(created_by=user))
    return qs.none()


def can_access_quote(user, quote):
    return quote_queryset_for_user(user).filter(pk=quote.pk).exists()
