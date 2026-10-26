from celery import shared_task

from apps.spots.services.forecasts import refresh_all


@shared_task(name="spots.refresh_forecasts")
def refresh_forecasts():
    """Каждые 3 ч (ARCHITECTURE §5): опрос провайдера FORECAST_PROVIDER; при "none" — без внешних запросов."""
    return refresh_all()
