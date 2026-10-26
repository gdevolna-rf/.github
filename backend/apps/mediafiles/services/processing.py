"""Проверка загруженного файла (magic bytes / Pillow), очистка EXIF и WebP-миниатюра (DATA-04, 11 «Медиа»)."""
import hashlib
import io
import logging
import warnings

from django.db import transaction
from django.utils import timezone
from PIL import Image, ImageOps, UnidentifiedImageError

from apps.mediafiles import policy
from apps.mediafiles.models import MediaAsset
from apps.mediafiles.services.uploads import _delete_objects
from apps.mediafiles.storage import get_storage

logger = logging.getLogger(__name__)

SNIFF_BYTES = 64
_PIL_FORMATS = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}
_QUICKTIME_ATOMS = {b"moov", b"mdat", b"wide", b"free", b"skip", b"pnot"}


class MediaRejected(Exception):
    pass


def sniff_content_type(head):
    """Определяет тип по сигнатуре. Возвращает MIME или None."""
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(head) >= 12 and head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    if head.startswith(b"%PDF-"):
        return "application/pdf"
    if head.startswith(b"\x1a\x45\xdf\xa3"):
        return "video/webm"
    if len(head) >= 12 and head[4:8] == b"ftyp":
        return "video/quicktime" if head[8:12] == b"qt  " else "video/mp4"
    if len(head) >= 8 and head[4:8] in _QUICKTIME_ATOMS:
        return "video/quicktime"
    return None


def _signature_matches(declared, detected):
    if detected is None:
        return False
    if declared == detected:
        return True
    # MP4 и MOV — одно семейство ISO BMFF: браузеры и камеры путают MIME.
    return {declared, detected} <= {"video/mp4", "video/quicktime"}


def _process_image(asset, data):
    """Проверка Pillow, удаление EXIF (с учётом ориентации), размеры и WebP-миниатюра."""
    expected = _PIL_FORMATS.get(asset.content_type)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            probe = Image.open(io.BytesIO(data))
            if probe.width * probe.height > policy.MAX_IMAGE_PIXELS:
                raise MediaRejected("Слишком большое разрешение изображения.")
            if expected and probe.format != expected:
                raise MediaRejected("Содержимое файла не соответствует заявленному формату.")
            probe.verify()
            image = Image.open(io.BytesIO(data))
            image.load()
    except MediaRejected:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError, Image.DecompressionBombWarning, OSError,
            SyntaxError, ValueError) as exc:
        raise MediaRejected("Файл повреждён или не является изображением.") from exc

    animated = getattr(image, "is_animated", False)
    if animated:
        # Анимированные PNG/WebP пересохраняются целиком (все кадры) — метаданные отбрасываются.
        out = io.BytesIO()
        image.save(out, expected, save_all=True)
        cleaned = out.getvalue()
        image.seek(0)
    else:
        image = ImageOps.exif_transpose(image)
        out = io.BytesIO()
        save_kwargs = {}
        icc = image.info.get("icc_profile")
        if icc:
            save_kwargs["icc_profile"] = icc
        if expected == "JPEG":
            if image.mode not in ("RGB", "L", "CMYK"):
                image = image.convert("RGB")
            image.save(out, "JPEG", quality=90, optimize=True, **save_kwargs)
        elif expected == "PNG":
            image.save(out, "PNG", optimize=True, **save_kwargs)
        else:
            image.save(out, "WEBP", quality=90, method=4, **save_kwargs)
        cleaned = out.getvalue()

    thumb = image.copy()
    if thumb.mode not in ("RGB", "RGBA"):
        thumb = thumb.convert("RGBA" if "A" in thumb.getbands() or thumb.mode == "P" else "RGB")
    thumb.thumbnail((policy.THUMBNAIL_MAX_SIDE, policy.THUMBNAIL_MAX_SIDE), Image.Resampling.LANCZOS)
    thumb_io = io.BytesIO()
    thumb.save(thumb_io, "WEBP", quality=80, method=4)
    return {
        "data": cleaned,
        "rewritten": cleaned is not data,
        "width": image.width,
        "height": image.height,
        "thumbnail": thumb_io.getvalue(),
    }


def process_media(asset_id):
    """Celery-обработка: ready или rejected с причиной. Повторный запуск безопасен."""
    asset = MediaAsset.objects.filter(id=asset_id).first()
    if asset is None or asset.status != MediaAsset.Status.PROCESSING:
        return asset.status if asset else None

    storage = get_storage()
    updates = {}
    try:
        is_image = asset.content_type in _PIL_FORMATS
        full_read = is_image or asset.content_type == "application/pdf"
        data = storage.read(asset.storage_key) if full_read else storage.read(asset.storage_key, SNIFF_BYTES)
        detected = sniff_content_type(data[:SNIFF_BYTES])
        if not _signature_matches(asset.content_type, detected):
            raise MediaRejected("Содержимое файла не соответствует заявленному формату.")
        if is_image:
            try:
                result = _process_image(asset, data)
            except MediaRejected:
                raise
            except Exception as exc:  # неожиданный формат внутри валидного контейнера
                logger.warning("image processing failed id=%s", asset.id, exc_info=True)
                raise MediaRejected("Не удалось обработать изображение.") from exc
            if result["rewritten"]:
                storage.write(asset.storage_key, result["data"], asset.content_type)
            thumb_key = policy.thumbnail_key_for(asset.storage_key)
            storage.write(thumb_key, result["thumbnail"], "image/webp")
            data = result["data"]
            updates.update(width=result["width"], height=result["height"], thumbnail_key=thumb_key,
                           size_bytes=len(data))
        if full_read:
            updates["checksum_sha256"] = hashlib.sha256(data).hexdigest()
    except MediaRejected as exc:
        return _finish_rejected(asset, str(exc))
    except FileNotFoundError:
        return _finish_rejected(asset, "Файл не найден в хранилище.")

    with transaction.atomic():
        locked = MediaAsset.objects.select_for_update().filter(id=asset.id).first()
        if locked is None or locked.status != MediaAsset.Status.PROCESSING:
            # Файл удалили во время обработки — подчистить созданную миниатюру.
            if locked is not None and updates.get("thumbnail_key"):
                storage.delete(updates["thumbnail_key"])
            return locked.status if locked else None
        for field, value in updates.items():
            setattr(locked, field, value)
        locked.status = MediaAsset.Status.READY
        locked.processed_at = timezone.now()
        locked.rejection_reason = ""
        locked.save()
    return MediaAsset.Status.READY


def _finish_rejected(asset, reason):
    with transaction.atomic():
        locked = MediaAsset.objects.select_for_update().filter(id=asset.id).first()
        if locked is None or locked.status != MediaAsset.Status.PROCESSING:
            return locked.status if locked else None
        locked.status = MediaAsset.Status.REJECTED
        locked.rejection_reason = reason[:300]
        locked.processed_at = timezone.now()
        locked.save(update_fields=["status", "rejection_reason", "processed_at", "updated_at"])
    _delete_objects(locked)
    logger.info("media rejected id=%s reason=%s", asset.id, reason)
    return MediaAsset.Status.REJECTED
