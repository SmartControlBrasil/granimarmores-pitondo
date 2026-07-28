# ruff: noqa: S105, S106
import re
from http import HTTPStatus

import pytest
from django.urls import reverse

from hando.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def test_allauth_login_page_uses_hando_template(client):
    response = client.get(reverse("account_login"))

    assert response.status_code == HTTPStatus.OK
    assert any(template.name == "account/login.html" for template in response.templates)


def test_login_form_posts_to_allauth_login_with_csrf(client):
    response = client.get(reverse("account_login"))
    html = response.content.decode()

    assert re.search(r'<form[^>]+method="post"[^>]+action="/accounts/login/"', html)
    assert 'name="csrfmiddlewaretoken"' in html
    assert "/accounts/login/post" not in html
    assert 'action="post"' not in html
    assert 'method="get"' not in html.lower()


def test_login_form_preserves_next_redirect_field(client):
    response = client.get(f"{reverse('account_login')}?next=/")
    html = response.content.decode()

    assert 'name="next"' in html
    assert 'value="/"' in html


def test_valid_login_redirects_without_password_in_url(client):
    password = "safe-test-password-123"
    user = UserFactory(password=password)
    response = client.post(
        reverse("account_login"),
        {"login": user.username, "password": password, "remember": "on", "next": "/"},
    )

    assert response.status_code == HTTPStatus.FOUND
    assert response.url == "/"
    assert password not in response.url
    assert "/accounts/login/post" not in response.url


def test_valid_login_without_next_redirects_to_panel(client):
    password = "safe-test-password-123"
    user = UserFactory(password=password)
    response = client.post(
        reverse("account_login"),
        {"login": user.username, "password": password, "remember": "on"},
    )

    assert response.status_code == HTTPStatus.FOUND
    assert response.url == "/painel/"
    assert password not in response.url



def test_invalid_login_stays_on_page_and_does_not_leak_password(client):
    password = "wrong-password-456"
    user = UserFactory(password="right-password-123")
    response = client.post(
        reverse("account_login"),
        {"login": user.username, "password": password},
    )

    assert response.status_code == HTTPStatus.OK
    assert any(template.name == "account/login.html" for template in response.templates)
    assert response.context["form"].errors
    assert password not in response.request["PATH_INFO"]
    assert "/accounts/login/post" not in response.request["PATH_INFO"]
