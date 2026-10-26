"""Публичный каталог инструкторов: видимость, карточка, бейдж сертификата, фильтры INS-09 (BR-01, BR-07, ATX-05)."""
import datetime as dt
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.accounts.models import HandleRedirect
from apps.learning.models import InstructorCertificate, InstructorProfile
from apps.organizations.models import Membership, Organization
from apps.trust.models import AccountRestriction

from .helpers import (
    AccountFactory,
    InstructorOfferFactory,
    OrganizationFactory,
    RegionFactory,
    SpotFactory,
    add_member,
    booking,
    certificate,
    future,
    gallery_media,
    private_session,
    published_instructor,
    school_session,
)

pytestmark = pytest.mark.django_db
URL = "/api/v1/instructors"


def ids(response):
    assert response.status_code == 200, response.content
    return {item["id"] for item in response.json()["results"]}


def test_guest_sees_only_published_profiles_of_active_accounts(api_client):
    visible = published_instructor()
    draft = published_instructor(status=InstructorProfile.Status.DRAFT)
    inactive = published_instructor()
    inactive.account.is_active = False
    inactive.account.save()
    suspended = published_instructor()
    AccountRestriction.objects.create(account=suspended.account, kind=AccountRestriction.Kind.SUSPENDED, reason="x")
    anonymized = published_instructor()
    anonymized.account.anonymized_at = timezone.now()
    anonymized.account.save()

    found = ids(api_client.get(URL))
    assert str(visible.pk) in found
    assert not {str(draft.pk), str(inactive.pk), str(suspended.pk), str(anonymized.pk)} & found


def test_card_has_public_fields_and_no_private_data(api_client):
    spot = SpotFactory()
    profile = published_instructor(spots=[spot], board_types=["longboard"], languages=["ru", "en"],
                                   student_levels=["beginner"], surfing_since=2010, teaching_since=2015)
    profile.account.profile.phone = "+79990000000"
    profile.account.profile.save()
    card = api_client.get(URL).json()["results"][0]
    assert card["handle"] == profile.account.profile.handle
    assert card["display_name"] == "Тест Пользователь"
    assert card["spots"] == [{"id": str(spot.pk), "slug": spot.slug, "name": spot.name,
                              "region": {"slug": spot.region.slug, "name": spot.region.name}}]
    assert card["regions"][0]["slug"]
    assert card["price_from"] == "3500.00"
    assert card["certificate_status"] == "none"
    assert card["schools"] == []
    for key in ("surfing_since", "teaching_since", "riding_level", "formats", "student_levels", "board_types",
                "languages", "currency", "rating_avg", "rating_count", "avatar", "headline"):
        assert key in card
    raw = str(card)
    assert profile.account.email not in raw and "+7999" not in raw


@pytest.mark.parametrize("statuses,expected", [
    ([], "none"),
    (["rejected"], "none"),
    (["uploaded"], "uploaded"),
    (["uploaded", "verified"], "verified"),
    (["revoked"], "none"),
])
def test_certificate_badge_reflects_moderation_only(api_client, statuses, expected):
    profile = published_instructor()
    for status in statuses:
        certificate(profile, status=status)
    card = api_client.get(URL).json()["results"][0]
    assert card["certificate_status"] == expected
    assert profile.certificate_status == expected


def test_expired_verified_certificate_is_not_shown_as_verified(api_client):
    profile = published_instructor()
    certificate(profile, status=InstructorCertificate.Status.VERIFIED,
                valid_until=timezone.localdate() - dt.timedelta(days=1))
    assert api_client.get(URL).json()["results"][0]["certificate_status"] == "uploaded"


def test_filters_region_spot_level_board_format(api_client):
    region = RegionFactory()
    spot = SpotFactory(region=region)
    match = published_instructor(region=region, spots=[spot], student_levels=["beginner"], board_types=["longboard"],
                                 formats=["group"])
    other = published_instructor(student_levels=["advanced"], board_types=["shortboard"])
    assert ids(api_client.get(URL, {"region": region.slug})) == {str(match.pk)}
    assert ids(api_client.get(URL, {"spot": spot.slug})) == {str(match.pk)}
    assert ids(api_client.get(URL, {"level": "beginner"})) == {str(match.pk)}
    assert ids(api_client.get(URL, {"board_type": "shortboard"})) == {str(other.pk)}
    assert ids(api_client.get(URL, {"format": "group"})) == {str(match.pk)}


def test_region_filter_matches_spots_of_region(api_client):
    spot = SpotFactory()
    profile = published_instructor(spots=[spot])
    assert ids(api_client.get(URL, {"region": spot.region.slug})) == {str(profile.pk)}


def test_price_filter_uses_cheapest_active_offer(api_client):
    cheap = published_instructor(price_from=None)
    InstructorOfferFactory(instructor=cheap, price=Decimal("2000"))
    InstructorOfferFactory(instructor=cheap, price=Decimal("1500"), is_active=False)
    expensive = published_instructor(price_from=Decimal("9000"))
    assert ids(api_client.get(URL, {"price_max": "2500"})) == {str(cheap.pk)}
    card = next(c for c in api_client.get(URL).json()["results"] if c["id"] == str(cheap.pk))
    assert card["price_from"] == "2000.00"
    ordered = [c["id"] for c in api_client.get(URL, {"ordering": "price"}).json()["results"]]
    assert ordered == [str(cheap.pk), str(expensive.pk)]


def test_certificate_filter(api_client):
    verified = published_instructor()
    certificate(verified, status="verified")
    uploaded = published_instructor()
    certificate(uploaded)
    none = published_instructor()
    assert ids(api_client.get(URL, {"certificate": "verified"})) == {str(verified.pk)}
    assert ids(api_client.get(URL, {"certificate": "uploaded"})) == {str(verified.pk), str(uploaded.pk)}
    assert ids(api_client.get(URL, {"certificate": "none"})) == {str(none.pk)}
    assert len(ids(api_client.get(URL, {"certificate": "any"}))) == 3
    assert api_client.get(URL, {"certificate": "gold"}).status_code == 400


def test_rating_and_text_filters(api_client):
    good = published_instructor(rating_avg=Decimal("4.80"), rating_count=5, headline="Лонгборд и кайф")
    published_instructor(rating_avg=Decimal("3.10"), rating_count=2)
    published_instructor(rating_avg=Decimal("0"), rating_count=0)
    assert ids(api_client.get(URL, {"rating_min": "4.5"})) == {str(good.pk)}
    assert ids(api_client.get(URL, {"q": "лонгборд"})) == {str(good.pk)}
    assert api_client.get(URL, {"rating_min": "abc"}).status_code == 400
    assert api_client.get(URL, {"ordering": "random"}).status_code == 400


def test_date_filter_requires_free_slot_that_day(api_client):
    region = RegionFactory(timezone="Europe/Moscow")
    with_slot = published_instructor(region=region)
    start = future(hours=72)[0]
    private_session(with_slot, start=start)
    full = published_instructor(region=region)
    full_session = private_session(full, start=start)
    booking(full_session)  # capacity 1 → занято
    teaches_at_school = published_instructor(region=region)
    school_session(instructor=teaches_at_school.account, start=start)
    draft_school = OrganizationFactory(status=Organization.Status.DRAFT)
    hidden = published_instructor(region=region)
    school_session(draft_school, instructor=hidden.account, start=start)
    day = timezone.localtime(start).date().isoformat()
    found = ids(api_client.get(URL, {"date": day, "region": region.slug}))
    assert found == {str(with_slot.pk), str(teaches_at_school.pk)}
    other_day = (timezone.localtime(start).date() + dt.timedelta(days=1)).isoformat()
    assert ids(api_client.get(URL, {"date": other_day})) == set()
    assert api_client.get(URL, {"date": "21-10-2026"}).status_code == 400


def test_schools_show_active_memberships_in_published_schools(api_client):
    profile = published_instructor()
    published = OrganizationFactory(name="Альфа")
    add_member(published, profile.account)
    draft = OrganizationFactory(status=Organization.Status.DRAFT)
    add_member(draft, profile.account)
    revoked = OrganizationFactory()
    m = add_member(revoked, profile.account)
    m.status = Membership.Status.REVOKED
    m.save()
    card = api_client.get(URL).json()["results"][0]
    assert [s["slug"] for s in card["schools"]] == [published.slug]


def test_detail_contains_offers_slots_media_certificates(api_client):
    profile = published_instructor(about="О себе", fun_facts=["Люблю шторм"], contact_note="Пишите в чат")
    active = InstructorOfferFactory(instructor=profile, title="Активное")
    InstructorOfferFactory(instructor=profile, title="Архив", is_active=False)
    slot = private_session(profile, offer=active)
    past = private_session(profile, offer=active, start=timezone.now() - dt.timedelta(days=1))
    full = private_session(profile, offer=active, hours=48)
    booking(full)
    media = gallery_media(profile.account)
    profile.media_items.create(media=media, position=1)
    certificate(profile, status="verified", allow_public_scan=True)
    certificate(profile, status="rejected", title="Отклонённый")
    data = api_client.get(f"{URL}/{profile.account.profile.handle}").json()
    assert data["about"] == "О себе" and data["fun_facts"] == ["Люблю шторм"]
    assert [o["title"] for o in data["offers"]] == ["Активное"]
    assert [s["id"] for s in data["upcoming_slots"]] == [str(slot.pk)]
    assert str(past.pk) not in str(data["upcoming_slots"])
    slot_data = data["upcoming_slots"][0]
    assert slot_data["free_seats"] == 1 and slot_data["kind"] == "private"
    assert slot_data["starts_at"].endswith("+03:00") or "+" in slot_data["starts_at"][-6:]
    assert data["media"][0]["media"]["id"] == str(media.pk)
    assert [c["title"] for c in data["certificates"]] == ["ISA Level 1"]
    assert data["certificates"][0]["scan_available"] is True
    assert "document" not in data["certificates"][0]
    assert data["certificate_status"] == "verified"


def test_detail_of_unpublished_profile_is_404_but_owner_can_preview(api_client, make_client):
    profile = published_instructor(status=InstructorProfile.Status.DRAFT)
    path = f"{URL}/{profile.account.profile.handle}"
    assert api_client.get(path).status_code == 404
    assert make_client().get(path).status_code == 404
    assert make_client(profile.account).get(path).status_code == 200


def test_old_handle_returns_redirect(api_client):
    profile = published_instructor()
    HandleRedirect.objects.create(old_handle="old-surfer", account=profile.account)
    response = api_client.get(f"{URL}/old-surfer")
    assert response.status_code == 200
    assert response.json() == {"redirect": profile.account.profile.handle}
    assert api_client.get(f"{URL}/nobody-here").status_code == 404


def test_catalog_is_paginated_and_counts_distinct(api_client):
    region = RegionFactory()
    spots = [SpotFactory(region=region), SpotFactory(region=region)]
    profile = published_instructor(region=region, spots=spots)
    InstructorOfferFactory(instructor=profile)
    InstructorOfferFactory(instructor=profile)
    data = api_client.get(URL, {"region": region.slug, "page_size": 1}).json()
    assert data["count"] == 1 and len(data["results"]) == 1
    assert set(data) >= {"count", "next", "previous", "results"}


def test_catalog_does_not_require_login_or_professional_registration(make_client):
    published_instructor()
    surfer = make_client(AccountFactory())
    assert surfer.get(URL).status_code == 200


def test_catalog_query_count_does_not_grow_with_profiles(api_client):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    def make(n):
        for _ in range(n):
            profile = published_instructor(spots=[SpotFactory()])
            add_member(OrganizationFactory(), profile.account)
            certificate(profile, status="verified")

    make(2)
    with CaptureQueriesContext(connection) as small:
        assert api_client.get(URL).json()["count"] == 2
    make(5)
    with CaptureQueriesContext(connection) as large:
        assert api_client.get(URL).json()["count"] == 7
    assert len(large.captured_queries) == len(small.captured_queries) <= 10
