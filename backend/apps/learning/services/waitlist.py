"""Лист ожидания (SCH-08): встать в очередь можно только на заполненное занятие; при освобождении места
первому в очереди предлагается запись."""
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.commerce.models import Booking
from apps.common.exceptions import Conflict, NotFound
from apps.learning.models import LessonSession, WaitlistEntry
from apps.messaging.models import Notification
from apps.messaging.services.notify import notify

ACTIVE_ENTRY_STATUSES = (WaitlistEntry.Status.WAITING, WaitlistEntry.Status.OFFERED)


def offer_next_seat(session):
    """Вызывать после отмены/отклонения брони занятия. Возвращает запись листа ожидания или None."""
    with transaction.atomic():
        entry = (WaitlistEntry.objects.select_for_update(skip_locked=True)
                 .filter(session=session, status=WaitlistEntry.Status.WAITING).order_by("created_at").first())
        if entry is None:
            return None
        entry.status = WaitlistEntry.Status.OFFERED
        entry.save(update_fields=["status", "updated_at"])
        notify(entry.account, Notification.Kind.BOOKING_STATUS, "Освободилось место на занятии",
               body=f"«{session.title}» — успейте записаться.", link=f"/sessions/{session.pk}",
               event_id=f"waitlist_offer:{entry.pk}")
        return entry


def position_of(entry):
    if entry.status != WaitlistEntry.Status.WAITING:
        return None
    return WaitlistEntry.objects.filter(session_id=entry.session_id, status=WaitlistEntry.Status.WAITING,
                                        created_at__lte=entry.created_at).count()


def current_entry(session, account):
    if not account or not account.is_authenticated:
        return None
    return (WaitlistEntry.objects.filter(session=session, account=account, status__in=ACTIVE_ENTRY_STATUSES)
            .order_by("-created_at").first())


@transaction.atomic
def join(session, account):
    from apps.learning.services.access import can_view_session_internals
    from apps.learning.services.common import free_seats

    session = LessonSession.objects.select_for_update(of=("self",)).select_related("organization", "offer__instructor").get(pk=session.pk)
    if session.status != LessonSession.Status.SCHEDULED or session.starts_at <= timezone.now():
        raise Conflict("Запись на это занятие закрыта.", code="session_closed")
    if can_view_session_internals(account, session):
        raise Conflict("Нельзя встать в лист ожидания на собственное занятие.", code="own_session")
    if Booking.objects.filter(lesson_session=session, customer=account,
                              status__in=[Booking.Status.REQUESTED, Booking.Status.CONFIRMED]).exists():
        raise Conflict("Вы уже записаны на это занятие.", code="already_booked")
    existing = current_entry(session, account)
    if existing is not None:
        return existing, False
    if free_seats(session) > 0:
        raise Conflict("Свободные места есть — запишитесь на занятие.", code="seats_available")
    try:
        with transaction.atomic():
            return WaitlistEntry.objects.create(session=session, account=account), True
    except IntegrityError:
        return current_entry(session, account), False


@transaction.atomic
def leave(session, account):
    entry = current_entry(session, account)
    if entry is None:
        raise NotFound("Вы не стоите в листе ожидания этого занятия.", code="waitlist_entry_not_found")
    was_offered = entry.status == WaitlistEntry.Status.OFFERED
    entry.status = WaitlistEntry.Status.CANCELLED
    entry.save(update_fields=["status", "updated_at"])
    if was_offered and session.status == LessonSession.Status.SCHEDULED and session.starts_at > timezone.now():
        offer_next_seat(session)  # предложенное место переходит следующему в очереди
    return entry
