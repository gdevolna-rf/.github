"""Rule-based помощник подбора (AIX-01..03) — без внешнего AI.

Принципы AIX-02: в ответе только данные каталога ГДеволна (у каждого элемента — источник и дата обновления),
прогноз — только реальный, от провайдера, с датой выпуска; никаких выдуманных фактов; явная оговорка о безопасности.

Объём доски — формула гильд-фактора (rule_version 1):
    объём, л = вес, кг × гильд-фактор уровня × поправка на волну
    гильд-фактор: beginner 0.85–1.00, intermediate 0.55–0.70, advanced 0.42–0.50, pro 0.36–0.42
    поправка на волну: small ×1.10 (слабая волна — больше объёма), medium ×1.00, big ×0.92
"""
import datetime as dt
import zoneinfo
from decimal import ROUND_HALF_UP, Decimal

from django.db.models import Case, F, IntegerField, Q, Value, When
from django.db.models.functions import Abs
from django.utils import timezone

from apps.boards.models import BoardModel, BoardType, BoardVariant
from apps.commerce.models import ACTIVE_BOOKING_STATUSES, Booking
from apps.common.exceptions import DomainError
from apps.inventory.models import InventoryItem
from apps.learning.models import InstructorProfile
from apps.organizations.models import Organization
from apps.search.services import catalog
from apps.spots.models import Region, Spot, SpotForecast

RULE_VERSION = 1
MAX_ITEMS = 6

LEVELS = {
    "beginner": "Новичок",
    "intermediate": "Средний",
    "advanced": "Продвинутый",
    "pro": "Профи",
}
WAVES = {"small": "небольшая волна (до 1 м)", "medium": "средняя волна (1–1,8 м)", "big": "большая волна (от 1,8 м)"}

GUILD_FACTORS = {
    "beginner": (Decimal("0.85"), Decimal("1.00")),
    "intermediate": (Decimal("0.55"), Decimal("0.70")),
    "advanced": (Decimal("0.42"), Decimal("0.50")),
    "pro": (Decimal("0.36"), Decimal("0.42")),
}
WAVE_FACTORS = {"small": Decimal("1.10"), "medium": Decimal("1.00"), "big": Decimal("0.92")}

BOARD_TYPES = {
    ("beginner", "small"): ["softtop", "longboard", "funboard"],
    ("beginner", "medium"): ["softtop", "funboard", "midlength"],
    ("beginner", "big"): ["softtop", "funboard"],
    ("intermediate", "small"): ["funboard", "midlength", "fish", "longboard"],
    ("intermediate", "medium"): ["fish", "hybrid", "funboard", "midlength"],
    ("intermediate", "big"): ["hybrid", "shortboard", "midlength"],
    ("advanced", "small"): ["fish", "hybrid", "egg"],
    ("advanced", "medium"): ["shortboard", "hybrid", "fish"],
    ("advanced", "big"): ["shortboard", "gun"],
    ("pro", "small"): ["shortboard", "fish", "hybrid"],
    ("pro", "medium"): ["shortboard", "hybrid"],
    ("pro", "big"): ["shortboard", "gun"],
}

# Сложность спота, подходящая уровню; порядок — от наиболее соответствующей уровню.
SPOT_DIFFICULTY = {
    "beginner": [Spot.Difficulty.BEGINNER],
    "intermediate": [Spot.Difficulty.INTERMEDIATE, Spot.Difficulty.BEGINNER],
    "advanced": [Spot.Difficulty.ADVANCED, Spot.Difficulty.INTERMEDIATE, Spot.Difficulty.BEGINNER],
    "pro": [Spot.Difficulty.EXPERT, Spot.Difficulty.ADVANCED, Spot.Difficulty.INTERMEDIATE, Spot.Difficulty.BEGINNER],
}

BOARD_DISCLAIMER = (
    "Это ориентир по формуле, а не гарантия: на выбор влияют рост, физическая форма, частота катания и конкретная "
    "модель. Перед покупкой посоветуйтесь с шейпером или инструктором и по возможности возьмите доску на тест."
)
SAFETY_DISCLAIMER = (
    "Подборка сформирована автоматически по правилам из данных каталога ГДеволна и не заменяет оценку условий на "
    "месте. Перед выходом в воду проверьте актуальный прогноз и штормовые предупреждения, оцените течения и свои силы, "
    "не катайтесь в одиночку на незнакомом споте и при сомнениях обратитесь к инструктору или местным сёрферам."
)


def _fmt(value, places=1):
    quant = Decimal(1).scaleb(-places)
    return str(Decimal(value).quantize(quant, rounding=ROUND_HALF_UP)).replace(".", ",")


def _round(value):
    return Decimal(value).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def source_label(moment):
    if moment is None:
        return "Каталог ГДеволна"
    return f"Каталог ГДеволна, данные обновлены {timezone.localtime(moment):%d.%m.%Y}"


# ---------------------------------------------------------------- размер доски (AIX-03)

def _board_types(codes):
    types = {t.code: t for t in BoardType.objects.filter(workshop__isnull=True, code__in=codes)}
    return [{"code": code, "name": types[code].name} for code in codes if code in types]


def _matching_boards(volume_min, volume_max, codes):
    middle = (volume_min + volume_max) / 2
    qs = (BoardVariant.objects
          .filter(is_active=True, volume_l__gte=volume_min, volume_l__lte=volume_max,
                  model__status=BoardModel.Status.PUBLISHED, model__workshop__status=Organization.Status.PUBLISHED)
          .select_related("model__workshop", "model__board_type")
          .annotate(_type_match=Case(When(model__board_type__code__in=codes, then=Value(0)), default=Value(1),
                                     output_field=IntegerField()),
                    _distance=Abs(F("volume_l") - Value(middle)))
          .order_by("_type_match", "_distance", "price", "sku"))
    cards, seen = [], set()
    for variant in qs[:60]:
        if variant.model_id in seen:
            continue
        seen.add(variant.model_id)
        cards.append(variant)
        if len(cards) == MAX_ITEMS:
            break
    models = {m.pk: m for m in catalog.public_board_models().filter(pk__in=[v.model_id for v in cards])}
    result = []
    for variant in cards:
        model = models.get(variant.model_id)
        if model is None:
            continue
        result.append({
            "variant_id": str(variant.pk),
            "model_id": str(model.pk),
            "sku": variant.sku,
            "title": model.name,
            "subtitle": f"{model.workshop.name} · {model.board_type.name}",
            "board_type": {"code": model.board_type.code, "name": model.board_type.name},
            "length_in": catalog.decimal_str(variant.length_in),
            "length_label": catalog.length_label(variant.length_in),
            "width_in": catalog.decimal_str(variant.width_in),
            "thickness_in": catalog.decimal_str(variant.thickness_in),
            "volume_l": catalog.decimal_str(variant.volume_l),
            "price": catalog.money(variant.price),
            "currency": variant.currency,
            "availability": variant.availability,
            "availability_label": variant.get_availability_display(),
            "type_match": variant._type_match == 0,
            "image": catalog.board_model_image(model),
            "url": f"/boards/{model.pk}",
            "source": source_label(variant.updated_at),
        })
    return result


def board_size(weight_kg, level, wave):
    weight = Decimal(str(weight_kg))
    gf_min, gf_max = GUILD_FACTORS[level]
    wave_k = WAVE_FACTORS[wave]
    volume_min, volume_max = _round(weight * gf_min * wave_k), _round(weight * gf_max * wave_k)
    codes = BOARD_TYPES[(level, wave)]
    types = _board_types(codes)
    explanation = (
        f"Объём рассчитан по формуле гильд-фактора: объём (л) = вес (кг) × гильд-фактор уровня × поправка на волну. "
        f"Для уровня «{LEVELS[level]}» гильд-фактор {_fmt(gf_min, 2)}–{_fmt(gf_max, 2)}, поправка для условия "
        f"«{WAVES[wave]}» ×{_fmt(wave_k, 2)}: {_fmt(weight)} кг × {_fmt(gf_min, 2)}…{_fmt(gf_max, 2)} × "
        f"{_fmt(wave_k, 2)} ≈ {_fmt(volume_min)}–{_fmt(volume_max)} л. Чем ниже уровень и слабее волна, тем больше "
        f"нужен объём — доска устойчивее и легче ловит волну."
    )
    if types:
        explanation += " Подходящие типы досок: " + ", ".join(t["name"] for t in types) + "."
    warnings = []
    if level == "beginner" and wave == "big":
        warnings.append("Большая волна не рекомендуется новичкам: начните со спотов для начинающих и занятий "
                        "с инструктором.")
    return {
        "input": {"weight_kg": catalog.decimal_str(weight, 1), "level": level, "wave": wave},
        "volume_l": {"min": catalog.decimal_str(volume_min, 1), "max": catalog.decimal_str(volume_max, 1)},
        "formula": {
            "guild_factor": {"min": catalog.decimal_str(gf_min), "max": catalog.decimal_str(gf_max)},
            "wave_factor": catalog.decimal_str(wave_k),
            "rule_version": RULE_VERSION,
        },
        "board_types": types,
        "explanation": explanation,
        "warnings": warnings,
        "matching_boards": _matching_boards(volume_min, volume_max, codes),
        "disclaimer": BOARD_DISCLAIMER,
    }


# ---------------------------------------------------------------- рекомендации (AIX-01/02)

def resolve_region(value):
    value = str(value or "").strip()
    region = None
    if value.isdigit():
        region = Region.objects.filter(pk=int(value)).first()
    if region is None and value:
        region = Region.objects.filter(slug=value).first()
    if region is None:
        raise DomainError("region_not_found", "Регион не найден.", fields={"region": ["Выберите регион из списка."]})
    return region


def _day_bounds(day, region):
    try:
        tz = zoneinfo.ZoneInfo(region.timezone or "Europe/Moscow")
    except zoneinfo.ZoneInfoNotFoundError:
        tz = zoneinfo.ZoneInfo("Europe/Moscow")
    start = dt.datetime.combine(day, dt.time.min, tzinfo=tz)
    return start, start + dt.timedelta(days=1)


def _forecast(spot, start, end):
    forecast = (SpotForecast.objects.filter(spot=spot, valid_from__lt=end, valid_to__gt=start)
                .order_by("-issued_at", "valid_from").first())
    if forecast is None:
        return None
    return {
        "provider": forecast.provider,
        "issued_at": forecast.issued_at,
        "valid_from": forecast.valid_from,
        "valid_to": forecast.valid_to,
        "wave_height_m": catalog.decimal_str(forecast.wave_height_m),
        "wave_period_s": catalog.decimal_str(forecast.wave_period_s, 1),
        "wave_direction": forecast.wave_direction,
        "wind_speed_ms": catalog.decimal_str(forecast.wind_speed_ms, 1),
        "wind_direction": forecast.wind_direction,
        "water_temp_c": catalog.decimal_str(forecast.water_temp_c, 1),
        "source": f"Прогноз {forecast.provider}, выпущен {timezone.localtime(forecast.issued_at):%d.%m.%Y %H:%M}",
    }


def _spots(region, level, day, start, end):
    allowed = SPOT_DIFFICULTY[level]
    order = Case(*[When(difficulty=d, then=Value(i)) for i, d in enumerate(allowed)], output_field=IntegerField())
    qs = (catalog.public_spots().filter(region=region, difficulty__in=allowed)
          .filter(Q(closed_until__isnull=True) | Q(closed_until__lt=day))
          .annotate(_fit=order).order_by("_fit", "-rating_avg", "name"))
    items = []
    for spot in qs[:MAX_ITEMS]:
        card = catalog.spot_card(spot)
        items.append({
            "type": "spot", "id": str(spot.pk), "slug": spot.slug, "title": card["title"],
            "subtitle": card["subtitle"], "image": card["image"], "url": card["url"],
            "difficulty": spot.difficulty, "difficulty_label": spot.get_difficulty_display(),
            "typical_conditions": spot.typical_conditions,
            "season": spot.season,
            "season_match": (day.month in spot.best_months) if spot.best_months else None,
            "hazards": list(spot.hazards),
            "hazard_notes": spot.hazard_notes,
            "seasonal_warning": spot.seasonal_warning,
            "rating_avg": catalog.decimal_str(spot.rating_avg),
            "rating_count": spot.rating_count,
            "forecast": _forecast(spot, start, end),
            "source": source_label(spot.last_confirmed_at or spot.updated_at),
        })
    return items


def _instructors(region, level):
    in_region = InstructorProfile.objects.filter(Q(regions=region) | Q(spots__region=region)).values("pk")
    qs = (catalog.public_instructors().filter(pk__in=in_region, student_levels__contains=[level])
          .order_by("-rating_avg", "-rating_count", "pk"))
    items = []
    for instructor in qs[:MAX_ITEMS]:
        card = catalog.instructor_card(instructor)
        items.append({
            "type": "instructor", "id": str(instructor.pk), "handle": card["extra"]["handle"],
            "title": card["title"], "subtitle": card["subtitle"], "image": card["image"], "url": card["url"],
            "rating_avg": card["extra"]["rating_avg"], "rating_count": card["extra"]["rating_count"],
            "price_from": card["extra"]["price_from"], "currency": card["extra"]["currency"],
            "certificate_verified": card["extra"]["certificate_verified"],
            "source": source_label(instructor.updated_at),
        })
    return items


def _rentals(region, start, end, check_date):
    qs = (catalog.public_inventory_items()
          .filter(Q(region=region) | Q(spot__region=region),
                  purpose__in=[InventoryItem.Purpose.RENTAL, InventoryItem.Purpose.BOTH],
                  status=InventoryItem.Status.AVAILABLE))
    if check_date:
        busy = Booking.objects.filter(inventory_item__isnull=False, status__in=ACTIVE_BOOKING_STATUSES,
                                      starts_at__lt=end, ends_at__gt=start).values("inventory_item_id")
        qs = qs.exclude(pk__in=busy)
    qs = qs.order_by(F("rental_price_per_day").asc(nulls_last=True), "title", "pk")
    items = []
    for item in qs[:MAX_ITEMS]:
        card = catalog.inventory_item_card(item)
        items.append({
            "type": "rental", "id": str(item.pk), "title": card["title"], "subtitle": card["subtitle"],
            "image": card["image"], "url": card["url"], "kind": item.kind, "kind_label": item.get_kind_display(),
            "price_per_day": card["extra"]["price_per_day"], "price_per_hour": card["extra"]["price_per_hour"],
            "currency": item.currency, "owner_name": card["extra"]["owner_name"],
            "free_on_date": True if check_date else None,
            "source": source_label(item.updated_at),
        })
    return items


def recommend(region_value, level, day=None):
    region = resolve_region(region_value)
    check_date = day is not None
    day = day or timezone.localdate()
    start, end = _day_bounds(day, region)
    spots = _spots(region, level, day, start, end)
    instructors = _instructors(region, level)
    rentals = _rentals(region, start, end, check_date)
    notes = []
    if not spots:
        notes.append("В каталоге нет опубликованных спотов этого региона, подходящих вашему уровню.")
    elif not any(s["forecast"] for s in spots):
        notes.append("Прогноз для выбранной даты недоступен — проверьте условия по официальным источникам "
                     "перед выходом.")
    if not instructors:
        notes.append("В регионе нет опубликованных инструкторов, указавших работу с вашим уровнем.")
    if not rentals:
        notes.append("Свободного проката в регионе в каталоге не найдено.")
    return {
        "region": catalog.region_data(region),
        "level": level,
        "level_label": LEVELS[level],
        "date": day.isoformat(),
        "spots": spots,
        "instructors": instructors,
        "rentals": rentals,
        "notes": notes,
        "disclaimer": SAFETY_DISCLAIMER,
        "rule_version": RULE_VERSION,
        "generated_at": timezone.now(),
    }
