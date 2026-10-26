"""Celery-задачи learning (docs/ARCHITECTURE.md §5)."""
import datetime as dt

from celery import shared_task
from django.db.models import Prefetch
from django.utils import timezone

REMINDER_WINDOW = dt.timedelta(hours=24)


@shared_task(name="learning.send_lesson_reminders")
def send_lesson_reminders():
    """За 24 ч до начала — клиентам с подтверждённой записью и инструктору.

    Повторный запуск безопасен: event_id уведомления уникален для брони и времени начала (после переноса
    напоминание придёт снова — уже о новом времени).
    """
    from apps.commerce.models import Booking
    from apps.learning.models import LessonSession
    from apps.learning.services.common import human_start
    from apps.messaging.models import Notification
    from apps.messaging.services.notify import notify

    now = timezone.now()
    confirmed = Booking.objects.filter(status=Booking.Status.CONFIRMED).select_related("customer")
    upcoming = (LessonSession.objects
                .filter(status=LessonSession.Status.SCHEDULED, starts_at__gt=now, starts_at__lte=now + REMINDER_WINDOW)
                .select_related("instructor", "spot__region", "organization__region")
                .prefetch_related(Prefetch("bookings", queryset=confirmed, to_attr="confirmed_bookings")))
    sent = 0
    for session in upcoming:
        if not session.confirmed_bookings:
            continue
        stamp = int(session.starts_at.timestamp())
        when = human_start(session)
        place = f", {session.spot.name}" if session.spot_id else ""
        for booking in session.confirmed_bookings:
            if notify(booking.customer, Notification.Kind.LESSON_REMINDER, "Напоминание о занятии",
                      body=f"«{session.title}» — {when}{place}.", link=f"/account/bookings/{booking.pk}",
                      payload={"session_id": str(session.pk), "booking_id": str(booking.pk)},
                      event_id=f"lesson_reminder:{booking.pk}:{stamp}"):
                sent += 1
        if session.instructor_id:
            seats = sum(b.seats for b in session.confirmed_bookings)
            if notify(session.instructor, Notification.Kind.LESSON_REMINDER, "Завтра занятие",
                      body=f"«{session.title}» — {when}{place}. Записано: {seats}.",
                      link="/account/instructor/schedule", payload={"session_id": str(session.pk)},
                      event_id=f"lesson_reminder:session:{session.pk}:{stamp}"):
                sent += 1
    return sent
