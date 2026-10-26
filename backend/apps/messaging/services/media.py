"""Медиа в переписке: закрытые файлы отдаются участникам короткоживущими presigned GET (ARCHITECTURE §2, ATX-23).

Подпись — через хранилище mediafiles (``get_storage().presigned_get``), как у ``GET media/{id}/url``.
"""
import logging

from django.conf import settings

from apps.common.s3 import request_origin
from apps.mediafiles.models import MediaAsset
from apps.mediafiles.serializers import MediaSerializer
from apps.mediafiles.storage import get_storage

logger = logging.getLogger(__name__)


def _presign(origin, key, filename=None):
    if not key:
        return None
    try:
        return get_storage().presigned_get(key, settings.MEDIA_PRIVATE_URL_TTL, origin, filename=filename)
    except Exception:  # подпись — локальная операция; сбой не должен ронять ленту сообщений
        logger.warning("presign failed for %s", key, exc_info=True)
        return None


def signed_media(asset, request=None):
    """MediaSerializer + signed_url/signed_thumbnail_url. Файл, не прошедший проверку, не раздаётся."""
    data = dict(MediaSerializer(asset).data)
    data["signed_url"] = None
    data["signed_thumbnail_url"] = None
    if asset.status != MediaAsset.Status.READY:
        return data
    if asset.is_public:
        data["signed_url"] = asset.url
        data["signed_thumbnail_url"] = asset.thumbnail_url
        return data
    origin = request_origin(request)
    data["signed_url"] = _presign(origin, asset.storage_key, filename=asset.original_filename or None)
    data["signed_thumbnail_url"] = _presign(origin, asset.thumbnail_key or asset.storage_key)
    return data
