"""Ученики и посещаемость (SCH-10, INS-06, MET-04/05): строятся из броней, заметки — с проверкой доступа."""
from django.db import transaction
from django.db.models import Count, Max, Min, Q
from django.utils import timezone

from apps.accounts.models import Account
from apps.commerce.models import Booking
from apps.common.exceptions import DomainError, Forbidden, NotFound
from apps.learning.models import StudentNote
from apps.learning.services.access import TEACHING_ROLES
from apps.learning.services.common import SEAT_STATUSES
from apps.organizations.models import Membership
from apps.organizations.services.access import MANAGE_ROLES, active_membership, organization_ids_for
from apps.trust.services.audit import record

S = Booking.Status


def lesson_bookings():
    return Booking.objects.filter(kind=Booking.Kind.LESSON, lesson_session__isnull=False)


def aggregate_students(bookings, *, require_completed=False):
    """Строки по ученикам: число занятий, посещений, неявок, повторность, последнее/следующее занятие."""
    now_q = Q(lesson_session__starts_at__lte=timezone.now())
    rows = (bookings.filter(status__in=SEAT_STATUSES).values("customer_id")
            .annotate(bookings_count=Count("id", distinct=True),
                      completed_count=Count("id", filter=Q(status=S.COMPLETED), distinct=True),
                      no_show_count=Count("id", filter=Q(status=S.NO_SHOW), distinct=True),
                      last_session_at=Max("lesson_session__starts_at", filter=now_q),
                      next_session_at=Min("lesson_session__starts_at",
                                          filter=~now_q & Q(status__in=[S.CONFIRMED, S.IN_PROGRESS])),
                      first_session_at=Min("lesson_session__starts_at")))
    if require_completed:
        rows = rows.filter(completed_count__gte=1)
    return rows.order_by("-last_session_at", "-next_session_at", "customer_id")


def summary(rows):
    total = rows.count()
    with_completed = rows.filter(completed_count__gte=1).count()
    repeat = rows.filter(completed_count__gte=2).count()
    return {
        "unique_students": with_completed,
        "repeat_students": repeat,
        "repeat_students_pct": round(repeat * 100 / with_completed, 1) if with_completed else None,
        "students_with_bookings": total,
    }


def hydrate(rows, *, bookings, note_filter=None):
    """Добавляет к строкам аккаунт (публичный), последнее занятие, заметки."""
    rows = list(rows)
    ids = [r["customer_id"] for r in rows]
    accounts = {a.pk: a for a in Account.objects.filter(pk__in=ids).select_related("profile__avatar")}
    last_sessions = {}
    for b in (bookings.filter(customer_id__in=ids, status__in=SEAT_STATUSES,
                              lesson_session__starts_at__lte=timezone.now())
              .select_related("lesson_session").order_by("customer_id", "-lesson_session__starts_at")):
        last_sessions.setdefault(b.customer_id, b.lesson_session)
    notes = {}
    if note_filter is not None:
        for note in (StudentNote.objects.filter(note_filter, student_id__in=ids)
                     .select_related("author__profile__avatar", "organization").order_by("-created_at")):
            notes.setdefault(note.student_id, []).append(note)
    for row in rows:
        row["student"] = accounts.get(row["customer_id"])
        row["is_repeat"] = row["completed_count"] >= 2
        attended = row["completed_count"] + row["no_show_count"]
        row["attendance_pct"] = round(row["completed_count"] * 100 / attended, 1) if attended else None
        row["last_session"] = last_sessions.get(row["customer_id"])
        row["notes"] = notes.get(row["customer_id"], [])
    return rows


def my_students_bookings(account):
    return lesson_bookings().filter(lesson_session__instructor=account)


def org_students_bookings(org, membership):
    qs = lesson_bookings().filter(lesson_session__organization=org)
    if membership.role == Membership.Role.INSTRUCTOR:
        qs = qs.filter(lesson_session__instructor=membership.account)  # инструктор видит только своих учеников
    return qs


# --- заметки (SCH-10) ------------------------------------------------------------------------------------------

def visible_notes_q(account):
    managed = organization_ids_for(account, roles=MANAGE_ROLES)
    member_of = organization_ids_for(account)
    return (
        (Q(author=account) & (Q(organization__isnull=True) | Q(organization_id__in=member_of)))
        | Q(organization_id__in=managed)
        | Q(student=account, visible_to_student=True)
    )


def visible_notes(account):
    return StudentNote.objects.filter(visible_notes_q(account)).select_related(
        "author__profile__avatar", "student__profile__avatar", "organization", "session")


def _taught(student, *, organization=None, instructor=None, session=None):
    """Ученик действительно записан (подтверждённо) на занятия школы / инструктора / конкретное занятие."""
    qs = lesson_bookings().filter(customer=student, status__in=SEAT_STATUSES)
    if organization is not None:
        qs = qs.filter(lesson_session__organization=organization)
    if instructor is not None:
        qs = qs.filter(lesson_session__instructor=instructor)
    if session is not None:
        qs = qs.filter(lesson_session=session)
    return qs.exists()


@transaction.atomic
def create_note(author, data, request=None):
    student = data["student"]
    if student.pk == author.pk:
        raise DomainError("validation_error", "Нельзя оставить заметку о себе.", fields={"student_id": ["Это вы."]})
    session = data.get("session")
    organization = data.get("organization") or (session.organization if session and session.organization_id else None)
    if session is not None and session.organization_id and organization and session.organization_id != organization.pk:
        raise DomainError("validation_error", "Занятие относится к другой школе.", fields={"session_id": ["Другая школа."]})
    if organization is not None:
        membership = active_membership(author, organization)
        if membership is None or membership.role not in TEACHING_ROLES:
            raise Forbidden("Заметки об учениках школы пишут её инструкторы и менеджеры.")
        teacher = author if membership.role == Membership.Role.INSTRUCTOR else None  # инструктор — только о своих
        taught = _taught(student, organization=organization, instructor=teacher, session=session)
    else:
        if session is not None and session.instructor_id != author.pk:
            raise Forbidden("Заметку к занятию оставляет его инструктор.")
        taught = _taught(student, instructor=author, session=session)
    if not taught:
        raise DomainError("not_a_student", "Этот пользователь не записан на ваши занятия.",
                          fields={"student_id": ["Нет записей на занятия."]})
    note = StudentNote.objects.create(
        student=student, author=author, organization=organization, session=session, level=data.get("level", ""),
        comment=data["comment"], visible_to_student=data.get("visible_to_student", True),
    )
    record(author, "student_note.created", note, organization=organization, request=request)
    return note


def get_note_for(account, note_id):
    note = visible_notes(account).filter(pk=note_id).first()
    if note is None:
        raise NotFound("Заметка не найдена.")
    return note


def _can_edit(account, note):
    if note.author_id != account.pk:
        return False
    return note.organization_id is None or active_membership(account, note.organization) is not None


@transaction.atomic
def update_note(account, note, data, request=None):
    if not _can_edit(account, note):
        raise Forbidden("Изменять заметку может только её автор.")
    for field in ("level", "comment", "visible_to_student"):
        if field in data:
            setattr(note, field, data[field])
    note.save()
    record(account, "student_note.updated", note, organization=note.organization, request=request)
    return note


@transaction.atomic
def delete_note(account, note, request=None):
    from apps.organizations.services.access import can_manage

    if not (_can_edit(account, note) or (note.organization_id and can_manage(account, note.organization))):
        raise Forbidden("Удалить заметку может автор или менеджер школы.")
    record(account, "student_note.deleted", note, organization=note.organization, request=request)
    note.delete()
