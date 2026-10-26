"""Жалобы и апелляции (TRUST-07, MSG-13, F14): проверка цели, владелец цели, скрытие/восстановление."""
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.models import Account
from apps.boards.models import BoardModel
from apps.club.models import ClubEvent
from apps.common.exceptions import Conflict, DomainError, NotFound
from apps.inventory.models import InventoryItem
from apps.mediafiles.models import MediaAsset
from apps.messaging.models import ConversationParticipant, Message
from apps.organizations.models import Organization
from apps.spots.models import Spot
from apps.spots.services.catalog import public_spots
from apps.trust.models import Complaint, ModerationCase, Review
from apps.trust.services.audit import record
from apps.trust.services.moderation_queue import close_cases, open_case
from apps.trust.services.ratings import recalculate_for_review

T = Complaint.Target
APPEALABLE_ACTIONS = (Complaint.Action.WARNING, Complaint.Action.HIDDEN, Complaint.Action.SUSPENDED)


def _inventory_owner(item):
    return item.owner_account if item.owner_account_id else item.owner_organization.owner


def _visible_target(target_type, target_id, reporter):
    """Цель, которую жалующийся действительно может видеть, и её владелец. Иначе NotFound (без раскрытия)."""
    if target_type == T.SPOT:
        obj = public_spots().filter(pk=target_id).first()
        return obj, None
    if target_type == T.ACCOUNT:
        obj = Account.objects.filter(pk=target_id, is_active=True, anonymized_at__isnull=True).first()
        return obj, obj
    if target_type == T.REVIEW:
        obj = Review.objects.select_related("author").filter(pk=target_id, status=Review.Status.PUBLISHED).first()
        return obj, obj.author if obj else None
    if target_type == T.MESSAGE:
        obj = Message.objects.select_related("sender").filter(
            pk=target_id, is_hidden=False, kind=Message.Kind.TEXT,
            conversation_id__in=ConversationParticipant.objects.filter(account=reporter).values("conversation_id"),
        ).first()
        return obj, obj.sender if obj else None
    if target_type == T.BOARD_MODEL:
        obj = BoardModel.objects.select_related("workshop__owner").filter(
            pk=target_id, status=BoardModel.Status.PUBLISHED).first()
        return obj, obj.workshop.owner if obj else None
    if target_type == T.INVENTORY_ITEM:
        obj = InventoryItem.objects.select_related("owner_account", "owner_organization__owner").filter(
            pk=target_id, is_published=True).first()
        return obj, _inventory_owner(obj) if obj else None
    if target_type == T.ORGANIZATION:
        obj = Organization.objects.select_related("owner").filter(pk=target_id, status=Organization.Status.PUBLISHED).first()
        return obj, obj.owner if obj else None
    if target_type == T.MEDIA:
        obj = MediaAsset.objects.select_related("owner").filter(
            pk=target_id, status=MediaAsset.Status.READY, visibility=MediaAsset.Visibility.PUBLIC).first()
        return obj, obj.owner if obj else None
    if target_type == T.CLUB_EVENT:
        obj = ClubEvent.objects.select_related("organizer").filter(
            pk=target_id, status__in=[ClubEvent.Status.PUBLISHED, ClubEvent.Status.COMPLETED]).first()
        return obj, obj.organizer if obj else None
    raise DomainError("validation_error", "Неизвестный тип объекта жалобы.", fields={"target_type": ["Неверное значение."]})


_MODELS = {
    T.SPOT: Spot, T.ACCOUNT: Account, T.REVIEW: Review, T.MESSAGE: Message, T.BOARD_MODEL: BoardModel,
    T.INVENTORY_ITEM: InventoryItem, T.ORGANIZATION: Organization, T.MEDIA: MediaAsset, T.CLUB_EVENT: ClubEvent,
}


def target_object(complaint):
    """Цель жалобы в любом статусе (для модератора) или None, если удалена."""
    return _MODELS[complaint.target_type].objects.filter(pk=complaint.target_id).first()


def target_label(target_type, obj):
    if obj is None:
        return "объект удалён"
    if target_type == T.ACCOUNT:
        profile = getattr(obj, "profile", None)
        return profile.display_name if profile else "пользователь"
    if target_type == T.REVIEW:
        return f"отзыв {obj.rating}★"
    if target_type == T.MESSAGE:
        return "сообщение в чате"
    if target_type == T.MEDIA:
        return obj.original_filename or "медиафайл"
    return getattr(obj, "name", None) or getattr(obj, "title", None) or str(obj.pk)


def create_complaint(reporter, *, target_type, target_id, reason, text="", request=None):
    text = (text or "").strip()
    if reason == Complaint.Reason.OTHER and not text:
        raise DomainError("validation_error", "Опишите причину жалобы.", fields={"text": ["Обязательное поле для «Другое»."]})
    obj, owner = _visible_target(target_type, target_id, reporter)
    if obj is None:
        raise NotFound("Объект жалобы не найден.", code="target_not_found")
    if owner is not None and owner.pk == reporter.pk:
        raise DomainError("self_complaint", "Нельзя пожаловаться на собственный материал или профиль.")
    with transaction.atomic():
        try:
            with transaction.atomic():
                complaint = Complaint.objects.create(
                    reporter=reporter, target_type=target_type, target_id=str(obj.pk), reason=reason, text=text,
                    target_owner=owner,
                )
        except IntegrityError:
            raise Conflict("Вы уже отправили жалобу на этот объект — она рассматривается.", code="complaint_exists")
        summary = f"Жалоба: {complaint.get_reason_display()} — {complaint.get_target_type_display()} «{target_label(target_type, obj)}»"
        open_case("complaint", summary, complaint=complaint)
        record(reporter, "complaint.created", complaint,
               after={"target_type": target_type, "target_id": str(obj.pk), "reason": reason}, request=request)
    return complaint


def appeal_complaint(complaint_id, account, text, request=None):
    """Апелляция владельца цели на применённую меру (TRUST-07) → кейс appeal в очереди."""
    text = (text or "").strip()
    if not text:
        raise DomainError("validation_error", "Опишите, почему решение стоит пересмотреть.", fields={"text": ["Обязательное поле."]})
    with transaction.atomic():
        complaint = Complaint.objects.select_for_update().filter(pk=complaint_id, target_owner=account).first()
        if complaint is None or complaint.status != Complaint.Status.RESOLVED or complaint.action_taken not in APPEALABLE_ACTIONS:
            if complaint is None:
                raise NotFound("Жалоба не найдена.")
            raise Conflict("Обжаловать можно только применённую модератором меру.", code="invalid_status")
        if complaint.appealed_at is not None:
            raise Conflict("Апелляция по этому решению уже подана.", code="appeal_exists")
        complaint.appeal_text, complaint.appealed_at = text, timezone.now()
        complaint.save(update_fields=["appeal_text", "appealed_at", "updated_at"])
        open_case("appeal", f"Апелляция: {complaint.get_action_taken_display()} — {complaint.get_target_type_display()}",
                  complaint=complaint)
        record(account, "complaint.appealed", complaint, after={"appeal_text": text}, request=request)
    return complaint


def has_open_appeal(complaint):
    return ModerationCase.objects.filter(
        complaint=complaint, kind=ModerationCase.Kind.APPEAL,
        status__in=[ModerationCase.Status.OPEN, ModerationCase.Status.IN_REVIEW],
    ).exists()


# --- скрытие и восстановление цели (решение модератора) -----------------------------------------

def hide_target(complaint, note="", moderator=None):
    """Скрывает цель жалобы. Возвращает (before, after) для журнала и последующего восстановления."""
    obj = target_object(complaint)
    if obj is None:
        raise DomainError("target_missing", "Объект жалобы уже удалён.")
    tt = complaint.target_type
    if tt == T.ACCOUNT:
        raise DomainError("action_not_applicable", "Профиль нельзя скрыть — используйте ограничение профиля (suspended).")
    if tt == T.SPOT:
        before, obj.status = {"status": obj.status}, Spot.Status.HIDDEN
        obj.save(update_fields=["status", "updated_at"])
    elif tt == T.BOARD_MODEL:
        before, obj.status = {"status": obj.status}, BoardModel.Status.HIDDEN
        obj.save(update_fields=["status", "updated_at"])
    elif tt == T.INVENTORY_ITEM:
        before, obj.is_published = {"is_published": obj.is_published}, False
        obj.save(update_fields=["is_published", "updated_at"])
    elif tt == T.REVIEW:
        before, obj.status = {"status": obj.status}, Review.Status.HIDDEN
        obj.has_pending_revision, obj.pending_rating, obj.pending_text = False, None, ""
        obj.save(update_fields=["status", "has_pending_revision", "pending_rating", "pending_text", "updated_at"])
        obj.pending_photos.clear()
        close_cases("hidden", moderator, note, review=obj)
        recalculate_for_review(obj)
    elif tt == T.MESSAGE:
        before, obj.is_hidden = {"is_hidden": obj.is_hidden}, True
        obj.save(update_fields=["is_hidden", "updated_at"])
    elif tt == T.ORGANIZATION:
        before, obj.status = {"status": obj.status}, Organization.Status.SUSPENDED
        obj.save(update_fields=["status", "updated_at"])
    elif tt == T.CLUB_EVENT:
        from apps.club.services.manage import hide_event_by_moderation

        before, after = hide_event_by_moderation(obj, moderator, note)
        return before, after
    elif tt == T.MEDIA:
        before = {"status": obj.status, "rejection_reason": obj.rejection_reason}
        obj.status, obj.rejection_reason = MediaAsset.Status.REJECTED, (note or "Скрыто модератором по жалобе")[:300]
        obj.save(update_fields=["status", "rejection_reason", "updated_at"])
    else:  # pragma: no cover
        raise DomainError("action_not_applicable", "Для этого типа объекта скрытие недоступно.")
    after = {k: getattr(obj, k) for k in before}
    return before, after


def restore_target(complaint, before, moderator=None):
    """Возвращает поля цели к состоянию до скрытия (удовлетворённая апелляция)."""
    obj = target_object(complaint)
    if obj is None or not before:
        return None
    for field, value in before.items():
        setattr(obj, field, value)
    obj.save(update_fields=list(before) + ["updated_at"])
    if complaint.target_type == T.REVIEW:
        recalculate_for_review(obj)
    if complaint.target_type == T.CLUB_EVENT:
        from apps.club.services.manage import restore_event_after_appeal

        restore_event_after_appeal(obj, moderator)
    return {k: getattr(obj, k) for k in before}
