"""Клубные события: публичный календарь, регистрация с лимитом мест и листом ожидания (CLB-01/02).

Вместимость проверяется под select_for_update строки события, поэтому параллельные регистрации не превышают лимит.
"""
import datetime as dt
import uuid

from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.accounts.serializers_public import PublicAccountSerializer
from apps.club.models import ClubAnnouncement, ClubEvent, EventRegistration
from apps.common.exceptions import Conflict, DomainError, NotFound
from apps.messaging.models import Notification
from apps.messaging.services.notify import notify
from apps.organizations.models import Organization
from apps.search.services.catalog import organization_url, public_media, region_data, spot_ref
from apps.spots.models import Region, Spot

LIST_STATUSES = [ClubEvent.Status.PUBLISHED, ClubEvent.Status.COMPLETED]
DETAIL_STATUSES = [ClubEvent.Status.PUBLISHED, ClubEvent.Status.COMPLETED, ClubEvent.Status.CANCELLED]
ACTIVE_REG_STATUSES = [EventRegistration.Status.REGISTERED, EventRegistration.Status.WAITLIST]
DEFAULT_TZ = "Europe/Moscow"


def parse_uuid(value):
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        return None


def with_counts(qs):
    return qs.annotate(
        registered_count=Count("registrations", filter=Q(registrations__status=EventRegistration.Status.REGISTERED),
                               distinct=True),
        waitlist_count=Count("registrations", filter=Q(registrations__status=EventRegistration.Status.WAITLIST),
                             distinct=True),
    ).select_related("spot", "region", "cover", "organizer__profile__avatar", "organizer_organization")


def public_events():
    return with_counts(ClubEvent.objects.filter(status__in=LIST_STATUSES))


def upcoming_events():
    return public_events().filter(status=ClubEvent.Status.PUBLISHED, ends_at__gte=timezone.now()).order_by("starts_at")


def _parse_bound(value, name, end=False):
    if not value:
        return None
    moment = parse_datetime(value) if len(value) > 10 else None
    if moment is None:
        try:
            day = dt.date.fromisoformat(value[:10])
        except ValueError:
            raise DomainError("validation_error", "Неверный формат даты.",
                              fields={name: ["Ожидается YYYY-MM-DD или ISO 8601."]}) from None
        if end:
            day += dt.timedelta(days=1)
        moment = dt.datetime.combine(day, dt.time.min)
    if timezone.is_naive(moment):
        moment = timezone.make_aware(moment)
    return moment


def lookup_region(value):
    value = str(value or "").strip()
    if not value:
        return None
    if value.isdigit():
        return Region.objects.filter(pk=int(value)).first()
    return Region.objects.filter(slug=value).first()


def filter_events(qs, params):
    """from/to — окно календаря (пересечение), kind, region (slug|id), spot (slug|id). Без окна — предстоящие."""
    start = _parse_bound(params.get("from"), "from")
    end = _parse_bound(params.get("to"), "to", end=True)
    if start is None and end is None:
        qs = qs.filter(ends_at__gte=timezone.now())
    if start is not None:
        qs = qs.filter(ends_at__gte=start)
    if end is not None:
        qs = qs.filter(starts_at__lt=end)
    kind = params.get("kind")
    if kind:
        if kind not in ClubEvent.Kind.values:
            raise DomainError("validation_error", "Неизвестный тип события.",
                              fields={"kind": [f"Допустимо: {', '.join(ClubEvent.Kind.values)}."]})
        qs = qs.filter(kind=kind)
    region = params.get("region")
    if region:
        obj = lookup_region(region)
        qs = qs.filter(Q(region=obj) | Q(spot__region=obj)) if obj else qs.none()
    spot = params.get("spot")
    if spot:
        pk = parse_uuid(spot)
        qs = qs.filter(spot_id=pk) if pk else qs.filter(spot__slug=spot)
    return qs.order_by("starts_at", "id")


# ---------------------------------------------------------------- карточки

def _counts(event):
    registered = getattr(event, "registered_count", None)
    waitlist = getattr(event, "waitlist_count", None)
    if registered is None:
        registered = event.registrations.filter(status=EventRegistration.Status.REGISTERED).count()
    if waitlist is None:
        waitlist = event.registrations.filter(status=EventRegistration.Status.WAITLIST).count()
    return registered, waitlist


def registration_is_open(event, now=None):
    now = now or timezone.now()
    return bool(event.registration_open and event.status == ClubEvent.Status.PUBLISHED and event.starts_at > now)


def event_card(event):
    registered, waitlist = _counts(event)
    free = max(event.capacity - registered, 0) if event.capacity else None
    org = event.organizer_organization
    org_data = None
    if org is not None and org.status == Organization.Status.PUBLISHED:
        org_data = {"id": str(org.pk), "slug": org.slug, "name": org.name, "kind": org.kind,
                    "url": organization_url(org)}
    spot = event.spot if event.spot_id and event.spot.status == Spot.Status.PUBLISHED else None
    region = event.region or (spot.region if spot else None)
    return {
        "id": str(event.pk),
        "slug": event.slug,
        "title": event.title,
        "kind": event.kind,
        "kind_label": event.get_kind_display(),
        "status": event.status,
        "status_label": event.get_status_display(),
        "starts_at": event.starts_at,
        "ends_at": event.ends_at,
        "timezone": region.timezone if region else DEFAULT_TZ,
        "spot": spot_ref(spot),
        "region": region_data(region),
        "location_note": event.location_note,
        "capacity": event.capacity,
        "registrations_count": registered,
        "waitlist_count": waitlist,
        "free_places": free,
        "is_full": free == 0,
        "registration_open": registration_is_open(event),
        "cover": public_media(event.cover) if event.cover_id else None,
        "organizer": PublicAccountSerializer(event.organizer).data,
        "organizer_organization": org_data,
        "url": f"/club/events/{event.slug}",
    }


def waitlist_position(registration):
    if registration.status != EventRegistration.Status.WAITLIST:
        return None
    return EventRegistration.objects.filter(
        event_id=registration.event_id, status=EventRegistration.Status.WAITLIST
    ).filter(Q(created_at__lt=registration.created_at)
             | Q(created_at=registration.created_at, id__lt=registration.id)).count() + 1


def registration_data(registration):
    return {
        "id": str(registration.pk),
        "status": registration.status,
        "status_label": registration.get_status_display(),
        "created_at": registration.created_at,
        "promoted_at": registration.promoted_at,
        "waitlist_position": waitlist_position(registration),
    }


def active_registration(event, account):
    if account is None or not getattr(account, "is_authenticated", False):
        return None
    return event.registrations.filter(account=account, status__in=ACTIVE_REG_STATUSES).first()


def event_detail(event, viewer):
    data = event_card(event)
    registration = active_registration(event, viewer)
    data.update({
        "description": event.description,
        "my_registration": registration_data(registration) if registration else None,
    })
    return data


def get_public_event(slug):
    event = with_counts(ClubEvent.objects.filter(status__in=DETAIL_STATUSES, slug=slug)).first()
    if event is None:
        raise NotFound("Событие не найдено.", code="club_event_not_found")
    return event


def announcement_data(announcement):
    return {
        "id": str(announcement.pk),
        "title": announcement.title,
        "body": announcement.body,
        "is_pinned": announcement.is_pinned,
        "published_at": announcement.published_at,
    }


def published_announcements():
    return ClubAnnouncement.objects.filter(published_at__isnull=False, published_at__lte=timezone.now()).order_by(
        "-is_pinned", "-published_at")


# ---------------------------------------------------------------- регистрация

def _lock_event(event_id):
    pk = parse_uuid(event_id)
    event = ClubEvent.objects.select_for_update().filter(pk=pk).first() if pk else None
    if event is None or event.status == ClubEvent.Status.DRAFT:
        raise NotFound("Событие не найдено.", code="club_event_not_found")
    return event


def _event_link(event):
    return f"/club/events/{event.slug}"


def register(event_id, account):
    """Идемпотентная регистрация: registered при свободных местах, иначе waitlist. → (registration, created)."""
    with transaction.atomic():
        event = _lock_event(event_id)
        existing = event.registrations.filter(account=account, status__in=ACTIVE_REG_STATUSES).first()
        if existing:
            return existing, False
        if event.status == ClubEvent.Status.CANCELLED:
            raise Conflict("Событие отменено.", code="club_event_cancelled")
        if event.status != ClubEvent.Status.PUBLISHED or event.starts_at <= timezone.now():
            raise Conflict("Событие уже началось или прошло.", code="club_event_started")
        if not event.registration_open:
            raise Conflict("Регистрация на событие закрыта.", code="club_registration_closed")
        registered = event.registrations.filter(status=EventRegistration.Status.REGISTERED).count()
        status = (EventRegistration.Status.REGISTERED if event.capacity is None or registered < event.capacity
                  else EventRegistration.Status.WAITLIST)
        try:
            with transaction.atomic():
                registration = EventRegistration.objects.create(event=event, account=account, status=status)
        except IntegrityError:
            return event.registrations.get(account=account, status__in=ACTIVE_REG_STATUSES), False
    return registration, True


def promote_waitlist(event):
    """Переводит первых из листа ожидания на свободные места. Вызывать под блокировкой события."""
    if event.status != ClubEvent.Status.PUBLISHED or event.starts_at <= timezone.now():
        return []
    waiting = event.registrations.select_for_update().filter(status=EventRegistration.Status.WAITLIST).order_by(
        "created_at", "id")
    if event.capacity is not None:
        registered = event.registrations.filter(status=EventRegistration.Status.REGISTERED).count()
        free = event.capacity - registered
        if free <= 0:
            return []
        waiting = waiting[:free]
    promoted = []
    now = timezone.now()
    for registration in list(waiting):
        registration.status = EventRegistration.Status.REGISTERED
        registration.promoted_at = now
        registration.save(update_fields=["status", "promoted_at", "updated_at"])
        notify(registration.account, Notification.Kind.EVENT_STATUS, "Освободилось место — вы в списке участников",
               body=f"«{event.title}»: место из листа ожидания подтверждено.", link=_event_link(event),
               payload={"club_event_id": str(event.pk), "registration_id": str(registration.pk)},
               event_id=f"club_waitlist_promoted:{registration.pk}")
        promoted.append(registration)
    return promoted


def cancel_registration(event_id, account):
    """Идемпотентная отмена своей регистрации; освободившееся место получает первый из листа ожидания."""
    with transaction.atomic():
        event = _lock_event(event_id)
        registration = (event.registrations.select_for_update()
                        .filter(account=account, status__in=ACTIVE_REG_STATUSES).first())
        if registration is None:
            return None
        was_registered = registration.status == EventRegistration.Status.REGISTERED
        registration.status = EventRegistration.Status.CANCELLED
        registration.cancelled_at = timezone.now()
        registration.save(update_fields=["status", "cancelled_at", "updated_at"])
        if was_registered:
            promote_waitlist(event)
    return registration


def release_deleted_account(account):
    """AT-10: активные регистрации удалённого аккаунта на будущие события отменяются, места уходят листу ожидания."""
    event_ids = (EventRegistration.objects.filter(account=account, status__in=ACTIVE_REG_STATUSES,
                                                  event__ends_at__gt=timezone.now())
                 .values_list("event_id", flat=True).distinct())
    released = []
    for event_id in list(event_ids):
        try:
            released.append(cancel_registration(event_id, account))
        except NotFound:  # черновик без регистраций — пропускаем, удаление аккаунта не должно падать
            continue
    return released


def reload_event(event_id):
    return with_counts(ClubEvent.objects.filter(pk=event_id)).get()
