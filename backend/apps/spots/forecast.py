"""Интерфейс провайдера прогнозов (GEO-04). Прогноз хранится отдельно от «типичных условий» (SPT-04).

Провайдер выбирается настройкой FORECAST_PROVIDER: короткое имя из PROVIDERS ("none" — по умолчанию,
без сетевых запросов) или dotted path к классу-наследнику ForecastProvider. Запросы к провайдеру делает
только Celery-задача spots.refresh_forecasts; HTTP-эндпоинт читает сохранённые SpotForecast.
"""
import dataclasses
import datetime as dt
import logging
from decimal import Decimal

from django.conf import settings
from django.utils.module_loading import import_string

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class ForecastPoint:
    valid_from: dt.datetime
    valid_to: dt.datetime
    wave_height_m: Decimal | None = None
    wave_period_s: Decimal | None = None
    wave_direction: str = ""
    wind_speed_ms: Decimal | None = None
    wind_direction: str = ""
    water_temp_c: Decimal | None = None
    tide_note: str = ""
    payload: dict = dataclasses.field(default_factory=dict)


@dataclasses.dataclass
class ForecastResult:
    issued_at: dt.datetime
    points: list[ForecastPoint]


class ForecastProvider:
    """Базовый класс. name — машинное имя (сохраняется в SpotForecast.provider), title — для интерфейса."""

    name: str | None = None
    title: str = ""
    enabled: bool = True

    def fetch(self, spot) -> ForecastResult | None:  # pragma: no cover - интерфейс
        """Возвращает прогноз по точным координатам спота (spot.lat/lng) или None, если данных нет."""
        raise NotImplementedError


class NoneProvider(ForecastProvider):
    """Провайдер не подключён: ничего не запрашивает и ничего не возвращает."""

    name = None
    title = ""
    enabled = False

    def fetch(self, spot):
        return None


PROVIDERS = {"none": NoneProvider, "": NoneProvider}


def get_provider() -> ForecastProvider:
    key = (getattr(settings, "FORECAST_PROVIDER", "none") or "none").strip()
    cls = PROVIDERS.get(key.lower())
    if cls is None:
        try:
            cls = import_string(key)
        except ImportError:
            logger.warning("unknown FORECAST_PROVIDER=%r, forecasts disabled", key)
            cls = NoneProvider
    return cls()
