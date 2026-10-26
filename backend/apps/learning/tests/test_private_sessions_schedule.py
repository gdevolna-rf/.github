"""Частные слоты инструктора (INS-06/08) и единое расписание (INS-07, SCH-06, AT-06)."""
import datetime as dt

import pytest
from django.utils import timezone

from apps.commerce.models import Booking
from apps.learning.models import InstructorProfile, LessonSession

from .helpers import (
    AccountFactory,
    InstructorOfferFactory,
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
SLOTS = "/api/v1/me/instructor/sessions"


@pytest.fixture
def coach(make_client):
    profile = published_instructor(instructor_account())
    client = make_client(profile.account)
    client.profile = profile
    return client


def test_create_slot_from_offer(coach, api_client):
    spot = SpotFactory()
    offer = InstructorOfferFactory(instructor=coach.profile, capacity=2, duration_min=60, spot=spot)
    start, _ = future(hours=20)
    response = coach.post(SLOTS, {"offer_id": str(offer.pk), "starts_at": start.isoformat()}, format="json")
    assert response.status_code == 201, response.content
    data = response.json()
    assert data["capacity"] == 2 and data["price"] == "4000.00" and data["spot"]["slug"] == spot.slug
    assert data["instructor"]["id"] == str(coach.account.pk) and data["kind"] == "private"
    session = LessonSession.objects.get(pk=data["id"])
    assert session.ends_at - session.starts_at == dt.timedelta(minutes=60)
    profile_page = api_client.get(f"/api/v1/instructors/{coach.account.profile.handle}").json()
    assert [s["id"] for s in profile_page["upcoming_slots"]] == [data["id"]]
    assert coach.get(SLOTS).json()["count"] == 1


def test_slot_validation(coach):
    offer = InstructorOfferFactory(instructor=coach.profile)
    past = timezone.now() - dt.timedelta(hours=1)
    assert coach.post(SLOTS, {"offer_id": str(offer.pk), "starts_at": past.isoformat()},
                      format="json").status_code == 400
    archived = InstructorOfferFactory(instructor=coach.profile, is_active=False)
    response = coach.post(SLOTS, {"offer_id": str(archived.pk), "starts_at": future()[0].isoformat()}, format="json")
    assert response.json()["error"]["code"] == "offer_inactive"
    foreign = InstructorOfferFactory(instructor=published_instructor())
    response = coach.post(SLOTS, {"offer_id": str(foreign.pk), "starts_at": future()[0].isoformat()}, format="json")
    assert "offer_id" in response.json()["error"]["fields"]


def test_private_slot_conflicting_with_school_lesson_is_409(coach):
    """F11 / ATX-15: двойная запись инструктора на один час блокируется."""
    org = school()
    school_instructor(org, coach.account)
    lesson = school_session(org, instructor=coach.account)
    offer = InstructorOfferFactory(instructor=coach.profile)
    response = coach.post(SLOTS, {"offer_id": str(offer.pk),
                                  "starts_at": (lesson.starts_at + dt.timedelta(minutes=30)).isoformat()},
                          format="json")
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "instructor_busy" and "Инструктор уже занят" in error["message"]
    assert not LessonSession.objects.filter(offer=offer).exists()


def test_patch_and_delete_slot(coach, make_client):
    session = private_session(coach.profile)
    url = f"{SLOTS}/{session.pk}"
    new_start = session.starts_at + dt.timedelta(hours=3)
    data = coach.patch(url, {"title": "Утренний урок", "starts_at": new_start.isoformat()}, format="json").json()
    assert data["title"] == "Утренний урок" and data["starts_at"] == timezone.localtime(new_start).isoformat()
    other = make_client(instructor_account())
    published_instructor(other.account)
    assert other.get(url).status_code == 404 and other.delete(url).status_code == 404
    booking(session, status=Booking.Status.REQUESTED)
    assert coach.delete(url).status_code == 409
    empty = private_session(coach.profile, hours=72)
    assert coach.delete(f"{SLOTS}/{empty.pk}").status_code == 204


def test_schedule_combines_school_and_private_lessons(coach, make_client):
    """INS-07: одно расписание — уроки всех школ и частные, с участниками и местами."""
    org_a, org_b = school(), school()
    school_instructor(org_a, coach.account)
    school_instructor(org_b, coach.account)
    lesson_a = school_session(org_a, instructor=coach.account, hours=10, capacity=4)
    lesson_b = school_session(org_b, instructor=coach.account, hours=30)
    private = private_session(coach.profile, hours=50)
    alien = school_session(org_a, hours=12)  # без инструктора
    student = AccountFactory(profile__first_name="Маша", profile__last_name="Иванова")
    booking(lesson_a, customer=student, seats=2)
    booking(lesson_a, status=Booking.Status.REQUESTED, participant_name="Петя (8 лет)", participant_is_minor=True)
    booking(lesson_a, status=Booking.Status.CANCELLED)
    data = coach.get("/api/v1/me/schedule").json()
    items = {item["id"]: item for item in data["results"]}
    assert set(items) == {str(lesson_a.pk), str(lesson_b.pk), str(private.pk)}
    assert str(alien.pk) not in items
    first = items[str(lesson_a.pk)]
    assert first["organization"]["id"] == str(org_a.pk) and first["seats_taken"] == 2 and first["capacity"] == 4
    assert [p["name"] for p in first["participants"]] == ["Маша Иванова"]
    assert first["requested_count"] == 1 and first["can_manage"] is False
    assert items[str(private.pk)]["kind"] == "private" and items[str(private.pk)]["can_manage"] is True
    assert set(data["period"]) == {"from", "to", "timezone", "starts_at", "ends_at"}


def test_schedule_period_and_isolation(coach, make_client):
    org = school()
    school_instructor(org, coach.account)
    later = school_session(org, instructor=coach.account, hours=24 * 40)
    day = timezone.localtime(later.starts_at).date().isoformat()
    assert coach.get("/api/v1/me/schedule").json()["results"] == []  # по умолчанию — 30 дней вперёд
    assert [i["id"] for i in coach.get("/api/v1/me/schedule", {"from": day, "to": day}).json()["results"]] \
        == [str(later.pk)]
    stranger = make_client(AccountFactory())
    assert stranger.get("/api/v1/me/schedule", {"from": day, "to": day}).json()["results"] == []
    assert coach.get("/api/v1/me/schedule", {"from": "2026-01-01", "to": "2026-12-31"}).status_code == 400


def test_slots_require_instructor_specialty(make_client):
    account = AccountFactory()
    InstructorProfile.objects.create(account=account)
    assert make_client(account).get(SLOTS).status_code == 403


def test_schedule_query_count_does_not_grow(coach, django_assert_max_num_queries):
    org = school()
    school_instructor(org, coach.account)
    for hours in (5, 15, 25, 35):
        booking(school_session(org, instructor=coach.account, hours=hours))
        private_session(coach.profile, hours=hours + 3)
    with django_assert_max_num_queries(12):
        assert len(coach.get("/api/v1/me/schedule").json()["results"]) == 8
