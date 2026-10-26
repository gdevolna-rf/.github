"""Очередь модерации, сертификаты (BR-07, F04, ATX-05), организации, отзывы-hide, журнал, статистика."""
import datetime as dt
import uuid

import pytest
from django.utils import timezone

from apps.analytics.services import track
from apps.messaging.models import Notification
from apps.organizations.models import Organization
from apps.trust.models import AuditEvent, ModerationCase, Review
from apps.trust.services.moderation_queue import open_case
from apps.trust.tests.helpers import certificate
from tests.factories import (
    AccountFactory,
    InstructorProfileFactory,
    OrganizationFactory,
    SpotFactory,
    add_member,
    make_moderator,
)

pytestmark = pytest.mark.django_db


def test_queue_requires_moderator_with_2fa(api_client, make_client):
    for client, expected in ((api_client, 401), (make_client(), 403), (make_client(make_moderator(AccountFactory())), 403)):
        assert client.get("/api/v1/moderation/cases").status_code == expected
        assert client.get("/api/v1/moderation/audit").status_code == expected
        assert client.get("/api/v1/moderation/stats").status_code == expected


def test_case_list_filters_by_kind_status_and_overdue(mod_client):
    org = OrganizationFactory(status=Organization.Status.PENDING_REVIEW)
    org_case = open_case("organization", "Школа на проверке", organization=org)
    instructor = InstructorProfileFactory()
    cert_case = open_case("certificate", "Сертификат", certificate=certificate(instructor))
    ModerationCase.objects.filter(pk=cert_case.pk).update(due_at=timezone.now() - dt.timedelta(hours=1))
    resolved = open_case("organization", "Старая", organization=OrganizationFactory())
    ModerationCase.objects.filter(pk=resolved.pk).update(status="resolved", resolved_at=timezone.now())

    def ids(query=""):
        response = mod_client.get(f"/api/v1/moderation/cases{query}")
        assert response.status_code == 200, response.json()
        return [c["id"] for c in response.json()["results"]]

    assert ids() == [str(cert_case.id), str(org_case.id)]  # по сроку SLA
    assert ids("?kind=organization") == [str(org_case.id)]
    assert ids("?status=resolved") == [str(resolved.id)]
    assert ids("?overdue=true") == [str(cert_case.id)]
    assert len(ids("?status=all")) == 3
    item = mod_client.get("/api/v1/moderation/cases?kind=certificate").json()["results"][0]
    assert item["is_overdue"] is True and item["target_id"] == str(cert_case.certificate_id)
    assert mod_client.get("/api/v1/moderation/cases?kind=bogus").status_code == 400


def test_take_case_assigns_moderator(mod_client, moderator):
    case = open_case("organization", "x", organization=OrganizationFactory(status="pending_review"))
    response = mod_client.post(f"/api/v1/moderation/cases/{case.id}/take")
    assert response.status_code == 200 and response.json()["status"]["code"] == "in_review"
    assert mod_client.get("/api/v1/moderation/cases?assigned=me").json()["count"] == 1


# --- сертификаты --------------------------------------------------------------------------------

def test_certificate_badge_only_after_moderator_approval(mod_client, moderator, api_client):
    """BR-07 / F04 / ATX-05."""
    instructor = InstructorProfileFactory()
    cert = certificate(instructor)
    case = open_case("certificate", "Сертификат", certificate=cert)
    assert instructor.certificate_status == "uploaded"
    detail = mod_client.get(f"/api/v1/moderation/cases/{case.id}").json()
    doc = detail["target"]["document"]
    assert doc["url"] is None and "X-Amz-Signature" in doc["signed_url"]
    assert detail["available_actions"] == ["approve", "reject"]
    assert AuditEvent.objects.filter(action="certificate.scan_viewed", object_id=str(cert.id)).exists()

    response = mod_client.post(f"/api/v1/moderation/certificates/{cert.id}/approve", {}, format="json")
    assert response.status_code == 200 and response.json()["status"]["code"] == "verified"
    cert.refresh_from_db()
    assert cert.moderator == moderator and cert.decided_at
    assert instructor.certificate_status == "verified"
    case.refresh_from_db()
    assert case.status == "resolved"
    assert Notification.objects.filter(recipient=instructor.account, kind="certificate_decision").exists()
    assert AuditEvent.objects.filter(action="certificate.verified").exists()
    assert mod_client.post(f"/api/v1/moderation/certificates/{cert.id}/approve", {}, format="json").status_code == 409


def test_certificate_reject_requires_note_and_revoke_removes_badge(mod_client):
    instructor = InstructorProfileFactory()
    cert = certificate(instructor)
    assert mod_client.post(f"/api/v1/moderation/certificates/{cert.id}/reject", {}, format="json").status_code == 400
    response = mod_client.post(f"/api/v1/moderation/certificates/{cert.id}/reject", {"note": "Нечитаемый скан"},
                               format="json")
    assert response.status_code == 200 and response.json()["status"]["code"] == "rejected"
    assert instructor.certificate_status == "none"
    verified = certificate(instructor, status="verified")
    response = mod_client.post(f"/api/v1/moderation/certificates/{verified.id}/revoke", {"note": "Истёк"}, format="json")
    assert response.status_code == 200 and instructor.certificate_status == "none"


def test_moderator_cannot_verify_own_certificate(make_client):
    instructor = InstructorProfileFactory()
    make_moderator(instructor.account)
    cert = certificate(instructor)
    client = make_client(instructor.account, two_factor=True)
    response = client.post(f"/api/v1/moderation/certificates/{cert.id}/approve", {}, format="json")
    assert response.status_code == 403 and response.json()["error"]["code"] == "self_moderation"


# --- организации ---------------------------------------------------------------------------------

def test_organization_approve_publishes_and_verifies(mod_client):
    org = OrganizationFactory(status=Organization.Status.PENDING_REVIEW, verification_status="pending")
    case = open_case("organization", "Школа", organization=org)
    detail = mod_client.get(f"/api/v1/moderation/cases/{case.id}").json()
    assert detail["target"]["type"] == "organization" and detail["target"]["name"] == org.name
    response = mod_client.post(f"/api/v1/moderation/organizations/{org.id}/approve", {"note": "ok"}, format="json")
    assert response.status_code == 200
    org.refresh_from_db()
    assert (org.status, org.verification_status) == ("published", "verified") and org.published_at
    case.refresh_from_db()
    assert case.status == "resolved"
    assert Notification.objects.filter(recipient=org.owner, link=f"/account/orgs/{org.id}/profile").exists()
    audit = AuditEvent.objects.get(action="organization.published")
    assert audit.organization_id == org.id


def test_organization_reject_returns_to_draft_with_note(mod_client):
    org = OrganizationFactory(status=Organization.Status.PENDING_REVIEW)
    assert mod_client.post(f"/api/v1/moderation/organizations/{org.id}/reject", {}, format="json").status_code == 400
    response = mod_client.post(f"/api/v1/moderation/organizations/{org.id}/reject", {"note": "Нет адреса"}, format="json")
    assert response.status_code == 200
    org.refresh_from_db()
    assert org.status == "draft" and org.moderation_note == "Нет адреса" and org.verification_status == "rejected"
    assert mod_client.post(f"/api/v1/moderation/organizations/{org.id}/approve", {}, format="json").status_code == 409


def test_moderator_member_cannot_approve_own_organization(make_client):
    org = OrganizationFactory(status=Organization.Status.PENDING_REVIEW)
    moderator = make_moderator(AccountFactory())
    add_member(org, moderator)
    response = make_client(moderator, two_factor=True).post(f"/api/v1/moderation/organizations/{org.id}/approve")
    assert response.status_code == 403


# --- отзывы: скрытие ---------------------------------------------------------------------------

def test_hide_published_review_recalculates_rating(mod_client):
    spot = SpotFactory()
    keep = Review.objects.create(author=AccountFactory(), target_type="spot", spot=spot, rating=5, status="published")
    bad = Review.objects.create(author=AccountFactory(), target_type="spot", spot=spot, rating=1, status="published")
    from apps.trust.services.ratings import recalculate

    recalculate("spot", spot.id)
    spot.refresh_from_db()
    assert spot.rating_count == 2
    assert mod_client.post(f"/api/v1/moderation/reviews/{bad.id}/hide", {}, format="json").status_code == 400
    response = mod_client.post(f"/api/v1/moderation/reviews/{bad.id}/hide", {"note": "Оскорбления"}, format="json")
    assert response.status_code == 200 and response.json()["status"]["code"] == "hidden"
    spot.refresh_from_db()
    assert (str(spot.rating_avg), spot.rating_count) == ("5.00", 1)
    assert mod_client.post(f"/api/v1/moderation/reviews/{bad.id}/hide", {"note": "x"}, format="json").status_code == 409
    assert mod_client.post(f"/api/v1/moderation/reviews/{keep.id}/approve", {}, format="json").status_code == 409


def test_review_case_detail_contains_text_author_and_target(mod_client):
    spot = SpotFactory(name="Халактыр")
    review = Review.objects.create(author=AccountFactory(), target_type="spot", spot=spot, rating=4, text="Волна!")
    case = open_case("review", "Отзыв", review=review)
    target = mod_client.get(f"/api/v1/moderation/cases/{case.id}").json()["target"]
    assert target["type"] == "review" and target["text"] == "Волна!" and target["rating"] == 4
    assert target["target"]["name"] == "Халактыр" and target["author"]["display_name"]


# --- журнал и статистика -----------------------------------------------------------------------

def test_audit_list_filters(mod_client, moderator):
    from apps.trust.services.audit import record

    spot = SpotFactory()
    record(moderator, "spot.change_approved", spot, before={"a": 1}, after={"a": 2})
    record(AccountFactory(), "review.published", object_type="trust.review", object_id=str(uuid.uuid4()))
    data = mod_client.get(f"/api/v1/moderation/audit?object_type=spots.spot&object_id={spot.id}").json()
    assert data["count"] == 1 and data["results"][0]["before"] == {"a": 1}
    assert data["results"][0]["actor"]["id"] == str(moderator.id)
    assert mod_client.get(f"/api/v1/moderation/audit?actor={moderator.id}").json()["count"] == 1
    assert mod_client.get("/api/v1/moderation/audit?action=review.published").json()["count"] == 1
    assert mod_client.get("/api/v1/moderation/audit?action_prefix=spot.").json()["count"] == 1
    assert mod_client.get("/api/v1/moderation/audit?actor=not-a-uuid").status_code == 400


def test_stats_open_overdue_and_median_hours(mod_client):
    open_case("organization", "a", organization=OrganizationFactory(status="pending_review"))
    late = open_case("organization", "b", organization=OrganizationFactory(status="pending_review"))
    ModerationCase.objects.filter(pk=late.pk).update(due_at=timezone.now() - dt.timedelta(hours=2))
    for i, hours in enumerate((1.0, 3.0, 10.0)):
        track("spot_proposal_reviewed", subject_type="spot_change_request", subject_id=uuid.uuid4(),
              context={"hours_from_submitted": hours, "decision": "approved" if i else "rejected"})
    data = mod_client.get("/api/v1/moderation/stats").json()
    assert data["open_cases"]["total"] == 2 and data["open_cases"]["by_kind"]["organization"] == 2
    assert data["open_cases"]["by_kind"]["review"] == 0
    assert data["overdue_cases"]["total"] == 1
    assert data["spot_proposals"]["median_hours_to_decision"] == 3.0
    assert data["spot_proposals"]["decided"] == 3 and data["spot_proposals"]["rejected"] == 1
