from django import template

from core.utils import format_brl as _format_brl

register = template.Library()


@register.filter(name="format_brl")
def format_brl_filter(value):
    return _format_brl(value)
