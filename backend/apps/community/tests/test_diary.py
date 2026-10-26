"""Дневник катания: CRUD, видимость каждой записи, статистика (COM-04/06/08, MET-06, F12)."""
import datetime as dt

import pytest
from django.utils import timezone

from apps.community.models import SurfSession
from apps.community.services.diary import compute_stats
from apps.community.tests.factories import SurfSessionFactory, gg_account
from apps.mediafiles.models import MediaAsset
from tests.factories import AccountFactory, MediaAssetFactory, SpotFactory

pytestmark = pytest.mark.django_db

TODAY = dt.date(2026, 10, 21)


def days_ago(n):
    return timezone.localdate() - dt.timedelta(days=n)


# ---------------------------------------------------------------- CRUD


def test_create_entry_with_catalog_spot_and_photos(make_client):
    client = make_client()
    spot = SpotFactory(name="Халактыр")
    photo = MediaAssetFactory(owner=client.account, purpose=MediaAsset.Purpose.DIARY_PHOTO)
    response = client.post("/api/v1/me/diary", {
        "spot_id": str(spot.pk), "date": days_ago(1).isoformat(), "duration_min": 90, "board_note": "Фиш 5'8",
        "conditions": "Оффшор, чисто", "wave_height_m": "1.2", "mood_rating": 5, "notes": "Лучшая сессия",
        "visibility": "community", "photo_ids": [str(photo.pk)],
    }, format="json")
    assert response.status_code == 201, response.content
    body = response.json()
    assert body["spot"]["name"] == "Халактыр"
    assert body["place_name"] == "Халактыр"
    assert body["wave_height_m"] == "1.2"
    assert body["visibility"] == "community"
    assert [p["id"] for p in body["photos"]] == [str(photo.pk)]
    entry = SurfSession.objects.get()
    assert entry.account == client.account


def test_create_entry_with_free_place_name_defaults_to_private(make_client):
    client = make_client()
    response = client.post("/api/v1/me/diary", {"spot_name": "Секретная бухта", "date": days_ago(0).isoformat()},
                           format="json")
    assert response.status_code == 201
    assert response.json()["visibility"] == "private"
    assert response.json()["spot"] is None


@pytest.mark.parametrize("payload,field", [
    ({"date": "2026-01-01"}, "spot_id"),
    ({"spot_name": "X", "date": "2099-01-01"}, "date"),
    ({"spot_name": "X", "date": "2026-01-01", "mood_rating": 6}, "mood_rating"),
    ({"spot_name": "X", "date": "2026-01-01", "duration_min": 0}, "duration_min"),
    ({"spot_name": "X", "date": "2026-01-01", "wave_height_m": "-1"}, "wave_height_m"),
    ({"spot_name": "X", "date": "2026-01-01", "visibility": "friends"}, "visibility"),
])
def test_create_entry_validation(make_client, payload, field):
    response = make_client().post("/api/v1/me/diary", payload, format="json")
    assert response.status_code == 400
    assert field in response.json()["error"]["fields"]


def test_unpublished_spot_rejected(make_client):
    spot = SpotFactory(status="hidden")
    response = make_client().post("/api/v1/me/diary", {"spot_id": str(spot.pk), "date": "2026-01-01"}, format="json")
    assert response.status_code == 400
    assert "spot_id" in response.json()["error"]["fields"]


@pytest.mark.parametrize("make_photo", [
    lambda client: MediaAssetFactory(purpose=MediaAsset.Purpose.DIARY_PHOTO),  # чужой файл
    lambda client: MediaAssetFactory(owner=client.account, purpose=MediaAsset.Purpose.CERTIFICATE),
    lambda client: MediaAssetFactory(owner=client.account, purpose=MediaAsset.Purpose.DIARY_PHOTO,
                                     status=MediaAsset.Status.PENDING),
])
def test_foreign_or_wrong_photos_rejected(make_client, make_photo):
    client = make_client()
    photo = make_photo(client)
    response = client.post("/api/v1/me/diary", {"spot_name": "X", "date": "2026-01-01", "photo_ids": [str(photo.pk)]},
                           format="json")
    assert response.status_code == 400
    assert not SurfSession.objects.exists()


def test_update_and_delete_own_entry(make_client):
    client = make_client()
    entry = SurfSessionFactory(account=client.account, visibility="private")
    url = f"/api/v1/me/diary/{entry.pk}"
    response = client.patch(url, {"visibility": "public", "notes": "Обновлено"}, format="json")
    assert response.status_code == 200
    assert response.json()["visibility"] == "public"
    assert client.get(url).json()["notes"] == "Обновлено"
    # нельзя убрать и спот, и название
    assert client.patch(url, {"spot_name": ""}, format="json").status_code == 400
    assert client.delete(url).status_code == 204
    assert not SurfSession.objects.exists()


def test_replacing_photos_on_update(make_client):
    client = make_client()
    entry = SurfSessionFactory(account=client.account)
    first = MediaAssetFactory(owner=client.account, purpose=MediaAsset.Purpose.DIARY_PHOTO)
    second = MediaAssetFactory(owner=client.account, purpose=MediaAsset.Purpose.DIARY_PHOTO)
    entry.photos.add(first)
    response = client.patch(f"/api/v1/me/diary/{entry.pk}", {"photo_ids": [str(second.pk)]}, format="json")
    assert [p["id"] for p in response.json()["photos"]] == [str(second.pk)]


def test_foreign_entry_is_not_accessible(make_client):
    owner, other = make_client(), make_client()
    entry = SurfSessionFactory(account=owner.account)
    url = f"/api/v1/me/diary/{entry.pk}"
    assert other.get(url).status_code == 404
    assert other.patch(url, {"notes": "взлом"}, format="json").status_code == 404
    assert other.delete(url).status_code == 404
    assert other.get("/api/v1/me/diary/not-a-uuid").status_code == 404
    assert SurfSession.objects.filter(pk=entry.pk, notes="").exists()
    assert other.get("/api/v1/me/diary").json()["count"] == 0


def test_my_diary_filters(make_client):
    client = make_client()
    spot = SpotFactory(slug="kacha")
    SurfSessionFactory(account=client.account, date=days_ago(10), visibility="public")
    SurfSessionFactory(account=client.account, date=days_ago(2), visibility="private", spot=spot)
    assert client.get("/api/v1/me/diary", {"from": days_ago(5).isoformat()}).json()["count"] == 1
    assert client.get("/api/v1/me/diary", {"visibility": "public"}).json()["count"] == 1
    assert client.get("/api/v1/me/diary", {"spot": "kacha"}).json()["count"] == 1
    assert client.get("/api/v1/me/diary", {"from": "bad"}).status_code == 400


def test_guest_cannot_use_my_diary(api_client):
    assert api_client.get("/api/v1/me/diary").status_code == 401
    assert api_client.get("/api/v1/me/diary/stats").status_code == 401


# ---------------------------------------------------------------- видимость (COM-06/08, F12)


@pytest.fixture
def diary_owner():
    owner = gg_account()
    SurfSessionFactory(account=owner, visibility="public", notes="публичная", date=days_ago(3))
    SurfSessionFactory(account=owner, visibility="community", notes="для своих", date=days_ago(2))
    SurfSessionFactory(account=owner, visibility="private", notes="только я", date=days_ago(1),
                       spot_name="Тайное место")
    return owner


def notes_seen(client, owner):
    response = client.get(f"/api/v1/surfers/{owner.profile.handle}/diary")
    assert response.status_code == 200
    return {row["notes"] for row in response.json()["results"]}


def test_guest_sees_only_public_entries(api_client, diary_owner):
    assert notes_seen(api_client, diary_owner) == {"публичная"}


def test_non_gg_user_sees_only_public_entries(make_client, diary_owner):
    assert notes_seen(make_client(AccountFactory()), diary_owner) == {"публичная"}


def test_gg_member_sees_public_and_community_entries(make_client, diary_owner):
    assert notes_seen(make_client(gg_account()), diary_owner) == {"публичная", "для своих"}


def test_owner_sees_all_entries(make_client, diary_owner):
    assert notes_seen(make_client(diary_owner), diary_owner) == {"публичная", "для своих", "только я"}


def test_public_profile_stats_count_only_visible_entries(api_client, make_client, diary_owner):
    """COM-08: статистика не раскрывает больше, чем опубликовал владелец."""
    guest_stats = api_client.get(f"/api/v1/surfers/{diary_owner.profile.handle}").json()["diary"]
    assert guest_stats["sessions"] == 1
    assert guest_stats["ride_days"] == 1
    member_stats = make_client(gg_account()).get(f"/api/v1/surfers/{diary_owner.profile.handle}").json()["diary"]
    assert member_stats["sessions"] == 2
    assert "Тайное место" not in str(member_stats)


def test_diary_of_non_gg_account_is_hidden_even_if_public(api_client):
    owner = AccountFactory()
    SurfSessionFactory(account=owner, visibility="public")
    assert api_client.get(f"/api/v1/surfers/{owner.profile.handle}/diary").status_code == 404


def test_public_entry_hides_unpublished_spot_and_private_photos(api_client):
    owner = gg_account()
    spot = SpotFactory(status="hidden", name="Закрытый спот")
    entry = SurfSessionFactory(account=owner, spot=spot, spot_name="", visibility="public")
    entry.photos.add(MediaAssetFactory(owner=owner, purpose="diary_photo", visibility="private"),
                     MediaAssetFactory(owner=owner, purpose="diary_photo", status="processing"))
    row = api_client.get(f"/api/v1/surfers/{owner.profile.handle}/diary").json()["results"][0]
    assert row["spot"] is None
    assert row["photos"] == []
    assert "created_at" not in row


# ---------------------------------------------------------------- статистика (MET-06)


def test_stats_endpoint(make_client):
    client = make_client()
    spot = SpotFactory(name="Кача")
    today = timezone.localdate()
    for offset in (0, 1, 2):  # текущая серия 3 дня
        SurfSessionFactory(account=client.account, spot=spot, spot_name="", date=today - dt.timedelta(days=offset))
    SurfSessionFactory(account=client.account, spot=spot, spot_name="", date=today)  # второй выход в тот же день
    SurfSessionFactory(account=client.account, spot_name="Бухта Ольга", date=today - dt.timedelta(days=10))
    SurfSessionFactory(account=client.account, spot_name="бухта ольга", date=today - dt.timedelta(days=11))
    stats = client.get("/api/v1/me/diary/stats").json()
    assert stats["sessions"] == 6
    assert stats["ride_days"] == 5
    assert stats["spots_visited"] == 2
    assert stats["current_streak_days"] == 3
    assert stats["longest_streak_days"] == 3
    assert stats["top_spots"][0]["name"] == "Кача"
    assert stats["top_spots"][0]["days"] == 3
    assert stats["top_spots"][0]["spot"]["slug"] == spot.slug
    assert stats["top_spots"][1] == {"spot": None, "name": "Бухта Ольга", "days": 2}
    assert stats["last_ride_date"] == today.isoformat()


def test_streaks_and_year_counters():
    account = AccountFactory()
    dates = [dt.date(2025, 12, 30), dt.date(2025, 12, 31), dt.date(2026, 1, 1), dt.date(2026, 1, 2),
             dt.date(2026, 10, 19), dt.date(2026, 10, 20)]
    for day in dates:
        SurfSessionFactory(account=account, date=day)
    stats = compute_stats(SurfSession.objects.filter(account=account), today=TODAY)
    assert stats["longest_streak_days"] == 4
    assert stats["current_streak_days"] == 2  # вчера + позавчера, сегодня ещё не катался
    assert stats["this_year_days"] == 4
    later = compute_stats(SurfSession.objects.filter(account=account), today=TODAY + dt.timedelta(days=2))
    assert later["current_streak_days"] == 0


def test_empty_stats():
    stats = compute_stats(SurfSession.objects.none(), today=TODAY)
    assert stats == {"ride_days": 0, "sessions": 0, "spots_visited": 0, "this_year_days": 0,
                     "longest_streak_days": 0, "current_streak_days": 0, "last_ride_date": None, "top_spots": []}
