"""Правила загрузки медиа: назначение → допустимые типы и видимость, расширения, ключи хранилища."""
import uuid

from django.conf import settings
from django.utils import timezone

from apps.mediafiles.models import MediaAsset

P = MediaAsset.Purpose
K = MediaAsset.Kind

# Закрытые назначения: файлы лежат под private/ и отдаются только presigned-ссылкой после проверки прав.
PRIVATE_PURPOSES = frozenset({
    P.CERTIFICATE, P.MESSAGE_ATTACHMENT, P.SPOT_EVIDENCE, P.REPAIR_PHOTO, P.HANDOVER_PHOTO, P.DATA_EXPORT,
})

# Какие виды файлов допустимы для назначения.
PURPOSE_KINDS = {
    P.AVATAR: {K.IMAGE},
    P.ORG_LOGO: {K.IMAGE},
    P.ORG_COVER: {K.IMAGE},
    P.ORG_GALLERY: {K.IMAGE, K.VIDEO},
    P.SPOT_PHOTO: {K.IMAGE},
    P.SPOT_EVIDENCE: {K.IMAGE, K.DOCUMENT},
    P.BOARD_PHOTO: {K.IMAGE},
    P.BOARD_VIDEO: {K.VIDEO},
    P.PROMO_VIDEO: {K.VIDEO},
    P.PROFILE_GALLERY: {K.IMAGE, K.VIDEO},
    P.ITEM_PHOTO: {K.IMAGE},
    P.CERTIFICATE: {K.DOCUMENT, K.IMAGE},
    P.MESSAGE_ATTACHMENT: {K.IMAGE, K.VIDEO, K.DOCUMENT},
    P.REPAIR_PHOTO: {K.IMAGE},
    P.HANDOVER_PHOTO: {K.IMAGE},
    P.REVIEW_PHOTO: {K.IMAGE},
    P.DIARY_PHOTO: {K.IMAGE},
    P.EVENT_COVER: {K.IMAGE},
    P.PRODUCT_PHOTO: {K.IMAGE},
}

# Создаются только сервером (выгрузка персональных данных).
SERVER_ONLY_PURPOSES = frozenset({P.DATA_EXPORT})

EXTENSIONS = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "video/mp4": "mp4",
    "video/webm": "webm",
    "video/quicktime": "mov",
    "application/pdf": "pdf",
    "application/json": "json",
}

THUMBNAIL_SUFFIX = ".thumb.webp"
THUMBNAIL_MAX_SIDE = 640
MAX_IMAGE_PIXELS = 50_000_000
MAX_PENDING_UPLOADS_PER_ACCOUNT = 50


def visibility_for(purpose):
    return MediaAsset.Visibility.PRIVATE if purpose in PRIVATE_PURPOSES else MediaAsset.Visibility.PUBLIC


def limits_for(kind):
    return settings.MEDIA_LIMITS.get(kind)


def build_key(purpose, content_type, visibility=None, now=None):
    """`{public|private}/{purpose}/{yyyy}/{mm}/{uuid}.{ext}`."""
    visibility = visibility or visibility_for(purpose)
    now = now or timezone.now()
    prefix = settings.MEDIA_PRIVATE_PREFIX if visibility == MediaAsset.Visibility.PRIVATE else settings.MEDIA_PUBLIC_PREFIX
    ext = EXTENSIONS.get(content_type, "bin")
    return f"{prefix}{purpose}/{now:%Y}/{now:%m}/{uuid.uuid4().hex}.{ext}"


def thumbnail_key_for(storage_key):
    return f"{storage_key}{THUMBNAIL_SUFFIX}"
