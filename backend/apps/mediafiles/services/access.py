"""Права на закрытые медиа (9.1, ATX-23). Чужой или угаданный id → 404, существование не раскрывается."""
import datetime as dt

from django.conf import settings
from django.utils import timezone

from apps.common.exceptions import DomainError, NotFound
from apps.common.s3 import request_origin
from apps.mediafiles.models import MediaAsset
from apps.mediafiles.storage import get_storage


def _is_moderator(request):
    from apps.accounts.services.roles import has_verified_staff_role

    return has_verified_staff_role(request, "moderator")


def _message_attachment_access(asset, user):
    """Тот, кто сейчас видит диалог с этим вложением (messaging.conversation_side): клиент, исполнитель,
    действующие сотрудники организации-исполнителя, участники личной переписки. Право вычисляется по текущему
    членству — отозванный сотрудник теряет доступ сразу, даже если строка ConversationParticipant осталась (AT-09)."""
    from apps.messaging.models import Conversation, MessageAttachment
    from apps.messaging.services.conversations import conversation_side

    conversation_ids = MessageAttachment.objects.filter(media=asset).values("message__conversation_id")
    conversations = Conversation.objects.filter(id__in=conversation_ids).select_related(
        "inquiry", "inquiry__provider_organization")
    return any(conversation_side(conversation, user) is not None for conversation in conversations)


def _handover_access(asset, user):
    from apps.inventory.models import RentalHandover
    from apps.organizations.services.access import is_member

    for handover in RentalHandover.objects.filter(photos=asset).select_related("booking__provider_organization"):
        booking = handover.booking
        if user.pk in (booking.customer_id, booking.provider_account_id):
            return True
        if booking.provider_organization_id and is_member(user, booking.provider_organization):
            return True
    return False


def _public_certificate(asset):
    """Те же правила, что у GET certificates/{id}/scan: проверен, не истёк, показ разрешён, карточка опубликована."""
    from apps.learning.models import InstructorCertificate
    from apps.learning.services.instructors import is_scan_public

    certificates = InstructorCertificate.objects.filter(
        document=asset, status=InstructorCertificate.Status.VERIFIED, allow_public_scan=True,
    ).select_related("instructor__account")
    return any(is_scan_public(cert) for cert in certificates)


def can_access(asset, request):
    """Может ли текущий пользователь получить файл (для закрытых — presigned GET)."""
    if asset.status == MediaAsset.Status.DELETED:
        return False
    user = request.user if request is not None else None
    authenticated = bool(user and user.is_authenticated)
    if authenticated and asset.owner_id == user.pk:
        return True
    if asset.status != MediaAsset.Status.READY:
        return authenticated and _is_moderator(request)
    if asset.purpose == MediaAsset.Purpose.DIARY_PHOTO:
        # Публичный файл (public/, неугадываемый ключ), но метаданные и ссылку отдаём по видимости записи дневника.
        from apps.community.services.diary import photo_visible_to

        return (authenticated and _is_moderator(request)) or photo_visible_to(asset, user)
    if asset.is_public:
        return True
    if asset.purpose == MediaAsset.Purpose.CERTIFICATE and _public_certificate(asset):
        return True
    if not authenticated:
        return False
    if _is_moderator(request):
        return True
    if _message_attachment_access(asset, user):
        return True
    if _handover_access(asset, user):
        return True
    return False


def get_accessible(asset_id, request):
    asset = MediaAsset.objects.filter(id=asset_id).first()
    if asset is None or not can_access(asset, request):
        raise NotFound("Файл не найден.")
    return asset


def access_url(asset, request, variant="original", *, allow_processing=False):
    """Ссылка на файл: публичный путь или presigned GET на MEDIA_PRIVATE_URL_TTL секунд.

    allow_processing=True — оригинал ещё проверяемого файла (владельцу/модератору, напр. скан сертификата).
    Права проверяет вызывающий (can_access / собственные правила приложения).
    """
    processing_ok = allow_processing and asset.status == MediaAsset.Status.PROCESSING and variant == "original"
    if asset.status != MediaAsset.Status.READY and not processing_ok:
        raise DomainError("media_not_ready", "Файл ещё обрабатывается.", status_code=409)
    key = asset.storage_key
    if variant == "thumbnail":
        if not asset.thumbnail_key:
            raise DomainError("thumbnail_missing", "Для этого файла нет миниатюры.")
        key = asset.thumbnail_key
    if asset.is_public and asset.status == MediaAsset.Status.READY:
        path = asset.thumbnail_url if variant == "thumbnail" else asset.url
        return {"url": path, "expires_at": None}
    ttl = settings.MEDIA_PRIVATE_URL_TTL
    attachment = asset.purpose == MediaAsset.Purpose.DATA_EXPORT
    filename = asset.original_filename or None
    if variant == "thumbnail":
        filename = None
    url = get_storage().presigned_get(key, ttl, request_origin(request), filename=filename, attachment=attachment)
    return {"url": url, "expires_at": timezone.now() + dt.timedelta(seconds=ttl)}


def private_url_for(asset, request, variant="original"):
    """Для других приложений (например, скан сертификата): ссылка без повторной проверки прав."""
    return access_url(asset, request, variant)

