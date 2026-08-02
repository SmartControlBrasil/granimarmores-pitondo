from django import template

from access_control.services.authorization import user_has_permission

register = template.Library()


@register.simple_tag(takes_context=True)
def has_permission(context, permission_code):
    request = context.get("request")
    if not request:
        return False
    return user_has_permission(request.user, permission_code)


def _match_nav_rule(namespace, url_name, rule):
    """Match resolver_match against a compact nav rule.

    Formats:
    - ``app`` → namespace equals app
    - ``app:name`` → namespace and exact url_name
    - ``app:prefix*`` → namespace and url_name startswith prefix
    - ``app:*part*`` → namespace and substring in url_name
    - ``:name`` → exact url_name (any namespace)
    """
    rule = (rule or "").strip()
    if not rule:
        return False
    if ":" in rule:
        rule_ns, rule_name = rule.split(":", 1)
        if rule_ns and namespace != rule_ns:
            return False
        if rule_name.startswith("*") and rule_name.endswith("*") and len(rule_name) > 2:
            return rule_name[1:-1] in url_name
        if rule_name.endswith("*"):
            return url_name.startswith(rule_name[:-1])
        return url_name == rule_name
    return namespace == rule


@register.simple_tag(takes_context=True)
def nav_active(context, *rules):
    """Return True when the current route matches any nav rule (no DB)."""
    request = context.get("request")
    match = getattr(request, "resolver_match", None) if request else None
    if not match:
        return False
    namespace = match.namespace or ""
    url_name = match.url_name or ""
    return any(_match_nav_rule(namespace, url_name, rule) for rule in rules)
