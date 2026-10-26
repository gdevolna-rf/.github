"""Rule-based помощник (AIX-01..03): формула объёма, только данные каталога, источники и оговорки (AIX-02)."""
import datetime as dt
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.boards.models import BoardType
from apps.commerce.models import Booking
from apps.inventory.models import InventoryItem
from apps.spots.models import Spot, SpotForecast
from tests.factories import (
    AccountFactory,
    BoardModelFactory,
    BoardVariantFactory,
    InstructorProfileFactory,
    InventoryItemFactory,
    RegionFactory,
    SpotFactory,
    WorkshopFactory,
)

pytestmark = pytest.mark.django_db


def board_size(client, **data):
    payload = {"weight_kg": 75, "level": "intermediate", "wave": "medium", **data}
    return client.post("/api/v1/assistant/board-size", payload, format="json")


def recommend(client, **data):
    return client.post("/api/v1/assistant/recommend", data, format="json")


# ---------------------------------------------------------------- объём доски (AIX-03)


def test_board_size_uses_guild_factor_formula(api_client):
    body = board_size(api_client).json()
    # 75 × 0,55…0,70 × 1,00
    assert body["volume_l"] == {"min": "41.3", "max": "52.5"}
    assert body["formula"] == {"guild_factor": {"min": "0.55", "max": "0.70"}, "wave_factor": "1.00",
                               "rule_version": 1}
    assert "гильд-фактор" in body["explanation"]
    assert "75,0 кг × 0,55…0,70 × 1,00" in body["explanation"]
    assert [t["code"] for t in body["board_types"]] == ["fish", "hybrid", "funboard", "midlength"]
    assert body["disclaimer"]


@pytest.mark.parametrize("level,wave,expected", [
    ("beginner", "small", {"min": "70.1", "max": "82.5"}),   # 75 × 0,85…1,00 × 1,10
    ("advanced", "big", {"min": "29.0", "max": "34.5"}),     # 75 × 0,42…0,50 × 0,92
    ("pro", "medium", {"min": "27.0", "max": "31.5"}),
])
def test_board_size_ranges(api_client, level, wave, expected):
    assert board_size(api_client, level=level, wave=wave).json()["volume_l"] == expected


def test_beginner_big_wave_gets_safety_warning(api_client):
    body = board_size(api_client, level="beginner", wave="big").json()
    assert body["warnings"] and "новичкам" in body["warnings"][0]


@pytest.mark.parametrize("data,field", [
    ({"weight_kg": 10}, "weight_kg"), ({"weight_kg": 400}, "weight_kg"),
    ({"level": "god"}, "level"), ({"wave": "tsunami"}, "wave"),
])
def test_board_size_validation(api_client, data, field):
    response = board_size(api_client, **data)
    assert response.status_code == 400
    assert field in response.json()["error"]["fields"]


def test_matching_boards_only_published_in_range_and_preferred_types(api_client):
    workshop = WorkshopFactory(name="Шейп-Камчатка")
    fish = BoardModelFactory(workshop=workshop, name="Рыба",
                             board_type=BoardType.objects.get(workshop=None, code="fish"))
    short = BoardModelFactory(workshop=workshop, name="Шорт")
    BoardVariantFactory(model=fish, volume_l=Decimal("45"), price=Decimal("60000"))
    BoardVariantFactory(model=fish, volume_l=Decimal("46"), price=Decimal("61000"))  # тот же model — одна карточка
    BoardVariantFactory(model=short, volume_l=Decimal("44"))
    BoardVariantFactory(model=short, volume_l=Decimal("30"))  # вне диапазона
    draft = BoardModelFactory(workshop=workshop, status="draft")
    BoardVariantFactory(model=draft, volume_l=Decimal("45"))
    hidden_workshop_model = BoardModelFactory(workshop=WorkshopFactory(status="draft"))
    BoardVariantFactory(model=hidden_workshop_model, volume_l=Decimal("45"))
    BoardVariantFactory(model=short, volume_l=Decimal("45"), is_active=False)
    boards = board_size(api_client).json()["matching_boards"]
    assert [b["title"] for b in boards] == ["Рыба", "Шорт"]
    assert boards[0]["type_match"] is True and boards[1]["type_match"] is False
    assert boards[0]["url"] == f"/boards/{fish.pk}"
    assert boards[0]["price"] == "61000.00"  # вариант ближе к середине диапазона (46,9 л)
    assert boards[0]["source"].startswith("Каталог ГДеволна, данные обновлены")
    assert boards[0]["length_label"] == "5′10″"


def test_matching_boards_capped_at_six(api_client):
    for _ in range(8):
        BoardVariantFactory(volume_l=Decimal("45"))
    assert len(board_size(api_client).json()["matching_boards"]) == 6


# ---------------------------------------------------------------- рекомендации (AIX-01/02)


@pytest.fixture
def region():
    return RegionFactory(slug="kamchatka", name="Камчатский край")


def test_recommend_spots_match_level_and_carry_sources(api_client, region):
    easy = SpotFactory(region=region, name="Халактыр", difficulty=Spot.Difficulty.BEGINNER,
                       typical_conditions="Волна 0,5–1 м", last_confirmed_at=timezone.now(), best_months=[7, 8, 9])
    SpotFactory(region=region, name="Риф", difficulty=Spot.Difficulty.EXPERT)
    SpotFactory(region=region, name="Скрытый", difficulty=Spot.Difficulty.BEGINNER, status="hidden")
    SpotFactory(region=region, name="Закрыт", difficulty=Spot.Difficulty.BEGINNER,
                closed_until=timezone.localdate() + dt.timedelta(days=30))
    SpotFactory(name="Другой регион", difficulty=Spot.Difficulty.BEGINNER)
    body = recommend(api_client, region="kamchatka", level="beginner").json()
    assert [s["title"] for s in body["spots"]] == ["Халактыр"]
    spot = body["spots"][0]
    assert spot["url"] == f"/spots/{easy.slug}"
    assert spot["typical_conditions"] == "Волна 0,5–1 м"
    assert spot["source"] == f"Каталог ГДеволна, данные обновлены {timezone.localdate():%d.%m.%Y}"
    assert spot["forecast"] is None
    assert body["disclaimer"]
    assert any("Прогноз" in note for note in body["notes"])


def test_recommend_orders_spots_by_level_fit(api_client, region):
    SpotFactory(region=region, name="Лёгкий", difficulty=Spot.Difficulty.BEGINNER)
    SpotFactory(region=region, name="Средний", difficulty=Spot.Difficulty.INTERMEDIATE)
    SpotFactory(region=region, name="Сложный", difficulty=Spot.Difficulty.ADVANCED)
    body = recommend(api_client, region=str(region.pk), level="intermediate").json()
    assert [s["title"] for s in body["spots"]] == ["Средний", "Лёгкий"]


def test_recommend_includes_real_forecast_for_date(api_client, region):
    spot = SpotFactory(region=region, difficulty=Spot.Difficulty.BEGINNER)
    day = timezone.localdate() + dt.timedelta(days=2)
    start = timezone.make_aware(dt.datetime.combine(day, dt.time(9)))
    SpotForecast.objects.create(spot=spot, provider="open-meteo", issued_at=timezone.now(), valid_from=start,
                                valid_to=start + dt.timedelta(hours=3), wave_height_m=Decimal("1.20"))
    body = recommend(api_client, region="kamchatka", level="beginner", date=day.isoformat()).json()
    forecast = body["spots"][0]["forecast"]
    assert forecast["provider"] == "open-meteo"
    assert forecast["wave_height_m"] == "1.20"
    assert forecast["source"].startswith("Прогноз open-meteo, выпущен")
    assert body["date"] == day.isoformat()


def test_recommend_instructors_in_region_teaching_level(api_client, region):
    good = InstructorProfileFactory(student_levels=["beginner"], rating_avg=Decimal("4.9"))
    good.regions.add(region)
    by_spot = InstructorProfileFactory(student_levels=["beginner", "intermediate"])
    by_spot.spots.add(SpotFactory(region=region))
    wrong_level = InstructorProfileFactory(student_levels=["advanced"])
    wrong_level.regions.add(region)
    draft = InstructorProfileFactory(student_levels=["beginner"], status="draft")
    draft.regions.add(region)
    elsewhere = InstructorProfileFactory(student_levels=["beginner"])
    elsewhere.regions.add(RegionFactory())
    body = recommend(api_client, region="kamchatka", level="beginner").json()
    assert [i["id"] for i in body["instructors"]] == [str(good.pk), str(by_spot.pk)]
    assert body["instructors"][0]["url"] == f"/instructors/{good.account.profile.handle}"
    assert body["instructors"][0]["source"].startswith("Каталог ГДеволна")


def test_recommend_rentals_free_on_date(api_client, region):
    cheap = InventoryItemFactory(region=region, rental_price_per_day=Decimal("1500"))
    busy = InventoryItemFactory(region=region, rental_price_per_day=Decimal("1000"))
    InventoryItemFactory(region=region, purpose=InventoryItem.Purpose.SALE)
    InventoryItemFactory(region=region, status=InventoryItem.Status.MAINTENANCE)
    InventoryItemFactory(region=region, is_published=False)
    day = timezone.localdate() + dt.timedelta(days=3)
    start = timezone.make_aware(dt.datetime.combine(day, dt.time(10)))
    Booking.objects.create(kind=Booking.Kind.RENTAL, status=Booking.Status.CONFIRMED, customer=AccountFactory(),
                           provider_account=busy.owner_account, inventory_item=busy, starts_at=start,
                           ends_at=start + dt.timedelta(hours=4))
    without_date = recommend(api_client, region="kamchatka", level="beginner").json()
    assert [r["id"] for r in without_date["rentals"]] == [str(busy.pk), str(cheap.pk)]
    with_date = recommend(api_client, region="kamchatka", level="beginner", date=day.isoformat()).json()
    assert [r["id"] for r in with_date["rentals"]] == [str(cheap.pk)]
    assert with_date["rentals"][0]["free_on_date"] is True
    assert with_date["rentals"][0]["url"] == f"/rentals/{cheap.pk}"


def test_recommend_with_empty_catalog_invents_nothing(api_client, region):
    body = recommend(api_client, region="kamchatka", level="pro").json()
    assert body["spots"] == [] and body["instructors"] == [] and body["rentals"] == []
    assert len(body["notes"]) == 3
    assert body["region"] == {"id": region.pk, "slug": "kamchatka", "name": "Камчатский край"}


@pytest.mark.parametrize("data,field", [
    ({"region": "atlantis", "level": "beginner"}, "region"),
    ({"region": "kamchatka", "level": "god"}, "level"),
    ({"region": "kamchatka", "level": "beginner", "date": "2001-01-01"}, "date"),
])
def test_recommend_validation(api_client, region, data, field):
    response = recommend(api_client, **data)
    assert response.status_code == 400
    assert field in response.json()["error"]["fields"]
