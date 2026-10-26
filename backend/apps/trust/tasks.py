from celery import shared_task

from apps.trust.services.ratings import recalculate_all


@shared_task(name="trust.recalculate_ratings")
def recalculate_ratings():
    """Ежедневно 04:00 (ARCHITECTURE §5): контрольный пересчёт рейтингов по published-отзывам (BR-08)."""
    return {"fixed": recalculate_all()}
