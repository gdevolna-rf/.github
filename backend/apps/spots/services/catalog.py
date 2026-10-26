"""Публичный каталог спотов (BR-01, SPT-01/12, GEO-06): видимость, маскирование координат, маркеры карты."""
from decimal import ROUND_HALF_UP, Decimal

from django.core.cache import cache
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from apps.common.exceptions import NotFound
from apps.spots.models import Region, Spot

PUBLIC_STATUSES = (Spot.Status.PUBLISHED, Spot.Status.CLOSED)
MAP_CACHE_KEY = "spots:map:v1"
MAP_CACHE_TTL = 10 * 60  # страховка; основное — инвалидация сигналами
_TWO_PLACES = Decimal("0.01")
_ONE_PLACE = Decimal("0.1")


def public_spots():
    """Опубликованные споты (в т.ч. временно закрытые — их статус показывается, GEO-06)."""
    return Spot.objects.filter(status__in=PUBLIC_STATUSES)


def is_public_spot(spot):
    """Спот можно показывать и ссылаться на него из других приложений (черновик/скрытый модератором — нет)."""
    return spot is not None and spot.status in PUBLIC_STATUSES


def get_public_spot(*, slug=None, pk=None, queryset=None):
    qs = queryset if queryset is not None else public_spots()
    lookup = {"slug": slug} if slug is not None else {"pk": pk}
    spot = qs.filter(**lookup).first()
    if spot is None:
        raise NotFound("Спот не найден.", code="spot_not_found")
    return spot


def effective_precision(spot):
    """Чувствительная геоточка никогда не показывается точно, даже если precision=exact (SPT-12)."""
    if spot.is_sensitive and spot.location_precision == Spot.Precision.EXACT:
        return Spot.Precision.APPROXIMATE
    return spot.location_precision


def _round(value, quantum):
    return float(Decimal(value).quantize(quantum, rounding=ROUND_HALF_UP)) if value is not None else None


def public_coordinates(spot):
    """{lat, lng, precise, precision} для публичных ответов. Точные координаты остаются только на сервере."""
    precision = effective_precision(spot)
    if precision == Spot.Precision.EXACT:
        return {"lat": float(spot.lat), "lng": float(spot.lng), "precise": True, "precision": precision}
    if precision == Spot.Precision.APPROXIMATE:
        return {"lat": _round(spot.lat, _TWO_PLACES), "lng": _round(spot.lng, _TWO_PLACES), "precise": False,
                "precision": precision}
    region = spot.region
    if region.center_lat is not None and region.center_lng is not None:
        lat, lng = float(region.center_lat), float(region.center_lng)
    else:  # центр региона не задан — грубое округление (~10 км), но не точная точка
        lat, lng = _round(spot.lat, _ONE_PLACE), _round(spot.lng, _ONE_PLACE)
    return {"lat": lat, "lng": lng, "precise": False, "precision": precision}


def is_closed(spot, today=None):
    today = today or timezone.localdate()
    return spot.status == Spot.Status.CLOSED or bool(spot.closed_until and spot.closed_until >= today)


def regions_with_counts():
    return Region.objects.annotate(spots_count=Count("spots", filter=Q(spots__status__in=PUBLIC_STATUSES)))


def _cover(spot):
    cover = spot.cover
    if cover is None or cover.status != cover.Status.READY or not cover.is_public:
        photos = [p for p in spot.photos.all() if p.media.status == p.media.Status.READY and p.media.is_public]
        cover = photos[0].media if photos else None
    return cover


def public_cover(spot):
    """Обложка: явная cover или первое готовое публичное фото галереи."""
    return _cover(spot)


def build_map_markers():
    spots = (public_spots().select_related("region", "cover")
             .prefetch_related("photos__media").order_by("region__sort_order", "name"))
    markers = []
    for spot in spots:
        coords = public_coordinates(spot)
        cover = _cover(spot)
        markers.append({
            "id": str(spot.id),
            "slug": spot.slug,
            "name": spot.name,
            "region_slug": spot.region.slug,
            "region_name": spot.region.name,
            "lat": coords["lat"],
            "lng": coords["lng"],
            "precise": coords["precise"],
            "difficulty": spot.difficulty,
            "difficulty_label": str(spot.get_difficulty_display()),
            "status": spot.status,
            "is_closed": is_closed(spot),
            "rating_avg": str(spot.rating_avg),
            "rating_count": spot.rating_count,
            "thumbnail_url": cover.thumbnail_url if cover else None,
        })
    return markers


def map_markers():
    """Лёгкие маркеры для карты из кеша Django (Redis); пересчёт при промахе."""
    markers = cache.get(MAP_CACHE_KEY)
    if markers is None:
        markers = build_map_markers()
        cache.set(MAP_CACHE_KEY, markers, MAP_CACHE_TTL)
    return markers


def invalidate_map_cache():
    """Сбрасывает кеш сразу и ещё раз после коммита (чтобы параллельный запрос не закешировал старое)."""
    cache.delete(MAP_CACHE_KEY)
    transaction.on_commit(lambda: cache.delete(MAP_CACHE_KEY))
