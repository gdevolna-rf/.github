"""Решения по правкам спотов (7.4, TRUST-04, AT-07, F08, ATX-13) и права модератора (TRUST-06)."""
from unittest import mock

import pytest
from django.core.cache import cache

from apps.analytics.models import AnalyticsEvent
from apps.mediafiles.models import MediaAsset
from apps.messaging.models import Notification
from apps.spots.models import SpotChangeRequest, SpotPhoto, SpotSourceRecord
from apps.spots.services.catalog import MAP_CACHE_KEY
from apps.trust.models import AuditEvent, ModerationCase
from tests.factories import AccountFactory, MediaAssetFactory, SpotFactory, make_moderator

pytestmark = pytest.mark.django_db


@pytest.fixture
def spot():
    return SpotFactory(best_wind_directions=["N", "NW"], season="Лето", difficulty="intermediate")


@pytest.fixture
def author_client(make_client):
    return make_client()


def _propose(client, spot, changes=None, **extra):
    response = client.post(f"/api/v1/spots/{spot.id}/proposals",
                           {"changes": changes or {"best_wind_directions": ["W"]}, **extra}, format="json")
    assert response.status_code == 201, response.json()
    return response.json()["id"]


def _mod(client, pid, action, body=None):
    return client.post(f"/api/v1/moderation/proposals/{pid}/{action}", body or {}, format="json")


@pytest.mark.parametrize("action", ["approve", "reject", "request-info", "revert"])
def test_decisions_require_moderator_with_2fa(api_client, make_client, author_client, spot, action):
    pid = _propose(author_client, spot)
    plain_moderator = make_client(make_moderator(AccountFactory()), two_factor=False)
    response = _mod(api_client, pid, action, {"comment": "x"})
    assert response.status_code == 401, response.content
    assert response.json()["error"]["code"] == "not_authenticated"
    for client in (make_client(), author_client, plain_moderator):
        response = _mod(client, pid, action, {"comment": "x"})
        assert response.status_code == 403, (client, response.content)
    assert SpotChangeRequest.objects.get(pk=pid).status == "submitted"


def test_admin_role_implies_moderator(make_client, author_client, spot):
    admin = make_client(make_moderator(AccountFactory(), role="admin"), two_factor=True)
    pid = _propose(author_client, spot)
    assert _mod(admin, pid, "approve").status_code == 200


def test_approve_updates_spot_audit_case_notification_and_analytics(mod_client, moderator, author_client, api_client, spot):
    """AT-07 / F08 / ATX-13."""
    pid = _propose(author_client, spot, {"best_wind_directions": ["W"], "difficulty": "beginner"}, source="Местный клуб")
    assert [d["code"] for d in api_client.get(f"/api/v1/spots/{spot.slug}").json()["best_wind_directions"]] == ["N", "NW"]
    api_client.get("/api/v1/spots/map")
    assert cache.get(MAP_CACHE_KEY) is not None

    response = _mod(mod_client, pid, "approve", {"comment": "Подтверждено"})
    assert response.status_code == 200, response.json()
    assert response.json()["status"]["code"] == "approved"
    spot.refresh_from_db()
    assert spot.best_wind_directions == ["W"] and spot.difficulty == "beginner"
    assert spot.last_confirmed_at is not None
    assert [d["code"] for d in api_client.get(f"/api/v1/spots/{spot.slug}").json()["best_wind_directions"]] == ["W"]
    assert cache.get(MAP_CACHE_KEY) is None

    event = AuditEvent.objects.get(action="spot.change_approved")
    assert event.object_id == str(spot.id) and event.actor == moderator
    assert event.before == {"difficulty": "intermediate", "best_wind_directions": ["N", "NW"]}
    assert event.after == {"difficulty": "beginner", "best_wind_directions": ["W"]}
    assert event.metadata["proposal_id"] == pid
    assert SpotSourceRecord.objects.get(spot=spot).source == "Местный клуб"

    case = ModerationCase.objects.get(spot_change_request_id=pid)
    assert case.status == "resolved" and case.resolution == "approved" and case.resolved_by == moderator
    note = Notification.objects.get(recipient=author_client.account, kind="moderation_decision")
    assert note.link == f"/spots/{spot.slug}" and "Подтверждено" in note.body
    analytics = AnalyticsEvent.objects.get(name="spot_proposal_reviewed")
    assert analytics.context["decision"] == "approved" and analytics.context["hours_from_submitted"] >= 0

    proposal = author_client.get(f"/api/v1/proposals/{pid}").json()
    assert proposal["status"]["code"] == "approved" and proposal["moderator_comment"] == "Подтверждено"


def test_second_decision_on_same_proposal_is_conflict(mod_client, author_client, spot):
    pid = _propose(author_client, spot)
    assert _mod(mod_client, pid, "approve").status_code == 200
    for action in ("approve", "reject", "request-info"):
        response = _mod(mod_client, pid, action, {"comment": "x"})
        assert response.status_code == 409 and response.json()["error"]["code"] == "invalid_status"


def test_moderator_cannot_decide_own_proposal(make_client, spot):
    moderator = make_moderator(AccountFactory())
    client = make_client(moderator, two_factor=True)
    pid = _propose(client, spot)
    response = _mod(client, pid, "approve")
    assert response.status_code == 403 and response.json()["error"]["code"] == "self_moderation"


def test_reject_requires_comment_and_keeps_spot(mod_client, author_client, spot):
    pid = _propose(author_client, spot)
    assert _mod(mod_client, pid, "reject", {}).status_code == 400
    response = _mod(mod_client, pid, "reject", {"comment": "Нет источника"})
    assert response.status_code == 200
    spot.refresh_from_db()
    assert spot.best_wind_directions == ["N", "NW"]
    assert SpotChangeRequest.objects.get(pk=pid).moderator_comment == "Нет источника"
    assert AuditEvent.objects.filter(action="spot.change_rejected", object_id=pid).exists()
    assert AnalyticsEvent.objects.get(name="spot_proposal_reviewed").context["decision"] == "rejected"
    assert Notification.objects.filter(recipient=author_client.account, link="/account/proposals").exists()


def test_request_info_cycle_returns_proposal_to_queue(mod_client, author_client, spot):
    pid = _propose(author_client, spot)
    response = _mod(mod_client, pid, "request-info", {"comment": "Приложите фото"})
    assert response.status_code == 200 and response.json()["status"]["code"] == "needs_info"
    assert not ModerationCase.objects.filter(spot_change_request_id=pid, status="open").exists()
    mine = author_client.get(f"/api/v1/proposals/{pid}").json()
    assert mine["can_edit"] is True and mine["moderator_comment"] == "Приложите фото"
    evidence = MediaAssetFactory(owner=author_client.account, purpose=MediaAsset.Purpose.SPOT_EVIDENCE)
    response = author_client.patch(f"/api/v1/proposals/{pid}", {"evidence_ids": [str(evidence.id)]}, format="json")
    assert response.status_code == 200 and response.json()["status"]["code"] == "submitted"
    assert ModerationCase.objects.filter(spot_change_request_id=pid, status="open").count() == 1
    assert _mod(mod_client, pid, "approve").status_code == 200


def test_approve_with_evidence_adds_public_photo_to_gallery(mod_client, author_client, spot, api_client):
    evidence = MediaAssetFactory(owner=author_client.account, purpose=MediaAsset.Purpose.SPOT_EVIDENCE)
    pid = _propose(author_client, spot, evidence_ids=[str(evidence.id)])
    assert _mod(mod_client, pid, "approve", {"add_evidence_to_gallery": True}).status_code == 200
    photo = SpotPhoto.objects.get(spot=spot)
    assert photo.media == evidence and photo.author == author_client.account
    assert api_client.get(f"/api/v1/spots/{spot.slug}").json()["photos"][0]["media"]["id"] == str(evidence.id)


def test_private_evidence_is_copied_to_public_asset_for_gallery(mod_client, author_client, spot):
    evidence = MediaAssetFactory(owner=author_client.account, purpose=MediaAsset.Purpose.SPOT_EVIDENCE,
                                 visibility=MediaAsset.Visibility.PRIVATE, storage_key="private/evidence/1.jpg")
    pid = _propose(author_client, spot, evidence_ids=[str(evidence.id)])
    with mock.patch("apps.common.s3.internal_client") as client:
        assert _mod(mod_client, pid, "approve", {"add_evidence_to_gallery": True}).status_code == 200
    copy_kwargs = client.return_value.copy_object.call_args.kwargs
    assert copy_kwargs["CopySource"]["Key"] == "private/evidence/1.jpg" and copy_kwargs["Key"].startswith("public/")
    photo = SpotPhoto.objects.get(spot=spot)
    assert photo.media != evidence and photo.media.is_public and photo.media.purpose == "spot_photo"


def test_failed_copy_skips_photo_but_approves(mod_client, author_client, spot):
    evidence = MediaAssetFactory(owner=author_client.account, purpose=MediaAsset.Purpose.SPOT_EVIDENCE,
                                 visibility=MediaAsset.Visibility.PRIVATE, storage_key="private/evidence/2.jpg")
    pid = _propose(author_client, spot, evidence_ids=[str(evidence.id)])
    with mock.patch("apps.common.s3.internal_client", side_effect=RuntimeError("s3 down")):
        assert _mod(mod_client, pid, "approve", {"add_evidence_to_gallery": True}).status_code == 200
    assert not SpotPhoto.objects.filter(spot=spot).exists()
    event = AuditEvent.objects.get(action="spot.change_approved")
    assert event.metadata["skipped_evidence_ids"] == [str(evidence.id)]


def test_revert_restores_audited_values_and_keeps_status(mod_client, author_client, spot, api_client):
    evidence = MediaAssetFactory(owner=author_client.account, purpose=MediaAsset.Purpose.SPOT_EVIDENCE)
    pid = _propose(author_client, spot, {"best_wind_directions": ["W"], "season": "Осень"},
                   evidence_ids=[str(evidence.id)], source="Наблюдение")
    _mod(mod_client, pid, "approve", {"add_evidence_to_gallery": True})
    assert SpotSourceRecord.objects.filter(spot=spot).count() == 1
    response = _mod(mod_client, pid, "revert", {"comment": "Ошибочные данные"})
    assert response.status_code == 200, response.json()
    assert response.json()["status"]["code"] == "approved" and response.json()["reverted_at"]
    spot.refresh_from_db()
    assert spot.best_wind_directions == ["N", "NW"] and spot.season == "Лето"
    assert spot.last_confirmed_at is None
    assert not SpotPhoto.objects.filter(spot=spot).exists()
    assert not SpotSourceRecord.objects.filter(spot=spot).exists()
    event = AuditEvent.objects.get(action="spot.change_reverted")
    assert event.before == {"season": "Осень", "best_wind_directions": ["W"]}
    assert event.after == {"season": "Лето", "best_wind_directions": ["N", "NW"]}
    assert _mod(mod_client, pid, "revert").status_code == 409
    assert author_client.get(f"/api/v1/proposals/{pid}").json()["is_reverted"] is True


def test_revert_conflicts_when_field_changed_later_unless_forced(mod_client, make_client, spot):
    first = _propose(make_client(), spot, {"season": "Осень"})
    _mod(mod_client, first, "approve")
    second = _propose(make_client(), spot, {"season": "Зима"})
    _mod(mod_client, second, "approve")
    response = _mod(mod_client, first, "revert")
    assert response.status_code == 409 and response.json()["error"]["code"] == "revert_conflict"
    assert "season" in response.json()["error"]["fields"]
    assert _mod(mod_client, first, "revert", {"force": True}).status_code == 200
    spot.refresh_from_db()
    assert spot.season == "Лето"


def test_revert_of_unapproved_proposal_is_conflict(mod_client, author_client, spot):
    pid = _propose(author_client, spot)
    assert _mod(mod_client, pid, "revert").status_code == 409


def test_unknown_proposal_is_404(mod_client):
    import uuid

    assert _mod(mod_client, uuid.uuid4(), "approve").status_code == 404


def test_case_detail_shows_old_current_new_diff_and_signed_evidence(mod_client, author_client, spot):
    evidence = MediaAssetFactory(owner=author_client.account, purpose=MediaAsset.Purpose.SPOT_EVIDENCE,
                                 visibility=MediaAsset.Visibility.PRIVATE, storage_key="private/evidence/3.jpg")
    pid = _propose(author_client, spot, {"season": "Осень"}, comment="Сам видел", evidence_ids=[str(evidence.id)])
    spot.season = "Весна"  # поле изменилось после подачи
    spot.save()
    case = ModerationCase.objects.get(spot_change_request_id=pid)
    data = mod_client.get(f"/api/v1/moderation/cases/{case.id}").json()
    assert data["kind"]["code"] == "spot_change" and data["available_actions"] == ["approve", "reject", "request_info"]
    target = data["target"]
    assert target["type"] == "spot_change" and target["comment"] == "Сам видел"
    assert target["author"]["id"] == str(author_client.account.id)
    diff = target["diff"][0]
    assert (diff["old"], diff["current"], diff["new"]) == ("Лето", "Весна", "Осень")
    assert diff["changed_since_submission"] is True
    signed = target["evidence"][0]["signed_url"]
    assert "private/evidence/3.jpg" in signed and "X-Amz-Signature" in signed
    assert target["evidence"][0]["url"] is None
    assert data["history"][0]["action"] == "spot.change_proposed"
