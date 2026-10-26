"""Согласия, выгрузка данных и удаление аккаунта (ACC-13, TRUST-09, AT-10)."""
import datetime as dt
import json

import pytest
from django.core import mail
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Account, AccountDeletionRequest, ConsentRecord, DataExportRequest, UserProfile
from apps.accounts.serializers_public import PublicAccountSerializer
from apps.accounts.tasks import process_deletion_requests
from apps.commerce.models import Inquiry
from apps.mediafiles.models import MediaAsset
from apps.mediafiles.storage import get_storage
from apps.messaging.models import Conversation, Message, Notification
from apps.organizations.models import Membership, Organization
from apps.trust.models import AuditEvent
from tests.factories import AccountFactory, MediaAssetFactory, OrganizationFactory, add_member

pytestmark = pytest.mark.django_db


# --- согласия ---------------------------------------------------------------------------------------------

def test_consents_journal_and_current_state(auth_client):
    auth_client.post("/api/v1/me/consents", {"kind": "marketing", "granted": True}, format="json")
    response = auth_client.post("/api/v1/me/consents", {"kind": "marketing", "granted": False}, format="json")
    assert response.status_code == 201
    body = auth_client.get("/api/v1/me/consents").json()
    assert body["current"]["marketing"] is False
    assert [r["granted"] for r in body["history"] if r["kind"] == "marketing"] == [False, True]


def test_gg_consent_via_journal_syncs_profile(auth_client):
    auth_client.post("/api/v1/me/consents", {"kind": "gg_surfer", "granted": True}, format="json")
    assert UserProfile.objects.get(account=auth_client.account).gg_surfer_enabled is True
    auth_client.post("/api/v1/me/consents", {"kind": "gg_surfer", "granted": False}, format="json")
    assert UserProfile.objects.get(account=auth_client.account).gg_surfer_enabled is False


def test_required_consents_cannot_be_withdrawn(auth_client):
    response = auth_client.post("/api/v1/me/consents", {"kind": "privacy", "granted": False}, format="json")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "consent_required"


def test_guardian_consent_not_managed_here(auth_client):
    response = auth_client.post("/api/v1/me/consents", {"kind": "guardian", "granted": True}, format="json")
    assert response.status_code == 400


def test_consent_record_stores_ip_and_user_agent(auth_client):
    auth_client.post("/api/v1/me/consents", {"kind": "geolocation", "granted": True}, format="json",
                     HTTP_USER_AGENT="Surf/1.0", HTTP_X_FORWARDED_FOR="203.0.113.7, 10.0.0.1")
    record = ConsentRecord.objects.get(account=auth_client.account, kind="geolocation")
    assert record.ip == "203.0.113.7" and record.user_agent == "Surf/1.0"


# --- выгрузка ---------------------------------------------------------------------------------------------

def _inquiry_with_message(customer):
    provider = AccountFactory()
    inquiry = Inquiry.objects.create(kind="general", customer=customer, provider_account=provider, subject="Вопрос")
    conversation = Conversation.objects.create(inquiry=inquiry)
    Message.objects.create(conversation=conversation, sender=customer, body="Моё сообщение")
    Message.objects.create(conversation=conversation, sender=provider, body="Чужое сообщение")
    return inquiry


def test_data_export_builds_private_json_and_notifies(auth_client, run_on_commit):
    _inquiry_with_message(auth_client.account)
    response = run_on_commit(auth_client.post, "/api/v1/me/exports")
    assert response.status_code == 202
    export = DataExportRequest.objects.get(account=auth_client.account)
    assert export.status == DataExportRequest.Status.READY
    asset = export.file
    assert asset.purpose == "data_export" and asset.visibility == "private" and asset.owner == auth_client.account
    assert asset.storage_key.startswith("private/data_export/")
    data = json.loads(get_storage().read(asset.storage_key))
    assert data["account"]["email"] == auth_client.account.email
    assert {"profile", "specialties", "memberships", "inquiries", "messages", "bookings", "reviews", "favorites",
            "diary", "consents"} <= set(data)
    assert [m["body"] for m in data["messages"]] == ["Моё сообщение"]  # только свои сообщения
    assert len(data["inquiries"]) == 1
    notification = Notification.objects.get(recipient=auth_client.account, kind="system")
    assert notification.link == "/account/settings"
    listed = auth_client.get("/api/v1/me/exports").json()
    assert listed[0]["status"] == "ready" and listed[0]["file"]["id"] == str(asset.pk)
    # Скачивание — только владельцу.
    assert auth_client.get(f"/api/v1/media/{asset.pk}/url").status_code == 200
    assert APIClient().get(f"/api/v1/media/{asset.pk}/url").status_code == 404


def test_second_export_while_pending_is_conflict(auth_client):
    assert auth_client.post("/api/v1/me/exports").status_code == 202  # задача не выполнена (on_commit)
    response = auth_client.post("/api/v1/me/exports")
    assert response.status_code == 409


# --- удаление ---------------------------------------------------------------------------------------------

def test_deletion_request_and_cancel(auth_client, run_on_commit, settings):
    response = run_on_commit(auth_client.post, "/api/v1/me/deletion", {"reason": "Уезжаю"}, format="json")
    assert response.status_code == 202
    body = response.json()
    assert body["pending"] is True and body["grace_days"] == settings.ACCOUNT_DELETION_GRACE_DAYS
    scheduled = dt.datetime.fromisoformat(body["request"]["scheduled_for"])
    assert (scheduled - timezone.now()).days in (settings.ACCOUNT_DELETION_GRACE_DAYS - 1,
                                                 settings.ACCOUNT_DELETION_GRACE_DAYS)
    assert len(mail.outbox) == 1 and "/account/settings" in mail.outbox[0].body
    assert auth_client.get("/api/v1/me").json()["deletion"]["scheduled_for"]
    # Повторный запрос возвращает тот же.
    again = auth_client.post("/api/v1/me/deletion", {}, format="json")
    assert again.json()["request"]["id"] == body["request"]["id"]
    cancelled = auth_client.delete("/api/v1/me/deletion")
    assert cancelled.status_code == 200 and cancelled.json()["pending"] is False
    assert Account.objects.get(pk=auth_client.account.pk).deletion_requested_at is None
    assert auth_client.delete("/api/v1/me/deletion").status_code == 404


def test_owner_with_team_must_transfer_ownership_first(make_client):
    org = OrganizationFactory()
    add_member(org, AccountFactory())
    response = make_client(org.owner).post("/api/v1/me/deletion", {}, format="json")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "ownership_transfer_required"


def test_deletion_is_processed_only_after_grace_period(auth_client):
    auth_client.post("/api/v1/me/deletion", {}, format="json")
    assert process_deletion_requests() == 0
    assert Account.objects.get(pk=auth_client.account.pk).anonymized_at is None


def test_anonymization_keeps_orders_and_hides_personal_data(make_client, run_on_commit):
    """AT-10: необходимые записи сохраняются, личные данные недоступны."""
    account = AccountFactory(email="leaving@example.com")
    avatar = MediaAssetFactory(owner=account, purpose="avatar")
    get_storage().write(avatar.storage_key, b"x", "image/jpeg")
    UserProfile.objects.filter(account=account).update(phone="+70000000000", bio="о себе", gg_surfer_enabled=True,
                                                       avatar=avatar, birth_date=dt.date(1990, 1, 1))
    handle = account.profile.handle
    client = make_client(account)
    client.patch("/api/v1/me", {"handle": "leaving-rider"}, format="json")
    inquiry = _inquiry_with_message(account)
    solo_org = OrganizationFactory(owner=account)
    other_org = OrganizationFactory()
    add_member(other_org, account)
    client.post("/api/v1/me/deletion", {}, format="json")
    AccountDeletionRequest.objects.filter(account=account).update(scheduled_for=timezone.now() - dt.timedelta(minutes=1))

    assert run_on_commit(process_deletion_requests) == 1

    account.refresh_from_db()
    assert account.email.startswith("deleted-") and account.email.endswith("@deleted.local")
    assert not account.is_active and not account.has_usable_password() and account.anonymized_at
    profile = UserProfile.objects.get(account=account)
    assert profile.first_name == profile.last_name == profile.phone == profile.bio == ""
    assert profile.birth_date is None and profile.avatar is None and not profile.gg_surfer_enabled
    assert profile.handle.startswith("deleted-")
    assert MediaAsset.objects.get(pk=avatar.pk).status == "deleted"
    assert get_storage().head(avatar.storage_key) is None
    # Обязательные записи на месте и ссылаются на тот же id.
    assert Inquiry.objects.filter(pk=inquiry.pk, customer=account).exists()
    assert Message.objects.filter(sender=account).count() == 1
    assert AuditEvent.objects.filter(action="account.anonymized", object_id=str(account.pk)).exists()
    # Публично — «Удалённый пользователь», профиль и старые handle не находятся.
    assert PublicAccountSerializer(account).data["display_name"] == "Удалённый пользователь"
    api = APIClient()
    assert api.get(f"/api/v1/profiles/{handle}").status_code == 404
    assert api.get("/api/v1/profiles/leaving-rider").status_code == 404
    assert api.post("/api/v1/auth/login", {"email": "leaving@example.com", "password": "Passw0rd!x"},
                    format="json").status_code == 400
    assert client.get("/api/v1/me").status_code == 401
    # Организация без команды архивируется, членства закрыты.
    assert Organization.objects.get(pk=solo_org.pk).status == Organization.Status.ARCHIVED
    assert not Membership.objects.filter(account=account, status="active").exists()
    assert AccountDeletionRequest.objects.get(account=account).status == "completed"


def test_ownership_passes_to_manager_if_team_appeared_during_grace(make_client):
    org = OrganizationFactory()
    owner = org.owner
    make_client(owner).post("/api/v1/me/deletion", {}, format="json")
    manager = AccountFactory()
    add_member(org, manager, Membership.Role.MANAGER)
    AccountDeletionRequest.objects.filter(account=owner).update(scheduled_for=timezone.now())
    process_deletion_requests()
    org.refresh_from_db()
    assert org.owner == manager and org.status == Organization.Status.PUBLISHED
    assert Membership.objects.get(organization=org, account=manager, status="active").role == "owner"
