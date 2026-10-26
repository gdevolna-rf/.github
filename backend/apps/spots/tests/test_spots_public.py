"""Публичный каталог спотов (BR-01, SPT-02…06, SPT-11/12, GEO-06)."""
import datetime as dt
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.learning.models import InstructorCertificate
from apps.mediafiles.models import MediaAsset
from apps.organizations.models import Organization
from apps.spots.models import Spot, SpotChangeRequest, SpotPhoto, SpotSourceRecord
from apps.trust.models import Review
from tests.factories import (
    AccountFactory,
    InstructorProfileFactory,
    MediaAssetFactory,
    OrganizationFactory,
    RegionFactory,
    SpotFactory,
)

pytestmark = pytest.mark.django_db


def _photo(spot, position, status=MediaAsset.Status.READY, visibility=MediaAsset.Visibility.PUBLIC):
    media = MediaAssetFactory(purpose=MediaAsset.Purpose.SPOT_PHOTO, status=status, visibility=visibility)
    return SpotPhoto.objects.create(spot=spot, media=media, position=position, caption=f"фото {position}")


def test_guest_lists_regions_with_published_spot_counts(api_client):
    region = RegionFactory(slug="kamchatka", name="Камчатский край", center_lat=Decimal("53.0"), center_lng=Decimal("158.6"))
    SpotFactory(region=region)
    SpotFactory(region=region, status=Spot.Status.HIDDEN)
    response = api_client.get("/api/v1/regions")
    assert response.status_code == 200
    item = next(r for r in response.json() if r["slug"] == "kamchatka")
    assert item["spots_count"] == 1
    assert item["center_lat"] == 53.0


def test_guest_sees_only_published_and_closed_spots(api_client):
    visible = SpotFactory(name="Халактыр")
    closed = SpotFactory(status=Spot.Status.CLOSED)
    SpotFactory(status=Spot.Status.DRAFT)
    SpotFactory(status=Spot.Status.HIDDEN)
    response = api_client.get("/api/v1/spots")
    assert response.status_code == 200
    ids = {s["id"] for s in response.json()["results"]}
    assert ids == {str(visible.id), str(closed.id)}
    closed_item = next(s for s in response.json()["results"] if s["id"] == str(closed.id))
    assert closed_item["is_closed"] is True
    assert closed_item["status"] == {"code": "closed", "label": "Закрыт"}


def test_hidden_or_draft_spot_detail_is_404(api_client):
    hidden = SpotFactory(status=Spot.Status.HIDDEN)
    draft = SpotFactory(status=Spot.Status.DRAFT)
    assert api_client.get(f"/api/v1/spots/{hidden.slug}").status_code == 404
    assert api_client.get(f"/api/v1/spots/{draft.slug}").status_code == 404
    assert api_client.get("/api/v1/spots/no-such-spot").json()["error"]["code"] == "spot_not_found"


def test_list_filters_by_region_difficulty_bottom_break_and_q(api_client):
    kam = RegionFactory(slug="kam")
    crimea = RegionFactory(slug="crimea")
    a = SpotFactory(region=kam, name="Англичанка", difficulty="beginner", bottom_type="sand", break_type="beach")
    b = SpotFactory(region=crimea, name="Оленевка", difficulty="advanced", bottom_type="rock", break_type="reef")
    SpotFactory(region=crimea, name="Кача", difficulty="intermediate", bottom_type="pebble", break_type="point")

    def ids(query):
        response = api_client.get(f"/api/v1/spots?{query}")
        assert response.status_code == 200, response.json()
        return {s["id"] for s in response.json()["results"]}

    assert ids("region=kam") == {str(a.id)}
    assert ids("difficulty=advanced") == {str(b.id)}
    assert ids("bottom=sand,rock") == {str(a.id), str(b.id)}
    assert ids("break=reef") == {str(b.id)}
    assert ids("q=оленев") == {str(b.id)}
    assert ids("region=crimea&difficulty=advanced") == {str(b.id)}


def test_unknown_filter_value_is_validation_error(api_client):
    response = api_client.get("/api/v1/spots?difficulty=insane")
    assert response.status_code == 400
    assert "difficulty" in response.json()["error"]["fields"]


def test_list_sort_by_rating(api_client):
    low = SpotFactory(rating_avg=Decimal("3.00"), rating_count=2)
    high = SpotFactory(rating_avg=Decimal("4.90"), rating_count=5)
    results = api_client.get("/api/v1/spots?sort=rating").json()["results"]
    assert [r["id"] for r in results] == [str(high.id), str(low.id)]


def test_detail_contains_labels_compass_conditions_infrastructure_and_sources(api_client):
    spot = SpotFactory(
        difficulty="beginner", bottom_type="sand", break_type="beach", best_months=[7, 6],
        best_wind_directions=["NW"], best_swell_directions=["SE", "S"], hazards=["rocks", "cold_water"],
        typical_conditions="Свелл с юго-востока, утром стекло", infrastructure=[{"type": "parking", "name": "", "distance_m": 150}],
        data_source="Сообщество, 2026", last_confirmed_at=timezone.now(), seasonal_warning="Медведи в сентябре",
        closed_until=timezone.localdate() + dt.timedelta(days=10), webcam_url="https://cam.example.com/1",
    )
    SpotSourceRecord.objects.create(spot=spot, source="Местный инструктор", confirmed_at=timezone.now())
    data = api_client.get(f"/api/v1/spots/{spot.slug}").json()
    assert data["difficulty"] == {"code": "beginner", "label": "Для новичков"}
    assert data["bottom_type"] == {"code": "sand", "label": "Песок"}
    assert data["break_type"] == {"code": "beach", "label": "Бич-брейк"}
    assert data["best_wind_directions"] == [{"code": "NW", "label": "Северо-запад", "short": "СЗ", "degrees": 315.0}]
    assert [d["code"] for d in data["best_swell_directions"]] == ["SE", "S"]
    assert data["best_months"] == [{"code": 7, "label": "Июль"}, {"code": 6, "label": "Июнь"}]
    assert data["hazards"][0] == {"code": "rocks", "label": "Камни"}
    assert data["typical_conditions"] == "Свелл с юго-востока, утром стекло"
    assert data["infrastructure"] == [{"type": "parking", "type_label": "Парковка", "name": "", "distance_m": 150}]
    assert data["sources"][0]["source"] == "Местный инструктор"
    assert data["data_source"] == "Сообщество, 2026" and data["last_confirmed_at"]
    assert data["seasonal_warning"] == "Медведи в сентябре" and data["is_closed"] is True
    assert data["webcam_url"] == "https://cam.example.com/1" and data["has_webcam"] is True
    assert data["rating_avg"] == "0.00" and data["rating_count"] == 0
    assert data["my_review"] is None and data["my_pending_proposals"] == []
    assert "forecast" not in data  # прогноз — отдельный эндпоинт (SPT-04)


def test_premium_webcam_url_is_not_exposed(api_client):
    spot = SpotFactory(webcam_url="https://cam.example.com/premium", webcam_is_premium=True)
    data = api_client.get(f"/api/v1/spots/{spot.slug}").json()
    assert data["webcam_url"] is None and data["has_webcam"] is True and data["webcam_is_premium"] is True


def test_detail_photos_are_ordered_ready_public_only_and_cover_falls_back(api_client):
    spot = SpotFactory()
    second = _photo(spot, 2)
    first = _photo(spot, 1)
    _photo(spot, 0, status=MediaAsset.Status.PROCESSING)
    _photo(spot, 3, visibility=MediaAsset.Visibility.PRIVATE)
    data = api_client.get(f"/api/v1/spots/{spot.slug}").json()
    assert [p["id"] for p in data["photos"]] == [first.id, second.id]
    assert data["cover"]["id"] == str(first.media_id)
    assert data["photos"][0]["media"]["url"].endswith(first.media.storage_key)


def test_exact_coordinates_for_regular_spot(api_client):
    spot = SpotFactory(lat=Decimal("52.934860"), lng=Decimal("158.779867"))
    data = api_client.get(f"/api/v1/spots/{spot.slug}").json()
    assert (data["lat"], data["lng"], data["precise"]) == (52.93486, 158.779867, True)


def test_approximate_spot_coordinates_rounded_to_two_decimals(api_client):
    spot = SpotFactory(lat=Decimal("52.934860"), lng=Decimal("158.779867"), location_precision=Spot.Precision.APPROXIMATE)
    for payload in (api_client.get(f"/api/v1/spots/{spot.slug}").json(), api_client.get("/api/v1/spots").json()["results"][0]):
        assert (payload["lat"], payload["lng"], payload["precise"]) == (52.93, 158.78, False)
        assert payload["location_precision"]["code"] == "approximate"


def test_sensitive_spot_never_shows_exact_point(api_client):
    spot = SpotFactory(lat=Decimal("52.934860"), lng=Decimal("158.779867"), is_sensitive=True)
    data = api_client.get(f"/api/v1/spots/{spot.slug}").json()
    assert (data["lat"], data["lng"], data["precise"]) == (52.93, 158.78, False)


def test_region_only_spot_shows_region_centre(api_client):
    region = RegionFactory(center_lat=Decimal("53.000000"), center_lng=Decimal("158.000000"))
    spot = SpotFactory(region=region, location_precision=Spot.Precision.REGION_ONLY)
    data = api_client.get(f"/api/v1/spots/{spot.slug}").json()
    assert (data["lat"], data["lng"], data["precise"]) == (53.0, 158.0, False)
    marker = api_client.get("/api/v1/spots/map").json()["markers"][0]
    assert (marker["lat"], marker["lng"], marker["precise"]) == (53.0, 158.0, False)


def test_detail_lists_only_published_organizations_and_instructors(api_client):
    spot = SpotFactory()
    school = OrganizationFactory(name="Школа Волна")
    draft = OrganizationFactory(status=Organization.Status.DRAFT)
    school.spots.add(spot)
    draft.spots.add(spot)
    instructor = InstructorProfileFactory()
    hidden = InstructorProfileFactory(status="hidden")
    instructor.spots.add(spot)
    hidden.spots.add(spot)
    data = api_client.get(f"/api/v1/spots/{spot.slug}").json()
    assert [o["id"] for o in data["organizations"]] == [str(school.id)]
    assert data["organizations"][0]["kind"] == {"code": "school", "label": "Сёрф-школа"}
    assert [i["id"] for i in data["instructors"]] == [str(instructor.id)]
    card = data["instructors"][0]
    assert card["certificate_verified"] is False
    assert "email" not in card["account"]


def test_instructor_card_shows_verified_badge_only_after_verification(api_client):
    spot = SpotFactory()
    instructor = InstructorProfileFactory()
    instructor.spots.add(spot)
    doc = MediaAssetFactory(owner=instructor.account, kind="document", purpose="certificate", visibility="private")
    cert = InstructorCertificate.objects.create(instructor=instructor, title="ISA", document=doc)
    assert api_client.get(f"/api/v1/spots/{spot.slug}").json()["instructors"][0]["certificate_verified"] is False
    cert.status = InstructorCertificate.Status.VERIFIED
    cert.save()
    assert api_client.get(f"/api/v1/spots/{spot.slug}").json()["instructors"][0]["certificate_verified"] is True


def test_detail_includes_my_review_and_my_pending_proposals(make_client):
    user = AccountFactory()
    other = AccountFactory()
    spot = SpotFactory()
    Review.objects.create(author=user, target_type="spot", spot=spot, rating=4, text="Хорошо")
    mine = SpotChangeRequest.objects.create(spot=spot, author=user, changes={"season": {"old": "", "new": "лето"}})
    SpotChangeRequest.objects.create(spot=spot, author=user, status="approved", changes={"season": {"old": "", "new": "x"}})
    SpotChangeRequest.objects.create(spot=spot, author=other, changes={"season": {"old": "", "new": "y"}})
    data = make_client(user).get(f"/api/v1/spots/{spot.slug}").json()
    assert data["my_review"]["rating"] == 4
    assert data["my_review"]["status"] == {"code": "pending", "label": "На модерации"}
    assert [p["id"] for p in data["my_pending_proposals"]] == [str(mine.id)]
    assert data["my_pending_proposals"][0]["changed_fields"] == ["season"]


def test_dictionaries_describe_filters_and_editable_fields(api_client):
    data = api_client.get("/api/v1/spots/dictionaries").json()
    assert {"code": "beginner", "label": "Для новичков"} in data["difficulty"]
    assert len(data["compass_points"]) == 16 and len(data["months"]) == 12
    fields = {f["field"]: f for f in data["editable_fields"]}
    assert fields["best_wind_directions"]["kind"] == "compass"
    assert fields["short_description"]["max_length"] == 300
    assert "name" not in fields and "lat" not in fields
