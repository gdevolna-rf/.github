"""Школа: программы (SCH-04), занятия (SCH-05/06), назначение и конфликты инструктора (AT-06, F11, ATX-15),
отзыв доступа (AT-09, F15, ATX-18)."""
import datetime as dt
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.learning.models import LessonSession, SchoolProgram
from apps.messaging.models import Notification
from apps.organizations.models import Membership, Organization
from apps.trust.models import AuditEvent

from .helpers import (
    AccountFactory,
    OrganizationFactory,
    SchoolProgramFactory,
    SpotFactory,
    booking,
    future,
    instructor_account,
    private_session,
    published_instructor,
    school,
    school_instructor,
    school_session,
)

pytestmark = pytest.mark.django_db


def iso(value):
    return value.isoformat()


@pytest.fixture
def org():
    return school()


@pytest.fixture
def owner(make_client, org):
    return make_client(org.owner)


def programs_url(org):
    return f"/api/v1/organizations/{org.pk}/programs"


def sessions_url(org):
    return f"/api/v1/organizations/{org.pk}/sessions"


# --- программы -------------------------------------------------------------------------------------------------

def test_owner_and_manager_manage_programs(owner, org, make_client):
    payload = {"title": "Курс для новичков", "level": "beginner", "age_category": "adults", "format": "group",
               "duration_min": 90, "sessions_count": 5, "price": "12000", "max_group_size": 8}
    created = owner.post(programs_url(org), payload, format="json")
    assert created.status_code == 201, created.content
    program_id = created.json()["id"]
    manager = make_client(school_instructor(org, role=Membership.Role.MANAGER))
    assert manager.patch(f"{programs_url(org)}/{program_id}", {"price": "13000"}, format="json").json()["price"] \
        == "13000.00"
    assert owner.get(programs_url(org)).json()["count"] == 1
    assert AuditEvent.objects.filter(action="school_program.created", organization=org).exists()


def test_program_access_rules(org, make_client):
    program = SchoolProgramFactory(organization=org)
    instructor = make_client(school_instructor(org))
    assert instructor.get(programs_url(org)).status_code == 200  # инструктор видит программы
    assert instructor.post(programs_url(org), {"title": "x", "price": "1"}, format="json").status_code == 403
    assert instructor.delete(f"{programs_url(org)}/{program.pk}").status_code == 403
    outsider = make_client(AccountFactory())
    assert outsider.get(programs_url(org)).status_code == 403
    draft = OrganizationFactory(status=Organization.Status.DRAFT)
    assert outsider.get(programs_url(draft)).status_code == 404  # существование черновика не раскрывается
    workshop = OrganizationFactory(kind=Organization.Kind.WORKSHOP)
    response = make_client(workshop.owner).get(programs_url(workshop))
    assert response.status_code == 403 and response.json()["error"]["code"] == "not_a_school"


def test_program_validation(owner, org):
    response = owner.post(programs_url(org), {"title": "x", "price": "-1", "max_group_size": 0}, format="json")
    assert response.status_code == 400
    assert {"price", "max_group_size"} <= set(response.json()["error"]["fields"])


def test_program_with_sessions_is_archived_not_deleted(owner, org):
    program = SchoolProgramFactory(organization=org)
    school_session(program=program)
    assert owner.delete(f"{programs_url(org)}/{program.pk}").status_code == 204
    program.refresh_from_db()
    assert program.is_active is False
    empty = SchoolProgramFactory(organization=org)
    assert owner.delete(f"{programs_url(org)}/{empty.pk}").status_code == 204
    assert not SchoolProgram.objects.filter(pk=empty.pk).exists()


# --- занятия ---------------------------------------------------------------------------------------------------

def test_create_session_defaults_from_program_and_notifies_instructor(owner, org):
    program = SchoolProgramFactory(organization=org, title="Утренняя группа", duration_min=90, max_group_size=7,
                                   price=Decimal("3200"))
    coach = school_instructor(org)
    spot = SpotFactory()
    start, _ = future(hours=30)
    response = owner.post(sessions_url(org), {"program_id": str(program.pk), "starts_at": iso(start),
                                              "instructor_id": str(coach.pk), "spot_slug": spot.slug}, format="json")
    assert response.status_code == 201, response.content
    data = response.json()
    assert data["title"] == "Утренняя группа" and data["capacity"] == 7 and data["price"] == "3200.00"
    assert data["free_seats"] == 7 and data["kind"] == "school"
    assert data["timezone"] == spot.region.timezone
    session = LessonSession.objects.get(pk=data["id"])
    assert session.ends_at - session.starts_at == dt.timedelta(minutes=90)
    note = Notification.objects.get(recipient=coach, kind=Notification.Kind.LESSON_ASSIGNED)
    assert note.link == "/account/instructor/schedule"


def test_create_session_validation(owner, org):
    other_program = SchoolProgramFactory()
    start, _ = future()
    past = timezone.now() - dt.timedelta(hours=1)
    assert "program_id" in owner.post(sessions_url(org), {"program_id": str(other_program.pk), "starts_at": iso(start)},
                                      format="json").json()["error"]["fields"]
    assert "title" in owner.post(sessions_url(org), {"starts_at": iso(start)}, format="json").json()["error"]["fields"]
    assert "starts_at" in owner.post(sessions_url(org), {"title": "x", "starts_at": iso(past)},
                                     format="json").json()["error"]["fields"]
    assert "ends_at" in owner.post(sessions_url(org), {"title": "x", "starts_at": iso(start),
                                                       "ends_at": iso(start - dt.timedelta(hours=1))},
                                   format="json").json()["error"]["fields"]
    without_spot = owner.post(sessions_url(org), {"title": "Свободная тема", "starts_at": iso(start)}, format="json")
    assert without_spot.status_code == 201 and without_spot.json()["spot"] is None


def test_instructor_must_be_active_member_of_this_school(owner, org):
    start, _ = future()
    stranger = instructor_account()
    response = owner.post(sessions_url(org), {"title": "x", "starts_at": iso(start), "instructor_id": str(stranger.pk)},
                          format="json")
    assert response.json()["error"]["code"] == "instructor_not_member"
    revoked = school_instructor(org)
    Membership.objects.filter(account=revoked, organization=org).update(status=Membership.Status.REVOKED)
    response = owner.post(sessions_url(org), {"title": "x", "starts_at": iso(start), "instructor_id": str(revoked.pk)},
                          format="json")
    assert response.json()["error"]["code"] == "instructor_not_member"


def test_assigned_lesson_appears_in_schedule_and_conflict_is_blocked(org, owner, make_client):
    """AT-06: назначение → в расписании инструктора; второй конфликтующий урок (другая школа) — 409."""
    coach = school_instructor(org)
    session = school_session(org)
    response = owner.post(f"/api/v1/sessions/{session.pk}/assign", {"instructor_id": str(coach.pk)}, format="json")
    assert response.status_code == 200 and response.json()["instructor"]["id"] == str(coach.pk)
    schedule = make_client(coach).get("/api/v1/me/schedule").json()["results"]
    assert [item["id"] for item in schedule] == [str(session.pk)]

    other_school = school()
    school_instructor(other_school, coach)
    clash = school_session(other_school, start=session.starts_at + dt.timedelta(minutes=30))
    response = make_client(other_school.owner).post(f"/api/v1/sessions/{clash.pk}/assign",
                                                    {"instructor_id": str(coach.pk)}, format="json")
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "instructor_busy"
    local = timezone.localtime(session.starts_at)
    assert f"{local:%H:%M}" in error["message"]
    assert "instructor_id" in error["fields"]
    clash.refresh_from_db()
    assert clash.instructor_id is None


def test_create_with_busy_instructor_is_409(owner, org):
    coach = school_instructor(org)
    first = school_session(org, instructor=coach)
    response = owner.post(sessions_url(org), {"title": "Второе", "starts_at": iso(first.starts_at),
                                              "instructor_id": str(coach.pk)}, format="json")
    assert response.status_code == 409 and response.json()["error"]["code"] == "instructor_busy"
    adjacent = owner.post(sessions_url(org), {"title": "Следом", "starts_at": iso(first.ends_at),
                                              "instructor_id": str(coach.pk)}, format="json")
    assert adjacent.status_code == 201  # стык интервалов не пересечение


def test_private_lesson_blocks_school_assignment(owner, org):
    """F11: частный урок и назначение школы на одно время — конфликт."""
    profile = published_instructor()
    school_instructor(org, profile.account)
    private = private_session(profile)
    session = school_session(org, start=private.starts_at)
    response = owner.post(f"/api/v1/sessions/{session.pk}/assign", {"instructor_id": str(profile.account.pk)},
                          format="json")
    assert response.status_code == 409 and response.json()["error"]["code"] == "instructor_busy"


def test_instructor_allowing_overlap_can_be_double_booked(owner, org):
    profile = published_instructor(allow_overlap=True)
    school_instructor(org, profile.account)
    private = private_session(profile, allow_overlap=True)
    session = school_session(org, start=private.starts_at)
    response = owner.post(f"/api/v1/sessions/{session.pk}/assign", {"instructor_id": str(profile.account.pk)},
                          format="json")
    assert response.status_code == 200
    assert LessonSession.objects.get(pk=session.pk).allow_overlap is True


def test_reassign_notifies_both_instructors_and_unassign(owner, org):
    first, second = school_instructor(org), school_instructor(org)
    session = school_session(org, instructor=first)
    owner.post(f"/api/v1/sessions/{session.pk}/assign", {"instructor_id": str(second.pk)}, format="json")
    assert Notification.objects.filter(recipient=second, kind="lesson_assigned").exists()
    assert Notification.objects.filter(recipient=first, title__icontains="другому").exists()
    response = owner.post(f"/api/v1/sessions/{session.pk}/assign", {"instructor_id": None}, format="json")
    assert response.json()["instructor"] is None


def test_revoked_manager_loses_management_immediately(org, make_client):
    """AT-09 / F15: отзыв членства закрывает управление, занятия и история остаются."""
    manager_account = school_instructor(org, role=Membership.Role.MANAGER)
    manager = make_client(manager_account)
    session = school_session(org)
    assert manager.get(sessions_url(org)).status_code == 200
    Membership.objects.filter(account=manager_account, organization=org).update(
        status=Membership.Status.REVOKED, revoked_at=timezone.now())
    start, _ = future(hours=50)
    assert manager.get(sessions_url(org)).status_code == 403
    assert manager.post(sessions_url(org), {"title": "x", "starts_at": iso(start)}, format="json").status_code == 403
    assert manager.patch(f"{sessions_url(org)}/{session.pk}", {"title": "y"}, format="json").status_code == 403
    for action, body in (("assign", {"instructor_id": None}), ("cancel", {"reason": "погода"}),
                         ("reschedule", {"starts_at": iso(start)})):
        assert manager.post(f"/api/v1/sessions/{session.pk}/{action}", body, format="json").status_code == 403
    assert manager.get(f"/api/v1/organizations/{org.pk}/students").status_code == 403
    assert LessonSession.objects.filter(pk=session.pk, status="scheduled").exists()


def test_instructor_member_cannot_manage_sessions(org, make_client):
    coach = make_client(school_instructor(org))
    session = school_session(org)
    assert coach.get(sessions_url(org)).status_code == 200
    assert coach.post(f"/api/v1/sessions/{session.pk}/cancel", {"reason": "хочу"}, format="json").status_code == 403
    start, _ = future()
    assert coach.post(sessions_url(org), {"title": "x", "starts_at": iso(start)}, format="json").status_code == 403


def test_patch_session_fields_capacity_and_program(owner, org):
    session = school_session(org, capacity=3)
    booking(session)
    booking(session)
    url = f"{sessions_url(org)}/{session.pk}"
    response = owner.patch(url, {"capacity": 1}, format="json")
    assert response.status_code == 409 and response.json()["error"]["code"] == "capacity_below_booked"
    program = SchoolProgramFactory(organization=org)
    data = owner.patch(url, {"capacity": 4, "title": "Новое имя", "notes": "Взять воду", "program_id": str(program.pk)},
                       format="json").json()
    assert data["capacity"] == 4 and data["title"] == "Новое имя" and data["program"]["id"] == str(program.pk)
    assert data["bookings_summary"]["confirmed"] == 2 and data["free_seats"] == 2
    foreign_program = SchoolProgramFactory()
    assert owner.patch(url, {"program_id": str(foreign_program.pk)}, format="json").status_code == 400


def test_patch_times_reschedules(owner, org):
    session = school_session(org)
    reserved = booking(session)
    new_start = session.starts_at + dt.timedelta(days=1)
    data = owner.patch(f"{sessions_url(org)}/{session.pk}", {"starts_at": iso(new_start)}, format="json").json()
    assert data["starts_at"] == iso(timezone.localtime(new_start))
    reserved.refresh_from_db()
    assert reserved.starts_at == new_start and reserved.ends_at == new_start + dt.timedelta(hours=2)


def test_delete_session_only_without_bookings(owner, org):
    empty = school_session(org)
    assert owner.delete(f"{sessions_url(org)}/{empty.pk}").status_code == 204
    booked = school_session(org, hours=40)
    booking(booked, status="cancelled")
    response = owner.delete(f"{sessions_url(org)}/{booked.pk}")
    assert response.status_code == 409 and response.json()["error"]["code"] == "session_has_bookings"


def test_session_list_filters(owner, org):
    coach = school_instructor(org)
    soon = school_session(org, instructor=coach, hours=5)
    later = school_session(org, hours=24 * 10)
    cancelled = school_session(org, hours=30, status="cancelled")
    other = school_session()
    listing = owner.get(sessions_url(org)).json()
    assert [s["id"] for s in listing["results"]] == [str(soon.pk), str(cancelled.pk), str(later.pk)]
    assert str(other.pk) not in str(listing)
    assert [s["id"] for s in owner.get(sessions_url(org), {"instructor_id": str(coach.pk)}).json()["results"]] \
        == [str(soon.pk)]
    assert owner.get(sessions_url(org), {"status": "cancelled"}).json()["count"] == 1
    day = timezone.localtime(later.starts_at).date().isoformat()
    assert [s["id"] for s in owner.get(sessions_url(org), {"from": day, "to": day}).json()["results"]] \
        == [str(later.pk)]
    assert owner.get(sessions_url(org), {"from": "garbage"}).status_code == 400


def test_cannot_schedule_archived_program(owner, org):
    program = SchoolProgramFactory(organization=org, is_active=False)
    response = owner.post(sessions_url(org), {"program_id": str(program.pk), "starts_at": iso(future()[0])},
                          format="json")
    assert response.status_code == 400 and response.json()["error"]["code"] == "program_inactive"


def test_session_list_query_count_does_not_grow(owner, org, django_assert_max_num_queries):
    for hours in (10, 20, 30, 40, 50):
        booking(school_session(org, instructor=school_instructor(org), hours=hours))
    with django_assert_max_num_queries(15):
        assert owner.get(sessions_url(org)).json()["count"] == 5
