"""Прогнозы (GEO-04): сохранение ответа провайдера и чтение актуального прогноза для карточки."""
import datetime as dt
import logging

from django.db import transaction
from django.utils import timezone

from apps.spots.forecast import get_provider
from apps.spots.models import SpotForecast
from apps.spots.services.catalog import public_spots

logger = logging.getLogger(__name__)

KEEP_HISTORY = dt.timedelta(days=2)
NO_PROVIDER_MESSAGE = "Прогноз для спотов пока не подключён. Ориентируйтесь на типичные условия и проверяйте погоду перед выездом."
NO_DATA_MESSAGE = "Прогноз для этого спота ещё не получен. Данные обновляются каждые несколько часов."


def store_forecast(spot, provider, result):
    """Заменяет прогноз провайдера по споту новым выпуском (одна транзакция)."""
    rows = [
        SpotForecast(
            spot=spot, provider=provider.name, issued_at=result.issued_at, valid_from=p.valid_from, valid_to=p.valid_to,
            wave_height_m=p.wave_height_m, wave_period_s=p.wave_period_s, wave_direction=(p.wave_direction or "")[:3],
            wind_speed_ms=p.wind_speed_ms, wind_direction=(p.wind_direction or "")[:3], water_temp_c=p.water_temp_c,
            tide_note=(p.tide_note or "")[:120], payload=p.payload or {},
        )
        for p in result.points
        if p.valid_to > p.valid_from
    ]
    with transaction.atomic():
        SpotForecast.objects.filter(spot=spot, provider=provider.name).delete()
        SpotForecast.objects.bulk_create(rows)
    return len(rows)


def refresh_all(provider=None):
    """Опрос провайдера по всем публичным спотам. Ошибка по одному споту не останавливает остальные."""
    provider = provider or get_provider()
    stats = {"provider": provider.name, "spots": 0, "points": 0, "errors": 0}
    if not provider.enabled or not provider.name:
        return stats
    for spot in public_spots().select_related("region").iterator():
        try:
            result = provider.fetch(spot)
        except Exception:  # провайдер внешний — не доверяем ему стабильность
            logger.warning("forecast fetch failed spot=%s provider=%s", spot.pk, provider.name, exc_info=True)
            stats["errors"] += 1
            continue
        if result is None:
            continue
        stats["points"] += store_forecast(spot, provider, result)
        stats["spots"] += 1
    SpotForecast.objects.filter(valid_to__lt=timezone.now() - KEEP_HISTORY).delete()
    return stats


def current_forecast(spot):
    """{provider, provider_title, issued_at, items, message} — стабильная форма ответа."""
    provider = get_provider()
    if not provider.enabled or not provider.name:
        return {"provider": None, "provider_title": None, "issued_at": None, "items": [], "message": NO_PROVIDER_MESSAGE}
    now = timezone.now()
    rows = list(SpotForecast.objects.filter(spot=spot, provider=provider.name, valid_to__gte=now).order_by("valid_from"))
    if not rows:
        return {"provider": provider.name, "provider_title": provider.title or provider.name, "issued_at": None,
                "items": [], "message": NO_DATA_MESSAGE}
    return {
        "provider": provider.name,
        "provider_title": provider.title or provider.name,
        "issued_at": max(r.issued_at for r in rows),
        "items": rows,
        "message": "",
    }
