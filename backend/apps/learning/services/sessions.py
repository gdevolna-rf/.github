"""Занятия школ и частные уроки: создание, назначение, перенос, отмена, проведение (SCH-05/06, INS-06/07, F05, F11)."""
import datetime as dt

from django.db import transaction
from django.utils import timezone

from apps.analytics.services import track
from apps.commerce.models import Booking
from apps.commerce.services.booking_transitions import notify_booking_status, transition
from apps.common.exceptions import Conflict, DomainError
from apps.learning.models import InstructorProfile, LessonSession, WaitlistEntry
from apps.learning.services.access import (
    active_school_member,
    require_complete_session,
    require_manage_session,
)
from apps.learning.services.common import (
    OPEN_BOOKING_STATUSES,
    human_start,
    save_session,
    seats_taken,
)
from apps.messaging.models import Notification
from apps.messaging.services.notify import notify
from apps.trust.services.audit import record
from apps.trust.services.restrictions import require_can_publish

MIN_DURATION = dt.timedelta(minutes=15)
MAX_DURATION = dt.timedelta(hours=24)
SCHEDULE_LINK = "/account/instructor/schedule"
St = LessonSession.Status


def _profile_allows_overlap(account_id):
    if not account_id:
        return False
    return InstructorProfile.objects.filter(account_id=account_id, allow_overlap=True).exists()


def _validate_times(starts_at, ends_at, *, allow_past=False):
    if ends_at <= starts_at:
        raise DomainError("validation_error", "Окончание занятия должно быть позже начала.",
                          fields={"ends_at": ["Окончание раньше начала."]})
    if not MIN_DURATION <= ends_at - starts_at <= MAX_DURATION:
        raise DomainError("validation_error", "Длительность занятия — от 15 минут до 24 часов.",
                          fields={"ends_at": ["Недопустимая длительность."]})
    if not allow_past and starts_at <= timezone.now():
        raise DomainError("validation_error", "Нельзя запланировать занятие в прошлом.",
                          fields={"starts_at": ["Время начала уже прошло."]})


def _snapshot(session):
    return {"starts_at": session.starts_at.isoformat(), "ends_at": session.ends_at.isoformat(),
            "instructor_id": str(session.instructor_id) if session.instructor_id else None,
            "status": session.status, "capacity": session.capacity}


def _lock(session):
    return LessonSession.objects.select_for_update(of=("self",)).select_related(
        "organization__region", "program", "offer__instructor__account", "spot__region", "instructor__profile",
    ).get(pk=session.pk)


def _require_scheduled(session, action):
    if session.status != St.SCHEDULED:
        raise Conflict(f"Нельзя {action}: занятие в статусе «{session.get_status_display()}».",
                       code="invalid_session_status")


def _validate_school_instructor(org, account_id):
    membership = active_school_member(account_id, org)
    if membership is None:
        raise DomainError("instructor_not_member",
                          "Назначить можно только активного участника команды этой школы.",
                          fields={"instructor_id": ["Инструктор не состоит в команде школы или доступ отозван."]})
    return membership.account


# --- создание --------------------------------------------------------------------------------------------------

@transaction.atomic
def create_school_session(org, actor, data, request=None):
    require_can_publish(actor)
    program = data.get("program")
    if program is not None and program.organization_id != org.pk:
        raise DomainError("validation_error", "Программа принадлежит другой школе.",
                          fields={"program_id": ["Программа не найдена в этой школе."]})
    if program is not None and not program.is_active:
        raise DomainError("program_inactive", "Программа в архиве — активируйте её, чтобы добавить занятие.",
                          fields={"program_id": ["Программа не активна."]})
    title = (data.get("title") or (program.title if program else "")).strip()
    if not title:
        raise DomainError("validation_error", "Укажите название занятия или программу.",
                          fields={"title": ["Обязательное поле, если программа не выбрана."]})
    starts_at = data["starts_at"]
    duration = dt.timedelta(minutes=program.duration_min if program else 120)
    ends_at = data.get("ends_at") or starts_at + duration
    _validate_times(starts_at, ends_at)
    instructor = None
    if data.get("instructor_id"):
        instructor = _validate_school_instructor(org, data["instructor_id"])
    session = LessonSession(
        organization=org, program=program, title=title[:200], instructor=instructor, spot=data.get("spot"),
        starts_at=starts_at, ends_at=ends_at,
        capacity=data.get("capacity") or (program.max_group_size if program else 1),
        price=data["price"] if data.get("price") is not None else (program.price if program else None),
        currency=data.get("currency") or (program.currency if program else "RUB"),
        notes=data.get("notes", ""), allow_overlap=_profile_allows_overlap(getattr(instructor, "pk", None)),
        created_by=actor,
    )
    save_session(session, conflict_field="instructor_id" if instructor else "starts_at")
    record(actor, "lesson_session.created", session, after=_snapshot(session), organization=org, request=request)
    if instructor is not None:
        _notify_assigned(session, instructor, actor)
    return session


@transaction.atomic
def create_private_session(profile, actor, data, request=None):
    require_can_publish(actor)
    offer = data["offer"]
    if offer.instructor_id != profile.pk:
        raise DomainError("validation_error", "Предложение не найдено.", fields={"offer_id": ["Не найдено."]})
    if not offer.is_active:
        raise DomainError("offer_inactive", "Предложение в архиве — сначала активируйте его.",
                          fields={"offer_id": ["Предложение не активно."]})
    starts_at = data["starts_at"]
    ends_at = data.get("ends_at") or starts_at + dt.timedelta(minutes=offer.duration_min)
    _validate_times(starts_at, ends_at)
    session = LessonSession(
        offer=offer, instructor=profile.account, title=(data.get("title") or offer.title)[:200],
        spot=data.get("spot") or offer.spot, starts_at=starts_at, ends_at=ends_at, capacity=offer.capacity,
        price=offer.price, currency=offer.currency, notes=data.get("notes", ""),
        allow_overlap=profile.allow_overlap, created_by=actor,
    )
    save_session(session)
    record(actor, "lesson_session.created", session, after=_snapshot(session), request=request)
    return session


# --- изменение -------------------------------------------------------------------------------------------------

SIMPLE_FIELDS = ("title", "spot", "price", "currency", "notes")


@transaction.atomic
def update_session(session, actor, data, request=None):
    session = _lock(session)
    require_manage_session(actor, session)
    _require_scheduled(session, "изменить занятие")
    before = _snapshot(session)
    changed = []
    for field in SIMPLE_FIELDS:
        if field in data and getattr(session, field) != data[field]:
            setattr(session, field, data[field])
            changed.append(field)
    if "program" in data:
        program = data["program"]
        if not session.organization_id or (program is not None and program.organization_id != session.organization_id):
            raise DomainError("validation_error", "Программа принадлежит другой школе.",
                              fields={"program_id": ["Программа не найдена в этой школе."]})
        session.program = program
        changed.append("program")
    if "capacity" in data and data["capacity"] != session.capacity:
        if not session.organization_id:
            raise DomainError("validation_error", "Вместимость частного занятия задаётся в предложении.",
                              fields={"capacity": ["Измените вместимость в предложении."]})
        if data["capacity"] < seats_taken(session):
            raise Conflict("Нельзя уменьшить число мест ниже уже подтверждённых записей.",
                           code="capacity_below_booked", fields={"capacity": ["Меньше подтверждённых мест."]})
        session.capacity = data["capacity"]
        changed.append("capacity")
    if not session.title.strip():
        raise DomainError("validation_error", "Название не может быть пустым.", fields={"title": ["Обязательное поле."]})
    if changed:
        session.save(update_fields=[*changed, "updated_at"])
    if "starts_at" in data or "ends_at" in data:
        starts_at = data.get("starts_at", session.starts_at)
        ends_at = data.get("ends_at") or (starts_at + (session.ends_at - session.starts_at))
        if (starts_at, ends_at) != (session.starts_at, session.ends_at):
            session = reschedule(session, actor, starts_at, ends_at, data.get("reschedule_reason", ""), request=request)
    if "instructor_id" in data and data["instructor_id"] != session.instructor_id:
        session = assign_instructor(session, actor, data["instructor_id"], request=request)
    if changed:
        record(actor, "lesson_session.updated", session, before=before, after=_snapshot(session),
               metadata={"fields": changed}, organization=session.organization, request=request)
    return session


def _notify_assigned(session, instructor, actor):
    notify(instructor, Notification.Kind.LESSON_ASSIGNED, "Вас назначили на занятие",
           body=f"«{session.title}» — {human_start(session)}.", link=SCHEDULE_LINK,
           payload={"session_id": str(session.pk)}, actor=actor)


@transaction.atomic
def assign_instructor(session, actor, instructor_id, request=None):
    session = _lock(session)
    require_manage_session(actor, session)
    if not session.organization_id:
        raise DomainError("private_session", "Частное занятие всегда ведёт сам инструктор.")
    _require_scheduled(session, "назначить инструктора")
    previous = session.instructor
    instructor = _validate_school_instructor(session.organization, instructor_id) if instructor_id else None
    if getattr(previous, "pk", None) == getattr(instructor, "pk", None):
        return session
    before = _snapshot(session)
    session.instructor = instructor
    session.allow_overlap = _profile_allows_overlap(getattr(instructor, "pk", None))
    save_session(session, update_fields=["instructor", "allow_overlap", "updated_at"], conflict_field="instructor_id")
    record(actor, "lesson_session.instructor_assigned", session, before=before, after=_snapshot(session),
           organization=session.organization, request=request)
    if instructor is not None:
        _notify_assigned(session, instructor, actor)
    if previous is not None:
        notify(previous, Notification.Kind.LESSON_ASSIGNED, "Занятие передано другому инструктору",
               body=f"«{session.title}» — {human_start(session)}.", link=SCHEDULE_LINK,
               payload={"session_id": str(session.pk)}, actor=actor)
    return session


@transaction.atomic
def reschedule(session, actor, starts_at, ends_at, reason="", request=None):
    """Перенос (в т.ч. из-за погоды, SCH-05): время занятия и активных броней меняется вместе, записанные уведомлены."""
    session = _lock(session)
    require_manage_session(actor, session)
    _require_scheduled(session, "перенести занятие")
    _validate_times(starts_at, ends_at)
    before = _snapshot(session)
    session.starts_at, session.ends_at = starts_at, ends_at
    session.reschedule_reason = (reason or "")[:300]
    save_session(session, update_fields=["starts_at", "ends_at", "reschedule_reason", "updated_at"])
    bookings = list(Booking.objects.select_for_update().filter(lesson_session=session,
                                                               status__in=OPEN_BOOKING_STATUSES)
                    .select_related("customer"))
    for booking in bookings:
        booking.starts_at, booking.ends_at = starts_at, ends_at
        booking.save(update_fields=["starts_at", "ends_at", "updated_at"])
    record(actor, "lesson_session.rescheduled", session, before=before, after=_snapshot(session),
           metadata={"reason": session.reschedule_reason, "bookings": len(bookings)},
           organization=session.organization, request=request)
    when = human_start(session)
    body = f"«{session.title}» перенесено на {when}." + (f" Причина: {session.reschedule_reason}." if reason else "")
    stamp = int(starts_at.timestamp())
    for booking in bookings:
        notify_booking_status(booking, actor, to_provider=False, title="Занятие перенесено", body=body,
                              payload={"session_id": str(session.pk)},
                              event_id=f"session_rescheduled:{session.pk}:{stamp}:{booking.pk}")
    if session.instructor_id:
        notify(session.instructor, Notification.Kind.LESSON_ASSIGNED, "Занятие перенесено", body=body,
               link=SCHEDULE_LINK, payload={"session_id": str(session.pk)},
               event_id=f"session_rescheduled:{session.pk}:{stamp}:instructor", actor=actor)
    return session


@transaction.atomic
def cancel_session(session, actor, reason, request=None):
    """Отмена занятия: активные брони → cancelled (сторона provider), лист ожидания закрыт, все уведомлены (F13)."""
    session = _lock(session)
    require_manage_session(actor, session)
    _require_scheduled(session, "отменить занятие")
    reason = (reason or "").strip()[:300]
    bookings = list(Booking.objects.select_for_update().filter(lesson_session=session,
                                                               status__in=OPEN_BOOKING_STATUSES)
                    .select_related("customer", "lesson_session"))
    for booking in bookings:
        transition(booking, Booking.Status.CANCELLED, actor, comment=reason or "Занятие отменено",
                   cancel_reason=reason or "Занятие отменено организатором", cancelled_side=Booking.Side.PROVIDER)
    before = _snapshot(session)
    session.status = St.CANCELLED
    session.cancel_reason = reason
    session.cancelled_at = timezone.now()
    session.save(update_fields=["status", "cancel_reason", "cancelled_at", "updated_at"])
    WaitlistEntry.objects.filter(session=session, status__in=[WaitlistEntry.Status.WAITING,
                                                              WaitlistEntry.Status.OFFERED]).update(
        status=WaitlistEntry.Status.CANCELLED, updated_at=timezone.now())
    record(actor, "lesson_session.cancelled", session, before=before, after=_snapshot(session),
           metadata={"reason": reason, "bookings": len(bookings)}, organization=session.organization, request=request)
    body = f"«{session.title}» ({human_start(session)}) отменено." + (f" Причина: {reason}." if reason else "")
    for booking in bookings:
        notify_booking_status(booking, actor, to_provider=False, title="Занятие отменено", body=body,
                              payload={"session_id": str(session.pk)},
                              event_id=f"session_cancelled:{session.pk}:{booking.pk}")
    if session.instructor_id:
        notify(session.instructor, Notification.Kind.LESSON_ASSIGNED, "Занятие отменено", body=body,
               link=SCHEDULE_LINK, payload={"session_id": str(session.pk)},
               event_id=f"session_cancelled:{session.pk}:instructor", actor=actor)
    return session


@transaction.atomic
def complete_session(session, actor, no_show_ids=(), request=None):
    """Факт проведения (10: «не по плану, а по подтверждённому факту»): confirmed/in_progress → completed | no_show."""
    session = _lock(session)
    require_complete_session(actor, session)
    if session.status not in (St.SCHEDULED, St.IN_PROGRESS):
        raise Conflict(f"Занятие уже в статусе «{session.get_status_display()}».", code="invalid_session_status")
    if session.starts_at > timezone.now():
        raise Conflict("Отметить проведение можно только после начала занятия.", code="session_not_started")
    bookings = {b.pk: b for b in Booking.objects.select_for_update().filter(
        lesson_session=session, status__in=[Booking.Status.CONFIRMED, Booking.Status.IN_PROGRESS],
    ).select_related("customer", "lesson_session")}
    no_show_ids = {str(pk) for pk in no_show_ids}
    known = {str(pk) for pk in bookings}
    unknown = no_show_ids - known
    if unknown:
        raise DomainError("no_show_invalid", "Неявку можно отметить только для подтверждённых записей этого занятия.",
                          fields={"no_show_booking_ids": [f"Не найдено: {', '.join(sorted(unknown))}"]})
    started = [str(b.pk) for b in bookings.values() if b.status == Booking.Status.IN_PROGRESS and str(b.pk) in no_show_ids]
    if started:
        raise DomainError("no_show_invalid", "Ученик уже начал занятие — неявку отметить нельзя.",
                          fields={"no_show_booking_ids": started})
    completed, no_show = [], []
    for booking in bookings.values():
        if str(booking.pk) in no_show_ids:
            transition(booking, Booking.Status.NO_SHOW, actor, comment="Неявка")
            no_show.append(booking)
            continue
        transition(booking, Booking.Status.COMPLETED, actor, comment="Занятие проведено")
        completed.append(booking)
        track("session_completed", subject_type="booking", subject_id=booking.pk, actor=actor,
              owner_account=session.instructor, owner_organization=session.organization,
              context={"session_id": str(session.pk), "seats": booking.seats,
                       "program_id": str(session.program_id) if session.program_id else None,
                       "offer_id": str(session.offer_id) if session.offer_id else None},
              dedup_key=f"session_completed:{booking.pk}", request=request)
    before = _snapshot(session)
    session.status = St.COMPLETED
    session.completed_at = timezone.now()
    session.save(update_fields=["status", "completed_at", "updated_at"])
    record(actor, "lesson_session.completed", session, before=before, after=_snapshot(session),
           metadata={"completed": len(completed), "no_show": len(no_show)}, organization=session.organization,
           request=request)
    for booking in completed:
        notify_booking_status(booking, actor, to_provider=False, title="Занятие проведено",
                              body=f"«{session.title}» завершено. Поделитесь впечатлениями — оставьте отзыв.",
                              payload={"session_id": str(session.pk)}, event_id=f"session_completed:{booking.pk}")
    for booking in no_show:
        notify_booking_status(booking, actor, to_provider=False, payload={"session_id": str(session.pk)})
    return session, completed, no_show


def release_deleted_instructor(account, now=None):
    """AT-10: удалённый инструктор. Его будущие частные слоты отменяются (брони уже отменены commerce), с будущих
    занятий школ он снимается — менеджеры школы получают уведомление и могут назначить другого. Лист ожидания
    аккаунта закрывается. Вызывать внутри транзакции анонимизации после commerce.cancel_for_deleted_account."""
    from apps.organizations.services.access import staff_accounts

    now = now or timezone.now()
    private = LessonSession.objects.select_for_update().filter(
        offer__instructor__account=account, organization__isnull=True, status=St.SCHEDULED, starts_at__gt=now)
    for session in private:
        session.status, session.cancelled_at = St.CANCELLED, now
        session.cancel_reason = "Аккаунт инструктора удалён"
        session.save(update_fields=["status", "cancelled_at", "cancel_reason", "updated_at"])
    assigned = list(LessonSession.objects.select_for_update().select_related("organization").filter(
        instructor=account, organization__isnull=False, status=St.SCHEDULED, starts_at__gt=now))
    for session in assigned:
        session.instructor, session.allow_overlap = None, False
        session.save(update_fields=["instructor", "allow_overlap", "updated_at"])
        record(None, "lesson_session.instructor_unassigned", session, organization=session.organization,
               metadata={"reason": "account_deleted", "account": str(account.pk)})
        for manager in staff_accounts(session.organization):
            notify(manager, Notification.Kind.LESSON_ASSIGNED, "Нужен инструктор на занятие",
                   body=f"«{session.title}» — {human_start(session)}: аккаунт инструктора удалён.",
                   link=f"/account/orgs/{session.organization_id}/schedule",
                   payload={"session_id": str(session.pk)}, event_id=f"session_unassigned:{session.pk}:{account.pk}")
    WaitlistEntry.objects.filter(account=account, status__in=[WaitlistEntry.Status.WAITING,
                                                              WaitlistEntry.Status.OFFERED]).update(
        status=WaitlistEntry.Status.CANCELLED, updated_at=now)
    return len(assigned)


@transaction.atomic
def delete_session(session, actor, request=None):
    session = _lock(session)
    require_manage_session(actor, session)
    if Booking.objects.filter(lesson_session=session).exists():
        raise Conflict("У занятия есть записи — отмените его, чтобы сохранить историю.", code="session_has_bookings")
    record(actor, "lesson_session.deleted", session, before=_snapshot(session), organization=session.organization,
           request=request)
    session.delete()
