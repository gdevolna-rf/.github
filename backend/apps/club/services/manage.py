"""Управление клубом (CLB-03): организатор (серверная роль organizer) — свои события и анонсы;
администратор с 2FA — все. Каждое изменение пишет AuditEvent в той же транзакции."""
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import StaffRole
from apps.accounts.services.roles import has_role, has_verified_staff_role
from apps.club.models import ClubAnnouncement, ClubEvent, EventRegistration
from apps.club.services.events import ACTIVE_REG_STATUSES, parse_uuid, promote_waitlist, with_counts
from apps.common.exceptions import Conflict, DomainError, Forbidden, NotFound
from apps.common.text import unique_slug
from apps.mediafiles.models import MediaAsset
from apps.mediafiles.services import claim_media
from apps.messaging.models import Notification
from apps.messaging.services.notify import notify
from apps.organizations.models import Organization
from apps.organizations.services.access import can_manage
from apps.spots.models import Region, Spot
from apps.trust.services.audit import record
from apps.trust.services.restrictions import require_can_publish

MANAGE_STATUSES = [ClubEvent.Status.DRAFT, ClubEvent.Status.PUBLISHED, ClubEvent.Status.CANCELLED]
CLOSED_STATUSES = [ClubEvent.Status.CANCELLED, ClubEvent.Status.COMPLETED]
AUDIT_FIELDS = ["title", "kind", "status", "starts_at", "ends_at", "capacity", "registration_open", "spot_id",
                "region_id", "location_note", "organizer_organization_id", "cover_id"]


def is_admin(request):
    return has_verified_staff_role(request, StaffRole.Role.ADMIN)


def is_club_manager(request):
    return has_role(request.user, StaffRole.Role.ORGANIZER) or is_admin(request)


def _json(value):
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _snapshot(obj, fields):
    return {field: _json(getattr(obj, field)) for field in fields}


# ---------------------------------------------------------------- события

def manageable_events(request):
    qs = with_counts(ClubEvent.objects.all())
    if not is_admin(request):
        qs = qs.filter(organizer=request.user)
    return qs


def get_manageable_event(request, pk, lock=False):
    pk = parse_uuid(pk)
    qs = ClubEvent.objects.select_for_update() if lock else manageable_events(request)
    if lock and not is_admin(request):
        qs = qs.filter(organizer=request.user)
    event = qs.filter(pk=pk).first() if pk else None
    if event is None:
        raise NotFound("Событие не найдено.", code="club_event_not_found")
    return event


def _resolve_relations(actor, request, data, event=None):
    """spot_id/region_id/organizer_organization_id/cover_id → объекты с проверкой прав."""
    resolved = {}
    if "spot_id" in data:
        spot = None
        if data["spot_id"]:
            spot = Spot.objects.filter(pk=data["spot_id"], status=Spot.Status.PUBLISHED).select_related("region").first()
            if spot is None:
                raise DomainError("club_spot_invalid", "Спот не найден в каталоге.",
                                  fields={"spot_id": ["Выберите опубликованный спот."]})
        resolved["spot"] = spot
    if "region_id" in data:
        region = None
        if data["region_id"] is not None:
            region = Region.objects.filter(pk=data["region_id"]).first()
            if region is None:
                raise DomainError("club_region_invalid", "Регион не найден.", fields={"region_id": ["Неизвестный регион."]})
        resolved["region"] = region
    if resolved.get("spot") is not None and "region" not in resolved and (event is None or event.region_id is None):
        resolved["region"] = resolved["spot"].region
    if "organizer_organization_id" in data:
        org = None
        if data["organizer_organization_id"]:
            org = Organization.objects.filter(pk=data["organizer_organization_id"]).first()
            if org is None or not (is_admin(request) or can_manage(actor, org)):
                raise DomainError("club_organization_invalid", "Можно указать только организацию, которой вы управляете.",
                                  fields={"organizer_organization_id": ["Нет прав на эту организацию."]})
        resolved["organizer_organization"] = org
    if "cover_id" in data:
        cover = None
        if data["cover_id"]:
            if event is not None and event.cover_id == data["cover_id"]:
                cover = event.cover
            else:
                cover = claim_media(data["cover_id"], actor, purposes=[MediaAsset.Purpose.EVENT_COVER],
                                    kinds=[MediaAsset.Kind.IMAGE])
        resolved["cover"] = cover
    return resolved


SIMPLE_FIELDS = ["title", "kind", "description", "location_note", "starts_at", "ends_at", "capacity",
                 "registration_open"]


def create_event(actor, request, data):
    require_can_publish(actor)
    status = data.get("status", ClubEvent.Status.DRAFT)
    if status == ClubEvent.Status.CANCELLED:
        raise DomainError("club_status_invalid", "Нельзя создать сразу отменённое событие.",
                          fields={"status": ["Выберите «Черновик» или «Опубликовано»."]})
    if status == ClubEvent.Status.PUBLISHED and data["ends_at"] <= timezone.now():
        raise DomainError("club_event_in_past", "Нельзя опубликовать прошедшее событие.",
                          fields={"ends_at": ["Событие уже закончилось."]})
    relations = _resolve_relations(actor, request, data)
    with transaction.atomic():
        event = ClubEvent.objects.create(
            slug=unique_slug(ClubEvent, data["title"], max_length=80),
            organizer=actor,
            status=status,
            **{f: data[f] for f in SIMPLE_FIELDS if f in data},
            **relations,
        )
        record(actor, "club.event_created", event, after=_snapshot(event, AUDIT_FIELDS), request=request)
    return event


def _check_transition(event, new_status):
    if new_status == event.status:
        return
    if event.status in CLOSED_STATUSES:
        raise Conflict("Отменённое или прошедшее событие нельзя вернуть.", code="club_event_closed")
    if new_status == ClubEvent.Status.DRAFT and event.registrations.filter(status__in=ACTIVE_REG_STATUSES).exists():
        raise Conflict("У события есть регистрации — снять с публикации нельзя, его можно только отменить.",
                       code="club_event_has_registrations")


def _notify_registrants(event, title, body, event_key, actor=None):
    """Уведомление всем активным участникам события (вид event_status, ссылка на карточку события)."""
    for registration in event.registrations.filter(status__in=ACTIVE_REG_STATUSES).select_related("account"):
        notify(registration.account, Notification.Kind.EVENT_STATUS, title, body=body,
               link=f"/club/events/{event.slug}", payload={"club_event_id": str(event.pk), "status": event.status},
               event_id=f"{event_key}:{registration.pk}", actor=actor)


def update_event(request, pk, data):
    actor = request.user
    cancel_reason = data.pop("cancel_reason", "")
    with transaction.atomic():
        event = get_manageable_event(request, pk, lock=True)
        if event.status in CLOSED_STATUSES:
            raise Conflict("Отменённое или прошедшее событие нельзя изменить.", code="club_event_closed")
        before = _snapshot(event, AUDIT_FIELDS)
        new_status = data.get("status", event.status)
        if set(data) - {"status"} or new_status not in (event.status, ClubEvent.Status.CANCELLED):
            require_can_publish(actor)  # отменить своё событие можно и при ограничении
        _check_transition(event, new_status)
        relations = _resolve_relations(actor, request, data, event=event)
        old_start, old_end = event.starts_at, event.ends_at
        for field in SIMPLE_FIELDS:
            if field in data:
                setattr(event, field, data[field])
        for field, value in relations.items():
            setattr(event, field, value)
        if event.ends_at <= event.starts_at:
            raise DomainError("club_event_dates", "Окончание должно быть позже начала.",
                              fields={"ends_at": ["Окончание должно быть позже начала."]})
        if new_status == ClubEvent.Status.PUBLISHED and event.ends_at <= timezone.now():
            raise DomainError("club_event_in_past", "Нельзя опубликовать прошедшее событие.",
                              fields={"ends_at": ["Событие уже закончилось."]})
        registered = event.registrations.filter(status=EventRegistration.Status.REGISTERED).count()
        if event.capacity is not None and event.capacity < registered:
            raise Conflict(f"Уже зарегистрировано {registered} участников — лимит не может быть меньше.",
                           code="club_capacity_below_registered", fields={"capacity": [f"Минимум {registered}."]})
        event.status = new_status
        event.save()
        rescheduled = (event.status == ClubEvent.Status.PUBLISHED
                       and (event.starts_at != old_start or event.ends_at != old_end))
        if rescheduled:
            # Новое время — новое напоминание за 24 ч каждому участнику.
            event.registrations.filter(status__in=ACTIVE_REG_STATUSES).update(reminder_sent_at=None)
            event.reminder_sent_at = None
            event.save(update_fields=["reminder_sent_at"])
            _notify_registrants(event, f"Событие «{event.title}» перенесено",
                                "Проверьте новое время и место в карточке события.",
                                f"club_event_rescheduled:{event.pk}:{event.starts_at.isoformat()}")
        if new_status == ClubEvent.Status.CANCELLED and before["status"] != ClubEvent.Status.CANCELLED:
            body = f"Организатор отменил событие. {cancel_reason}".strip() if cancel_reason else \
                "Организатор отменил событие. Приносим извинения."
            _notify_registrants(event, f"Событие «{event.title}» отменено", body, f"club_event_cancelled:{event.pk}")
            action = "club.event_cancelled"
        elif new_status == ClubEvent.Status.PUBLISHED and before["status"] != ClubEvent.Status.PUBLISHED:
            action = "club.event_published"
        else:
            action = "club.event_updated"
        promote_waitlist(event)
        record(actor, action, event, before=before, after=_snapshot(event, AUDIT_FIELDS),
               metadata={"cancel_reason": cancel_reason} if cancel_reason else None, request=request)
    return event


def delete_event(request, pk):
    with transaction.atomic():
        event = get_manageable_event(request, pk, lock=True)
        if event.registrations.exists():
            raise Conflict("На событие уже регистрировались — отмените его вместо удаления.",
                           code="club_event_has_registrations")
        record(request.user, "club.event_deleted", event, before=_snapshot(event, AUDIT_FIELDS), request=request)
        event.delete()


def event_registrations(request, pk, status=None):
    event = get_manageable_event(request, pk)
    qs = event.registrations.select_related("account__profile__avatar").order_by("created_at", "id")
    if status:
        if status not in EventRegistration.Status.values:
            raise DomainError("validation_error", "Неизвестный статус регистрации.",
                              fields={"status": [f"Допустимо: {', '.join(EventRegistration.Status.values)}."]})
        qs = qs.filter(status=status)
    else:
        qs = qs.filter(status__in=ACTIVE_REG_STATUSES)
    return qs


# ---------------------------------------------------------------- анонсы

ANNOUNCEMENT_AUDIT_FIELDS = ["title", "is_pinned", "published_at"]


def manageable_announcements(request):
    qs = ClubAnnouncement.objects.select_related("author__profile__avatar")
    if not is_admin(request):
        qs = qs.filter(author=request.user)
    return qs.order_by("-is_pinned", "-published_at", "-created_at")


def get_manageable_announcement(request, pk):
    pk = parse_uuid(pk)
    announcement = manageable_announcements(request).filter(pk=pk).first() if pk else None
    if announcement is None:
        raise NotFound("Анонс не найден.", code="club_announcement_not_found")
    return announcement


def _apply_publication(announcement, data):
    if "published_at" in data:
        announcement.published_at = data["published_at"]
    if "is_published" in data:
        if data["is_published"] and announcement.published_at is None:
            announcement.published_at = timezone.now()
        elif not data["is_published"]:
            announcement.published_at = None


def create_announcement(request, data):
    require_can_publish(request.user)
    announcement = ClubAnnouncement(author=request.user, title=data["title"], body=data["body"],
                                    is_pinned=data.get("is_pinned", False))
    _apply_publication(announcement, data)
    with transaction.atomic():
        announcement.save()
        record(request.user, "club.announcement_created", announcement,
               after=_snapshot(announcement, ANNOUNCEMENT_AUDIT_FIELDS), request=request)
    return announcement


def update_announcement(request, pk, data):
    announcement = get_manageable_announcement(request, pk)
    if set(data) - {"is_published"} or data.get("is_published"):
        require_can_publish(request.user)  # снять анонс с публикации можно и при ограничении
    before = _snapshot(announcement, ANNOUNCEMENT_AUDIT_FIELDS)
    for field in ["title", "body", "is_pinned"]:
        if field in data:
            setattr(announcement, field, data[field])
    _apply_publication(announcement, data)
    with transaction.atomic():
        announcement.save()
        record(request.user, "club.announcement_updated", announcement, before=before,
               after=_snapshot(announcement, ANNOUNCEMENT_AUDIT_FIELDS), request=request)
    return announcement


def delete_announcement(request, pk):
    announcement = get_manageable_announcement(request, pk)
    with transaction.atomic():
        record(request.user, "club.announcement_deleted", announcement,
               before=_snapshot(announcement, ANNOUNCEMENT_AUDIT_FIELDS), request=request)
        announcement.delete()


def require_manager(request):
    if not is_club_manager(request):
        raise Forbidden("Управление клубом доступно организаторам и администраторам.", code="club_organizer_required")


def cancel_event_by_admin(event, actor, request=None, reason=""):
    """Отмена из Django Admin: та же логика уведомлений и аудита, что и в API."""
    with transaction.atomic():
        event = ClubEvent.objects.select_for_update().get(pk=event.pk)
        if event.status in CLOSED_STATUSES:
            return False
        before = _snapshot(event, AUDIT_FIELDS)
        event.status = ClubEvent.Status.CANCELLED
        event.save(update_fields=["status", "updated_at"])
        body = f"Организатор отменил событие. {reason}".strip() if reason else \
            "Организатор отменил событие. Приносим извинения."
        _notify_registrants(event, f"Событие «{event.title}» отменено", body, f"club_event_cancelled:{event.pk}")
        record(actor, "club.event_cancelled", event, before=before, after=_snapshot(event, AUDIT_FIELDS),
               metadata={"source": "admin"}, request=request)
    return True


# ---------------------------------------------------------------- решения модератора (trust, F14)

def hide_event_by_moderation(event, moderator, note=""):
    """Жалоба удовлетворена «скрыть»: событие отменяется, записавшиеся уведомляются (журнал пишет trust).

    Возвращает (before, after) для AuditEvent и восстановления по апелляции. Вызывать внутри транзакции trust.
    """
    event = ClubEvent.objects.select_for_update().get(pk=event.pk)
    before = {"status": event.status}
    if event.status == ClubEvent.Status.CANCELLED:
        return before, before
    upcoming = event.status == ClubEvent.Status.PUBLISHED and event.ends_at > timezone.now()
    event.status = ClubEvent.Status.CANCELLED
    event.save(update_fields=["status", "updated_at"])
    if upcoming:  # прошедшее событие просто скрывается, участников не тревожим
        _notify_registrants(
            event, f"Событие «{event.title}» отменено",
            "Событие снято с публикации модератором. Регистрация больше не действует — приносим извинения.",
            f"club_event_moderated:{event.pk}:{int(timezone.now().timestamp())}", actor=moderator)
    return before, {"status": event.status}


def restore_event_after_appeal(event, moderator=None):
    """Апелляция удовлетворена: событие снова в силе — записавшимся сообщаем (статус вернул trust)."""
    if event.status != ClubEvent.Status.PUBLISHED or event.ends_at <= timezone.now():
        return
    _notify_registrants(
        event, f"Событие «{event.title}» снова в силе",
        "Модератор восстановил событие. Ваша регистрация сохранена — проверьте время и место.",
        f"club_event_restored:{event.pk}:{int(timezone.now().timestamp())}", actor=moderator)
