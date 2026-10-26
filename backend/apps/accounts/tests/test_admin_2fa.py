"""Django Admin доступен только после TOTP в текущей сессии (11, 34, DATA-09)."""
import re

import pyotp
import pytest
from django.test import Client

from apps.accounts.models import Account
from apps.accounts.services.roles import OTP_SESSION_KEY
from tests.factories import AccountFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def staff_client():
    account = AccountFactory(is_staff=True, is_superuser=True)
    client = Client()
    client.force_login(account)
    client.account = account
    return client


def test_admin_redirects_to_2fa_page(staff_client):
    response = staff_client.get("/admin/")
    assert response.status_code == 302
    assert response["Location"] == "/admin/2fa/?next=/admin/"


def test_setup_page_shows_secret_and_enables_on_valid_code(staff_client):
    page = staff_client.get("/admin/2fa/?next=/admin/accounts/account/")
    assert page.status_code == 200
    secret = re.search(r'class="secret">([A-Z2-7]+)<', page.content.decode()).group(1)
    assert staff_client.get("/admin/2fa/").content.decode().count(secret) >= 1  # секрет стабилен между загрузками
    wrong = staff_client.post("/admin/2fa/", {"code": "000000", "next": "/admin/accounts/account/"})
    assert wrong.status_code == 400
    response = staff_client.post("/admin/2fa/", {"code": pyotp.TOTP(secret).now(),
                                                 "next": "/admin/accounts/account/"})
    assert response.status_code == 302 and response["Location"] == "/admin/accounts/account/"
    assert Account.objects.get(pk=staff_client.account.pk).totp_enabled
    assert staff_client.session[OTP_SESSION_KEY]
    assert staff_client.get("/admin/").status_code == 200


def test_enabled_2fa_requires_code_each_session(staff_client):
    import pyotp as _pyotp

    secret = _pyotp.random_base32()
    Account.objects.filter(pk=staff_client.account.pk).update(totp_secret=secret, totp_enabled=True)
    page = staff_client.get("/admin/2fa/")
    assert "class=\"secret\"" not in page.content.decode()
    response = staff_client.post("/admin/2fa/", {"code": _pyotp.TOTP(secret).now()})
    assert response.status_code == 302 and response["Location"] == "/admin/"


def test_open_redirect_is_blocked(staff_client):
    secret = pyotp.random_base32()
    Account.objects.filter(pk=staff_client.account.pk).update(totp_secret=secret, totp_enabled=True)
    response = staff_client.post("/admin/2fa/?next=https://evil.example/", {"code": pyotp.TOTP(secret).now(),
                                                                            "next": "https://evil.example/"})
    assert response["Location"] == "/admin/"


def test_non_staff_is_sent_to_admin_login():
    client = Client()
    client.force_login(AccountFactory())
    response = client.get("/admin/2fa/")
    assert response.status_code == 302 and response["Location"].startswith("/admin/login/")
    assert Client().get("/admin/2fa/").status_code == 302


def test_2fa_page_requires_csrf():
    account = AccountFactory(is_staff=True)
    client = Client(enforce_csrf_checks=True)
    client.force_login(account)
    assert client.post("/admin/2fa/", {"code": "123456"}).status_code == 403
