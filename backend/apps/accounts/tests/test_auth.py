"""Вход/выход, подтверждение email, восстановление и смена пароля (5.3, ACC-13)."""
import re

import pytest
from django.core import mail, signing
from rest_framework.test import APIClient

from apps.accounts.models import Account
from apps.accounts.services.tokens import EMAIL_VERIFICATION_SALT, make_email_token
from apps.trust.models import AuditEvent
from tests.factories import AccountFactory

pytestmark = pytest.mark.django_db

PASSWORD = "Passw0rd!x"


def test_csrf_endpoint_sets_cookie(api_client):
    response = api_client.get("/api/v1/auth/csrf")
    assert response.status_code == 200
    assert response.cookies["csrftoken"].value
    assert response.json()["csrf_token"]


def test_login_returns_me_payload_and_session(api_client):
    account = AccountFactory(email="rider@example.com")
    response = api_client.post("/api/v1/auth/login", {"email": "Rider@Example.com", "password": PASSWORD},
                               format="json")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(account.pk)
    assert {"profile", "specialties", "organizations", "two_factor", "staff_roles"} <= set(body)
    assert api_client.get("/api/v1/me").status_code == 200


def test_login_wrong_password(api_client):
    AccountFactory(email="rider@example.com")
    response = api_client.post("/api/v1/auth/login", {"email": "rider@example.com", "password": "nope"},
                               format="json")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_credentials"


def test_inactive_account_cannot_login(api_client):
    AccountFactory(email="gone@example.com", is_active=False)
    response = api_client.post("/api/v1/auth/login", {"email": "gone@example.com", "password": PASSWORD},
                               format="json")
    assert response.status_code == 400


def test_logout_ends_session(auth_client):
    assert auth_client.post("/api/v1/auth/logout").status_code == 204
    assert auth_client.get("/api/v1/me").status_code == 401


def test_me_requires_login(api_client):
    assert api_client.get("/api/v1/me").status_code == 401


def test_verify_email_with_valid_token(api_client):
    account = AccountFactory(email_verified_at=None)
    response = api_client.post("/api/v1/auth/verify-email", {"token": make_email_token(account)}, format="json")
    assert response.status_code == 200
    assert response.json() == {"email": account.email, "email_verified": True}
    account.refresh_from_db()
    assert account.is_email_verified
    assert AuditEvent.objects.filter(action="account.email_verified", object_id=str(account.pk)).exists()


def test_verify_email_rejects_tampered_and_expired_tokens(api_client, settings):
    account = AccountFactory(email_verified_at=None)
    token = make_email_token(account)
    bad = api_client.post("/api/v1/auth/verify-email", {"token": token[:-2] + "xx"}, format="json")
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "token_invalid"
    old = signing.dumps({"a": str(account.pk), "e": account.email}, salt=EMAIL_VERIFICATION_SALT)
    settings.EMAIL_VERIFICATION_TTL_HOURS = -1  # любой токен старше «минус часа» считается истёкшим
    expired = api_client.post("/api/v1/auth/verify-email", {"token": old}, format="json")
    assert expired.json()["error"]["code"] == "token_expired"


def test_verify_email_token_is_bound_to_address(api_client):
    account = AccountFactory(email_verified_at=None)
    token = make_email_token(account)
    Account.objects.filter(pk=account.pk).update(email="changed@example.com")
    response = api_client.post("/api/v1/auth/verify-email", {"token": token}, format="json")
    assert response.status_code == 400


def test_resend_verification(make_client, run_on_commit):
    client = make_client(AccountFactory(email_verified_at=None))
    response = run_on_commit(client.post, "/api/v1/auth/verify-email/resend")
    assert response.status_code == 202
    assert len(mail.outbox) == 1 and "/verify-email?token=" in mail.outbox[0].body


def test_resend_when_already_verified_is_rejected(auth_client):
    response = auth_client.post("/api/v1/auth/verify-email/resend")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "already_verified"


def test_password_reset_does_not_reveal_accounts(api_client, run_on_commit):
    AccountFactory(email="real@example.com")
    unknown = run_on_commit(api_client.post, "/api/v1/auth/password-reset", {"email": "ghost@example.com"},
                            format="json")
    known = run_on_commit(api_client.post, "/api/v1/auth/password-reset", {"email": "real@example.com"},
                          format="json")
    assert unknown.status_code == known.status_code == 202
    assert unknown.json() == known.json()
    assert len(mail.outbox) == 1 and mail.outbox[0].to == ["real@example.com"]


def test_password_reset_confirm_flow(api_client, run_on_commit, settings):
    account = AccountFactory(email="real@example.com", email_verified_at=None)
    run_on_commit(api_client.post, "/api/v1/auth/password-reset", {"email": "real@example.com"}, format="json")
    match = re.search(rf"{re.escape(settings.SITE_URL)}/reset-password\?uid=([\w-]+)&token=([\w-]+)",
                      mail.outbox[0].body)
    uid, token = match.groups()
    weak = api_client.post("/api/v1/auth/password-reset/confirm", {"uid": uid, "token": token,
                                                                    "new_password": "123"}, format="json")
    assert weak.status_code == 400
    response = api_client.post("/api/v1/auth/password-reset/confirm",
                               {"uid": uid, "token": token, "new_password": "New-Wave-2026!"}, format="json")
    assert response.status_code == 200
    account.refresh_from_db()
    assert account.check_password("New-Wave-2026!")
    assert account.is_email_verified
    # Ссылка одноразовая.
    again = api_client.post("/api/v1/auth/password-reset/confirm",
                            {"uid": uid, "token": token, "new_password": "Other-Wave-2026!"}, format="json")
    assert again.status_code == 400


def test_password_reset_confirm_with_garbage(api_client):
    response = api_client.post("/api/v1/auth/password-reset/confirm",
                               {"uid": "zzz", "token": "abc", "new_password": "New-Wave-2026!"}, format="json")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "token_invalid"


def test_password_change_requires_old_password_and_keeps_session(make_client):
    account = AccountFactory()
    client = make_client(account)
    other_device = APIClient()
    other_device.post("/api/v1/auth/login", {"email": account.email, "password": PASSWORD}, format="json")
    wrong = client.post("/api/v1/auth/password-change", {"old_password": "bad", "new_password": "New-Wave-2026!"},
                        format="json")
    assert wrong.status_code == 400
    ok = client.post("/api/v1/auth/password-change",
                     {"old_password": PASSWORD, "new_password": "New-Wave-2026!"}, format="json")
    assert ok.status_code == 200
    assert client.get("/api/v1/me").status_code == 200
    # Другие сессии завершаются после смены пароля.
    assert other_device.get("/api/v1/me").status_code == 401
    assert AuditEvent.objects.filter(action="account.password_changed").exists()


def test_login_requires_csrf_for_browser_clients():
    AccountFactory(email="rider@example.com")
    client = APIClient(enforce_csrf_checks=True)
    response = client.post("/api/v1/auth/login", {"email": "rider@example.com", "password": PASSWORD},
                           format="json")
    assert response.status_code == 403
