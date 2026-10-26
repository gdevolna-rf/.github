"""Агрегаты рейтинга (7.5, BR-08, TRUST-01, F09): среднее и число только по реальным published-отзывам.

Пересчитывается только цель изменённого отзыва — соседние объекты не трогаются (ATX-12).
"""
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.db.models import Avg, Count, Q

from apps.learning.models import InstructorProfile
from apps.organizations.models import Organization
from apps.spots.models import Spot
from apps.trust.models import Review

TARGET_MODELS = {
    Review.Target.SPOT: (Spot, "spot"),
    Review.Target.INSTRUCTOR: (InstructorProfile, "instructor"),
    Review.Target.ORGANIZATION: (Organization, "organization"),
}
_ZERO = Decimal("0.00")


def counted_reviews():
    """Отзывы, которые учитываются в рейтинге: опубликованные и не демонстрационные."""
    return Review.objects.filter(status=Review.Status.PUBLISHED, is_demo=False)


def _quantize(value):
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if value is not None else _ZERO


def recalculate(target_type, target_id):
    """Пересчёт одной цели. Строка цели блокируется, чтобы параллельные решения не затёрли друг друга."""
    model, fk = TARGET_MODELS[target_type]
    with transaction.atomic():
        locked = list(model.objects.select_for_update().filter(pk=target_id).values_list("pk", flat=True))
        if not locked:
            return None
        agg = counted_reviews().filter(**{f"{fk}_id": target_id}).aggregate(avg=Avg("rating"), count=Count("id"))
        avg, count = _quantize(agg["avg"]), agg["count"] or 0
        model.objects.filter(pk=target_id).update(rating_avg=avg, rating_count=count)
    if target_type == Review.Target.SPOT:
        from apps.spots.services.catalog import invalidate_map_cache

        invalidate_map_cache()
    return avg, count


def target_id_of(review):
    return {"spot": review.spot_id, "instructor": review.instructor_id, "organization": review.organization_id}[
        review.target_type
    ]


def recalculate_for_review(review):
    return recalculate(review.target_type, target_id_of(review))


def recalculate_all():
    """Контрольный пересчёт всех агрегатов (Celery trust.recalculate_ratings). Возвращает число исправленных строк."""
    fixed = 0
    for target_type, (model, fk) in TARGET_MODELS.items():
        actual = {
            row[f"{fk}_id"]: (_quantize(row["avg"]), row["count"])
            for row in counted_reviews().filter(target_type=target_type).values(f"{fk}_id")
            .annotate(avg=Avg("rating"), count=Count("id"))
        }
        stale = model.objects.filter(Q(pk__in=list(actual)) | ~Q(rating_count=0) | ~Q(rating_avg=_ZERO))
        for pk, rating_avg, rating_count in stale.values_list("pk", "rating_avg", "rating_count"):
            avg, count = actual.get(pk, (_ZERO, 0))
            if rating_avg != avg or rating_count != count:
                model.objects.filter(pk=pk).update(rating_avg=avg, rating_count=count)
                fixed += 1
        if fixed and target_type == Review.Target.SPOT:
            from apps.spots.services.catalog import invalidate_map_cache

            invalidate_map_cache()
    return fixed
