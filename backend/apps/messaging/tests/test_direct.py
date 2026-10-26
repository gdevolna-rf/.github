"""Личная переписка GG Surfer: согласие, политика контактов, блокировки, одна беседа на пару (BR-12, COM-03/07)."""
import pytest

from apps.accounts.models import UserProfile
from apps.messaging.models import AccountBlock, Conversation, Notification

pytestmark = pytest.mark.django_db


def gg(account, policy="everyone"):
    UserProfile.objects.filter(account=account).update(gg_surfer_enabled=True, gg_contact_policy=policy)
    return account


def open_direct(client, account):
    return client.post("/api/v1/direct-conversations", {"account_id": str(account.pk)}, format="json")


def test_open_direct_conversation_once_per_pair(make_client):
    me, peer = make_client(), make_client()
    gg(peer.account)
    gg(me.account)
    first = open_direct(me, peer.account)
    assert first.status_code == 201, first.json()
    data = first.json()
    assert data["kind"] == "direct" and data["inquiry"] is None and data["context"] is None
    assert data["counterpart"]["id"] == str(peer.account.pk) and data["can_send"] is True
    assert {p["role"] for p in data["participants"]} == {"peer"}
    again = open_direct(me, peer.account)
    assert again.status_code == 200 and again.json()["id"] == data["id"]
    reverse = open_direct(peer, me.account)
    assert reverse.status_code == 200 and reverse.json()["id"] == data["id"]
    assert Conversation.objects.filter(kind="direct").count() == 1


def test_direct_messages_and_notifications(make_client):
    me, peer = make_client(), make_client()
    gg(peer.account)
    conversation_id = open_direct(me, peer.account).json()["id"]
    response = me.post(f"/api/v1/conversations/{conversation_id}/messages", {"body": "Покатаем завтра?"}, format="json")
    assert response.status_code == 201
    note = Notification.objects.get(recipient=peer.account, kind="message_new")
    assert note.link == f"/account/inquiries?conversation={conversation_id}"
    assert peer.get("/api/v1/me/counters").json()["unread_messages"] == 1
    reply = peer.post(f"/api/v1/conversations/{conversation_id}/messages", {"body": "Да!"}, format="json")
    assert reply.status_code == 201


@pytest.mark.parametrize("enabled,policy", [(False, "everyone"), (True, "nobody")])
def test_contact_policy_respected(make_client, enabled, policy):
    me, peer = make_client(), make_client()
    UserProfile.objects.filter(account=peer.account).update(gg_surfer_enabled=enabled, gg_contact_policy=policy)
    response = open_direct(me, peer.account)
    assert response.status_code == 403 and response.json()["error"]["code"] == "contact_not_allowed"


def test_self_blocked_and_missing_targets(make_client):
    me, peer = make_client(), make_client()
    gg(peer.account)
    assert open_direct(me, me.account).json()["error"]["code"] == "self_conversation"
    AccountBlock.objects.create(blocker=peer.account, blocked=me.account)
    response = open_direct(me, peer.account)
    assert response.status_code == 403 and response.json()["error"]["code"] == "blocked"
    missing = me.post("/api/v1/direct-conversations", {"account_id": "00000000-0000-0000-0000-000000000000"},
                      format="json")
    assert missing.status_code == 404


def test_block_after_contact_stops_messages(make_client):
    me, peer = make_client(), make_client()
    gg(peer.account)
    conversation_id = open_direct(me, peer.account).json()["id"]
    peer.post("/api/v1/blocks", {"account_id": str(me.account.pk)}, format="json")
    response = me.post(f"/api/v1/conversations/{conversation_id}/messages", {"body": "?"}, format="json")
    assert response.status_code == 403 and response.json()["error"]["code"] == "blocked"
    detail = me.get(f"/api/v1/conversations/{conversation_id}").json()
    assert detail["can_send"] is False and detail["send_blocked_reason"] == "blocked"


def test_outsider_cannot_open_foreign_direct_conversation(make_client):
    me, peer, other = make_client(), make_client(), make_client()
    gg(peer.account)
    conversation_id = open_direct(me, peer.account).json()["id"]
    assert other.get(f"/api/v1/conversations/{conversation_id}").status_code == 404
