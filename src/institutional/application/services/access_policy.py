from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import resolve_url

from src.institutional.infrastructure.django.models import ContactRequest
from src.institutional.infrastructure.django.models import Opportunity
from src.institutional.infrastructure.django.models import Quote
from src.institutional.infrastructure.django.models import QuoteDocument
from src.institutional.infrastructure.django.models import QuoteDelivery

ADMINISTRATOR = "Administrador"
SALES_MANAGER = "Gerente Comercial"
SALESPERSON = "Vendedor"
VIEWER = "Visualizador"
OPERATIONAL_GROUPS = (ADMINISTRATOR, SALES_MANAGER, SALESPERSON, VIEWER)
ASSIGNABLE_GROUPS = (ADMINISTRATOR, SALES_MANAGER, SALESPERSON)

ROLE_LABELS = {
    ADMINISTRATOR: "Administrador",
    SALES_MANAGER: "Gerente Comercial",
    SALESPERSON: "Vendedor",
    VIEWER: "Visualizador",
}


def user_group_names(user):
    if not getattr(user, "is_authenticated", False):
        return set()
    return set(user.groups.values_list("name", flat=True))


def is_administrator(user):
    return getattr(user, "is_superuser", False) or ADMINISTRATOR in user_group_names(user)


def is_sales_manager(user):
    return SALES_MANAGER in user_group_names(user)


def is_salesperson(user):
    return SALESPERSON in user_group_names(user)


def is_viewer(user):
    return VIEWER in user_group_names(user)


def has_operational_access(user):
    return bool(
        getattr(user, "is_authenticated", False)
        and (getattr(user, "is_superuser", False) or user_group_names(user) & set(OPERATIONAL_GROUPS))
    )


def user_role_label(user):
    if getattr(user, "is_superuser", False):
        return "Superusuário"
    groups = user_group_names(user)
    for group in OPERATIONAL_GROUPS:
        if group in groups:
            return ROLE_LABELS[group]
    return "Sem perfil operacional"


def can_view_all_leads(user):
    return bool(is_administrator(user) or is_sales_manager(user) or is_viewer(user))


def get_visible_contact_requests(user):
    queryset = ContactRequest.objects.select_related("assigned_to")
    if can_view_all_leads(user):
        return queryset
    if is_salesperson(user):
        return queryset.filter(assigned_to=user)
    return queryset.none()


def can_view_lead(user, lead):
    if can_view_all_leads(user):
        return True
    return bool(is_salesperson(user) and lead.assigned_to_id == user.id)


def can_change_lead(user, lead):
    if is_administrator(user) or is_sales_manager(user):
        return True
    return bool(is_salesperson(user) and lead.assigned_to_id == user.id)


def can_assign_lead(user, lead=None):
    return bool(is_administrator(user) or is_sales_manager(user))


def can_add_note(user, lead):
    return can_change_lead(user, lead)


def can_view_audit(user, lead):
    return can_view_lead(user, lead)


def can_view_all_opportunities(user):
    return can_view_all_leads(user)


def get_visible_opportunities(user):
    queryset = Opportunity.objects.select_related("contact_request", "assigned_to")
    if can_view_all_opportunities(user):
        return queryset
    if is_salesperson(user):
        return queryset.filter(assigned_to=user)
    return queryset.none()


def can_view_opportunity(user, opportunity):
    if can_view_all_opportunities(user):
        return True
    return bool(is_salesperson(user) and opportunity.assigned_to_id == user.id)


def can_change_opportunity(user, opportunity):
    if is_viewer(user):
        return False
    if is_administrator(user) or is_sales_manager(user):
        return True
    return bool(is_salesperson(user) and opportunity.assigned_to_id == user.id)


def can_convert_lead_to_opportunity(user, lead):
    if is_viewer(user):
        return False
    return can_change_lead(user, lead)


def get_visible_quotes(user):
    return Quote.objects.select_related("opportunity", "opportunity__assigned_to", "opportunity__contact_request").filter(
        opportunity__in=get_visible_opportunities(user),
    )


def can_view_quote(user, quote):
    return can_view_opportunity(user, quote.opportunity)


def can_change_quote(user, quote):
    return can_change_opportunity(user, quote.opportunity)


def assignable_users_queryset(user_model):
    return (
        user_model.objects.filter(is_active=True, groups__name__in=ASSIGNABLE_GROUPS)
        .distinct()
        .order_by("first_name", "username")
    )


def backoffice_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path(), resolve_url("backoffice:login"))
        if not has_operational_access(request.user):
            raise PermissionDenied("Usuário sem perfil operacional.")
        return view_func(request, *args, **kwargs)

    return wrapped


def get_visible_quote_documents(user):
    return QuoteDocument.objects.select_related("quote", "quote__opportunity", "quote__opportunity__assigned_to").filter(
        quote__in=get_visible_quotes(user),
    )


def get_visible_quote_deliveries(user):
    return QuoteDelivery.objects.select_related("quote", "document", "requested_by").filter(
        quote__in=get_visible_quotes(user),
    )
