from django import forms

from commercial.models import CommercialPartner
from commercial.models import CommercialSource
from commercial.models import ContactChannel
from commercial.models import LossReason
from commercial.models import ProjectType
from commercial.models import ServiceRegion


class CommercialSourceForm(forms.ModelForm):
    class Meta:
        model = CommercialSource
        fields = [
            "name",
            "slug",
            "description",
            "channel_group",
            "display_order",
            "is_active",
        ]
        labels = {
            "name": "Nome",
            "slug": "Slug",
            "description": "Descrição",
            "channel_group": "Grupo de canal",
            "display_order": "Ordem de exibição",
            "is_active": "Ativo",
        }


class ProjectTypeForm(forms.ModelForm):
    class Meta:
        model = ProjectType
        fields = [
            "name",
            "slug",
            "description",
            "requires_measurement",
            "allows_installation",
            "display_order",
            "is_active",
        ]
        labels = {
            "name": "Nome",
            "slug": "Slug",
            "description": "Descrição",
            "requires_measurement": "Requer medição",
            "allows_installation": "Permite instalação",
            "display_order": "Ordem de exibição",
            "is_active": "Ativo",
        }


class CommercialPartnerForm(forms.ModelForm):
    class Meta:
        model = CommercialPartner
        fields = [
            "partner_type",
            "name",
            "trade_name",
            "document",
            "contact_name",
            "email",
            "phone",
            "mobile_phone",
            "website",
            "postal_code",
            "street",
            "number",
            "complement",
            "district",
            "city",
            "state",
            "notes",
            "assigned_salesperson",
            "is_active",
        ]
        labels = {
            "partner_type": "Tipo de parceiro",
            "name": "Nome",
            "trade_name": "Nome fantasia",
            "document": "Documento",
            "contact_name": "Contato",
            "email": "E-mail",
            "phone": "Telefone",
            "mobile_phone": "Celular",
            "website": "Site",
            "postal_code": "CEP",
            "street": "Logradouro",
            "number": "Número",
            "complement": "Complemento",
            "district": "Bairro",
            "city": "Cidade",
            "state": "UF",
            "notes": "Observações",
            "assigned_salesperson": "Responsável comercial",
            "is_active": "Ativo",
        }


class LossReasonForm(forms.ModelForm):
    class Meta:
        model = LossReason
        fields = [
            "name",
            "slug",
            "description",
            "category",
            "requires_notes",
            "display_order",
            "is_active",
        ]
        labels = {
            "name": "Nome",
            "slug": "Slug",
            "description": "Descrição",
            "category": "Categoria",
            "requires_notes": "Exige observação",
            "display_order": "Ordem de exibição",
            "is_active": "Ativo",
        }


class ServiceRegionForm(forms.ModelForm):
    class Meta:
        model = ServiceRegion
        fields = [
            "name",
            "city",
            "state",
            "district",
            "postal_code_start",
            "postal_code_end",
            "service_enabled",
            "travel_fee",
            "minimum_order_value",
            "estimated_travel_minutes",
            "notes",
            "display_order",
            "is_active",
        ]
        labels = {
            "name": "Nome",
            "city": "Cidade",
            "state": "UF",
            "district": "Bairro",
            "postal_code_start": "CEP inicial",
            "postal_code_end": "CEP final",
            "service_enabled": "Atendimento habilitado",
            "travel_fee": "Taxa de deslocamento",
            "minimum_order_value": "Pedido mínimo",
            "estimated_travel_minutes": "Tempo estimado (min)",
            "notes": "Observações",
            "display_order": "Ordem de exibição",
            "is_active": "Ativo",
        }


class ContactChannelForm(forms.ModelForm):
    class Meta:
        model = ContactChannel
        fields = [
            "name",
            "slug",
            "description",
            "display_order",
            "is_active",
        ]
        labels = {
            "name": "Nome",
            "slug": "Slug",
            "description": "Descrição",
            "display_order": "Ordem de exibição",
            "is_active": "Ativo",
        }
