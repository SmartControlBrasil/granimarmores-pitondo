from django import forms

from src.institutional.infrastructure.django.models import ContactRequest


class ContactRequestForm(forms.ModelForm):
    privacidade = forms.BooleanField(required=True)
    website = forms.CharField(required=False)

    class Meta:
        model = ContactRequest
        fields = [
            "nome",
            "telefone",
            "email",
            "cidade",
            "ambiente",
            "medidas",
            "mensagem",
        ]

    def clean_website(self):
        value = self.cleaned_data.get("website", "").strip()
        if value:
            raise forms.ValidationError(
                "Não foi possível processar a solicitação. Tente novamente.",
            )
        return value

    def clean_mensagem(self):
        value = self.cleaned_data.get("mensagem", "").strip()
        if len(value) < 10:
            raise forms.ValidationError(
                "Descreva o projeto com um pouco mais de detalhe.",
            )
        return value

    def clean(self):
        cleaned_data = super().clean()
        required_fields = ["nome", "telefone", "cidade", "ambiente", "mensagem"]
        if any(not cleaned_data.get(field) for field in required_fields):
            raise forms.ValidationError(
                "Preencha os campos obrigatórios para solicitar a avaliação.",
            )
        return cleaned_data
