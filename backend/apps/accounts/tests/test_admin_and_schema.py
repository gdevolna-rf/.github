"""Django Admin моделей identity открывается без ошибок; OpenAPI-схема содержит эндпоинты приложений."""
import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import (
    AccountDeletionRequest,
    ConsentRecord,
    DataExportRequest,
    HandleRedirect,
    StaffRole,
)
from apps.accounts.services.roles import OTP_SESSION_KEY
from apps.organizations.models import OrganizationInvite
from tests.factories import AccountFactory, MediaAssetFactory, OrganizationFactory, add_member

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_client_2fa():
    account = AccountFactory(is_staff=True, is_superuser=True)
    client = Client()
    client.force_login(account)
    session = client.session
    session[OTP_SESSION_KEY] = "test"
    session.save()
    client.account = account
    return client


def test_admin_pages_render(admin_client_2fa):
    account = AccountFactory()
    org = OrganizationFactory(owner=account)
    membership = add_member(org, AccountFactory())
    media = MediaAssetFactory(owner=account)
    StaffRole.objects.create(account=account, role="moderator")
    HandleRedirect.objects.create(old_handle="old-one", account=account)
    ConsentRecord.objects.create(account=account, kind="terms", granted=True)
    DataExportRequest.objects.create(account=account)
    AccountDeletionRequest.objects.create(account=account, scheduled_for="2099-01-01T00:00:00Z")
    invite = OrganizationInvite.objects.create(organization=org, email="x@example.com", role="staff", token="t",
                                               invited_by=account, expires_at="2099-01-01T00:00:00Z")
    objects = {
        "accounts_account": account, "accounts_userprofile": account.profile, "accounts_specialty": None,
        "accounts_userspecialty": account.specialties.first(), "accounts_staffrole": StaffRole.objects.first(),
        "accounts_handleredirect": HandleRedirect.objects.first(), "accounts_consentrecord": ConsentRecord.objects.first(),
        "accounts_dataexportrequest": DataExportRequest.objects.first(),
        "accounts_accountdeletionrequest": AccountDeletionRequest.objects.first(),
        "organizations_organization": org, "organizations_membership": membership,
        "organizations_organizationinvite": invite, "mediafiles_mediaasset": media,
    }
    for name, obj in objects.items():
        changelist = admin_client_2fa.get(reverse(f"admin:{name}_changelist"))
        assert changelist.status_code == 200, name
        if obj is not None:
            change = admin_client_2fa.get(reverse(f"admin:{name}_change", args=[obj.pk]))
            assert change.status_code == 200, name
    assert admin_client_2fa.get(reverse("admin:accounts_account_add")).status_code == 200
    assert admin_client_2fa.get(reverse("admin:accounts_consentrecord_add")).status_code == 403


def test_admin_creates_account_with_lowercased_email(admin_client_2fa):
    response = admin_client_2fa.post(reverse("admin:accounts_account_add"), {
        "email": "New.Staff@Example.com", "password1": "Volna-2026-secure", "password2": "Volna-2026-secure",
        "usable_password": "true",
    })
    assert response.status_code == 302, response.content.decode()[:2000]
    from apps.accounts.models import Account

    created = Account.objects.get(email="new.staff@example.com")
    assert created.profile.handle.startswith("new-staff")
    assert created.specialties.filter(specialty_id="surfer", status="active").exists()


def test_openapi_schema_contains_identity_endpoints():
    from drf_spectacular.generators import SchemaGenerator

    schema = SchemaGenerator().get_schema(request=None, public=True)
    paths = set(schema["paths"])
    expected = {
        "/api/v1/auth/register", "/api/v1/auth/login", "/api/v1/auth/2fa/verify", "/api/v1/me",
        "/api/v1/me/specialties/{code}", "/api/v1/me/consents", "/api/v1/me/exports", "/api/v1/me/deletion",
        "/api/v1/profiles/{handle}", "/api/v1/staff/roles", "/api/v1/organizations",
        "/api/v1/organizations/{slug}", "/api/v1/organizations/{id}/manage", "/api/v1/organizations/{id}/members",
        "/api/v1/organizations/{id}/invites", "/api/v1/invites/{token}/accept", "/api/v1/me/invites",
        "/api/v1/media/uploads", "/api/v1/media/{id}/complete", "/api/v1/media/{id}/url",
    }
    missing = {p for p in expected if p not in paths and p.replace("{id}", "{pk}") not in paths}
    assert not missing, missing
