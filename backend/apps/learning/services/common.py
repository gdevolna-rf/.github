"""Общие правила learning: места на занятии, часовые пояса, перевод конфликта инструктора в 409 (F11, ATX-15)."""
from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F, IntegerField, OuterRef, Subquery, Sum, Value
from django.db.models.functions import Coalesce, Greatest
from django.utils import timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from apps.commerce.models import Booking
from apps.common.exceptions import Conflict
from apps.learning.models import LessonSession

S = Booking.Status
# Места, которые занимает бронь (подтверждённые и уже состоявшиеся) — 6.2, ATX-14.
SEAT_STATUSES = (S.CONFIRMED, S.IN_PROGRESS, S.COMPLETED, S.NO_SHOW)
# Брони, которые ещё «живые» и переносятся/отменяются вместе с занятием.
OPEN_BOOKING_STATUSES = (S.REQUESTED, S.CONFIRMED)
LIVE_SESSION_STATUSES = (LessonSession.Status.SCHEDULED, LessonSession.Status.IN_PROGRESS)

OVERLAP_CONSTRAINT = "no_instructor_overlap"

MONTHS_GENITIVE = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября",
                   "октября", "ноября", "декабря"]


def seats_taken_subquery():
    taken = (Booking.objects.filter(lesson_session=OuterRef("pk"), status__in=SEAT_STATUSES)
             .order_by().values("lesson_session").annotate(total=Sum("seats")).values("total")[:1])
    return Coalesce(Subquery(taken, output_field=IntegerField()), Value(0))


def with_seats(queryset):
    """Аннотирует seats_taken и free_seats_db (не меньше нуля)."""
    return queryset.annotate(seats_taken=seats_taken_subquery()).annotate(
        free_seats_db=Greatest(F("capacity") - F("seats_taken"), Value(0))
    )


def seats_taken(session):
    value = getattr(session, "seats_taken", None)
    if value is None:
        value = (Booking.objects.filter(lesson_session=session, status__in=SEAT_STATUSES)
                 .aggregate(total=Sum("seats"))["total"] or 0)
    return value


def free_seats(session):
    return max(session.capacity - seats_taken(session), 0)


def tz_name_for(session):
    spot = getattr(session, "spot", None) if session.spot_id else None
    if spot is not None and spot.region_id:
        return spot.region.timezone
    org = session.organization if session.organization_id else None
    if org is not None and org.region_id:
        return org.region.timezone
    return settings.TIME_ZONE


def zone(name):
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo(settings.TIME_ZONE)


def human_range(starts_at, ends_at, tz_name):
    tz = zone(tz_name)
    start, end = starts_at.astimezone(tz), ends_at.astimezone(tz)
    day = f"{start.day} {MONTHS_GENITIVE[start.month - 1]} {start.year}"
    if start.date() == end.date():
        return f"{day}, {start:%H:%M}–{end:%H:%M} ({tz_name})"
    end_day = f"{end.day} {MONTHS_GENITIVE[end.month - 1]} {end.year}"
    return f"{day} {start:%H:%M} — {end_day} {end:%H:%M} ({tz_name})"


def human_start(session):
    tz = zone(tz_name_for(session))
    start = session.starts_at.astimezone(tz)
    return f"{start.day} {MONTHS_GENITIVE[start.month - 1]} {start.year}, {start:%H:%M}"


def find_instructor_conflict(session):
    """Пересекающееся занятие того же инструктора (условия совпадают с exclusion-ограничением)."""
    if not session.instructor_id or session.allow_overlap or session.status not in LIVE_SESSION_STATUSES:
        return None
    qs = LessonSession.objects.filter(
        instructor_id=session.instructor_id, status__in=LIVE_SESSION_STATUSES, allow_overlap=False,
        starts_at__lt=session.ends_at, ends_at__gt=session.starts_at,
    )
    if session.pk and not session._state.adding:
        qs = qs.exclude(pk=session.pk)
    return qs.select_related("spot__region", "organization__region").order_by("starts_at").first()


def raise_instructor_busy(conflict, field="starts_at"):
    when = human_range(conflict.starts_at, conflict.ends_at, tz_name_for(conflict)) if conflict else None
    message = (f"Инструктор уже занят в это время: {when}. Выберите другое время или другого инструктора."
               if when else "Инструктор уже занят в это время. Выберите другое время или другого инструктора.")
    raise Conflict(message, code="instructor_busy", fields={field: [message]})


def _constraint_name(exc):
    cause = exc.__cause__
    diag = getattr(cause, "diag", None)
    return getattr(diag, "constraint_name", None) or ""


def save_session(session, *, update_fields=None, conflict_field="starts_at"):
    """Сохраняет занятие; пересечение у инструктора (во всех школах и частных уроках) → 409 instructor_busy.

    Предварительная проверка даёт понятное сообщение, exclusion-ограничение PostgreSQL закрывает гонку.
    """
    conflict = find_instructor_conflict(session)
    if conflict is not None:
        raise_instructor_busy(conflict, conflict_field)
    try:
        with transaction.atomic():
            session.save(update_fields=update_fields)
    except IntegrityError as exc:
        if OVERLAP_CONSTRAINT in _constraint_name(exc) or OVERLAP_CONSTRAINT in str(exc):
            raise_instructor_busy(find_instructor_conflict(session), conflict_field)
        raise
    return session


def now():
    return timezone.now()


def suspended_exists(account_ref="account_id"):
    """Exists() для аккаунтов с действующим ограничением профиля (F14): такие карточки не публичны."""
    from apps.trust.services.restrictions import suspended_exists as _suspended

    return _suspended(account_ref)
