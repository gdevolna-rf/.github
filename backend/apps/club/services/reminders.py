"""Напоминания о клубных событиях за 24 часа (CLB-02, ARCHITECTURE §5) — один раз на регистрацию."""
import datetime as dt
import logging
import zoneinfo

from django.db import transaction
from django.utils import timezone

from apps.club.models import ClubEvent, EventRegistration
from apps.club.services.events import DEFAULT_TZ
from apps.messaging.models import Notification
from apps.messaging.services.notify import notify

logger = logging.getLogger(__name__)
REMINDER_WINDOW = dt.timedelta(hours=24)


def _local_start(event):
    tz_name = (event.region.timezone if event.region_id else None) or DEFAULT_TZ
    try:
        tz = zoneinfo.ZoneInfo(tz_name)
    except zoneinfo.ZoneInfoNotFoundError:
        tz = zoneinfo.ZoneInfo(DEFAULT_TZ)
    return timezone.localtime(event.starts_at, tz)


def reminder_body(event):
    start = _local_start(event)
    place = event.spot.name if event.spot_id else event.location_note
    parts = [f"Начало {start:%d.%m в %H:%M} (местное время)"]
    if place:
        parts.append(place)
    return " · ".join(parts)


def send_due_reminders(now=None):
    """Регистрациям со статусом registered на опубликованные события, начинающиеся в ближайшие 24 ч."""
    now = now or timezone.now()
    due = (EventRegistration.objects
           .filter(status=EventRegistration.Status.REGISTERED, reminder_sent_at__isnull=True,
                   event__status=ClubEvent.Status.PUBLISHED, event__starts_at__gt=now,
                   event__starts_at__lte=now + REMINDER_WINDOW)
           .values_list("pk", flat=True))
    sent = 0
    for pk in list(due):
        with transaction.atomic():
            registration = (EventRegistration.objects.select_for_update(skip_locked=True, of=("self",))
                            .select_related("event__spot", "event__region", "account")
                            .filter(pk=pk, reminder_sent_at__isnull=True,
                                    status=EventRegistration.Status.REGISTERED).first())
            if registration is None:
                continue
            event = registration.event
            notify(registration.account, Notification.Kind.EVENT_REMINDER, f"Скоро событие «{event.title}»",
                   body=reminder_body(event), link=f"/club/events/{event.slug}",
                   payload={"club_event_id": str(event.pk)},
                   event_id=f"club_event_reminder:{registration.pk}:{event.starts_at.isoformat()}")
            registration.reminder_sent_at = now
            registration.save(update_fields=["reminder_sent_at", "updated_at"])
            ClubEvent.objects.filter(pk=event.pk).update(reminder_sent_at=now)
            sent += 1
    completed = complete_past_events(now)
    logger.info("club reminders sent: %s, events completed: %s", sent, completed)
    return sent


def complete_past_events(now=None):
    """Опубликованные события, которые закончились, переводятся в «Прошло» (часть того же почасового обхода)."""
    now = now or timezone.now()
    return ClubEvent.objects.filter(status=ClubEvent.Status.PUBLISHED, ends_at__lt=now).update(
        status=ClubEvent.Status.COMPLETED, updated_at=now)
