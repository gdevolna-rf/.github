"""Кабинет инструктора: профиль, публикация (ACC-15, F03, ATX-04, INS-05), медиа (INS-12), предложения (INS-08)."""
from decimal import Decimal

import pytest

from apps.learning.models import InstructorMedia, InstructorOffer, InstructorProfile
from apps.mediafiles.models import MediaAsset
from apps.trust.models import AccountRestriction, AuditEvent

from .helpers import (
    AccountFactory,
    InstructorOfferFactory,
    RegionFactory,
    SpotFactory,
    gallery_media,
    instructor_account,
    private_session,
    published_instructor,
)

pytestmark = pytest.mark.django_db
ME = "/api/v1/me/instructor"


@pytest.fixture
def instructor(make_client):
    return make_client(instructor_account())


def fill_profile(client, **extra):
    region = RegionFactory()
    payload = {"headline": "Учу вставать на доску", "region_slugs": [region.slug], "formats": ["individual"],
               "price_from": "3000.00"}
    payload.update(extra)
    response = client.put(ME, payload, format="json")
    assert response.status_code == 200, response.content
    return response.json()


def test_cabinet_requires_login_and_instructor_specialty(api_client, make_client):
    assert api_client.get(ME).status_code == 401
    response = make_client(AccountFactory()).put(ME, {"headline": "x"}, format="json")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "specialty_required"


def test_get_before_first_save_is_404(instructor):
    response = instructor.get(ME)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "instructor_profile_not_found"


def test_first_put_creates_draft_profile_with_regions_and_spots(instructor):
    spot = SpotFactory()
    data = fill_profile(instructor, spot_slugs=[spot.slug], board_types=["longboard", "softtop"],
                        student_levels=["beginner"], languages=["ru"], fun_facts=["Серфлю зимой", " "],
                        surfing_since=2012, teaching_since=2018, riding_level="advanced")
    assert data["status"] == "draft"
    assert data["spots"][0]["slug"] == spot.slug
    assert data["board_types"] == ["longboard", "softtop"]
    assert data["fun_facts"] == ["Серфлю зимой"]
    assert data["publish_check"] == {"can_publish": True, "missing": {}}
    profile = InstructorProfile.objects.get(account=instructor.account)
    assert profile.regions.count() == 1
    assert AuditEvent.objects.filter(action="instructor_profile.created", object_id=str(profile.pk)).exists()


@pytest.mark.parametrize("payload,field", [
    ({"region_slugs": ["atlantis"]}, "region_slugs"),
    ({"board_types": ["spaceship"]}, "board_types"),
    ({"surfing_since": 1800}, "surfing_since"),
    ({"surfing_since": 2015, "teaching_since": 2010}, "teaching_since"),
    ({"formats": ["telepathy"]}, "formats"),
    ({"languages": ["Russian"]}, "languages"),
    ({"price_from": "-5"}, "price_from"),
    ({"fun_facts": ["a", "b", "c", "d", "e", "f"]}, "fun_facts"),
])
def test_profile_validation(instructor, payload, field):
    response = instructor.put(ME, payload, format="json")
    assert response.status_code == 400
    assert field in response.json()["error"]["fields"]


def test_publish_without_certificate_or_workplace_document(instructor, api_client):
    """F03, ATX-04, INS-05: базовых полей достаточно, бейджа «проверен» нет."""
    fill_profile(instructor)
    response = instructor.post(f"{ME}/publish")
    assert response.status_code == 200, response.content
    assert response.json()["status"] == "published"
    card = api_client.get("/api/v1/instructors").json()["results"][0]
    assert card["handle"] == instructor.account.profile.handle
    assert card["certificate_status"] == "none"
    assert AuditEvent.objects.filter(action="instructor_profile.published").exists()


def test_publish_lists_missing_required_fields(instructor):
    instructor.put(ME, {"about": ""}, format="json")
    profile = instructor.account.profile
    profile.last_name = ""
    profile.save()
    response = instructor.post(f"{ME}/publish")
    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "publish_requirements"
    assert set(error["fields"]) == {"name", "headline", "region_slugs", "formats", "price_from"}
    assert instructor.get(ME).json()["publish_check"]["can_publish"] is False


def test_active_offer_replaces_price_from_for_publication(instructor):
    fill_profile(instructor, price_from=None)
    assert instructor.post(f"{ME}/publish").status_code == 400
    instructor.post(f"{ME}/offers", {"title": "Урок", "price": "2500", "format": "individual"}, format="json")
    assert instructor.post(f"{ME}/publish").status_code == 200


def test_publish_requires_verified_email(make_client):
    account = instructor_account(email_verified_at=None)
    client = make_client(account)
    fill_profile(client)
    response = client.post(f"{ME}/publish")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "email_not_verified"


def test_publish_blocked_for_hidden_or_restricted_profile(instructor):
    fill_profile(instructor)
    profile = InstructorProfile.objects.get(account=instructor.account)
    profile.status = InstructorProfile.Status.HIDDEN
    profile.save()
    assert instructor.post(f"{ME}/publish").json()["error"]["code"] == "profile_hidden"
    profile.status = InstructorProfile.Status.DRAFT
    profile.save()
    AccountRestriction.objects.create(account=instructor.account, kind=AccountRestriction.Kind.PUBLISHING, reason="x")
    assert instructor.post(f"{ME}/publish").json()["error"]["code"] == "account_restricted"


def test_published_profile_cannot_lose_required_fields(instructor):
    fill_profile(instructor)
    instructor.post(f"{ME}/publish")
    response = instructor.patch(ME, {"region_slugs": []}, format="json")
    assert response.status_code == 400
    assert "region_slugs" in response.json()["error"]["fields"]
    assert InstructorProfile.objects.get(account=instructor.account).regions.count() == 1


def test_unpublish_hides_card(instructor, api_client):
    fill_profile(instructor)
    instructor.post(f"{ME}/publish")
    assert instructor.post(f"{ME}/unpublish").json()["status"] == "draft"
    assert api_client.get("/api/v1/instructors").json()["count"] == 0


def test_patch_updates_only_given_fields(instructor):
    fill_profile(instructor, about="Первый текст")
    data = instructor.patch(ME, {"contact_note": "Пишите в чат"}, format="json").json()
    assert data["contact_note"] == "Пишите в чат" and data["about"] == "Первый текст"


# --- медиа -----------------------------------------------------------------------------------------------------

def test_media_add_reorder_move_delete(instructor):
    fill_profile(instructor)
    photo = gallery_media(instructor.account)
    video = gallery_media(instructor.account, kind=MediaAsset.Kind.VIDEO, content_type="video/mp4")
    first = instructor.post(f"{ME}/media", {"media_id": str(photo.pk)}, format="json")
    assert first.status_code == 201 and first.json()["position"] == 1
    second = instructor.post(f"{ME}/media", {"media_id": str(video.pk)}, format="json").json()
    assert second["position"] == 2
    listing = instructor.patch(f"{ME}/media", {"ids": [second["id"], first.json()["id"]]}, format="json").json()
    assert [i["media"]["id"] for i in listing] == [str(video.pk), str(photo.pk)]
    moved = instructor.patch(f"{ME}/media/{second['id']}", {"position": 2}, format="json").json()
    assert [i["media"]["id"] for i in moved] == [str(photo.pk), str(video.pk)]
    assert instructor.delete(f"{ME}/media/{first.json()['id']}").status_code == 204
    remaining = instructor.get(f"{ME}/media").json()
    assert [(i["position"], i["media"]["id"]) for i in remaining] == [(1, str(video.pk))]


def test_media_rules(instructor, make_client):
    fill_profile(instructor)
    board_photo = gallery_media(instructor.account, purpose=MediaAsset.Purpose.BOARD_PHOTO)
    assert instructor.post(f"{ME}/media", {"media_id": str(board_photo.pk)}, format="json").json()["error"]["code"] \
        == "media_purpose"
    foreign = gallery_media(AccountFactory())
    assert instructor.post(f"{ME}/media", {"media_id": str(foreign.pk)}, format="json").json()["error"]["code"] \
        == "media_invalid"
    mine = gallery_media(instructor.account)
    instructor.post(f"{ME}/media", {"media_id": str(mine.pk)}, format="json")
    assert instructor.post(f"{ME}/media", {"media_id": str(mine.pk)}, format="json").status_code == 409
    bad_order = instructor.patch(f"{ME}/media", {"ids": [999999]}, format="json")
    assert bad_order.status_code == 400
    other = make_client(instructor_account())
    published_instructor(other.account)
    item = InstructorMedia.objects.get(media=mine)
    assert other.delete(f"{ME}/media/{item.pk}").status_code == 404


# --- предложения (INS-08) --------------------------------------------------------------------------------------

def test_offer_crud(instructor):
    fill_profile(instructor)
    spot = SpotFactory()
    created = instructor.post(f"{ME}/offers", {
        "title": "Групповой урок", "format": "group", "level": "beginner", "duration_min": 120, "price": "3500",
        "capacity": 5, "spot_slug": spot.slug, "equipment_included": True, "rules": "Без опозданий"}, format="json")
    assert created.status_code == 201, created.content
    offer = created.json()
    assert offer["spot"]["slug"] == spot.slug and offer["capacity"] == 5
    assert instructor.get(f"{ME}/offers").json()["count"] == 1
    updated = instructor.patch(f"{ME}/offers/{offer['id']}", {"price": "4000.00", "spot_slug": None}, format="json")
    assert updated.json()["price"] == "4000.00" and updated.json()["spot"] is None
    assert instructor.delete(f"{ME}/offers/{offer['id']}").status_code == 204
    assert not InstructorOffer.objects.filter(pk=offer["id"]).exists()


def test_offer_with_sessions_is_archived_on_delete(instructor):
    fill_profile(instructor)
    profile = InstructorProfile.objects.get(account=instructor.account)
    offer = InstructorOfferFactory(instructor=profile)
    private_session(profile, offer=offer)
    assert instructor.delete(f"{ME}/offers/{offer.pk}").status_code == 204
    offer.refresh_from_db()
    assert offer.is_active is False
    assert instructor.get(f"{ME}/offers", {"active": "false"}).json()["count"] == 1


def test_offer_validation_and_isolation(instructor, make_client):
    fill_profile(instructor)
    response = instructor.post(f"{ME}/offers", {"title": "Инд", "format": "individual", "capacity": 6,
                                                "price": "100"}, format="json")
    assert "capacity" in response.json()["error"]["fields"]
    assert instructor.post(f"{ME}/offers", {"title": "x", "price": "-1"}, format="json").status_code == 400
    foreign = InstructorOfferFactory(instructor=published_instructor())
    assert instructor.get(f"{ME}/offers/{foreign.pk}").status_code == 404
    assert instructor.patch(f"{ME}/offers/{foreign.pk}", {"price": "1"}, format="json").status_code == 404
    assert instructor.delete(f"{ME}/offers/{foreign.pk}").status_code == 404
    foreign.refresh_from_db()
    assert foreign.price == Decimal("4000")


def test_offers_require_profile(instructor):
    response = instructor.post(f"{ME}/offers", {"title": "x", "price": "1"}, format="json")
    assert response.status_code == 404
