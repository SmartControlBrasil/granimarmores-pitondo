from django import forms

from hando.forms import BootstrapFormMixin

from access_control.models import AccessRole
from access_control.models import DataScope


class RoleForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = AccessRole
        fields = [
            "name",
            "slug",
            "description",
            "hierarchy_level",
            "has_full_access",
            "customer_scope",
            "quote_scope",
            "asset_scope",
            "maintenance_scope",
            "is_active",
        ]
        labels = {
            "name": "Cargo",
            "slug": "Identificador",
            "description": "Descrição",
            "hierarchy_level": "Nível hierárquico",
            "has_full_access": "Acesso total",
            "customer_scope": "Escopo de clientes",
            "quote_scope": "Escopo de orçamentos",
            "asset_scope": "Escopo de ativos",
            "maintenance_scope": "Escopo de manutenção",
            "is_active": "Ativo",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False
        scope_choices = DataScope.choices
        self.fields["customer_scope"].choices = scope_choices
        self.fields["quote_scope"].choices = scope_choices
        self.fields["asset_scope"].choices = scope_choices
        self.fields["maintenance_scope"].choices = scope_choices


class PermissionMatrixForm(BootstrapFormMixin, forms.Form):
    def __init__(self, *args, permissions=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.permissions = list(permissions or [])
        for permission in self.permissions:
            self.fields[f"permission_{permission.pk}"] = forms.BooleanField(
                label=permission.name,
                required=False,
            )
