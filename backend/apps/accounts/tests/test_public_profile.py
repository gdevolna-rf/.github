"""GET /profiles/{handle}: только публичные поля (ACC-14), поля сообщества — по согласию GG (BR-12, COM-02)."""
import datetime as dt

import pytest

from apps.accounts.models import UserProfile
from apps.learning.models import InstructorProfile
from apps.organizations.models import Organization
from tests.factories import (
    AccountFactory,
    InstructorProfileFactory,
    OrganizationFactory,
    RegionFactory,
    SpotFactory,
    add_member,
    add_specialty,
)

pytestmark = pytest.mark.django_db

PRIVATE = ("email", "phone", "birth_date", "private_contacts")


def profile_of(account, **fields):
    UserProfile.objects.filter(account=account).update(**fields)
    return UserProfile.objects.get(account=account)


def get(client, handle):
    return client.get(f"/api/v1/profiles/{handle}")


def test_public_profile_hides_private_and_gg_fields_without_consent(api_client):
    account = AccountFactory()
    profile = profile_of(account, phone="+79990000000", birth_date=dt.date(1990, 1, 1), private_contacts="secret",
                         bio="О себе", city="Сочи")
    body = get(api_client, profile.handle).json()
    assert body["id"] == str(account.pk)
    assert body["gg_surfer"] is False and body["gg"] is None
    text = str(body)
    for value in (account.email, "+79990000000", "1990", "secret", "Сочи"):
        assert value not in text
    for key in PRIVATE:
        assert key not in body


def test_gg_fields_follow_privacy_flags(api_client):
    region = RegionFactory()
    spot = SpotFactory()
    account = AccountFactory()
    today = dt.date.today()
    profile = profile_of(account, gg_surfer_enabled=True, bio="Катаю", region=region, city="Сочи",
                         gg_show_region=False, gg_show_age=True,
                         birth_date=dt.date(today.year - 30, 1, 1), riding_level="advanced")
    profile.favorite_spots.add(spot)
    gg = get(api_client, profile.handle).json()["gg"]
    assert gg["bio"] == "Катаю"
    assert gg["region"] is None and gg["city"] == ""
    assert gg["age"] in (29, 30)
    assert "birth_date" not in gg
    assert gg["favorite_spots"] == [{"id": str(spot.pk), "slug": spot.slug, "name": spot.name}]
    UserProfile.objects.filter(pk=profile.pk).update(gg_show_region=True, gg_show_age=False)
    gg = get(api_client, profile.handle).json()["gg"]
    assert gg["region"]["slug"] == region.slug and gg["city"] == "Сочи" and gg["age"] is None


def test_specialties_instructor_link_and_published_organizations(api_client):
    account = AccountFactory()
    add_specialty(account, "shaper")
    instructor = InstructorProfileFactory(account=account, status=InstructorProfile.Status.PUBLISHED)
    published = OrganizationFactory()
    draft = OrganizationFactory(status=Organization.Status.DRAFT)
    add_member(published, account)
    add_member(draft, account)
    body = get(api_client, account.profile.handle).json()
    assert set(body["specialties"]) == {"surfer", "shaper", "instructor"}
    assert body["instructor_profile"] == {"id": str(instructor.pk), "handle": account.profile.handle}
    assert [o["id"] for o in body["organizations"]] == [str(published.pk)]


def test_unpublished_instructor_profile_is_not_linked(api_client):
    instructor = InstructorProfileFactory(status=InstructorProfile.Status.HIDDEN)
    assert get(api_client, instructor.account.profile.handle).json()["instructor_profile"] is None


def test_unknown_inactive_and_anonymized_profiles_are_404(api_client):
    assert get(api_client, "nobody-here").status_code == 404
    inactive = AccountFactory(is_active=False)
    assert get(api_client, inactive.profile.handle).status_code == 404
    from django.utils import timezone

    anonymized = AccountFactory(anonymized_at=timezone.now())
    assert get(api_client, anonymized.profile.handle).status_code == 404
