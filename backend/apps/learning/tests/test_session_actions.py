"""Карточка занятия и действия: перенос (SCH-05), отмена (F13), проведение по факту (раздел 10, F05)."""
import datetime as dt

import pytest
from django.utils import timezone

from apps.analytics.models import AnalyticsEvent
from apps.commerce.models import Booking, BookingStatusChange
from apps.learning.models import LessonSession, WaitlistEntry
from apps.messaging.models import Notification
from apps.organizations.models import Membership, Organization
from apps.trust.models import AuditEvent

from .helpers import (
    AccountFactory,
    OrganizationFactory,
    SpotFactory,
    booking,
    future,
    past_start,
    private_session,
    published_instructor,
    school,
    school_instructor,
    school_session,
)

pytestmark = pytest.mark.django_db
S = Booking.Status


def url(session, action=""):
    return f"/api/v1/sessions/{session.pk}" + (f"/{action}" if action else "")


@pytest.fixture
def org():
    return school()


@pytest.fixture
def owner(make_client, org):
    return make_client(org.owner)


# --- публичная карточка ----------------------------------------------------------------------------------------

def test_public_session_card(api_client, org):
    spot = SpotFactory()
    coach = school_instructor(org)
    session = school_session(org, instructor=coach, spot=spot, capacity=3)
    booking(session, seats=2)
    booking(session, status=S.REQUESTED)
    data = api_client.get(url(session)).json()
    assert data["free_seats"] == 1 and data["seats_taken"] == 2 and data["is_full"] is False
    assert data["organization"]["slug"] == org.slug and data["program"]["title"]
    assert data["instructor"]["id"] == str(coach.pk) and "email" not in data["instructor"]
    assert data["spot"]["slug"] == spot.slug and data["timezone"] == spot.region.timezone
    assert data["starts_at"][-6] in "+-"  # ISO с часовым поясом
    assert data["my_waitlist"] is None and data["waitlist_count"] == 0
    assert "notes" not in data and "bookings_summary" not in data


def test_session_of_unpublished_school_is_hidden_from_public(api_client, make_client):
    draft = OrganizationFactory(status=Organization.Status.DRAFT)
    session = school_session(draft)
    assert api_client.get(url(session)).status_code == 404
    assert make_client().get(url(session)).status_code == 404
    assert make_client(draft.owner).get(url(session)).status_code == 200


def test_private_session_card_visible_only_for_published_instructor(api_client):
    profile = published_instructor()
    session = private_session(profile)
    data = api_client.get(url(session)).json()
    assert data["kind"] == "private" and data["offer"]["id"] == str(session.offer_id)
    profile.status = "draft"
    profile.save()
    assert api_client.get(url(session)).status_code == 404


# --- перенос ---------------------------------------------------------------------------------------------------

def test_reschedule_moves_session_and_bookings_and_notifies(owner, org):
    coach = school_instructor(org)
    session = school_session(org, instructor=coach)
    confirmed = booking(session)
    requested = booking(session, status=S.REQUESTED)
    cancelled = booking(session, status=S.CANCELLED)
    new_start = session.starts_at + dt.timedelta(days=2)
    response = owner.post(url(session, "reschedule"), {"starts_at": new_start.isoformat(), "reason": "Шторм"},
                          format="json")
    assert response.status_code == 200, response.content
    session.refresh_from_db()
    assert session.starts_at == new_start and session.ends_at == new_start + dt.timedelta(hours=2)
    assert session.reschedule_reason == "Шторм"
    for b in (confirmed, requested):
        b.refresh_from_db()
        assert b.starts_at == new_start
    cancelled.refresh_from_db()
    assert cancelled.starts_at != new_start
    notified = set(Notification.objects.filter(title="Занятие перенесено").values_list("recipient_id", flat=True))
    assert notified == {confirmed.customer_id, requested.customer_id, coach.pk}
    assert "Шторм" in Notification.objects.filter(recipient=confirmed.customer).first().body
    assert AuditEvent.objects.filter(action="lesson_session.rescheduled", object_id=str(session.pk)).exists()


def test_reschedule_into_instructor_conflict_is_409(owner, org):
    coach = school_instructor(org)
    session = school_session(org, instructor=coach)
    other = school_session(org, instructor=coach, hours=72)
    response = owner.post(url(session, "reschedule"), {"starts_at": other.starts_at.isoformat()}, format="json")
    assert response.status_code == 409 and response.json()["error"]["code"] == "instructor_busy"
    session.refresh_from_db()
    assert session.starts_at != other.starts_at


def test_reschedule_rules(owner, org, make_client):
    session = school_session(org)
    past = timezone.now() - dt.timedelta(hours=2)
    assert owner.post(url(session, "reschedule"), {"starts_at": past.isoformat()}, format="json").status_code == 400
    assert make_client().post(url(session, "reschedule"), {"starts_at": future(48)[0].isoformat()},
                              format="json").status_code == 403
    session.status = LessonSession.Status.CANCELLED
    session.save()
    response = owner.post(url(session, "reschedule"), {"starts_at": future(48)[0].isoformat()}, format="json")
    assert response.status_code == 409 and response.json()["error"]["code"] == "invalid_session_status"


def test_private_instructor_reschedules_own_slot(make_client):
    profile = published_instructor()
    session = private_session(profile)
    client = make_client(profile.account)
    new_start = session.starts_at + dt.timedelta(hours=5)
    assert client.post(url(session, "reschedule"), {"starts_at": new_start.isoformat()}, format="json").status_code == 200
    assert make_client(published_instructor().account).post(
        url(session, "reschedule"), {"starts_at": new_start.isoformat()}, format="json").status_code == 403


# --- отмена ----------------------------------------------------------------------------------------------------

def test_cancel_session_cancels_active_bookings_by_provider(owner, org):
    coach = school_instructor(org)
    session = school_session(org, instructor=coach)
    confirmed = booking(session)
    requested = booking(session, status=S.REQUESTED)
    declined = booking(session, status=S.DECLINED)
    waiting = WaitlistEntry.objects.create(session=session, account=AccountFactory())
    response = owner.post(url(session, "cancel"), {"reason": "Сильный ветер"}, format="json")
    assert response.status_code == 200, response.content
    assert response.json()["status"] == "cancelled" and response.json()["cancel_reason"] == "Сильный ветер"
    for b in (confirmed, requested):
        b.refresh_from_db()
        assert b.status == S.CANCELLED and b.cancelled_side == Booking.Side.PROVIDER
        assert b.cancel_reason == "Сильный ветер" and b.cancelled_by == org.owner
        assert BookingStatusChange.objects.filter(booking=b, to_status=S.CANCELLED).exists()
    declined.refresh_from_db()
    assert declined.status == S.DECLINED
    events = AnalyticsEvent.objects.filter(name="booking_cancelled")
    assert events.count() == 2 and all(e.context["side"] == "provider" for e in events)
    waiting.refresh_from_db()
    assert waiting.status == WaitlistEntry.Status.CANCELLED
    recipients = set(Notification.objects.filter(title="Занятие отменено").values_list("recipient_id", flat=True))
    assert recipients == {confirmed.customer_id, requested.customer_id, coach.pk}
    assert owner.post(url(session, "cancel"), {"reason": "ещё раз"}, format="json").status_code == 409


def test_cancel_requires_reason(owner, org):
    session = school_session(org)
    assert "reason" in owner.post(url(session, "cancel"), {}, format="json").json()["error"]["fields"]


# --- проведение ------------------------------------------------------------------------------------------------

def test_assigned_instructor_completes_with_no_show(org, make_client):
    coach = school_instructor(org)
    session = school_session(org, instructor=coach, start=past_start())
    came = booking(session, seats=2)
    absent = booking(session)
    started = booking(session, status=S.IN_PROGRESS)
    pending = booking(session, status=S.REQUESTED)
    response = make_client(coach).post(url(session, "complete"), {"no_show_booking_ids": [str(absent.pk)]},
                                       format="json")
    assert response.status_code == 200, response.content
    data = response.json()
    assert set(data["completed_booking_ids"]) == {str(came.pk), str(started.pk)}
    assert data["no_show_booking_ids"] == [str(absent.pk)]
    assert data["session"]["status"] == "completed"
    for b, status in ((came, S.COMPLETED), (started, S.COMPLETED), (absent, S.NO_SHOW), (pending, S.REQUESTED)):
        b.refresh_from_db()
        assert b.status == status
    events = AnalyticsEvent.objects.filter(name="session_completed")
    assert {e.subject_id for e in events} == {str(came.pk), str(started.pk)}
    event = events.get(subject_id=str(came.pk))
    assert event.subject_type == "booking" and event.owner_account == coach and event.owner_organization == org
    assert event.dedup_key == f"session_completed:{came.pk}" and event.context["seats"] == 2
    assert Notification.objects.filter(recipient=came.customer, title="Занятие проведено").exists()
    session.refresh_from_db()
    assert session.completed_at is not None


def test_complete_rules(org, owner, make_client):
    coach = school_instructor(org)
    upcoming = school_session(org, instructor=coach)
    response = owner.post(url(upcoming, "complete"), {}, format="json")
    assert response.status_code == 409 and response.json()["error"]["code"] == "session_not_started"
    held = school_session(org, instructor=coach, start=past_start(hours_ago=30))
    foreign = booking(school_session(org, start=past_start(hours_ago=60)))
    response = owner.post(url(held, "complete"), {"no_show_booking_ids": [str(foreign.pk)]}, format="json")
    assert response.status_code == 400 and response.json()["error"]["code"] == "no_show_invalid"
    started = booking(held, status=S.IN_PROGRESS)
    response = owner.post(url(held, "complete"), {"no_show_booking_ids": [str(started.pk)]}, format="json")
    assert response.json()["error"]["code"] == "no_show_invalid"
    assert make_client().post(url(held, "complete"), {}, format="json").status_code == 403
    assert owner.post(url(held, "complete"), {}, format="json").status_code == 200
    assert owner.post(url(held, "complete"), {}, format="json").status_code == 409


def test_revoked_instructor_cannot_complete_school_lesson(org, make_client):
    coach = school_instructor(org)
    session = school_session(org, instructor=coach, start=past_start())
    Membership.objects.filter(account=coach, organization=org).update(status=Membership.Status.REVOKED)
    assert make_client(coach).post(url(session, "complete"), {}, format="json").status_code == 403


def test_private_instructor_completes_own_lesson(make_client):
    profile = published_instructor()
    session = private_session(profile, start=past_start())
    student = booking(session)
    response = make_client(profile.account).post(url(session, "complete"), {}, format="json")
    assert response.status_code == 200
    event = AnalyticsEvent.objects.get(name="session_completed", subject_id=str(student.pk))
    assert event.owner_account == profile.account and event.owner_organization is None
