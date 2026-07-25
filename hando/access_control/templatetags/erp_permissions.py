from django import template

from access_control.services.authorization import user_has_permission

register = template.Library()


@register.simple_tag(takes_context=True)
def has_permission(context, permission_code):
    request = context.get("request")
    if not request:
        return False
    return user_has_permission(request.user, permission_code)
