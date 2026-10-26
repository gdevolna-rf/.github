"""Каталог GG Surfer: отдельное согласие (BR-12, ACC-06), приватность карточки (ACC-14, CLB-04), блокировки (COM-07)."""
import datetime as dt
import json

import pytest
from django.utils import timezone

from apps.accounts.models import HandleRedirect, UserProfile
from apps.community.tests.factories import gg_account
from apps.messaging.models import AccountBlock
from apps.trust.models import AccountRestriction
from tests.factories import AccountFactory, InstructorProfileFactory, MediaAssetFactory, RegionFactory, SpotFactory

pytestmark = pytest.mark.django_db


def surfers(client, **params):
    response = client.get("/api/v1/surfers", params)
    assert response.status_code == 200, response.content
    return response.json()


def handles(body):
    return {row["handle"] for row in body["results"]}


def test_catalog_lists_only_gg_enabled_active_accounts(api_client):
    visible = gg_account()
    AccountFactory()  # без согласия GG Surfer
    inactive = gg_account()
    inactive.is_active = False
    inactive.save()
    anonymized = gg_account()
    anonymized.anonymized_at = timezone.now()
    anonymized.save()
    suspended = gg_account()
    AccountRestriction.objects.create(account=suspended, kind=AccountRestriction.Kind.SUSPENDED, reason="спам")
    lifted = gg_account()
    AccountRestriction.objects.create(account=lifted, kind=AccountRestriction.Kind.SUSPENDED, reason="старое",
                                      lifted_at=timezone.now())
    assert handles(surfers(api_client)) == {visible.profile.handle, lifted.profile.handle}


def test_disabling_gg_surfer_hides_profile_without_losing_account(api_client):
    """ACC-06: согласие можно отключить без потери аккаунта."""
    account = gg_account()
    assert api_client.get(f"/api/v1/surfers/{account.profile.handle}").status_code == 200
    UserProfile.objects.filter(pk=account.pk).update(gg_surfer_enabled=False)
    assert api_client.get(f"/api/v1/surfers/{account.profile.handle}").status_code == 404
    assert surfers(api_client)["count"] == 0
    account.refresh_from_db()
    assert account.is_active


def test_card_never_exposes_private_fields(api_client):
    region = RegionFactory(name="Камчатка")
    account = gg_account(region=region, phone="+79990001122", birth_date=dt.date(1990, 5, 17), city="Елизово",
                         private_contacts="tg: @secret", gg_show_region=True, gg_show_age=True)
    raw = api_client.get("/api/v1/surfers").content.decode()
    detail = api_client.get(f"/api/v1/surfers/{account.profile.handle}").content.decode()
    for text in (raw, detail):
        assert account.email not in text
        assert "+79990001122" not in text
        assert "1990-05-17" not in text
        assert "Елизово" not in text
        assert "@secret" not in text
        assert "birth_date" not in text
    card = json.loads(raw)["results"][0]
    assert card["region"]["name"] == "Камчатка"
    assert card["age"] == timezone.localdate().year - 1990 - (
        (timezone.localdate().month, timezone.localdate().day) < (5, 17))


def test_region_and_age_hidden_unless_allowed(api_client):
    gg_account(region=RegionFactory(), birth_date=dt.date(1995, 1, 1), gg_show_region=False, gg_show_age=False)
    card = surfers(api_client)["results"][0]
    assert card["region"] is None
    assert card["age"] is None


def test_age_requires_birth_date(api_client):
    gg_account(gg_show_age=True, birth_date=None)
    assert surfers(api_client)["results"][0]["age"] is None


def test_region_filter_ignores_hidden_regions(api_client):
    region = RegionFactory(slug="kamchatka")
    shown = gg_account(region=region, gg_show_region=True)
    gg_account(region=region, gg_show_region=False)
    assert handles(surfers(api_client, region="kamchatka")) == {shown.profile.handle}
    assert handles(surfers(api_client, region=str(region.pk))) == {shown.profile.handle}
    assert surfers(api_client, region="unknown")["count"] == 0


def test_q_does_not_match_hidden_region(api_client):
    region = RegionFactory(name="Сахалин")
    gg_account(region=region, gg_show_region=False, first_name="Анна")
    assert surfers(api_client, q="Сахалин")["count"] == 0
    assert surfers(api_client, q="анн")["count"] == 1


def test_filters_by_spot_level_interest_board_type(api_client):
    spot = SpotFactory(slug="halaktyr")
    match = gg_account(riding_level="intermediate", interests=["Кемпинг", "Фотография"],
                       preferred_board_types=["longboard"], favorite_spots=[spot])
    gg_account(riding_level="beginner", interests=["Йога"], preferred_board_types=["shortboard"])
    assert handles(surfers(api_client, spot="halaktyr")) == {match.profile.handle}
    assert handles(surfers(api_client, spot=str(spot.pk))) == {match.profile.handle}
    assert handles(surfers(api_client, level="intermediate")) == {match.profile.handle}
    assert handles(surfers(api_client, interest="кемпинг")) == {match.profile.handle}
    assert handles(surfers(api_client, board_type="longboard")) == {match.profile.handle}
    assert surfers(api_client, q="фотограф")["count"] == 1
    assert api_client.get("/api/v1/surfers", {"level": "god"}).status_code == 400


def test_card_contains_public_profile_fields(api_client):
    spot = SpotFactory(name="Халактыр")
    hidden_spot = SpotFactory(status="hidden")
    avatar = MediaAssetFactory(purpose="avatar")
    account = gg_account(first_name="Алексей", last_name="Морозов", surfing_since=timezone.localdate().year - 8,
                         riding_level="advanced", preferred_board_types=["shortboard"], interests=["Походы"],
                         bio="Катаюсь круглый год. " * 30, fun_facts=["Видел косатку"], avatar=avatar,
                         favorite_spots=[spot, hidden_spot])
    card = surfers(api_client)["results"][0]
    assert card["id"] == str(account.pk)
    assert card["display_name"] == "Алексей Морозов"
    assert card["experience_years"] == 8
    assert card["riding_level_label"] == "Продвинутый"
    assert [s["name"] for s in card["favorite_spots"]] == ["Халактыр"]
    assert len(card["bio_excerpt"]) <= 201 and card["bio_excerpt"].endswith("…")
    assert card["fun_facts"] == ["Видел косатку"]
    assert card["avatar"]["id"] == str(avatar.pk)
    assert card["url"] == f"/surfers/{account.profile.handle}"


def test_can_message_respects_policy_blocks_and_self(make_client, api_client):
    open_ = gg_account()
    closed = gg_account(gg_contact_policy=UserProfile.ContactPolicy.NOBODY)
    viewer = make_client(gg_account())
    cards = {row["handle"]: row for row in surfers(viewer)["results"]}
    assert cards[open_.profile.handle]["can_message"] is True
    assert cards[closed.profile.handle]["can_message"] is False
    assert cards[closed.profile.handle]["accepts_messages"] is False
    me = cards[viewer.account.profile.handle]
    assert me["can_message"] is False and me["is_me"] is True
    # Гость видит анкету, но написать сможет только после входа.
    guest_cards = {row["handle"]: row for row in surfers(api_client)["results"]}
    assert guest_cards[open_.profile.handle]["can_message"] is False
    assert guest_cards[open_.profile.handle]["accepts_messages"] is True


@pytest.mark.parametrize("direction", ["viewer_blocked", "blocked_viewer"])
def test_blocked_accounts_are_hidden_both_ways(make_client, direction):
    target = gg_account()
    viewer = make_client(gg_account())
    if direction == "viewer_blocked":
        AccountBlock.objects.create(blocker=viewer.account, blocked=target)
    else:
        AccountBlock.objects.create(blocker=target, blocked=viewer.account)
    assert target.profile.handle not in handles(surfers(viewer))
    assert viewer.get(f"/api/v1/surfers/{target.profile.handle}").status_code == 404
    assert viewer.get(f"/api/v1/surfers/{target.profile.handle}/diary").status_code == 404


def test_detail_includes_public_extras(api_client):
    account = gg_account(bio="Полный текст о себе", languages=["ru", "en"])
    InstructorProfileFactory(account=account)
    body = api_client.get(f"/api/v1/surfers/{account.profile.handle}").json()
    assert body["bio"] == "Полный текст о себе"
    assert body["languages"] == ["ru", "en"]
    assert body["instructor_url"] == f"/instructors/{account.profile.handle}"
    assert body["member_since"] == account.date_joined.year
    assert body["diary"]["ride_days"] == 0


def test_detail_unknown_or_non_gg_returns_404(api_client):
    assert api_client.get("/api/v1/surfers/nobody-here").status_code == 404
    plain = AccountFactory()
    response = api_client.get(f"/api/v1/surfers/{plain.profile.handle}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "surfer_not_found"


def test_old_handle_returns_redirect(api_client):
    account = gg_account()
    HandleRedirect.objects.create(old_handle="old-name", account=account)
    assert api_client.get("/api/v1/surfers/old-name").json() == {"redirect": account.profile.handle}


def test_list_query_count_is_bounded(api_client, django_assert_max_num_queries):
    spot = SpotFactory()
    for _ in range(6):
        gg_account(favorite_spots=[spot], region=RegionFactory())
    with django_assert_max_num_queries(6):
        assert surfers(api_client)["count"] == 6
