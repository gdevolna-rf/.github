"""Напоминания за 24 часа (CLB-02, §5) и Django Admin клуба."""
import datetime as dt

import pytest
from django.utils import timezone

from apps.club.models import ClubEvent, EventRegistration
from apps.club.tasks import send_event_reminders
from apps.club.tests.factories import ClubEventFactory, EventRegistrationFactory
from apps.messaging.models import Notification
from tests.factories import RegionFactory

pytestmark = pytest.mark.django_db


def at(hours):
    return timezone.now() + dt.timedelta(hours=hours)


def test_reminder_sent_once_per_registration_within_24h():
    region = RegionFactory(timezone="Asia/Kamchatka")
    soon = ClubEventFactory(starts_at=at(20), ends_at=at(23), region=region, location_note="Парковка у пляжа")
    registered = EventRegistrationFactory(event=soon)
    EventRegistrationFactory(event=soon, status=EventRegistration.Status.WAITLIST)
    EventRegistrationFactory(event=soon, status=EventRegistration.Status.CANCELLED)
    later = ClubEventFactory(starts_at=at(30), ends_at=at(32))
    EventRegistrationFactory(event=later)
    assert send_event_reminders() == 1
    assert send_event_reminders() == 0
    notification = Notification.objects.get()
    assert notification.recipient == registered.account
    assert notification.kind == Notification.Kind.EVENT_REMINDER
    assert notification.link == f"/club/events/{soon.slug}"
    assert "местное время" in notification.body and "Парковка у пляжа" in notification.body
    registered.refresh_from_db()
    assert registered.reminder_sent_at is not None


def test_no_reminders_for_cancelled_or_draft_events():
    for status in (ClubEvent.Status.CANCELLED, ClubEvent.Status.DRAFT):
        EventRegistrationFactory(event=ClubEventFactory(starts_at=at(5), ends_at=at(6), status=status))
    assert send_event_reminders() == 0


def test_past_events_are_marked_completed():
    past = ClubEventFactory(starts_at=at(-5), ends_at=at(-2))
    running = ClubEventFactory(starts_at=at(-1), ends_at=at(2))
    send_event_reminders()
    past.refresh_from_db()
    running.refresh_from_db()
    assert past.status == ClubEvent.Status.COMPLETED
    assert running.status == ClubEvent.Status.PUBLISHED


@pytest.fixture
def superuser_client(make_client):
    from tests.factories import AccountFactory

    account = AccountFactory(is_staff=True, is_superuser=True)
    return make_client(account, two_factor=True)


def test_admin_pages_load(superuser_client):
    event = ClubEventFactory()
    EventRegistrationFactory(event=event)
    for url in ("/admin/club/clubevent/", f"/admin/club/clubevent/{event.pk}/change/", "/admin/club/clubevent/add/",
                "/admin/club/eventregistration/", "/admin/club/clubannouncement/"):
        assert superuser_client.get(url).status_code == 200, url


def test_admin_cancel_action_notifies(superuser_client):
    event = ClubEventFactory()
    registration = EventRegistrationFactory(event=event)
    response = superuser_client.post("/admin/club/clubevent/", {"action": "cancel_events",
                                                                "_selected_action": [str(event.pk)]},
                                     format="multipart")
    assert response.status_code == 302
    event.refresh_from_db()
    assert event.status == ClubEvent.Status.CANCELLED
    assert Notification.objects.filter(recipient=registration.account).exists()


def test_admin_generates_slug_from_title(superuser_client):
    from tests.factories import AccountFactory

    organizer = AccountFactory()
    start = timezone.localtime() + dt.timedelta(days=2)
    end = start + dt.timedelta(hours=2)
    response = superuser_client.post("/admin/club/clubevent/add/", {
        "slug": "", "title": "Сёрф-трип на Сахалин", "kind": "trip", "status": "draft", "description": "",
        "location_note": "", "starts_at_0": start.strftime("%Y-%m-%d"), "starts_at_1": start.strftime("%H:%M:%S"),
        "ends_at_0": end.strftime("%Y-%m-%d"), "ends_at_1": end.strftime("%H:%M:%S"), "registration_open": "on",
        "organizer": str(organizer.pk),
        "registrations-TOTAL_FORMS": "0", "registrations-INITIAL_FORMS": "0",
        "registrations-MIN_NUM_FORMS": "0", "registrations-MAX_NUM_FORMS": "1000",
    }, format="multipart")
    assert response.status_code == 302
    assert ClubEvent.objects.get().slug == "serf-trip-na-sakhalin"
