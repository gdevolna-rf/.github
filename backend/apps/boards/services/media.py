"""Фото и видео моделей (BRD-03/04, UX-08/09, ATX-06).

Галерея модели — BoardMedia(variant=NULL), у каждого варианта — своя галерея; в каждой не более 10 фото.
Инвариант: обложка — всегда первое фото галереи (position=0, is_cover=True); выбор обложки переносит фото в начало,
изменение порядка делает обложкой первое фото, удаление обложки передаёт её следующему.
"""
from django.db import transaction

from apps.boards.models import BoardMedia, BoardModel
from apps.common.exceptions import Conflict, DomainError, NotFound
from apps.mediafiles.models import MediaAsset
from apps.mediafiles.services import claim_media, claim_many
from apps.trust.services.restrictions import require_can_publish


def gallery(model, variant=None):
    return BoardMedia.objects.filter(model=model, variant=variant).select_related("media").order_by("position", "id")


def _lock_model(model):
    BoardModel.objects.select_for_update().filter(pk=model.pk).first()


def _normalize(model, variant):
    """Позиции 0..n-1 и обложка на первом фото."""
    items = list(BoardMedia.objects.filter(model=model, variant=variant).order_by("-is_cover", "position", "id"))
    BoardMedia.objects.filter(model=model, variant=variant, is_cover=True).update(is_cover=False)
    for item in items:
        item.is_cover = False
    for index, item in enumerate(items):
        is_cover = index == 0
        if item.position != index or item.is_cover != is_cover:
            item.position, item.is_cover = index, is_cover
            item.save(update_fields=["position", "is_cover"])
    return items


@transaction.atomic
def add_photos(model, account, media_ids, variant=None):
    require_can_publish(account)
    _lock_model(model)
    existing = BoardMedia.objects.filter(model=model, variant=variant)
    count = existing.count()
    if count + len(media_ids) > BoardMedia.MAX_PHOTOS:
        raise Conflict(f"Можно загрузить не более {BoardMedia.MAX_PHOTOS} фотографий "
                       f"(сейчас {count}).", code="photo_limit")
    if len(set(media_ids)) != len(media_ids):
        raise DomainError("validation_error", "Одно и то же фото указано несколько раз.",
                          fields={"media_ids": ["Повторяющиеся id."]})
    assets = claim_many(media_ids, account, purposes=[MediaAsset.Purpose.BOARD_PHOTO], kinds=[MediaAsset.Kind.IMAGE])
    if BoardMedia.objects.filter(model=model, media__in=assets).exists():
        raise Conflict("Это фото уже добавлено к модели.", code="media_in_use")
    for offset, asset in enumerate(assets):
        BoardMedia.objects.create(model=model, variant=variant, media=asset, position=count + offset, is_cover=False)
    _normalize(model, variant)
    return list(gallery(model, variant))


def media_item(model, item_id):
    item = BoardMedia.objects.filter(model=model, pk=item_id).select_related("media").first()
    if item is None:
        raise NotFound("Фото не найдено.", code="media_not_found")
    return item


@transaction.atomic
def reorder(model, ids, variant=None):
    _lock_model(model)
    current = list(BoardMedia.objects.filter(model=model, variant=variant).values_list("pk", flat=True))
    if sorted(current) != sorted(ids) or len(ids) != len(set(ids)):
        raise DomainError("order_mismatch", "Передайте все фото галереи ровно по одному разу.",
                          fields={"ids": ["Список не совпадает с галереей."]})
    BoardMedia.objects.filter(model=model, variant=variant, is_cover=True).update(is_cover=False)
    for index, pk in enumerate(ids):
        BoardMedia.objects.filter(pk=pk).update(position=index, is_cover=index == 0)
    return list(gallery(model, variant))


@transaction.atomic
def set_cover(model, item):
    _lock_model(model)
    variant = item.variant
    others = [pk for pk in BoardMedia.objects.filter(model=model, variant=variant).order_by("position", "id")
              .values_list("pk", flat=True) if pk != item.pk]
    return reorder(model, [item.pk] + others, variant=variant)


@transaction.atomic
def delete_photo(model, item):
    _lock_model(model)
    model.refresh_from_db(fields=["status"])
    variant = item.variant
    if (variant is None and model.status == BoardModel.Status.PUBLISHED
            and BoardMedia.objects.filter(model=model, variant=None).count() <= 1):
        raise Conflict("У опубликованной модели должна остаться обложка. Загрузите другое фото или снимите модель "
                       "с публикации.", code="cover_required")
    item.delete()
    _normalize(model, variant)
    return list(gallery(model, variant))


@transaction.atomic
def set_video(model, account, media_id):
    require_can_publish(account)
    _lock_model(model)
    model.video = claim_media(media_id, account, purposes=[MediaAsset.Purpose.BOARD_VIDEO], kinds=[MediaAsset.Kind.VIDEO])
    model.save(update_fields=["video", "updated_at"])
    return model


@transaction.atomic
def remove_video(model):
    _lock_model(model)
    model.video = None
    model.save(update_fields=["video", "updated_at"])
    return model
