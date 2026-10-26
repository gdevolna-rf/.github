"""Уведомления, настройки каналов (MSG-12), блокировки (COM-07) и счётчики (MSG-07)."""
import pytest
from django.conf import settings
from django.core import mail

from apps.commerce.tests.helpers import board_inquiry, requested_lesson, results
from apps.messaging.models import AccountBlock, Notification, NotificationPreference
from apps.messaging.services.notify import notify
from tests.factories import AccountFactory, LessonSessionFactory

pytestmark = pytest.mark.django_db


def test_notify_is_idempotent_by_event_id_and_skips_actor():
    recipient, actor = AccountFactory(), AccountFactory()
    first = notify(recipient, "system", "Привет", event_id="evt-1", actor=actor)
    assert first is not None and first.event_id == f"evt-1:{recipient.pk}"
    assert notify(recipient, "system", "Привет", event_id="evt-1") is None
    assert notify(actor, "system", "Себе", actor=actor) is None
    assert Notification.objects.count() == 1


def test_email_sent_for_default_email_kinds(django_capture_on_commit_callbacks):
    recipient = AccountFactory()
    with django_capture_on_commit_callbacks(execute=True):
        notify(recipient, "inquiry_new", "Новое обращение", body="Текст", link="/account/inquiries/1", event_id="e1")
        notify(recipient, "message_new", "Новое сообщение", event_id="e2")
    assert len(mail.outbox) == 1 and mail.outbox[0].to == [recipient.email]
    assert f"{settings.SITE_URL}/account/inquiries/1" in mail.outbox[0].body
    assert Notification.objects.get(event_id__startswith="e1").email_sent_at is not None


def test_preferences_list_defaults_for_every_kind_and_update(make_client):
    client = make_client()
    data = client.get("/api/v1/me/notification-preferences").json()["preferences"]
    kinds = {p["kind"]: p for p in data}
    assert set(kinds) == set(Notification.Kind.values)
    assert kinds["message_new"] == {"kind": "message_new", "label": "Новое сообщение", "in_app": True, "email": False,
                                    "push": False, "is_default": True}
    assert kinds["inquiry_new"]["email"] is True
    response = client.put("/api/v1/me/notification-preferences",
                          {"preferences": [{"kind": "message_new", "email": True},
                                           {"kind": "booking_new", "in_app": False}]}, format="json")
    assert response.status_code == 200
    updated = {p["kind"]: p for p in response.json()["preferences"]}
    assert updated["message_new"]["email"] is True and updated["message_new"]["in_app"] is True
    assert updated["message_new"]["is_default"] is False
    assert updated["booking_new"]["in_app"] is False and updated["booking_new"]["email"] is False
    assert NotificationPreference.objects.filter(account=client.account).count() == 2
    bad = client.put("/api/v1/me/notification-preferences", {"preferences": [{"kind": "nope"}]}, format="json")
    assert bad.status_code == 400


def test_disabled_in_app_channel_creates_read_record_only_for_email(make_client):
    account = AccountFactory()
    NotificationPreference.objects.create(account=account, kind="inquiry_new", in_app=False, email=True)
    note = notify(account, "inquiry_new", "Новое обращение", event_id="x")
    assert note.read_at is not None
    NotificationPreference.objects.create(account=account, kind="system", in_app=False, email=False)
    assert notify(account, "system", "Тишина", event_id="y") is None


def test_notification_feed_read_and_read_all(make_client):
    client = make_client()
    for i in range(3):
        notify(client.account, "system", f"N{i}", event_id=f"n{i}")
    other = notify(AccountFactory(), "system", "Чужое", event_id="other")
    feed = results(client.get("/api/v1/me/notifications"))
    assert [n["title"] for n in feed] == ["N2", "N1", "N0"]
    assert set(feed[0]) >= {"id", "kind", "kind_label", "title", "body", "link", "payload", "actor", "created_at",
                            "read_at", "is_read"}
    response = client.post(f"/api/v1/me/notifications/{feed[0]['id']}/read")
    assert response.status_code == 200 and response.json()["is_read"] is True
    assert len(results(client.get("/api/v1/me/notifications?unread=1"))) == 2
    assert client.post(f"/api/v1/me/notifications/{other.pk}/read").status_code == 404
    assert client.post("/api/v1/me/notifications/read-all").json() == {"updated": 2}
    assert client.get("/api/v1/me/counters").json()["unread_notifications"] == 0
    assert len(results(client.get("/api/v1/me/notifications?kind=system"))) == 3


def test_blocks_api(make_client):
    client = make_client()
    target = AccountFactory()
    response = client.post("/api/v1/blocks", {"account_id": str(target.pk)}, format="json")
    assert response.status_code == 201 and response.json()["account"]["id"] == str(target.pk)
    assert client.post("/api/v1/blocks", {"account_id": str(target.pk)}, format="json").status_code == 200
    assert [b["account"]["id"] for b in results(client.get("/api/v1/me/blocks"))] == [str(target.pk)]
    assert client.post("/api/v1/blocks", {"account_id": str(client.account.pk)},
                       format="json").json()["error"]["code"] == "self_block"
    assert client.post("/api/v1/blocks", {"account_id": "00000000-0000-0000-0000-000000000000"},
                       format="json").status_code == 404
    assert client.delete(f"/api/v1/blocks/{target.pk}").status_code == 204
    assert client.delete(f"/api/v1/blocks/{target.pk}").status_code == 404
    assert not AccountBlock.objects.exists()


def test_counters_aggregate_server_state(make_client, api_client):
    inquiry, customer, workshop = board_inquiry()
    session = LessonSessionFactory(program__organization=workshop)  # бронь занятия на ту же организацию
    requested_lesson(session)
    shaper = make_client(workshop.owner)
    assert shaper.get("/api/v1/me/counters").json() == {"unread_messages": 1, "unread_notifications": 1,
                                                        "new_inquiries": 1, "pending_bookings": 1}
    assert make_client(customer).get("/api/v1/me/counters").json() == {
        "unread_messages": 0, "unread_notifications": 0, "new_inquiries": 0, "pending_bookings": 0}
    assert api_client.get("/api/v1/me/counters").status_code == 401
