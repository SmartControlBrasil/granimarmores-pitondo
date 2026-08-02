from django import template

from hando.forms import apply_bootstrap_classes

register = template.Library()


@register.inclusion_tag("erp/partials/form_fields.html")
def erp_form_fields(form):
    """Renderiza campos do formulário no padrão visual do painel."""
    apply_bootstrap_classes(form)
    widths = getattr(form, "field_widths", None) or {}
    get_width = getattr(form, "get_field_width", None)
    items = []
    for field in form.visible_fields():
        if callable(get_width):
            col = get_width(field.name)
        else:
            col = widths.get(field.name, "col-12")
        items.append({"field": field, "col": col or "col-12"})
    return {
        "form": form,
        "items": items,
        "hidden_fields": form.hidden_fields(),
    }


@register.filter
def erp_field_col(form, field_name):
    widths = getattr(form, "field_widths", None) or {}
    get_width = getattr(form, "get_field_width", None)
    if callable(get_width):
        return get_width(field_name)
    return widths.get(field_name, "col-12")
