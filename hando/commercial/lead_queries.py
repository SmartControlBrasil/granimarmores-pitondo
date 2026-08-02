from django.db.models import Q

from access_control.models import DataScope
from access_control.services.authorization import get_user_scope
from access_control.services.authorization import user_has_permission
from commercial.lead_models import Lead


def leads_queryset_for_user(user):
    qs = Lead.objects.select_related(
        "assigned_salesperson",
        "assigned_salesperson__user",
        "commercial_source",
        "contact_channel",
        "project_type",
        "partner",
        "service_region",
        "converted_customer",
        "created_by",
    )
    if user.is_superuser or user_has_permission(user, "leads.view_all"):
        return qs
    if not user_has_permission(user, "leads.view"):
        return qs.none()
    scope = get_user_scope(user, "customer")
    if scope == DataScope.ALL:
        return qs
    if scope == DataScope.TEAM:
        salesperson = getattr(user, "salesperson", None)
        if salesperson:
            return qs.filter(
                Q(assigned_salesperson=salesperson)
                | Q(assigned_salesperson__manager=salesperson)
                | Q(created_by=user),
            )
        return qs.filter(created_by=user)
    if scope == DataScope.OWN:
        return qs.filter(
            Q(assigned_salesperson__user=user) | Q(created_by=user),
        )
    return qs.none()


def can_access_lead(user, lead):
    return leads_queryset_for_user(user).filter(pk=lead.pk).exists()
