"""Привязка загруженных медиа к доменным объектам.

Остальные сервисы приложения: `uploads` (presigned PUT, complete, удаление, очистка), `processing` (Celery-проверка),
`access` (права на закрытые файлы и presigned GET).
"""
from apps.common.exceptions import DomainError
from apps.mediafiles.models import MediaAsset


def claim_media(media_id, account, purposes=None, kinds=None, allow_processing=True, organization=None):
    """Проверяет, что файл загружен этим аккаунтом, готов (или обрабатывается) и подходит по назначению.

    organization — привязать файл к организации (логотип, галерея), если он ещё ни к какой не привязан.
    """
    statuses = [MediaAsset.Status.READY] + ([MediaAsset.Status.PROCESSING] if allow_processing else [])
    asset = MediaAsset.objects.filter(id=media_id, owner=account, status__in=statuses).first()
    if asset is None:
        raise DomainError("media_invalid", "Файл не найден или ещё не загружен.", fields={"media": ["Файл недоступен."]})
    if purposes and asset.purpose not in purposes:
        raise DomainError("media_purpose", "Файл загружен для другого назначения.")
    if kinds and asset.kind not in kinds:
        raise DomainError("media_kind", "Неподходящий тип файла.")
    if organization is not None and asset.organization_id is None:
        asset.organization = organization
        asset.save(update_fields=["organization", "updated_at"])
    return asset


def claim_many(media_ids, account, **kwargs):
    return [claim_media(mid, account, **kwargs) for mid in media_ids]
