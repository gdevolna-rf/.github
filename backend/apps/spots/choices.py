"""Справочники спотов: компас, месяцы, опасности, инфраструктура, подписи редактируемых полей (SPT-02…08).

Коды — машинные (хранятся в БД и приходят от клиента), подписи — по-русски для интерфейса.
"""
from apps.spots.models import COMPASS_POINTS, EDITABLE_SPOT_FIELDS, Spot

# code -> (подпись, сокращение, азимут в градусах). Розы ветра/свелла рисует фронтенд (SPT-04).
COMPASS = {
    "N": ("Север", "С", 0.0),
    "NNE": ("Северо-северо-восток", "ССВ", 22.5),
    "NE": ("Северо-восток", "СВ", 45.0),
    "ENE": ("Восток-северо-восток", "ВСВ", 67.5),
    "E": ("Восток", "В", 90.0),
    "ESE": ("Восток-юго-восток", "ВЮВ", 112.5),
    "SE": ("Юго-восток", "ЮВ", 135.0),
    "SSE": ("Юго-юго-восток", "ЮЮВ", 157.5),
    "S": ("Юг", "Ю", 180.0),
    "SSW": ("Юго-юго-запад", "ЮЮЗ", 202.5),
    "SW": ("Юго-запад", "ЮЗ", 225.0),
    "WSW": ("Запад-юго-запад", "ЗЮЗ", 247.5),
    "W": ("Запад", "З", 270.0),
    "WNW": ("Запад-северо-запад", "ЗСЗ", 292.5),
    "NW": ("Северо-запад", "СЗ", 315.0),
    "NNW": ("Северо-северо-запад", "ССЗ", 337.5),
}
assert list(COMPASS) == COMPASS_POINTS

MONTHS = {
    1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель", 5: "Май", 6: "Июнь",
    7: "Июль", 8: "Август", 9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь",
}

HAZARD_CHOICES = [
    ("rocks", "Камни"),
    ("reef", "Острый риф"),
    ("rip_current", "Отбойное течение (тягун)"),
    ("strong_current", "Сильное течение"),
    ("shallow_water", "Мелководье"),
    ("shore_break", "Шорбрейк"),
    ("big_waves", "Мощные волны"),
    ("cold_water", "Холодная вода"),
    ("crowd", "Много людей в воде"),
    ("marine_life", "Морские животные"),
    ("wild_animals", "Дикие животные на берегу"),
    ("pollution", "Загрязнение воды"),
    ("debris", "Мусор и предметы в воде"),
    ("restricted_area", "Пограничная или закрытая зона"),
    ("difficult_access", "Сложный подход к воде"),
    ("no_lifeguards", "Нет спасателей"),
    ("weather_change", "Резкая смена погоды"),
    ("tides", "Сильные приливы и отливы"),
    ("other", "Другое"),
]
HAZARDS = dict(HAZARD_CHOICES)

INFRASTRUCTURE_CHOICES = [
    ("parking", "Парковка"),
    ("toilet", "Туалет"),
    ("shower", "Душ"),
    ("changing_room", "Раздевалка"),
    ("cafe", "Кафе"),
    ("shop", "Магазин"),
    ("school", "Сёрф-школа"),
    ("rental", "Прокат"),
    ("accommodation", "Жильё"),
    ("camping", "Кемпинг"),
    ("lifeguard", "Спасатели"),
    ("first_aid", "Медпункт"),
    ("public_transport", "Общественный транспорт"),
    ("trail", "Пеший подход"),
    ("other", "Другое"),
]
INFRASTRUCTURE_TYPES = dict(INFRASTRUCTURE_CHOICES)
INFRASTRUCTURE_MAX_ITEMS = 30
INFRASTRUCTURE_MAX_DISTANCE_M = 100_000

FIELD_LABELS = {
    "short_description": "Краткое описание",
    "description": "Описание",
    "difficulty": "Уровень сложности",
    "bottom_type": "Дно",
    "break_type": "Тип брейка",
    "wave_character": "Характер волн",
    "wave_power": "Мощность волн",
    "season": "Сезон",
    "best_months": "Лучшие месяцы",
    "best_wind_directions": "Подходящий ветер",
    "best_swell_directions": "Подходящий свелл",
    "best_tide": "Прилив",
    "typical_conditions": "Типичные условия",
    "hazards": "Опасности",
    "hazard_notes": "Особенности безопасности",
    "entry_exit": "Вход и выход из воды",
    "access": "Как добраться / ограничения доступа",
    "infrastructure": "Инфраструктура",
    "water_temp_note": "Температура воды",
    "seasonal_warning": "Сезонное предупреждение",
}

CHOICE_FIELDS = {
    "difficulty": Spot.Difficulty,
    "bottom_type": Spot.Bottom,
    "break_type": Spot.Break,
}

# Тип редактора поля в форме правки (SPT-08).
FIELD_KINDS = {
    "difficulty": "choice",
    "bottom_type": "choice",
    "break_type": "choice",
    "best_months": "months",
    "best_wind_directions": "compass",
    "best_swell_directions": "compass",
    "hazards": "hazards",
    "infrastructure": "infrastructure",
}
TEXT_MAX_LENGTH = 5000  # для TextField
assert set(FIELD_LABELS) == set(EDITABLE_SPOT_FIELDS)


def field_kind(field):
    return FIELD_KINDS.get(field, "text")


def field_max_length(field):
    if field_kind(field) != "text":
        return None
    return Spot._meta.get_field(field).max_length or TEXT_MAX_LENGTH


def compass_item(code):
    label, short, degrees = COMPASS.get(code, (code, code, None))
    return {"code": code, "label": label, "short": short, "degrees": degrees}


def month_item(month):
    return {"code": month, "label": MONTHS.get(month, str(month))}


def labeled(code, labels):
    return {"code": code, "label": str(labels.get(code, code))}


def choice_item(field, code):
    if code in (None, ""):
        return None
    return labeled(code, dict(CHOICE_FIELDS[field].choices))


def infrastructure_item(item):
    item = item if isinstance(item, dict) else {}
    kind = item.get("type") or "other"
    return {
        "type": kind,
        "type_label": INFRASTRUCTURE_TYPES.get(kind, str(kind)),
        "name": item.get("name") or "",
        "distance_m": item.get("distance_m"),
    }


def display_value(field, value):
    """Человекочитаемое значение для «было → стало» (TRUST-04)."""
    kind = field_kind(field)
    if value in (None, "", []):
        return "—"
    if kind == "choice":
        return str(dict(CHOICE_FIELDS[field].choices).get(value, value))
    if kind == "compass":
        return ", ".join(COMPASS.get(v, (v,))[0] for v in value)
    if kind == "months":
        return ", ".join(MONTHS.get(v, str(v)) for v in value)
    if kind == "hazards":
        return ", ".join(HAZARDS.get(v, v) for v in value)
    if kind == "infrastructure":
        parts = []
        for item in value:
            item = infrastructure_item(item)
            text = item["type_label"]
            if item["name"]:
                text += f" «{item['name']}»"
            if item["distance_m"] is not None:
                text += f" — {item['distance_m']} м"
            parts.append(text)
        return "; ".join(parts)
    return str(value)


def dictionaries():
    """Справочники для фильтров каталога и формы правки (GET spots/dictionaries)."""

    def choices(cls):
        return [{"code": c, "label": str(label)} for c, label in cls.choices]

    return {
        "difficulty": choices(Spot.Difficulty),
        "bottom_type": choices(Spot.Bottom),
        "break_type": choices(Spot.Break),
        "location_precision": choices(Spot.Precision),
        "compass_points": [compass_item(code) for code in COMPASS_POINTS],
        "months": [month_item(m) for m in MONTHS],
        "hazards": [{"code": c, "label": label} for c, label in HAZARD_CHOICES],
        "infrastructure_types": [{"code": c, "label": label} for c, label in INFRASTRUCTURE_CHOICES],
        "editable_fields": [
            {"field": f, "label": FIELD_LABELS[f], "kind": field_kind(f), "max_length": field_max_length(f)}
            for f in EDITABLE_SPOT_FIELDS
        ],
    }
