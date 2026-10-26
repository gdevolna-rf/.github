"""GET/PATCH /me: профиль, handle с редиректами, аватар только здесь (ACC-07, UX-10), согласия GG (BR-12)."""
import datetime as dt

import pytest

from apps.accounts.models import ConsentRecord, HandleRedirect
from apps.learning.models import InstructorProfile
from apps.mediafiles.models import MediaAsset
from apps.organizations.models import Membership
from tests.factories import (
    AccountFactory,
    InstructorProfileFactory,
    MediaAssetFactory,
    OrganizationFactory,
    RegionFactory,
    SpotFactory,
    add_member,
    make_moderator,
)

pytestmark = pytest.mark.django_db

ME = "/api/v1/me"

PROFILE_KEYS = {
    "handle", "first_name", "last_name", "display_name", "avatar", "region", "city", "bio", "fun_facts",
    "surfing_since", "riding_level", "preferred_board_types", "favorite_spot_ids", "interests", "languages",
    "phone", "birth_date", "private_contacts", "gg_surfer_enabled", "gg_contact_policy", "gg_show_region",
    "gg_show_age", "birthday_greetings_consent", "show_birthday",
}


def test_me_payload_shape(make_client):
    account = AccountFactory()
    org = OrganizationFactory(owner=account)
    InstructorProfileFactory(account=account, status=InstructorProfile.Status.DRAFT)
    body = make_client(account).get(ME).json()
    assert set(body) >= {"id", "email", "email_verified", "date_joined", "profile", "specialties",
                         "available_specialties", "staff_roles", "organizations", "instructor_profile", "two_factor"}
    assert set(body["profile"]) == PROFILE_KEYS
    assert body["organizations"] == [{"id": str(org.pk), "slug": org.slug, "name": org.name, "kind": "school",
                                      "status": "published", "role": "owner",
                                      "membership_id": str(org.memberships.get().pk)}]
    assert body["instructor_profile"]["status"] == "draft"
    assert {s["code"] for s in body["specialties"]} == {"surfer", "instructor"}
    assert body["staff_roles"] == []
    assert body["deletion"] is None


def test_me_lists_only_active_memberships(make_client):
    account = AccountFactory()
    org = OrganizationFactory()
    membership = add_member(org, account)
    membership.status = Membership.Status.REVOKED
    membership.save()
    assert make_client(account).get(ME).json()["organizations"] == []


def test_staff_roles_shown_for_admin(make_client):
    account = make_moderator(AccountFactory(), role="admin")
    body = make_client(account).get(ME).json()
    assert body["staff_roles"] == ["admin", "moderator"]
    assert body["two_factor"]["required"] is True


def test_patch_profile_fields(auth_client):
    region = RegionFactory()
    spot = SpotFactory()
    response = auth_client.patch(ME, {
        "first_name": "Маша", "last_name": "Волнова", "bio": "Катаюсь с 2015", "city": "Петропавловск",
        "fun_facts": ["Люблю холодную воду"], "surfing_since": 2015, "riding_level": "intermediate",
        "preferred_board_types": ["fish", "longboard"], "interests": ["фото"], "languages": ["RU", "en"],
        "phone": "+7 (900) 000-00-00", "birth_date": "1995-05-20", "private_contacts": "tg: @masha",
        "region_id": region.pk, "favorite_spot_ids": [str(spot.pk)], "gg_contact_policy": "nobody",
    }, format="json")
    assert response.status_code == 200, response.json()
    profile = response.json()["profile"]
    assert profile["display_name"] == "Маша Волнова"
    assert profile["region"] == {"id": region.pk, "slug": region.slug, "name": region.name}
    assert profile["favorite_spot_ids"] == [str(spot.pk)]
    assert profile["languages"] == ["ru", "en"]
    assert profile["phone"] == "+7 (900) 000-00-00"
    assert profile["birth_date"] == "1995-05-20"


def test_patch_accepts_nested_profile_object(auth_client):
    response = auth_client.patch(ME, {"profile": {"city": "Сочи"}}, format="json")
    assert response.json()["profile"]["city"] == "Сочи"


@pytest.mark.parametrize("field,value", [
    ("surfing_since", 2999),
    ("birth_date", (dt.date.today() + dt.timedelta(days=2)).isoformat()),
    ("riding_level", "god"),
    ("phone", "<script>"),
    ("region_id", 999999),
    ("favorite_spot_ids", ["00000000-0000-0000-0000-000000000000"]),
])
def test_patch_validation(auth_client, field, value):
    assert auth_client.patch(ME, {field: value}, format="json").status_code == 400


def test_handle_change_keeps_redirect(auth_client, api_client):
    old = auth_client.account.profile.handle
    response = auth_client.patch(ME, {"handle": "Wave-Rider"}, format="json")
    assert response.status_code == 200
    assert response.json()["profile"]["handle"] == "wave-rider"
    assert HandleRedirect.objects.filter(old_handle=old, account=auth_client.account).exists()
    redirect = api_client.get(f"/api/v1/profiles/{old}")
    assert redirect.status_code == 200 and redirect.json() == {"redirect": "wave-rider"}
    assert api_client.get("/api/v1/profiles/wave-rider").json()["id"] == str(auth_client.account.pk)


def test_old_handle_cannot_be_taken_by_someone_else(auth_client, make_client):
    old = auth_client.account.profile.handle
    auth_client.patch(ME, {"handle": "new-handle"}, format="json")
    response = make_client().patch(ME, {"handle": old}, format="json")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "handle_taken"


def test_user_can_reclaim_own_old_handle(auth_client):
    old = auth_client.account.profile.handle
    auth_client.patch(ME, {"handle": "temporary"}, format="json")
    response = auth_client.patch(ME, {"handle": old}, format="json")
    assert response.status_code == 200
    assert not HandleRedirect.objects.filter(old_handle=old).exists()
    assert HandleRedirect.objects.filter(old_handle="temporary").exists()


@pytest.mark.parametrize("handle", ["ab", "a" * 41, "admin", "moderation", "-lead", "trail-", "две-волны",
                                    "double--dash", "under_score", "deleted-x1"])
def test_invalid_or_reserved_handles(auth_client, handle):
    response = auth_client.patch(ME, {"handle": handle}, format="json")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "handle_invalid"


def test_taken_handle(auth_client, make_client):
    other = make_client()
    response = auth_client.patch(ME, {"handle": other.account.profile.handle}, format="json")
    assert response.json()["error"]["code"] == "handle_taken"


def test_avatar_is_set_from_own_ready_upload(auth_client):
    asset = MediaAssetFactory(owner=auth_client.account, purpose=MediaAsset.Purpose.AVATAR)
    response = auth_client.patch(ME, {"avatar_id": str(asset.pk)}, format="json")
    assert response.status_code == 200
    assert response.json()["profile"]["avatar"]["id"] == str(asset.pk)
    removed = auth_client.patch(ME, {"avatar_id": None}, format="json")
    assert removed.json()["profile"]["avatar"] is None


def test_avatar_from_foreign_or_wrong_purpose_upload_is_rejected(auth_client):
    foreign = MediaAssetFactory(purpose=MediaAsset.Purpose.AVATAR)
    assert auth_client.patch(ME, {"avatar_id": str(foreign.pk)}, format="json").status_code == 400
    wrong = MediaAssetFactory(owner=auth_client.account, purpose=MediaAsset.Purpose.BOARD_PHOTO)
    response = auth_client.patch(ME, {"avatar_id": str(wrong.pk)}, format="json")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "media_purpose"
    pending = MediaAssetFactory(owner=auth_client.account, purpose="avatar", status=MediaAsset.Status.PENDING)
    assert auth_client.patch(ME, {"avatar_id": str(pending.pk)}, format="json").status_code == 400


def test_gg_surfer_toggle_writes_consent_records(auth_client):
    """BR-12, ACC-06: GG Surfer — отдельное согласие, отключается без потери аккаунта."""
    auth_client.patch(ME, {"gg_surfer_enabled": True}, format="json")
    auth_client.patch(ME, {"gg_surfer_enabled": True}, format="json")  # без изменения — без новой записи
    auth_client.patch(ME, {"gg_surfer_enabled": False}, format="json")
    records = list(ConsentRecord.objects.filter(account=auth_client.account, kind="gg_surfer")
                   .order_by("created_at", "id").values_list("granted", flat=True))
    assert records == [True, False]
    assert auth_client.get(ME).status_code == 200


def test_birthday_consent_is_logged(auth_client):
    """COM-05: поздравления только по согласию."""
    response = auth_client.patch(ME, {"birthday_greetings_consent": True, "birth_date": "1990-01-01"}, format="json")
    assert response.json()["profile"]["birthday_greetings_consent"] is True
    record = ConsentRecord.objects.get(account=auth_client.account, kind="birthday_greetings")
    assert record.granted is True


def test_guest_cannot_patch(api_client):
    assert api_client.patch(ME, {"city": "x"}, format="json").status_code == 401
