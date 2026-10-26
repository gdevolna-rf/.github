"""TOTP-2FA (5.3, 11, DATA-09) и служебные роли (BR-04, TRUST-06)."""
import pyotp
import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Account, StaffRole
from apps.accounts.services.roles import OTP_SESSION_KEY
from apps.trust.models import AuditEvent
from tests.factories import AccountFactory, make_moderator

pytestmark = pytest.mark.django_db


def enable_2fa(client):
    secret = client.post("/api/v1/me/2fa/setup").json()["secret"]
    response = client.post("/api/v1/me/2fa/enable", {"code": pyotp.TOTP(secret).now()}, format="json")
    assert response.status_code == 200, response.json()
    return secret


def next_code(secret):
    """Код следующего шага: в пределах окна valid_window=1 и гарантированно не равен коду из enable_2fa."""
    import time

    return pyotp.TOTP(secret).at(time.time() + 30)


def test_setup_returns_secret_and_otpauth_uri(auth_client, settings):
    body = auth_client.post("/api/v1/me/2fa/setup").json()
    assert len(body["secret"]) >= 16
    assert body["otpauth_uri"].startswith("otpauth://totp/")
    assert "issuer=" in body["otpauth_uri"]
    assert not Account.objects.get(pk=auth_client.account.pk).totp_enabled


def test_enable_requires_valid_code(auth_client):
    auth_client.post("/api/v1/me/2fa/setup")
    response = auth_client.post("/api/v1/me/2fa/enable", {"code": "000000"}, format="json")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "two_factor_code_invalid"


def test_enable_marks_session_and_audits(auth_client):
    enable_2fa(auth_client)
    me = auth_client.get("/api/v1/me").json()
    assert me["two_factor"] == {"enabled": True, "verified": True, "required": False}
    assert AuditEvent.objects.filter(action="account.2fa_enabled").exists()
    assert auth_client.post("/api/v1/me/2fa/setup").status_code == 400


def test_enable_without_setup(auth_client):
    response = auth_client.post("/api/v1/me/2fa/enable", {"code": "123456"}, format="json")
    assert response.json()["error"]["code"] == "two_factor_not_setup"


def test_verify_session_after_new_login(make_client):
    account = AccountFactory()
    secret = enable_2fa(make_client(account))
    client = APIClient()
    client.post("/api/v1/auth/login", {"email": account.email, "password": "Passw0rd!x"}, format="json")
    assert client.get("/api/v1/me").json()["two_factor"]["verified"] is False
    wrong = client.post("/api/v1/auth/2fa/verify", {"code": "111111"}, format="json")
    assert wrong.status_code == 400
    ok = client.post("/api/v1/auth/2fa/verify", {"code": next_code(secret)}, format="json")
    assert ok.status_code == 200 and ok.json()["verified"] is True


def test_code_cannot_be_reused(make_client):
    account = AccountFactory()
    client = make_client(account)
    secret = client.post("/api/v1/me/2fa/setup").json()["secret"]
    code = pyotp.TOTP(secret).now()
    assert client.post("/api/v1/me/2fa/enable", {"code": code}, format="json").status_code == 200
    replay = make_client(account).post("/api/v1/auth/2fa/verify", {"code": code}, format="json")
    assert replay.status_code == 400


def test_verify_without_enabled_2fa(auth_client):
    response = auth_client.post("/api/v1/auth/2fa/verify", {"code": "123456"}, format="json")
    assert response.json()["error"]["code"] == "two_factor_not_enabled"


def test_too_many_wrong_codes_lock_out(auth_client):
    auth_client.post("/api/v1/me/2fa/setup")
    for _ in range(10):
        auth_client.post("/api/v1/me/2fa/enable", {"code": "000000"}, format="json")
    response = auth_client.post("/api/v1/me/2fa/enable", {"code": "000000"}, format="json")
    assert response.status_code == 429


def test_disable_requires_code_and_clears_session_flag(auth_client):
    secret = enable_2fa(auth_client)
    assert auth_client.post("/api/v1/me/2fa/disable", {"code": "000000"}, format="json").status_code == 400
    response = auth_client.post("/api/v1/me/2fa/disable", {"code": next_code(secret)}, format="json")
    assert response.status_code == 200
    assert response.json() == {"enabled": False, "verified": False, "required": False}
    account = Account.objects.get(pk=auth_client.account.pk)
    assert account.totp_secret == "" and not account.totp_enabled
    assert OTP_SESSION_KEY not in auth_client.session


# --- служебные роли ---------------------------------------------------------------------------------------

ROLES = "/api/v1/staff/roles"


def admin_client(make_client, two_factor=True):
    return make_client(make_moderator(AccountFactory(), role=StaffRole.Role.ADMIN), two_factor=two_factor)


def test_staff_roles_require_admin_with_2fa(make_client, api_client):
    assert api_client.get(ROLES).status_code == 401
    assert make_client().get(ROLES).status_code == 403
    moderator = make_moderator(AccountFactory())
    assert make_client(moderator, two_factor=True).get(ROLES).status_code == 403
    assert admin_client(make_client, two_factor=False).get(ROLES).status_code == 403
    assert admin_client(make_client).get(ROLES).status_code == 200


def test_admin_grants_and_revokes_moderator_with_audit(make_client):
    client = admin_client(make_client)
    target = AccountFactory(email="mod@example.com")
    granted = client.post(ROLES, {"account_email": "MOD@example.com", "role": "moderator"}, format="json")
    assert granted.status_code == 201, granted.json()
    role_id = granted.json()["id"]
    assert granted.json()["account"]["id"] == str(target.pk)
    assert StaffRole.objects.filter(account=target, role="moderator", revoked_at__isnull=True).exists()
    assert AuditEvent.objects.filter(action="staff_role.granted").exists()
    listed = client.get(ROLES).json()
    assert str(target.pk) in {r["account"]["id"] for r in listed}
    duplicate = client.post(ROLES, {"account_email": "mod@example.com", "role": "moderator"}, format="json")
    assert duplicate.status_code == 409
    revoked = client.delete(f"{ROLES}/{role_id}")
    assert revoked.status_code == 200 and revoked.json()["revoked_at"]
    assert AuditEvent.objects.filter(action="staff_role.revoked").exists()
    assert client.delete(f"{ROLES}/{role_id}").status_code == 404
    # История сохраняется.
    assert client.get(ROLES, {"include_revoked": "1"}).json()[0]["revoked_at"]


def test_revoke_by_email_and_role(make_client):
    client = admin_client(make_client)
    target = make_moderator(AccountFactory(email="m2@example.com"))
    response = client.delete(ROLES, {"account_email": "m2@example.com", "role": "moderator"}, format="json")
    assert response.status_code == 200
    assert not StaffRole.objects.filter(account=target, revoked_at__isnull=True).exists()


def test_grant_to_unknown_email_is_404(make_client):
    response = admin_client(make_client).post(ROLES, {"account_email": "x@nowhere.ru", "role": "moderator"},
                                              format="json")
    assert response.status_code == 404


def test_admin_cannot_revoke_own_admin_role(make_client):
    client = admin_client(make_client)
    own = StaffRole.objects.get(account=client.account, role="admin")
    response = client.delete(f"{ROLES}/{own.pk}")
    assert response.status_code == 400


def test_moderator_endpoint_requires_2fa_in_session(make_client):
    """Модераторская роль работает только с 2FA в текущей сессии (IsModerator)."""
    from rest_framework.test import APIRequestFactory

    from apps.common.permissions import IsModerator

    moderator = make_moderator(AccountFactory())
    request = APIRequestFactory().get("/")
    request.user = moderator
    request.session = {}
    assert IsModerator().has_permission(request, None) is False
    request.session = {OTP_SESSION_KEY: "x"}
    assert IsModerator().has_permission(request, None) is True
