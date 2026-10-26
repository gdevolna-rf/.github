"""Лист ожидания (SCH-08): только для заполненного занятия, очередь, освобождение предложенного места."""
import pytest

from apps.commerce.models import Booking
from apps.learning.models import WaitlistEntry
from apps.learning.services.waitlist import offer_next_seat
from apps.messaging.models import Notification

from .helpers import AccountFactory, booking, past_start, school, school_instructor, school_session

pytestmark = pytest.mark.django_db


def waitlist_url(session):
    return f"/api/v1/sessions/{session.pk}/waitlist"


@pytest.fixture
def full_session():
    session = school_session(school(), capacity=1)
    booking(session)
    return session


def test_join_only_when_session_is_full(make_client):
    session = school_session(school(), capacity=2)
    booking(session)
    response = make_client().post(waitlist_url(session))
    assert response.status_code == 409 and response.json()["error"]["code"] == "seats_available"


def test_join_queue_positions_and_repeat_join(make_client, full_session):
    first, second = make_client(), make_client()
    created = first.post(waitlist_url(full_session))
    assert created.status_code == 201
    assert created.json()["status"] == "waiting" and created.json()["position"] == 1
    assert second.post(waitlist_url(full_session)).json()["position"] == 2
    again = first.post(waitlist_url(full_session))
    assert again.status_code == 200 and again.json()["id"] == created.json()["id"]
    detail = second.get(f"/api/v1/sessions/{full_session.pk}").json()
    assert detail["my_waitlist"]["position"] == 2 and detail["waitlist_count"] == 2
    assert detail["is_full"] is True


def test_join_rejected_for_booked_customer_staff_and_closed_session(make_client, full_session):
    booked = Booking.objects.get(lesson_session=full_session)
    assert make_client(booked.customer).post(waitlist_url(full_session)).json()["error"]["code"] == "already_booked"
    coach = school_instructor(full_session.organization)
    assert make_client(coach).post(waitlist_url(full_session)).json()["error"]["code"] == "own_session"
    held = school_session(school(), capacity=1, start=past_start())
    booking(held)
    assert make_client().post(waitlist_url(held)).json()["error"]["code"] == "session_closed"


def test_guest_cannot_join(api_client, full_session):
    assert api_client.post(waitlist_url(full_session)).status_code == 401


def test_leave_and_offered_seat_passes_to_next(make_client, full_session):
    first_client, second_client = make_client(), make_client()
    first_client.post(waitlist_url(full_session))
    second_client.post(waitlist_url(full_session))
    offered = offer_next_seat(full_session)
    assert offered.account == first_client.account and offered.status == WaitlistEntry.Status.OFFERED
    assert Notification.objects.filter(recipient=first_client.account, link=f"/sessions/{full_session.pk}").exists()
    assert first_client.delete(waitlist_url(full_session)).status_code == 204
    second = WaitlistEntry.objects.get(session=full_session, account=second_client.account)
    assert second.status == WaitlistEntry.Status.OFFERED
    assert first_client.delete(waitlist_url(full_session)).status_code == 404


def test_leave_without_entry_is_404(make_client, full_session):
    response = make_client(AccountFactory()).delete(waitlist_url(full_session))
    assert response.status_code == 404 and response.json()["error"]["code"] == "waitlist_entry_not_found"
