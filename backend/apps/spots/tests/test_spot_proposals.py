"""Предложения правок спота со стороны автора (SPT-07/08, 7.4, AT-07, ATX-13)."""
import pytest

from apps.mediafiles.models import MediaAsset
from apps.spots.models import Spot, SpotChangeRequest
from apps.trust.models import AccountRestriction, AuditEvent, ModerationCase
from tests.factories import AccountFactory, MediaAssetFactory, SpotFactory

pytestmark = pytest.mark.django_db


def _url(spot):
    return f"/api/v1/spots/{spot.id}/proposals"


def _evidence(owner, **kwargs):
    defaults = {"purpose": MediaAsset.Purpose.SPOT_EVIDENCE}
    defaults.update(kwargs)
    return MediaAssetFactory(owner=owner, **defaults)


@pytest.fixture
def spot():
    return SpotFactory(best_wind_directions=["N", "NW"], difficulty="intermediate", season="Лето")


def test_guest_cannot_propose(api_client, spot):
    response = api_client.post(_url(spot), {"changes": {"season": "Осень"}}, format="json")
    assert response.status_code == 401
    assert SpotChangeRequest.objects.count() == 0


def test_proposal_stores_diff_from_current_values_and_opens_case(make_client, spot):
    client = make_client()
    evidence = _evidence(client.account)
    response = client.post(_url(spot), {
        "changes": {"best_wind_directions": ["w", "NW"], "season": "Лето", "difficulty": "beginner"},
        "comment": "Катаюсь тут 5 лет", "source": "Местный клуб", "evidence_ids": [str(evidence.id)],
    }, format="json")
    assert response.status_code == 201, response.json()
    data = response.json()
    proposal = SpotChangeRequest.objects.get(pk=data["id"])
    # неизменённый season не попал в diff; направления нормализованы
    assert proposal.changes == {
        "difficulty": {"old": "intermediate", "new": "beginner"},
        "best_wind_directions": {"old": ["N", "NW"], "new": ["W", "NW"]},
    }
    assert proposal.status == "submitted" and proposal.source == "Местный клуб"
    assert list(proposal.evidence.all()) == [evidence]
    assert data["status"] == {"code": "submitted", "label": "На модерации"}
    wind = next(c for c in data["changes"] if c["field"] == "best_wind_directions")
    assert wind["old_display"] == "Север, Северо-запад" and wind["new_display"] == "Запад, Северо-запад"
    assert data["can_withdraw"] is True and data["can_edit"] is False
    case = ModerationCase.objects.get(spot_change_request=proposal)
    assert case.kind == "spot_change" and case.status == "open" and case.due_at
    assert AuditEvent.objects.filter(action="spot.change_proposed", object_id=str(proposal.pk)).exists()


def test_public_card_is_unchanged_until_approve(make_client, api_client, spot):
    make_client().post(_url(spot), {"changes": {"best_wind_directions": ["S"]}}, format="json")
    spot.refresh_from_db()
    assert spot.best_wind_directions == ["N", "NW"]
    data = api_client.get(f"/api/v1/spots/{spot.slug}").json()
    assert [d["code"] for d in data["best_wind_directions"]] == ["N", "NW"]


def test_only_editable_fields_are_accepted(make_client, spot):
    response = make_client().post(_url(spot), {"changes": {"name": "Новое", "lat": 1, "status": "hidden"}}, format="json")
    assert response.status_code == 400
    fields = response.json()["error"]["fields"]
    assert {"changes.name", "changes.lat", "changes.status"} <= set(fields)


@pytest.mark.parametrize("field,value", [
    ("difficulty", "insane"),
    ("bottom_type", 5),
    ("best_wind_directions", ["NORTH"]),
    ("best_swell_directions", "S"),
    ("best_months", [0, 13]),
    ("best_months", [True]),
    ("hazards", ["sharks_with_lasers"]),
    ("infrastructure", [{"type": "spaceport"}]),
    ("infrastructure", [{"type": "parking", "distance_m": -5}]),
    ("infrastructure", [{"type": "parking", "price": 100}]),
    ("short_description", "x" * 301),
    ("description", ["not", "text"]),
])
def test_invalid_values_are_rejected_per_field(make_client, spot, field, value):
    response = make_client().post(_url(spot), {"changes": {field: value}}, format="json")
    assert response.status_code == 400, response.json()
    assert f"changes.{field}" in response.json()["error"]["fields"]


def test_valid_complex_values_are_normalized(make_client, spot):
    response = make_client().post(_url(spot), {"changes": {
        "best_months": [8, "7", 7],
        "hazards": ["cold_water", "rocks"],
        "infrastructure": [{"type": "cafe", "name": " Волна ", "distance_m": 200}, {"type": "parking"}],
    }}, format="json")
    assert response.status_code == 201, response.json()
    changes = SpotChangeRequest.objects.get().changes
    assert changes["best_months"]["new"] == [7, 8]
    assert changes["hazards"]["new"] == ["rocks", "cold_water"]
    assert changes["infrastructure"]["new"] == [{"type": "cafe", "name": "Волна", "distance_m": 200},
                                                {"type": "parking", "name": "", "distance_m": None}]


def test_proposal_without_real_changes_is_rejected(make_client, spot):
    response = make_client().post(_url(spot), {"changes": {"best_wind_directions": ["NW", "N"], "season": " Лето "}},
                                  format="json")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "no_changes"


def test_empty_changes_is_validation_error(make_client, spot):
    assert make_client().post(_url(spot), {"changes": {}}, format="json").status_code == 400


def test_evidence_must_be_own_ready_spot_evidence(make_client, spot):
    client = make_client()
    foreign = _evidence(AccountFactory())
    wrong_purpose = MediaAssetFactory(owner=client.account, purpose=MediaAsset.Purpose.AVATAR)
    pending = _evidence(client.account, status=MediaAsset.Status.PENDING)
    for media, code in ((foreign, "media_invalid"), (wrong_purpose, "media_purpose"), (pending, "media_invalid")):
        response = client.post(_url(spot), {"changes": {"season": "Осень"}, "evidence_ids": [str(media.id)]}, format="json")
        assert response.status_code == 400 and response.json()["error"]["code"] == code
    assert SpotChangeRequest.objects.count() == 0


def test_proposal_for_hidden_spot_is_404(make_client):
    hidden = SpotFactory(status=Spot.Status.HIDDEN)
    assert make_client().post(_url(hidden), {"changes": {"season": "x"}}, format="json").status_code == 404


def test_restricted_author_cannot_propose(make_client, spot):
    client = make_client()
    AccountRestriction.objects.create(account=client.account, kind="publishing", reason="спам")
    response = client.post(_url(spot), {"changes": {"season": "Осень"}}, format="json")
    assert response.status_code == 403 and response.json()["error"]["code"] == "account_restricted"


def test_too_many_open_proposals_per_spot(make_client, spot):
    client = make_client()
    for season in ("Осень", "Зима", "Весна"):
        assert client.post(_url(spot), {"changes": {"season": season}}, format="json").status_code == 201
    response = client.post(_url(spot), {"changes": {"season": "Круглый год"}}, format="json")
    assert response.status_code == 409 and response.json()["error"]["code"] == "too_many_open_proposals"


def test_author_sees_own_proposals_with_status_and_moderator_comment(make_client, spot):
    client = make_client()
    other = make_client()
    mine = SpotChangeRequest.objects.create(spot=spot, author=client.account, status="rejected",
                                            moderator_comment="Нет источника", changes={"season": {"old": "Лето", "new": "x"}})
    SpotChangeRequest.objects.create(spot=spot, author=other.account, changes={"season": {"old": "Лето", "new": "y"}})
    data = client.get("/api/v1/me/proposals").json()
    assert data["count"] == 1
    assert data["results"][0]["id"] == str(mine.id)
    assert data["results"][0]["moderator_comment"] == "Нет источника"
    assert client.get("/api/v1/me/proposals?status=submitted").json()["count"] == 0
    assert client.get(f"/api/v1/proposals/{mine.id}").status_code == 200
    assert other.get(f"/api/v1/proposals/{mine.id}").status_code == 404


def test_author_updates_only_when_needs_info_and_it_returns_to_queue(make_client, spot):
    client = make_client()
    response = client.post(_url(spot), {"changes": {"season": "Осень"}}, format="json")
    pid = response.json()["id"]
    assert client.patch(f"/api/v1/proposals/{pid}", {"comment": "ещё"}, format="json").status_code == 409
    proposal = SpotChangeRequest.objects.get(pk=pid)
    proposal.status = "needs_info"
    proposal.save()
    ModerationCase.objects.filter(spot_change_request=proposal).update(status="resolved", resolution="needs_info")
    response = client.patch(f"/api/v1/proposals/{pid}", {"changes": {"season": "Осень — зима"}, "source": "Фото"},
                            format="json")
    assert response.status_code == 200, response.json()
    proposal.refresh_from_db()
    assert proposal.status == "submitted" and proposal.source == "Фото"
    assert proposal.changes == {"season": {"old": "Лето", "new": "Осень — зима"}}
    assert ModerationCase.objects.filter(spot_change_request=proposal, status="open").count() == 1
    assert AuditEvent.objects.filter(action="spot.change_resubmitted").exists()


def test_foreign_user_cannot_update_or_withdraw(make_client, spot):
    owner = make_client()
    pid = owner.post(_url(spot), {"changes": {"season": "Осень"}}, format="json").json()["id"]
    stranger = make_client()
    assert stranger.patch(f"/api/v1/proposals/{pid}", {"comment": "x"}, format="json").status_code == 404
    assert stranger.post(f"/api/v1/proposals/{pid}/withdraw").status_code == 404


def test_withdraw_closes_case_and_cannot_repeat(make_client, spot):
    client = make_client()
    pid = client.post(_url(spot), {"changes": {"season": "Осень"}}, format="json").json()["id"]
    response = client.post(f"/api/v1/proposals/{pid}/withdraw")
    assert response.status_code == 200 and response.json()["status"]["code"] == "withdrawn"
    case = ModerationCase.objects.get(spot_change_request_id=pid)
    assert case.status == "resolved" and case.resolution == "withdrawn"
    assert client.post(f"/api/v1/proposals/{pid}/withdraw").status_code == 409
