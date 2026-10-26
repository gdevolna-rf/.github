"""Короткоживущие ссылки на закрытые файлы для модератора (сертификаты, доказательства, вложения)."""
import logging

from django.conf import settings

from apps.common.s3 import public_client, request_origin

logger = logging.getLogger(__name__)


def moderator_url(request, media):
    """Публичный готовый файл — обычный путь; закрытый — presigned GET на MEDIA_PRIVATE_URL_TTL секунд."""
    if media is None or not media.storage_key:
        return None
    if media.is_public and media.status == media.Status.READY:
        return media.url
    try:
        return public_client(request_origin(request)).generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.S3_BUCKET, "Key": media.storage_key},
            ExpiresIn=settings.MEDIA_PRIVATE_URL_TTL,
        )
    except Exception:  # подпись локальная, но конфигурация S3 могла быть не задана
        logger.warning("presign failed media=%s", media.pk, exc_info=True)
        return None
