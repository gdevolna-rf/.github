"""Сертификаты (INS-03/04, TRUST-03, BR-07, F04, ATX-05, ATX-23): загрузка → модерация, закрытый скан."""
import datetime as dt

import pytest
from django.utils import timezone

from apps.learning.models import InstructorCertificate
from apps.mediafiles.models import MediaAsset
from apps.trust.models import AuditEvent, ModerationCase
from tests.factories import make_moderator

from .helpers import (
    AccountFactory,
    certificate,
    gallery_media,
    instructor_account,
    private_document,
    published_instructor,
)

pytestmark = pytest.mark.django_db
ME = "/api/v1/me/instructor/certificates"


@pytest.fixture
def owner(make_client):
    profile = published_instructor(instructor_account())
    client = make_client(profile.account)
    client.profile = profile
    return client


def test_upload_creates_uploaded_certificate_and_moderation_case(owner, api_client):
    document = private_document(owner.account)
    response = owner.post(ME, {"title": "ISA Instructor", "issuer": "ISA", "issued_on": "2024-05-01",
                               "valid_until": "2030-05-01", "document_id": str(document.pk)}, format="json")
    assert response.status_code == 201, response.content
    data = response.json()
    assert data["status"] == "uploaded" and data["document"]["url"] is None  # закрытый файл без прямой ссылки
    cert = InstructorCertificate.objects.get(pk=data["id"])
    case = ModerationCase.objects.get(certificate=cert)
    assert case.kind == ModerationCase.Kind.CERTIFICATE and case.status == ModerationCase.Status.OPEN
    assert AuditEvent.objects.filter(action="certificate.uploaded", object_id=str(cert.pk)).exists()
    # ATX-05: до решения модератора значка «проверен» нет
    card = api_client.get("/api/v1/instructors").json()["results"][0]
    assert card["certificate_status"] == "uploaded"


def test_badge_verified_only_after_moderator_decision(owner, api_client):
    """F04: после решения модератора статус «проверен» на публичной карточке."""
    cert = certificate(owner.profile)
    handle = owner.account.profile.handle
    assert api_client.get(f"/api/v1/instructors/{handle}").json()["certificate_status"] == "uploaded"
    cert.status = InstructorCertificate.Status.VERIFIED  # решение принимает trust (moderation/certificates/approve)
    cert.decided_at = timezone.now()
    cert.save()
    assert api_client.get(f"/api/v1/instructors/{handle}").json()["certificate_status"] == "verified"


@pytest.mark.parametrize("make_doc,code", [
    (lambda acc: gallery_media(acc, kind=MediaAsset.Kind.DOCUMENT, purpose=MediaAsset.Purpose.CERTIFICATE),
     "certificate_must_be_private"),
    (lambda acc: gallery_media(acc), "media_purpose"),
    (lambda acc: private_document(AccountFactory()), "media_invalid"),
])
def test_upload_rejects_unsuitable_documents(owner, make_doc, code):
    document = make_doc(owner.account)
    response = owner.post(ME, {"title": "x", "document_id": str(document.pk)}, format="json")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == code


def test_upload_validates_dates_and_duplicates(owner):
    document = private_document(owner.account)
    future = (timezone.localdate() + dt.timedelta(days=5)).isoformat()
    bad = owner.post(ME, {"title": "x", "document_id": str(document.pk), "issued_on": future}, format="json")
    assert "issued_on" in bad.json()["error"]["fields"]
    reversed_dates = owner.post(ME, {"title": "x", "document_id": str(document.pk), "issued_on": "2024-01-01",
                                     "valid_until": "2023-01-01"}, format="json")
    assert "valid_until" in reversed_dates.json()["error"]["fields"]
    assert owner.post(ME, {"title": "x", "document_id": str(document.pk)}, format="json").status_code == 201
    assert owner.post(ME, {"title": "y", "document_id": str(document.pk)}, format="json").status_code == 409


def test_list_patch_delete_own_certificates(owner, make_client):
    cert = certificate(owner.profile)
    listing = owner.get(ME).json()
    assert [c["id"] for c in listing] == [str(cert.pk)]
    patched = owner.patch(f"{ME}/{cert.pk}", {"allow_public_scan": True}, format="json").json()
    assert patched["allow_public_scan"] is True
    assert AuditEvent.objects.filter(action="certificate.scan_visibility_changed").exists()
    stranger = make_client(instructor_account())
    published_instructor(stranger.account)
    assert stranger.get(f"{ME}/{cert.pk}").status_code == 404
    assert stranger.delete(f"{ME}/{cert.pk}").status_code == 404
    assert owner.delete(f"{ME}/{cert.pk}").status_code == 204
    assert not InstructorCertificate.objects.filter(pk=cert.pk).exists()
    assert AuditEvent.objects.filter(action="certificate.deleted", object_id=str(cert.pk)).exists()


def scan(client, cert):
    return client.get(f"/api/v1/certificates/{cert.pk}/scan")


def test_scan_access_rules(owner, api_client, make_client):
    """ATX-23: по угаданному URL документа не получить; доступ — владелец, модератор с 2FA, публично по разрешению."""
    cert = certificate(owner.profile)
    response = scan(owner, cert)
    assert response.status_code == 200
    assert "X-Amz-Signature" in response.json()["url"] and response.json()["expires_in"] > 0
    assert scan(api_client, cert).status_code == 404
    assert scan(make_client(), cert).status_code == 404
    moderator = make_moderator(AccountFactory())
    assert scan(make_client(moderator), cert).status_code == 404  # без 2FA в сессии
    assert scan(make_client(moderator, two_factor=True), cert).status_code == 200
    assert AuditEvent.objects.filter(action="certificate.scan_viewed", object_id=str(cert.pk)).exists()


def test_public_scan_only_when_verified_and_allowed(owner, api_client):
    cert = certificate(owner.profile, status=InstructorCertificate.Status.VERIFIED, allow_public_scan=False)
    assert scan(api_client, cert).status_code == 404
    cert.allow_public_scan = True
    cert.save()
    assert scan(api_client, cert).status_code == 200
    cert.valid_until = timezone.localdate() - dt.timedelta(days=1)
    cert.save()
    assert scan(api_client, cert).status_code == 404
    unknown = scan(api_client, type("X", (), {"pk": "00000000-0000-0000-0000-000000000000"})())
    assert unknown.status_code == 404


def test_scan_of_deleted_document_is_404(owner):
    cert = certificate(owner.profile)
    cert.document.status = MediaAsset.Status.DELETED
    cert.document.save()
    assert scan(owner, cert).status_code == 404


def test_certificate_endpoints_require_profile(make_client):
    client = make_client(instructor_account())
    document = private_document(client.account)
    response = client.post(ME, {"title": "x", "document_id": str(document.pk)}, format="json")
    assert response.status_code == 404
