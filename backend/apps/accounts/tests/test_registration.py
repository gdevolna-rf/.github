"""Регистрация (ATX-01, ACC-01, 5.3): один UUID, профиль, направления, согласия, письмо, вход."""
import re

import pytest
from django.core import mail

from apps.accounts.models import Account, ConsentRecord, UserSpecialty
from apps.organizations.models import OrganizationInvite
from tests.factories import AccountFactory, OrganizationFactory

pytestmark = pytest.mark.django_db

URL = "/api/v1/auth/register"


def payload(**overrides):
    data = {
        "email": "Ivan.Petrov@Example.com",
        "password": "Volna-2026-secure",
        "first_name": "Иван",
        "last_name": "Петров",
        "primary_type": "surfer",
        "extra_specialties": [],
        "accept_terms": True,
        "accept_privacy": True,
    }
    data.update(overrides)
    return data


def register(client, run_on_commit, **overrides):
    return run_on_commit(client.post, URL, payload(**overrides), format="json")


def test_register_surfer_creates_account_profile_and_logs_in(api_client, run_on_commit):
    response = register(api_client, run_on_commit)
    assert response.status_code == 201, response.json()
    body = response.json()
    account = Account.objects.get(email="ivan.petrov@example.com")
    assert body["id"] == str(account.pk)
    assert body["email"] == "ivan.petrov@example.com"
    assert body["email_verified"] is False
    assert body["next_step"] is None
    assert body["profile"]["handle"] == "ivan-petrov"
    assert body["profile"]["display_name"] == "Иван Петров"
    assert [(s["code"], s["status"], s["is_primary"]) for s in body["specialties"]] == [("surfer", "active", True)]
    assert {s["code"] for s in body["available_specialties"]} == {"surfer", "instructor", "shaper", "rental"}
    assert body["two_factor"] == {"enabled": False, "verified": False, "required": False}
    # Сессия создана — /me доступен тем же клиентом.
    assert api_client.get("/api/v1/me").json()["id"] == str(account.pk)
    kinds = set(ConsentRecord.objects.filter(account=account, granted=True).values_list("kind", flat=True))
    assert kinds == {"terms", "privacy"}


def test_register_sends_verification_email_with_signed_link(api_client, run_on_commit, settings):
    register(api_client, run_on_commit)
    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.to == ["ivan.petrov@example.com"]
    match = re.search(rf"{re.escape(settings.SITE_URL)}/verify-email\?token=(\S+)", message.body)
    assert match
    response = api_client.post("/api/v1/auth/verify-email", {"token": match.group(1)}, format="json")
    assert response.status_code == 200
    assert Account.objects.get(email="ivan.petrov@example.com").is_email_verified


def test_register_with_several_specialties_keeps_single_account(api_client, run_on_commit):
    """ATX-01 / AT-02: один account.id и несколько направлений."""
    response = register(api_client, run_on_commit, primary_type="instructor", extra_specialties=["shaper", "rental"])
    assert response.status_code == 201
    account = Account.objects.get()
    rows = {us.specialty_id: us for us in UserSpecialty.objects.filter(account=account)}
    assert set(rows) == {"surfer", "instructor", "shaper", "rental"}
    assert rows["instructor"].is_primary and not rows["surfer"].is_primary
    assert all(us.status == "active" for us in rows.values())


def test_register_school_offers_to_create_organization(api_client, run_on_commit):
    response = register(api_client, run_on_commit, primary_type="school")
    body = response.json()
    assert body["next_step"] == "create_school"
    assert [s["code"] for s in body["specialties"]] == ["surfer"]
    assert body["specialties"][0]["is_primary"] is True


def test_register_requires_terms_and_privacy(api_client):
    response = api_client.post(URL, payload(accept_privacy=False), format="json")
    assert response.status_code == 400
    assert "accept_privacy" in response.json()["error"]["fields"]
    assert not Account.objects.exists()


def test_register_duplicate_email_case_insensitive(api_client):
    AccountFactory(email="ivan.petrov@example.com")
    response = api_client.post(URL, payload(email="IVAN.PETROV@example.com"), format="json")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "email_taken"


def test_register_rejects_weak_password(api_client):
    response = api_client.post(URL, payload(password="12345678"), format="json")
    assert response.status_code == 400
    assert "password" in response.json()["error"]["fields"]


def test_register_rejects_unknown_primary_type(api_client):
    response = api_client.post(URL, payload(primary_type="moderator"), format="json")
    assert response.status_code == 400


def test_register_rejects_staff_role_as_extra_specialty(api_client):
    """BR-04: админ/модератор не включаются пользовательским переключателем."""
    response = api_client.post(URL, payload(extra_specialties=["admin"]), format="json")
    assert response.status_code == 400
    assert not Account.objects.exists()


def test_same_names_get_unique_handles(api_client, run_on_commit):
    from rest_framework.test import APIClient

    register(api_client, run_on_commit)
    second = register(APIClient(), run_on_commit, email="other@example.com")
    assert second.json()["profile"]["handle"] == "ivan-petrov-2"


def test_reserved_name_does_not_produce_reserved_handle(api_client, run_on_commit):
    response = register(api_client, run_on_commit, first_name="Admin", last_name="")
    handle = response.json()["profile"]["handle"]
    assert handle != "admin" and handle.startswith("admin")


def test_pending_invites_for_email_are_attached_on_registration(api_client, run_on_commit):
    org = OrganizationFactory()
    invite = OrganizationInvite.objects.create(
        organization=org, email="ivan.petrov@example.com", role="instructor", token="tok-1", invited_by=org.owner,
        expires_at="2099-01-01T00:00:00Z",
    )
    register(api_client, run_on_commit)
    invite.refresh_from_db()
    assert invite.account == Account.objects.get(email="ivan.petrov@example.com")
    listed = api_client.get("/api/v1/me/invites").json()
    assert [i["id"] for i in listed] == [str(invite.pk)]


def test_register_enforces_csrf_for_browser_clients(run_on_commit):
    from rest_framework.test import APIClient

    client = APIClient(enforce_csrf_checks=True)
    response = client.post(URL, payload(), format="json")
    assert response.status_code == 403
    csrf = client.get("/api/v1/auth/csrf")
    token = csrf.json()["csrf_token"]
    assert "csrftoken" in csrf.cookies
    response = run_on_commit(client.post, URL, payload(), format="json", HTTP_X_CSRFTOKEN=token)
    assert response.status_code == 201
