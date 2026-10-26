"""Управление клубом (CLB-03): организатор — свои события и анонсы, админ с 2FA — все; аудит и уведомления."""
import datetime as dt

import pytest
from django.utils import timezone

from apps.club.models import ClubAnnouncement, ClubEvent, EventRegistration
from apps.club.tests.factories import ClubAnnouncementFactory, ClubEventFactory, EventRegistrationFactory, make_organizer
from apps.mediafiles.models import MediaAsset
from apps.messaging.models import Notification
from apps.trust.models import AuditEvent
from tests.factories import MediaAssetFactory, OrganizationFactory, SpotFactory, add_member, make_moderator

pytestmark = pytest.mark.django_db


def iso(days, hours=0):
    return (timezone.now() + dt.timedelta(days=days, hours=hours)).isoformat()


@pytest.fixture
def organizer(make_client):
    return make_client(make_organizer())


@pytest.fixture
def admin(make_client):
    from apps.accounts.models import StaffRole

    client = make_client(two_factor=True)
    make_moderator(client.account, role=StaffRole.Role.ADMIN)
    return client


def create(client, **data):
    payload = {"title": "Рассветная сессия на Каче", "starts_at": iso(5), "ends_at": iso(5, 3), **data}
    return client.post("/api/v1/club/manage/events", payload, format="json")


def test_regular_user_and_guest_cannot_manage(make_client, api_client):
    event = ClubEventFactory()
    # Гость — 401 (нужен вход), вошедший без роли организатора — 403.
    for client, expected in ((make_client(), 403), (api_client, 401)):
        assert client.get("/api/v1/club/manage/events").status_code == expected
        assert create(client).status_code == expected
        assert client.get(f"/api/v1/club/manage/events/{event.pk}/registrations").status_code == expected
        assert client.get("/api/v1/club/manage/announcements").status_code == expected


def test_admin_without_2fa_cannot_manage(make_client):
    from apps.accounts.models import StaffRole

    client = make_client()
    make_moderator(client.account, role=StaffRole.Role.ADMIN)
    assert client.get("/api/v1/club/manage/events").status_code == 403


def test_organizer_creates_event_with_server_slug(organizer):
    spot = SpotFactory()
    cover = MediaAssetFactory(owner=organizer.account, purpose=MediaAsset.Purpose.EVENT_COVER)
    response = create(organizer, spot_id=str(spot.pk), capacity=10, kind="ride", cover_id=str(cover.pk),
                      description="Берите гидрики 4/3")
    assert response.status_code == 201, response.content
    body = response.json()
    assert body["slug"] == "rassvetnaya-sessiya-na-kache"
    assert body["status"] == "draft"
    assert body["region"]["id"] == spot.region_id  # регион берётся из спота
    assert body["cover"]["id"] == str(cover.pk)
    event = ClubEvent.objects.get()
    assert event.organizer == organizer.account
    assert AuditEvent.objects.filter(action="club.event_created", object_id=str(event.pk)).exists()
    # дубль названия → уникальный slug
    assert create(organizer).json()["slug"] == "rassvetnaya-sessiya-na-kache-2"


@pytest.mark.parametrize("data,field", [
    ({"ends_at": iso(4)}, "ends_at"),
    ({"capacity": 0}, "capacity"),
    ({"status": "completed"}, "status"),
    ({"kind": "party"}, "kind"),
])
def test_create_validation(organizer, data, field):
    response = create(organizer, **data)
    assert response.status_code == 400
    assert field in response.json()["error"]["fields"]


def test_create_rejects_foreign_cover_and_org(organizer):
    foreign_cover = MediaAssetFactory(purpose=MediaAsset.Purpose.EVENT_COVER)
    assert create(organizer, cover_id=str(foreign_cover.pk)).status_code == 400
    org = OrganizationFactory()
    response = create(organizer, organizer_organization_id=str(org.pk))
    assert response.status_code == 400
    assert "organizer_organization_id" in response.json()["error"]["fields"]
    add_member(org, organizer.account, role="manager")
    assert create(organizer, organizer_organization_id=str(org.pk)).status_code == 201


def test_cannot_publish_past_event(organizer):
    response = create(organizer, status="published", starts_at=iso(-2), ends_at=iso(-2, 2))
    assert response.status_code == 400


def test_organizer_sees_and_edits_only_own_events(organizer, make_client):
    own = ClubEventFactory(organizer=organizer.account)
    foreign = ClubEventFactory(organizer=make_organizer())
    ids = {e["id"] for e in organizer.get("/api/v1/club/manage/events").json()["results"]}
    assert ids == {str(own.pk)}
    assert organizer.get(f"/api/v1/club/manage/events/{foreign.pk}").status_code == 404
    assert organizer.patch(f"/api/v1/club/manage/events/{foreign.pk}", {"title": "x"}, format="json").status_code == 404
    assert organizer.get(f"/api/v1/club/manage/events/{foreign.pk}/registrations").status_code == 404


def test_admin_manages_all_events(admin):
    event = ClubEventFactory(organizer=make_organizer())
    assert admin.get("/api/v1/club/manage/events").json()["count"] == 1
    response = admin.patch(f"/api/v1/club/manage/events/{event.pk}", {"capacity": 20}, format="json")
    assert response.status_code == 200
    assert response.json()["capacity"] == 20


def test_cancelling_event_notifies_registrants(organizer):
    event = ClubEventFactory(organizer=organizer.account, capacity=1)
    registered = EventRegistrationFactory(event=event)
    waiting = EventRegistrationFactory(event=event, status=EventRegistration.Status.WAITLIST)
    gone = EventRegistrationFactory(event=event, status=EventRegistration.Status.CANCELLED)
    response = organizer.patch(f"/api/v1/club/manage/events/{event.pk}",
                               {"status": "cancelled", "cancel_reason": "Шторм"}, format="json")
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    recipients = set(Notification.objects.values_list("recipient_id", flat=True))
    assert recipients == {registered.account_id, waiting.account_id}
    assert gone.account_id not in recipients
    assert "Шторм" in Notification.objects.first().body
    assert AuditEvent.objects.filter(action="club.event_cancelled").exists()
    # отменённое событие нельзя вернуть или изменить
    response = organizer.patch(f"/api/v1/club/manage/events/{event.pk}", {"status": "published"}, format="json")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "club_event_closed"


def test_unpublish_with_registrations_is_forbidden(organizer):
    event = ClubEventFactory(organizer=organizer.account)
    EventRegistrationFactory(event=event)
    response = organizer.patch(f"/api/v1/club/manage/events/{event.pk}", {"status": "draft"}, format="json")
    assert response.status_code == 409


def test_capacity_rules(organizer):
    event = ClubEventFactory(organizer=organizer.account, capacity=2)
    EventRegistrationFactory(event=event)
    EventRegistrationFactory(event=event)
    waiting = EventRegistrationFactory(event=event, status=EventRegistration.Status.WAITLIST)
    url = f"/api/v1/club/manage/events/{event.pk}"
    response = organizer.patch(url, {"capacity": 1}, format="json")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "club_capacity_below_registered"
    assert organizer.patch(url, {"capacity": 3}, format="json").status_code == 200
    waiting.refresh_from_db()
    assert waiting.status == "registered"
    assert Notification.objects.filter(recipient=waiting.account).exists()


def test_reschedule_notifies_and_resets_reminders(organizer):
    event = ClubEventFactory(organizer=organizer.account)
    registration = EventRegistrationFactory(event=event, reminder_sent_at=timezone.now())
    response = organizer.patch(f"/api/v1/club/manage/events/{event.pk}",
                               {"starts_at": iso(7), "ends_at": iso(7, 2)}, format="json")
    assert response.status_code == 200
    registration.refresh_from_db()
    assert registration.reminder_sent_at is None
    assert "перенесено" in Notification.objects.get(recipient=registration.account).title


def test_end_before_start_on_partial_update(organizer):
    event = ClubEventFactory(organizer=organizer.account)
    response = organizer.patch(f"/api/v1/club/manage/events/{event.pk}", {"ends_at": iso(-1)}, format="json")
    assert response.status_code == 400


def test_delete_rules(organizer):
    draft = ClubEventFactory(organizer=organizer.account, status=ClubEvent.Status.DRAFT)
    used = ClubEventFactory(organizer=organizer.account)
    EventRegistrationFactory(event=used, status=EventRegistration.Status.CANCELLED)
    assert organizer.delete(f"/api/v1/club/manage/events/{used.pk}").status_code == 409
    assert organizer.delete(f"/api/v1/club/manage/events/{draft.pk}").status_code == 204
    assert not ClubEvent.objects.filter(pk=draft.pk).exists()
    assert AuditEvent.objects.filter(action="club.event_deleted").exists()


def test_registrations_list_shows_public_data_only(organizer):
    event = ClubEventFactory(organizer=organizer.account)
    active = EventRegistrationFactory(event=event)
    EventRegistrationFactory(event=event, status=EventRegistration.Status.CANCELLED)
    response = organizer.get(f"/api/v1/club/manage/events/{event.pk}/registrations")
    assert response.status_code == 200
    rows = response.json()["results"]
    assert [r["id"] for r in rows] == [str(active.pk)]
    assert active.account.email not in response.content.decode()
    all_rows = organizer.get(f"/api/v1/club/manage/events/{event.pk}/registrations", {"status": "cancelled"})
    assert all_rows.json()["count"] == 1


def test_draft_preview_hidden_publicly_until_published(organizer, api_client):
    created = create(organizer).json()
    assert api_client.get(f"/api/v1/club/events/{created['slug']}").status_code == 404
    response = organizer.patch(f"/api/v1/club/manage/events/{created['id']}", {"status": "published"}, format="json")
    assert response.status_code == 200
    assert api_client.get(f"/api/v1/club/events/{created['slug']}").status_code == 200
    assert AuditEvent.objects.filter(action="club.event_published").exists()


# ---------------------------------------------------------------- анонсы


def test_announcement_crud_and_publication(organizer, api_client):
    response = organizer.post("/api/v1/club/manage/announcements",
                              {"title": "Сбор в субботу", "body": "Подробности позже"}, format="json")
    assert response.status_code == 201
    created = response.json()
    assert created["is_published"] is False
    assert api_client.get("/api/v1/club").json()["announcements"] == []
    url = f"/api/v1/club/manage/announcements/{created['id']}"
    response = organizer.patch(url, {"is_published": True, "is_pinned": True}, format="json")
    assert response.json()["is_published"] is True
    assert [a["title"] for a in api_client.get("/api/v1/club").json()["announcements"]] == ["Сбор в субботу"]
    assert organizer.patch(url, {"is_published": False}, format="json").json()["published_at"] is None
    assert organizer.delete(url).status_code == 204
    assert not ClubAnnouncement.objects.exists()
    assert AuditEvent.objects.filter(action__startswith="club.announcement_").count() == 4  # create, 2×update, delete


def test_organizer_cannot_touch_foreign_announcements(organizer, admin):
    foreign = ClubAnnouncementFactory(author=make_organizer())
    url = f"/api/v1/club/manage/announcements/{foreign.pk}"
    assert organizer.patch(url, {"title": "x"}, format="json").status_code == 404
    assert organizer.delete(url).status_code == 404
    assert admin.patch(url, {"title": "Исправлено"}, format="json").status_code == 200


def test_announcement_validation(organizer):
    response = organizer.post("/api/v1/club/manage/announcements", {"title": ""}, format="json")
    assert response.status_code == 400
    assert {"title", "body"} <= set(response.json()["error"]["fields"])
