"""Жизненный цикл загрузки: presigned PUT → complete (HEAD) → обработка в Celery → ready/rejected (DATA-04)."""
import datetime as dt
import logging
import os

from django.conf import settings
from django.db import transaction
from django.db.models import ProtectedError
from django.utils import timezone

from apps.common.exceptions import Conflict, DomainError, NotFound
from apps.mediafiles import policy
from apps.mediafiles.models import MediaAsset
from apps.mediafiles.storage import get_storage

logger = logging.getLogger(__name__)

# Повторная постановка «зависших» в processing файлов (воркер упал, сообщение потеряно).
STUCK_PROCESSING_AFTER = dt.timedelta(minutes=30)
# Отклонённые/удалённые объекты удаляются из хранилища сразу; строки pending с истёкшей ссылкой — через grace.
EXPIRED_PENDING_GRACE = dt.timedelta(minutes=5)


def _sanitize_filename(filename):
    name = os.path.basename((filename or "").replace("\\", "/")).strip()
    name = "".join(ch for ch in name if ch.isprintable())
    return name[:255]


def validate_upload_request(kind, purpose, content_type, size):
    if kind not in MediaAsset.Kind.values:
        raise DomainError("media_kind_invalid", "Неизвестный тип файла.", fields={"kind": ["Недопустимое значение."]})
    if purpose not in MediaAsset.Purpose.values or purpose in policy.SERVER_ONLY_PURPOSES:
        raise DomainError("media_purpose_invalid", "Недопустимое назначение файла.",
                          fields={"purpose": ["Недопустимое значение."]})
    if kind not in policy.PURPOSE_KINDS.get(purpose, set()):
        raise DomainError("media_kind_not_allowed", "Этот тип файла нельзя загрузить для выбранного назначения.",
                          fields={"kind": ["Тип не подходит для назначения."]})
    limits = policy.limits_for(kind)
    if not limits or content_type not in limits["types"]:
        allowed = ", ".join(limits["types"]) if limits else "—"
        raise DomainError("media_type_not_allowed", f"Формат файла не поддерживается. Допустимо: {allowed}.",
                          fields={"content_type": ["Формат не поддерживается."]})
    if size is None or size <= 0:
        raise DomainError("media_empty", "Файл пустой.", fields={"size": ["Размер должен быть больше нуля."]})
    if size > limits["max_bytes"]:
        mb = limits["max_bytes"] // (1024 * 1024)
        raise DomainError("media_too_large", f"Файл слишком большой: максимум {mb} МБ.",
                          fields={"size": [f"Максимум {mb} МБ."]})
    return limits


def create_upload(account, *, kind, purpose, filename, content_type, size, origin, organization=None, alt_text=""):
    """Создаёт MediaAsset(status=pending) и одноразовую presigned PUT-ссылку на origin браузера.

    Ссылка подписывается с заголовком `If-None-Match: *`: объект можно записать только один раз,
    поэтому после проверки файл нельзя подменить повторным PUT по той же ссылке.
    """
    content_type = (content_type or "").lower().strip()
    validate_upload_request(kind, purpose, content_type, size)
    if organization is not None:
        from apps.organizations.services.access import is_member

        if not is_member(account, organization):
            raise NotFound("Организация не найдена.")
    pending = MediaAsset.objects.filter(owner=account, status=MediaAsset.Status.PENDING,
                                        upload_expires_at__gt=timezone.now()).count()
    if pending >= policy.MAX_PENDING_UPLOADS_PER_ACCOUNT:
        raise DomainError("media_too_many_pending", "Слишком много незавершённых загрузок. Завершите или подождите.",
                          status_code=429)

    visibility = policy.visibility_for(purpose)
    ttl = settings.MEDIA_UPLOAD_URL_TTL
    expires_at = timezone.now() + dt.timedelta(seconds=ttl)
    asset = MediaAsset.objects.create(
        owner=account,
        organization=organization,
        kind=kind,
        purpose=purpose,
        visibility=visibility,
        status=MediaAsset.Status.PENDING,
        storage_key=policy.build_key(purpose, content_type, visibility),
        original_filename=_sanitize_filename(filename),
        content_type=content_type,
        size_bytes=size,
        alt_text=(alt_text or "")[:300],
        upload_expires_at=expires_at,
    )
    url = get_storage().presigned_put(asset.storage_key, content_type, ttl, origin)
    headers = {"Content-Type": content_type, "If-None-Match": "*"}
    return asset, url, headers


def complete_upload(asset_id, account):
    """Проверяет, что объект загружен (HEAD: размер и тип), и ставит обработку в очередь."""
    reason = None
    with transaction.atomic():
        asset = MediaAsset.objects.select_for_update().filter(id=asset_id, owner=account).first()
        if asset is None or asset.status == MediaAsset.Status.DELETED:
            raise NotFound("Файл не найден.")
        if asset.status in (MediaAsset.Status.PROCESSING, MediaAsset.Status.READY):
            return asset  # повторный complete идемпотентен
        if asset.status == MediaAsset.Status.REJECTED:
            raise DomainError("media_rejected", asset.rejection_reason or "Файл отклонён.")

        info = get_storage().head(asset.storage_key)
        if info is None:
            if asset.upload_expires_at and asset.upload_expires_at < timezone.now():
                raise DomainError("upload_expired", "Срок ссылки для загрузки истёк. Загрузите файл заново.")
            raise DomainError("upload_not_found", "Файл ещё не загружен в хранилище.")

        limits = policy.limits_for(asset.kind)
        if info.size <= 0:
            reason = "Файл пустой."
        elif info.size > limits["max_bytes"]:
            reason = f"Файл слишком большой: максимум {limits['max_bytes'] // (1024 * 1024)} МБ."
        elif info.content_type.split(";")[0].strip().lower() != asset.content_type:
            reason = "Тип загруженного файла не совпадает с заявленным."

        if reason:
            _reject(asset, reason)
        else:
            asset.size_bytes = info.size
            asset.status = MediaAsset.Status.PROCESSING
            asset.save(update_fields=["size_bytes", "status", "updated_at"])
            enqueue_processing(asset.id)
    if reason:
        raise DomainError("media_rejected", reason)
    return asset


def enqueue_processing(asset_id):
    from apps.mediafiles.tasks import process_media

    transaction.on_commit(lambda: process_media.delay(str(asset_id)))


def _delete_objects(asset):
    storage = get_storage()
    for key in filter(None, [asset.storage_key, asset.thumbnail_key, asset.poster_key]):
        try:
            storage.delete(key)
        except Exception:  # хранилище недоступно — объект подчистит повторный запуск очистки
            logger.warning("media object delete failed key=%s", key, exc_info=True)


def _reject(asset, reason):
    asset.status = MediaAsset.Status.REJECTED
    asset.rejection_reason = reason[:300]
    asset.processed_at = timezone.now()
    asset.save(update_fields=["status", "rejection_reason", "processed_at", "updated_at"])
    _delete_objects(asset)


def media_in_use(asset):
    """Файл, который является частью истории (сообщение, сертификат, акт), нельзя удалить владельцу."""
    from apps.learning.models import InstructorCertificate
    from apps.messaging.models import MessageAttachment

    if MessageAttachment.objects.filter(media=asset).exists():
        return "Файл отправлен в сообщении и хранится в истории переписки."
    if InstructorCertificate.objects.filter(document=asset).exclude(
            status=InstructorCertificate.Status.REJECTED).exists():
        return "Файл привязан к сертификату. Удалите сертификат в кабинете инструктора."
    return None


def delete_media(asset_id, account):
    with transaction.atomic():
        asset = MediaAsset.objects.select_for_update().filter(id=asset_id, owner=account).exclude(
            status=MediaAsset.Status.DELETED).first()
        if asset is None:
            raise NotFound("Файл не найден.")
        reason = media_in_use(asset)
        if reason:
            raise Conflict(reason, code="media_in_use")
        from apps.accounts.models import UserProfile

        UserProfile.objects.filter(avatar=asset).update(avatar=None)
        asset.status = MediaAsset.Status.DELETED
        asset.save(update_fields=["status", "updated_at"])
        transaction.on_commit(lambda: _delete_objects(asset))
    return asset


def cleanup_expired_uploads(now=None):
    """Периодическая очистка: pending с истёкшей ссылкой удаляются; зависшие processing — перезапуск."""
    now = now or timezone.now()
    removed = 0
    expired = MediaAsset.objects.filter(status=MediaAsset.Status.PENDING,
                                        upload_expires_at__lt=now - EXPIRED_PENDING_GRACE)
    for asset in expired.iterator():
        _delete_objects(asset)
        try:
            MediaAsset.objects.filter(pk=asset.pk, status=MediaAsset.Status.PENDING).delete()
        except ProtectedError:  # кто-то сослался на незагруженный файл в обход claim_media — не удаляем строку
            MediaAsset.objects.filter(pk=asset.pk).update(status=MediaAsset.Status.DELETED, updated_at=now)
        removed += 1
    requeued = 0
    stuck = MediaAsset.objects.filter(status=MediaAsset.Status.PROCESSING, updated_at__lt=now - STUCK_PROCESSING_AFTER)
    for asset_id in stuck.values_list("id", flat=True):
        MediaAsset.objects.filter(pk=asset_id).update(updated_at=now)
        enqueue_processing(asset_id)
        requeued += 1
    return {"removed": removed, "requeued": requeued}
