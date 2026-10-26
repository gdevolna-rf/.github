"""Публичная часть клуба и регистрация на события (CLB-01/02)."""
import datetime as dt

import pytest
from django.utils import timezone

from apps.club.content import CLUB_ABOUT
from apps.club.models import ClubEvent, EventRegistration
from apps.club.tests.factories import ClubAnnouncementFactory, ClubEventFactory, EventRegistrationFactory
from apps.community.tests.factories import gg_account
from apps.messaging.models import Notification
from tests.factories import AccountFactory, RegionFactory, SpotFactory

pytestmark = pytest.mark.django_db


def in_days(days, hours=0):
    return timezone.now() + dt.timedelta(days=days, hours=hours)


# ---------------------------------------------------------------- страница клуба


def test_overview_has_about_stats_announcements_and_events(api_client):
    gg_account()
    gg_account()
    AccountFactory()
    upcoming = ClubEventFactory(title="Рассветная сессия")
    ClubEventFactory(status=ClubEvent.Status.DRAFT)
    ClubEventFactory(starts_at=in_days(-3), ends_at=in_days(-3, 2))  # прошло
    pinned = ClubAnnouncementFactory(title="Важное", is_pinned=True, published_at=timezone.now() - dt.timedelta(days=5))
    fresh = ClubAnnouncementFactory(title="Свежее")
    ClubAnnouncementFactory(title="Черновик", published_at=None)
    ClubAnnouncementFactory(title="Отложенное", published_at=timezone.now() + dt.timedelta(days=1))
    body = api_client.get("/api/v1/club").json()
    assert body["about"]["title"] == CLUB_ABOUT["title"] == "Добро пожаловать, дорогой друг."
    assert len(body["about"]["highlights"]) == 6
    assert body["stats"] == {"members": 2, "upcoming_events": 1}
    assert [a["title"] for a in body["announcements"]] == [pinned.title, fresh.title]
    assert [e["slug"] for e in body["upcoming_events"]] == [upcoming.slug]


# ---------------------------------------------------------------- календарь


def test_events_list_shows_only_published_upcoming_by_default(api_client):
    published = ClubEventFactory()
    ClubEventFactory(status=ClubEvent.Status.DRAFT)
    ClubEventFactory(status=ClubEvent.Status.CANCELLED)
    ClubEventFactory(starts_at=in_days(-2), ends_at=in_days(-2, 3))
    slugs = [e["slug"] for e in api_client.get("/api/v1/club/events").json()["results"]]
    assert slugs == [published.slug]


def test_events_calendar_window_and_filters(api_client):
    region = RegionFactory(slug="crimea")
    spot = SpotFactory(region=region, slug="kacha")
    past = ClubEventFactory(starts_at=in_days(-10), ends_at=in_days(-10, 2), status=ClubEvent.Status.COMPLETED,
                            kind=ClubEvent.Kind.CONTEST)
    meetup = ClubEventFactory(starts_at=in_days(5), kind=ClubEvent.Kind.MEETUP, region=region)
    at_spot = ClubEventFactory(starts_at=in_days(6), spot=spot)
    ClubEventFactory(starts_at=in_days(40))

    def slugs(**params):
        response = api_client.get("/api/v1/club/events", params)
        assert response.status_code == 200, response.content
        return {e["slug"] for e in response.json()["results"]}

    window_from = (timezone.localdate() - dt.timedelta(days=12)).isoformat()
    window_to = (timezone.localdate() + dt.timedelta(days=7)).isoformat()
    assert slugs(**{"from": window_from, "to": window_to}) == {past.slug, meetup.slug, at_spot.slug}
    assert slugs(kind="meetup") == {meetup.slug}
    assert slugs(region="crimea") == {meetup.slug, at_spot.slug}
    assert slugs(spot="kacha") == {at_spot.slug}
    assert api_client.get("/api/v1/club/events", {"kind": "rave"}).status_code == 400
    assert api_client.get("/api/v1/club/events", {"from": "21-10-2026"}).status_code == 400


def test_event_detail_counts_and_my_registration(make_client, api_client):
    event = ClubEventFactory(capacity=3, description="Встречаемся у кафе")
    EventRegistrationFactory(event=event)
    EventRegistrationFactory(event=event, status=EventRegistration.Status.CANCELLED)
    client = make_client()
    mine = EventRegistrationFactory(event=event, account=client.account)
    body = client.get(f"/api/v1/club/events/{event.slug}").json()
    assert body["registrations_count"] == 2
    assert body["free_places"] == 1
    assert body["is_full"] is False
    assert body["description"] == "Встречаемся у кафе"
    assert body["my_registration"]["id"] == str(mine.pk)
    assert body["url"] == f"/club/events/{event.slug}"
    assert body["organizer"]["display_name"]
    assert "email" not in str(body["organizer"])
    assert api_client.get(f"/api/v1/club/events/{event.slug}").json()["my_registration"] is None


def test_draft_event_detail_is_hidden_cancelled_is_visible(api_client):
    draft = ClubEventFactory(status=ClubEvent.Status.DRAFT)
    cancelled = ClubEventFactory(status=ClubEvent.Status.CANCELLED)
    assert api_client.get(f"/api/v1/club/events/{draft.slug}").status_code == 404
    body = api_client.get(f"/api/v1/club/events/{cancelled.slug}").json()
    assert body["status"] == "cancelled"
    assert body["registration_open"] is False


def test_unlimited_event_has_no_free_places_limit(api_client):
    event = ClubEventFactory(capacity=None)
    body = api_client.get(f"/api/v1/club/events/{event.slug}").json()
    assert body["free_places"] is None and body["is_full"] is False


# ---------------------------------------------------------------- регистрация


def register(client, event):
    return client.post(f"/api/v1/club/events/{event.pk}/registration")


def test_register_then_waitlist_when_full(make_client):
    event = ClubEventFactory(capacity=1)
    first, second = make_client(), make_client()
    response = register(first, event)
    assert response.status_code == 201
    assert response.json()["status"] == "registered"
    assert response.json()["event"]["free_places"] == 0
    response = register(second, event)
    assert response.status_code == 201
    assert response.json()["status"] == "waitlist"
    assert response.json()["waitlist_position"] == 1


def test_registration_is_idempotent(make_client):
    event = ClubEventFactory(capacity=5)
    client = make_client()
    first = register(client, event)
    second = register(client, event)
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    assert EventRegistration.objects.filter(event=event).count() == 1


def test_guest_cannot_register(api_client):
    event = ClubEventFactory()
    assert register(api_client, event).status_code == 401


@pytest.mark.parametrize("make_event,code,status", [
    (lambda: ClubEventFactory(registration_open=False), "club_registration_closed", 409),
    (lambda: ClubEventFactory(starts_at=in_days(0, -1), ends_at=in_days(0, 2)), "club_event_started", 409),
    (lambda: ClubEventFactory(status=ClubEvent.Status.CANCELLED), "club_event_cancelled", 409),
    (lambda: ClubEventFactory(status=ClubEvent.Status.DRAFT), "club_event_not_found", 404),
])
def test_registration_rules(make_client, make_event, code, status):
    response = register(make_client(), make_event())
    assert response.status_code == status
    assert response.json()["error"]["code"] == code


def test_register_unknown_event_returns_404(make_client):
    client = make_client()
    assert client.post("/api/v1/club/events/not-a-uuid/registration").status_code == 404
    assert client.post("/api/v1/club/events/00000000-0000-0000-0000-000000000000/registration").status_code == 404


def test_cancel_promotes_first_waitlisted_and_notifies(make_client):
    event = ClubEventFactory(capacity=1)
    holder, first_wait, second_wait = make_client(), make_client(), make_client()
    register(holder, event)
    register(first_wait, event)
    register(second_wait, event)
    assert holder.delete(f"/api/v1/club/events/{event.pk}/registration").status_code == 204
    statuses = dict(EventRegistration.objects.filter(event=event).values_list("account_id", "status"))
    assert statuses[holder.account.pk] == "cancelled"
    assert statuses[first_wait.account.pk] == "registered"
    assert statuses[second_wait.account.pk] == "waitlist"
    notification = Notification.objects.get(recipient=first_wait.account)
    assert notification.link == f"/club/events/{event.slug}"
    assert not Notification.objects.filter(recipient=second_wait.account).exists()
    body = second_wait.get(f"/api/v1/club/events/{event.slug}").json()
    assert body["my_registration"]["waitlist_position"] == 1


def test_cancelling_waitlist_entry_does_not_promote(make_client):
    event = ClubEventFactory(capacity=1)
    holder, waiting = make_client(), make_client()
    register(holder, event)
    register(waiting, event)
    assert waiting.delete(f"/api/v1/club/events/{event.pk}/registration").status_code == 204
    assert EventRegistration.objects.get(account=holder.account).status == "registered"
    assert not Notification.objects.exists()


def test_cancel_is_idempotent_and_allows_reregistration(make_client):
    event = ClubEventFactory(capacity=2)
    client = make_client()
    register(client, event)
    url = f"/api/v1/club/events/{event.pk}/registration"
    assert client.delete(url).status_code == 204
    assert client.delete(url).status_code == 204
    assert register(client, event).status_code == 201
    assert EventRegistration.objects.filter(event=event, account=client.account).count() == 2


def test_capacity_is_never_exceeded():
    """Последовательные регистрации под блокировкой события не превышают лимит."""
    from apps.club.services.events import register as register_service

    event = ClubEventFactory(capacity=3)
    results = [register_service(event.pk, AccountFactory())[0].status for _ in range(6)]
    assert results.count("registered") == 3
    assert results.count("waitlist") == 3
