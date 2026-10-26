"""Маркеры карты в кеше (SPT-01) и прогноз провайдера (GEO-04, SPT-04)."""
import datetime as dt
from decimal import Decimal

import pytest
from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone

from apps.mediafiles.models import MediaAsset
from apps.spots.forecast import ForecastPoint, ForecastProvider, ForecastResult, NoneProvider, get_provider
from apps.spots.models import Spot, SpotForecast, SpotPhoto
from apps.spots.services.catalog import MAP_CACHE_KEY
from apps.spots.tasks import refresh_forecasts
from tests.factories import MediaAssetFactory, SpotFactory

pytestmark = pytest.mark.django_db


class FakeProvider(ForecastProvider):
    name = "fake"
    title = "Тестовый прогноз"
    calls = []

    def fetch(self, spot):
        FakeProvider.calls.append((spot.slug, spot.lat))
        if spot.slug == "broken":
            raise RuntimeError("provider down")
        now = timezone.now().replace(minute=0, second=0, microsecond=0)
        return ForecastResult(issued_at=now, points=[
            ForecastPoint(valid_from=now + dt.timedelta(hours=h), valid_to=now + dt.timedelta(hours=h + 3),
                          wave_height_m=Decimal("1.20"), wave_period_s=Decimal("9.0"), wave_direction="SE",
                          wind_speed_ms=Decimal("4.5"), wind_direction="NW")
            for h in (0, 3)
        ])


FAKE = "apps.spots.tests.test_spots_map_forecast.FakeProvider"


def test_map_returns_lightweight_markers_for_public_spots(api_client):
    spot = SpotFactory(name="Англичанка")
    SpotFactory(status=Spot.Status.HIDDEN)
    data = api_client.get("/api/v1/spots/map").json()
    assert data["count"] == 1
    marker = data["markers"][0]
    assert marker["slug"] == spot.slug and marker["difficulty_label"]
    assert set(marker) == {"id", "slug", "name", "region_slug", "region_name", "lat", "lng", "precise", "difficulty",
                           "difficulty_label", "status", "is_closed", "rating_avg", "rating_count", "thumbnail_url"}


def test_map_is_cached_and_invalidated_when_spot_changes(api_client, django_assert_max_num_queries):
    spot = SpotFactory(name="Старое имя")
    api_client.get("/api/v1/spots/map")
    assert cache.get(MAP_CACHE_KEY) is not None
    with django_assert_max_num_queries(0):
        api_client.get("/api/v1/spots/map")
    spot.name = "Новое имя"
    spot.save()
    assert cache.get(MAP_CACHE_KEY) is None
    assert api_client.get("/api/v1/spots/map").json()["markers"][0]["name"] == "Новое имя"


def test_map_cache_invalidated_when_photo_added_or_spot_hidden(api_client):
    spot = SpotFactory()
    assert api_client.get("/api/v1/spots/map").json()["markers"][0]["thumbnail_url"] is None
    media = MediaAssetFactory(purpose=MediaAsset.Purpose.SPOT_PHOTO)
    SpotPhoto.objects.create(spot=spot, media=media, position=0)
    assert api_client.get("/api/v1/spots/map").json()["markers"][0]["thumbnail_url"].endswith(media.storage_key)
    spot.status = Spot.Status.HIDDEN
    spot.save()
    assert api_client.get("/api/v1/spots/map").json()["count"] == 0


def test_map_region_filter(api_client):
    a = SpotFactory(region__slug="kam")
    SpotFactory(region__slug="crimea")
    data = api_client.get("/api/v1/spots/map?region=kam").json()
    assert [m["id"] for m in data["markers"]] == [str(a.id)]


def test_default_provider_is_none_and_makes_no_requests():
    assert isinstance(get_provider(), NoneProvider)
    SpotFactory()
    assert refresh_forecasts() == {"provider": None, "spots": 0, "points": 0, "errors": 0}


@override_settings(FORECAST_PROVIDER="no.such.Provider")
def test_unknown_provider_falls_back_to_none():
    assert isinstance(get_provider(), NoneProvider)


def test_forecast_without_provider_returns_null_provider_and_message(api_client):
    spot = SpotFactory()
    data = api_client.get(f"/api/v1/spots/{spot.slug}/forecast").json()
    assert data["provider"] is None and data["items"] == [] and data["issued_at"] is None
    assert data["message"]


def test_forecast_of_hidden_spot_is_404(api_client):
    spot = SpotFactory(status=Spot.Status.HIDDEN)
    assert api_client.get(f"/api/v1/spots/{spot.slug}/forecast").status_code == 404


@override_settings(FORECAST_PROVIDER=FAKE)
def test_refresh_task_stores_forecast_and_endpoint_returns_it(api_client):
    FakeProvider.calls = []
    spot = SpotFactory(slug="ok", lat=Decimal("52.934860"), location_precision=Spot.Precision.REGION_ONLY)
    SpotFactory(slug="broken")
    stats = refresh_forecasts.delay().get()
    assert stats == {"provider": "fake", "spots": 1, "points": 2, "errors": 1}
    # провайдер получает точные координаты даже для скрытой геоточки — запрос делает сервер
    assert ("ok", Decimal("52.934860")) in FakeProvider.calls
    data = api_client.get(f"/api/v1/spots/{spot.slug}/forecast").json()
    assert data["provider"] == "fake" and data["provider_title"] == "Тестовый прогноз"
    assert len(data["items"]) == 2 and data["items"][0]["wave_height_m"] == "1.20"
    assert data["issued_at"] and data["message"] == ""
    # повторный опрос заменяет выпуск, а не дублирует его
    refresh_forecasts()
    assert SpotForecast.objects.filter(spot=spot).count() == 2


@override_settings(FORECAST_PROVIDER=FAKE)
def test_forecast_with_provider_but_no_data_explains_it(api_client):
    spot = SpotFactory()
    data = api_client.get(f"/api/v1/spots/{spot.slug}/forecast").json()
    assert data["provider"] == "fake" and data["items"] == [] and data["message"]
