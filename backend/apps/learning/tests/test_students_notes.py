"""Ученики, посещаемость и заметки преподавателя с проверкой доступа (SCH-10, INS-06, AT-09)."""
import pytest

from apps.commerce.models import Booking
from apps.learning.models import StudentNote
from apps.organizations.models import Membership

from .helpers import (
    AccountFactory,
    booking,
    instructor_account,
    past_start,
    private_session,
    published_instructor,
    school,
    school_instructor,
    school_session,
)

pytestmark = pytest.mark.django_db
S = Booking.Status
NOTES = "/api/v1/student-notes"


def held(org=None, instructor=None, hours_ago=5, **kwargs):
    return school_session(org, instructor=instructor, start=past_start(hours_ago), status="completed", **kwargs)


def test_my_students_unique_repeat_and_notes(make_client):
    profile = published_instructor(instructor_account())
    coach = make_client(profile.account)
    org = school()
    school_instructor(org, profile.account)
    loyal, once, absent = AccountFactory(), AccountFactory(), AccountFactory()
    for hours in (10, 30):
        booking(held(org, profile.account, hours_ago=hours), customer=loyal, status=S.COMPLETED)
    private = private_session(profile, start=past_start(50))
    booking(private, customer=loyal, status=S.COMPLETED)
    booking(held(org, profile.account, hours_ago=70), customer=once, status=S.COMPLETED)
    booking(held(org, profile.account, hours_ago=90), customer=absent, status=S.NO_SHOW)
    booking(held(org, hours_ago=110), customer=AccountFactory(), status=S.COMPLETED)  # чужой урок
    StudentNote.objects.create(student=loyal, author=profile.account, comment="Уверенно встаёт")
    data = coach.get("/api/v1/me/students").json()
    rows = {r["student"]["id"]: r for r in data["results"]}
    assert set(rows) == {str(loyal.pk), str(once.pk)}  # только с завершёнными занятиями
    assert rows[str(loyal.pk)]["completed_count"] == 3 and rows[str(loyal.pk)]["is_repeat"] is True
    assert rows[str(loyal.pk)]["notes"][0]["comment"] == "Уверенно встаёт"
    assert rows[str(once.pk)]["is_repeat"] is False
    assert data["summary"] == {"unique_students": 2, "repeat_students": 1, "repeat_students_pct": 50.0,
                               "students_with_bookings": 3}
    assert coach.get("/api/v1/me/students", {"repeat": "true"}).json()["count"] == 1
    assert "email" not in str(rows)


def test_school_students_for_owner_and_instructor(make_client):
    org = school()
    coach_a, coach_b = school_instructor(org), school_instructor(org)
    student_a, student_b = AccountFactory(), AccountFactory()
    booking(held(org, coach_a), customer=student_a, status=S.COMPLETED)
    booking(held(org, coach_a, hours_ago=30), customer=student_a, status=S.NO_SHOW)
    booking(held(org, coach_b), customer=student_b, status=S.COMPLETED)
    booking(school_session(org, instructor=coach_b), customer=student_b)  # предстоящая запись
    url = f"/api/v1/organizations/{org.pk}/students"
    data = make_client(org.owner).get(url).json()
    rows = {r["student"]["id"]: r for r in data["results"]}
    assert set(rows) == {str(student_a.pk), str(student_b.pk)}
    assert rows[str(student_a.pk)]["attendance_pct"] == 50.0 and rows[str(student_a.pk)]["no_show_count"] == 1
    assert rows[str(student_b.pk)]["next_session_at"] is not None
    assert rows[str(student_b.pk)]["last_session"]["title"]
    own = make_client(coach_a).get(url).json()
    assert [r["student"]["id"] for r in own["results"]] == [str(student_a.pk)]
    assert make_client(AccountFactory()).get(url).status_code == 403


def test_instructor_writes_note_about_own_student(make_client):
    org = school()
    coach = school_instructor(org)
    student = AccountFactory()
    session = held(org, coach)
    booking(session, customer=student, status=S.COMPLETED)
    client = make_client(coach)
    response = client.post(NOTES, {"student_id": str(student.pk), "session_id": str(session.pk), "level": "beginner",
                                   "comment": "Хорошая гребля", "visible_to_student": True}, format="json")
    assert response.status_code == 201, response.content
    note = response.json()
    assert note["organization"]["id"] == str(org.pk) and note["can_edit"] is True
    # ученик видит видимую ему заметку, но не может её править
    student_client = make_client(student)
    assert [n["id"] for n in student_client.get(NOTES).json()["results"]] == [note["id"]]
    assert student_client.get(f"{NOTES}/{note['id']}").json()["can_edit"] is False
    assert student_client.patch(f"{NOTES}/{note['id']}", {"comment": "x"}, format="json").status_code == 403
    # менеджмент школы видит заметки школы
    assert make_client(org.owner).get(NOTES, {"organization": str(org.pk)}).json()["count"] == 1
    # другой инструктор той же школы — нет
    assert make_client(school_instructor(org)).get(f"{NOTES}/{note['id']}").status_code == 404
    assert client.patch(f"{NOTES}/{note['id']}", {"comment": "Отличная гребля"}, format="json").json()["comment"] \
        == "Отличная гребля"


def test_hidden_note_is_not_visible_to_student(make_client):
    profile = published_instructor()
    student = AccountFactory()
    session = private_session(profile, start=past_start())
    booking(session, customer=student, status=S.COMPLETED)
    response = make_client(profile.account).post(NOTES, {"student_id": str(student.pk), "comment": "Боится волны",
                                                         "visible_to_student": False}, format="json")
    assert response.status_code == 201 and response.json()["organization"] is None
    assert make_client(student).get(NOTES).json()["count"] == 0


def test_note_creation_access_checks(make_client):
    org = school()
    coach = school_instructor(org)
    student, stranger = AccountFactory(), AccountFactory()
    booking(held(org, school_instructor(org)), customer=student, status=S.COMPLETED)  # урок другого инструктора
    client = make_client(coach)
    response = client.post(NOTES, {"student_id": str(stranger.pk), "organization_id": str(org.pk), "comment": "x"},
                           format="json")
    assert response.status_code == 400 and response.json()["error"]["code"] == "not_a_student"
    response = client.post(NOTES, {"student_id": str(student.pk), "organization_id": str(org.pk), "comment": "x"},
                           format="json")
    assert response.json()["error"]["code"] == "not_a_student"  # инструктор пишет только о своих учениках
    manager = make_client(school_instructor(org, role=Membership.Role.MANAGER))
    assert manager.post(NOTES, {"student_id": str(student.pk), "organization_id": str(org.pk), "comment": "ok"},
                        format="json").status_code == 201
    staff = make_client(school_instructor(org, role=Membership.Role.STAFF))
    assert staff.post(NOTES, {"student_id": str(student.pk), "organization_id": str(org.pk), "comment": "x"},
                      format="json").status_code == 403
    outsider = make_client(AccountFactory())
    assert outsider.post(NOTES, {"student_id": str(student.pk), "organization_id": str(org.pk), "comment": "x"},
                         format="json").status_code == 403
    assert client.post(NOTES, {"student_id": str(coach.pk), "comment": "я"}, format="json").status_code == 400


def test_revoked_author_loses_school_notes_and_manager_can_delete(make_client):
    org = school()
    coach = school_instructor(org)
    student = AccountFactory()
    booking(held(org, coach), customer=student, status=S.COMPLETED)
    note = make_client(coach).post(NOTES, {"student_id": str(student.pk), "organization_id": str(org.pk),
                                           "comment": "Прогресс"}, format="json").json()
    Membership.objects.filter(account=coach, organization=org).update(status=Membership.Status.REVOKED)
    revoked = make_client(coach)
    assert revoked.get(f"{NOTES}/{note['id']}").status_code == 404
    assert revoked.patch(f"{NOTES}/{note['id']}", {"comment": "x"}, format="json").status_code == 404
    assert make_client(org.owner).delete(f"{NOTES}/{note['id']}").status_code == 204
    assert not StudentNote.objects.filter(pk=note["id"]).exists()
