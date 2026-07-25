from http import HTTPStatus

import pytest
from django.contrib.auth.models import AnonymousUser
from django.template.loader import render_to_string
from django.test import RequestFactory
from django.urls import resolve
from django.urls import reverse

from accounts.models import UserProfile
from hando.users.models import User
from hando.users.templatetags.topbar_user import topbar_display_name
from hando.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def _dashboard_html(client, user):
    client.force_login(user)
    response = client.get(reverse("pages:dashboard"))
    assert response.status_code == HTTPStatus.OK
    return response.content.decode()


def test_topbar_shows_profile_full_name_for_marcelo_and_never_alex(client):
    user = UserFactory(username="marcelo", name="", email="marcelo@example.com")
    UserProfile.objects.create(user=user, full_name="Marcelo Pitondo")

    html = _dashboard_html(client, user)

    assert "Olá, Marcelo Pitondo" in html
    assert "Marcelo Pitondo" in html
    assert "marcelo@example.com" in html
    assert "Alex" not in html


def test_topbar_shows_current_authenticated_user_name(client):
    user = UserFactory(username="ana", name="Ana Granitos", email="ana@example.com")

    html = _dashboard_html(client, user)

    assert "Olá, Ana Granitos" in html
    assert "Ana Granitos" in html
    assert "ana@example.com" in html
    assert "Alex" not in html


def test_topbar_user_without_profile_falls_back_to_username(client):
    user = UserFactory(username="semperfil", name="", email="")

    html = _dashboard_html(client, user)

    assert "Olá, semperfil" in html
    assert "Alex" not in html


def test_topbar_links_to_authenticated_user_profile_and_allauth_logout(client):
    user = UserFactory(username="perfil", name="Usuário Perfil")

    html = _dashboard_html(client, user)

    assert 'href="/users/perfil/"' in html
    assert 'href="/accounts/logout/"' in html
    assert "auth-lock-screen" not in html
    assert "pages-profile" not in html
    assert "user-13.jpg" not in html


def test_user_get_full_name_uses_custom_name_field(user):
    user.name = "Nome Real"

    assert user.get_full_name() == "Nome Real"


def test_user_get_full_name_never_returns_none_none():
    user = User(username="identificador", name="", email="user@example.com")

    assert user.get_full_name() == "identificador"
    assert user.get_full_name() != "None None"


def test_topbar_display_name_falls_back_to_email_when_needed():
    user = User(username="", name="", email="sem-usuario@example.com")

    assert topbar_display_name(user) == "sem-usuario@example.com"


def test_topbar_anonymous_user_renders_safely():
    request = RequestFactory().get("/")
    request.user = AnonymousUser()

    html = render_to_string("partials/topbar.html", request=request)

    assert "Usuário" in html
    assert "Alex" not in html


def test_login_logout_urls_resolve_to_allauth_routes():
    assert reverse("account_login") == "/accounts/login/"
    assert reverse("account_logout") == "/accounts/logout/"
    assert resolve("/accounts/login/").view_name == "account_login"
    assert resolve("/accounts/logout/").view_name == "account_logout"
