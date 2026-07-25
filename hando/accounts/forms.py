from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

from access_control.models import UserAccess

User = get_user_model()


class UserCreateForm(forms.ModelForm):
    password1 = forms.CharField(label="Senha", widget=forms.PasswordInput)
    password2 = forms.CharField(
        label="Confirmação da senha",
        widget=forms.PasswordInput,
    )
    full_name = forms.CharField(label="Nome completo", max_length=180, required=False)
    phone = forms.CharField(label="Telefone", max_length=30, required=False)
    job_title = forms.CharField(label="Cargo interno", max_length=120, required=False)
    employee_code = forms.CharField(
        label="Código do colaborador",
        max_length=40,
        required=False,
    )

    class Meta:
        model = User
        fields = ["username", "name", "email", "is_active"]
        labels = {
            "username": "Usuário",
            "name": "Nome de exibição",
            "email": "Email",
            "is_active": "Ativo",
        }

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get("password1")
        password2 = cleaned.get("password2")
        if password1 and password2 and password1 != password2:
            self.add_error("password2", "As senhas não conferem.")
        if password1:
            validate_password(password1)
        return cleaned


class UserUpdateForm(forms.ModelForm):
    full_name = forms.CharField(label="Nome completo", max_length=180, required=False)
    phone = forms.CharField(label="Telefone", max_length=30, required=False)
    job_title = forms.CharField(label="Cargo interno", max_length=120, required=False)
    employee_code = forms.CharField(
        label="Código do colaborador",
        max_length=40,
        required=False,
    )
    is_operational_active = forms.BooleanField(
        label="Operacionalmente ativo",
        required=False,
    )
    must_change_password = forms.BooleanField(
        label="Exigir troca de senha",
        required=False,
    )

    class Meta:
        model = User
        fields = ["username", "name", "email", "is_active", "is_staff"]
        labels = {
            "username": "Usuário",
            "name": "Nome de exibição",
            "email": "Email",
            "is_active": "Ativo",
            "is_staff": "Acesso ao admin Django",
        }

    def __init__(self, *args, **kwargs):
        self.profile = kwargs.pop("profile", None)
        super().__init__(*args, **kwargs)
        if self.profile:
            self.fields["full_name"].initial = self.profile.full_name
            self.fields["phone"].initial = self.profile.phone
            self.fields["job_title"].initial = self.profile.job_title
            self.fields["employee_code"].initial = self.profile.employee_code
            self.fields[
                "is_operational_active"
            ].initial = self.profile.is_operational_active
            self.fields[
                "must_change_password"
            ].initial = self.profile.must_change_password


class UserAccessForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["valid_from"].required = False

    class Meta:
        model = UserAccess
        fields = ["role", "manager", "valid_from", "valid_until", "is_active"]
        labels = {
            "role": "Cargo",
            "manager": "Gestor",
            "valid_from": "Válido a partir de",
            "valid_until": "Válido até",
            "is_active": "Acesso ativo",
        }
        widgets = {
            "valid_from": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "valid_until": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }


class AdminPasswordResetForm(forms.Form):
    password1 = forms.CharField(label="Nova senha", widget=forms.PasswordInput)
    password2 = forms.CharField(
        label="Confirmação da senha",
        widget=forms.PasswordInput,
    )
    revoke_sessions = forms.BooleanField(
        label="Revogar sessões ativas",
        required=False,
        initial=True,
    )
    must_change_password = forms.BooleanField(
        label="Exigir troca no próximo acesso",
        required=False,
        initial=True,
    )

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get("password1")
        password2 = cleaned.get("password2")
        if password1 and password2 and password1 != password2:
            self.add_error("password2", "As senhas não conferem.")
        if password1:
            validate_password(password1)
        return cleaned
