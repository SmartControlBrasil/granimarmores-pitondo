"""Utilitários de formulário do painel Hando (sem regras de domínio)."""

from __future__ import annotations

from django import forms


def _append_css(widget: forms.Widget, *class_names: str) -> None:
    current = [c for c in (widget.attrs.get("class") or "").split() if c]
    for name in class_names:
        if name and name not in current:
            current.append(name)
    if current:
        widget.attrs["class"] = " ".join(current)


def apply_bootstrap_classes(form: forms.BaseForm) -> None:
    """Aplica classes Bootstrap 5 aos widgets de um formulário Django."""
    for name, field in form.fields.items():
        widget = field.widget
        if isinstance(widget, (forms.CheckboxInput, forms.CheckboxSelectMultiple, forms.RadioSelect)):
            _append_css(widget, "form-check-input")
        elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
            _append_css(widget, "form-select")
        else:
            _append_css(widget, "form-control")

        if form.is_bound and name in form.errors:
            _append_css(widget, "is-invalid")


class BootstrapFormMixin:
    """
    Mixin global para estilizar widgets com Bootstrap 5.

    Uso:
        class MeuForm(BootstrapFormMixin, forms.ModelForm):
            ...

    Opcional:
        field_widths = {"campo": "col-md-6"}  # grid no template ERP
    """

    field_widths: dict[str, str] = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_bootstrap_classes(self)

    def get_field_width(self, name: str) -> str:
        widths = getattr(self, "field_widths", None) or {}
        return widths.get(name, "col-12")
