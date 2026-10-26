"""Сообщения в диалоге: отправка, вложения, повтор по client_id, курсоры чтения, закрытые диалоги (8.6, 25)."""
import datetime as dt

import pytest
from django.core import mail
from django.utils import timezone

from apps.commerce.models import Inquiry
from apps.commerce.tests.helpers import attachment, board_inquiry, results
from apps.mediafiles.models import MediaAsset
from apps.messaging.models import AccountBlock, Conversation, ConversationParticipant, Message, Notification
from apps.trust.models import AccountRestriction

pytestmark = pytest.mark.django_db


@pytest.fixture
def chat(make_client):
    inquiry, customer, workshop = board_inquiry(message="Первое")
    return inquiry.conversation, make_client(customer), make_client(workshop.owner), workshop


def messages_url(conversation, query=""):
    return f"/api/v1/conversations/{conversation.pk}/messages{query}"


def test_participant_sends_message_with_contract_shape(chat):
    conversation, buyer, shaper, workshop = chat
    response = shaper.post(messages_url(conversation), {"body": "Да, в наличии", "client_id": "c-1"}, format="json")
    assert response.status_code == 201, response.json()
    data = response.json()
    assert set(data) == {"id", "conversation_id", "kind", "body", "sender", "is_mine", "is_hidden", "client_id",
                         "created_at", "edited_at", "attachments"}
    assert data["conversation_id"] == str(conversation.pk) and data["kind"] == "text"
    assert data["is_mine"] is True and data["client_id"] == "c-1" and data["attachments"] == []
    assert data["sender"]["id"] == str(workshop.owner_id) and "email" not in data["sender"]
    page = buyer.get(messages_url(conversation)).json()
    assert [m["body"] for m in page["results"]] == ["Первое", "Да, в наличии"]
    assert page["results"][1]["is_mine"] is False and page["results"][1]["client_id"] == ""
    assert page["results"][0]["is_mine"] is True


def test_retry_with_same_client_id_returns_existing_message(chat):
    conversation, buyer, _shaper, _ = chat
    first = buyer.post(messages_url(conversation), {"body": "Привет", "client_id": "retry-1"}, format="json")
    second = buyer.post(messages_url(conversation), {"body": "Привет", "client_id": "retry-1"}, format="json")
    assert first.status_code == 201 and second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert Message.objects.filter(conversation=conversation, client_id="retry-1").count() == 1


def test_empty_or_too_long_message_rejected(chat):
    conversation, buyer, _shaper, _ = chat
    assert buyer.post(messages_url(conversation), {"body": "   "}, format="json").json()["error"]["code"] == "message_empty"
    assert buyer.post(messages_url(conversation), {"body": "x" * 4001}, format="json").status_code == 400


def test_photo_attachments_are_signed_for_participants(chat):
    """MSG-04, 8.6: фото в переписке — media_assets + message_attachments; закрытые файлы — presigned GET."""
    conversation, buyer, shaper, _ = chat
    photo = attachment(buyer.account)
    pending = attachment(buyer.account, status=MediaAsset.Status.PROCESSING)
    response = buyer.post(messages_url(conversation), {"body": "", "attachment_ids": [str(photo.pk), str(pending.pk)]},
                          format="json")
    assert response.status_code == 201, response.json()
    ready, processing = response.json()["attachments"]
    assert ready["id"] == str(photo.pk) and ready["url"] is None
    assert ready["signed_url"].startswith("http://testserver/gdevolna-media/private/")
    assert "X-Amz-Signature" in ready["signed_url"]
    assert processing["status"] == "processing" and processing["signed_url"] is None
    seen = shaper.get(messages_url(conversation)).json()["results"][-1]["attachments"]
    assert "X-Amz-Signature" in seen[0]["signed_url"]
    assert results(shaper.get("/api/v1/inquiries"))[0]["last_message"]["body"] == "📎 Фото"


def test_attachment_rules(chat):
    conversation, buyer, _shaper, _ = chat
    foreign = attachment(_shaper.account)
    response = buyer.post(messages_url(conversation), {"attachment_ids": [str(foreign.pk)]}, format="json")
    assert response.status_code == 400 and response.json()["error"]["code"] == "media_invalid"
    wrong_purpose = attachment(buyer.account, purpose=MediaAsset.Purpose.AVATAR)
    response = buyer.post(messages_url(conversation), {"attachment_ids": [str(wrong_purpose.pk)]}, format="json")
    assert response.json()["error"]["code"] == "media_purpose"
    video = attachment(buyer.account, kind=MediaAsset.Kind.VIDEO)
    assert buyer.post(messages_url(conversation), {"attachment_ids": [str(video.pk)]},
                      format="json").json()["error"]["code"] == "media_kind"
    many = [str(attachment(buyer.account).pk) for _ in range(11)]
    assert buyer.post(messages_url(conversation), {"attachment_ids": many}, format="json").status_code == 400
    assert not Message.objects.filter(conversation=conversation).exclude(body="Первое").exists()


def test_cursor_pagination_newest_last(chat):
    conversation, buyer, _shaper, _ = chat
    base = timezone.now()
    for i in range(35):
        message = Message.objects.create(conversation=conversation, sender=buyer.account, body=f"m{i}")
        Message.objects.filter(pk=message.pk).update(created_at=base + dt.timedelta(seconds=i + 1))
    page = buyer.get(messages_url(conversation)).json()
    assert len(page["results"]) == 30 and page["has_more"] is True
    assert page["results"][-1]["body"] == "m34" and page["results"][0]["body"] == "m5"
    older = buyer.get(messages_url(conversation, f"?before={page['next_before']}")).json()
    assert [m["body"] for m in older["results"]] == ["Первое", "m0", "m1", "m2", "m3", "m4"]
    assert older["has_more"] is False and older["next_before"] is None
    newer = buyer.get(messages_url(conversation, f"?after={page['results'][-3]['id']}&limit=5")).json()
    assert [m["body"] for m in newer["results"]] == ["m33", "m34"] and newer["has_newer"] is False
    small = buyer.get(messages_url(conversation, "?limit=2")).json()
    assert [m["body"] for m in small["results"]] == ["m33", "m34"]
    assert buyer.get(messages_url(conversation, "?before=garbage")).status_code == 400


def test_strangers_cannot_read_or_post(chat, make_client):
    conversation, _buyer, _shaper, _ = chat
    stranger = make_client()
    assert stranger.get(f"/api/v1/conversations/{conversation.pk}").status_code == 404
    assert stranger.get(messages_url(conversation)).status_code == 404
    assert stranger.post(messages_url(conversation), {"body": "spam"}, format="json").status_code == 404
    assert stranger.post(f"/api/v1/conversations/{conversation.pk}/read", {}, format="json").status_code == 404


@pytest.mark.parametrize("closed_status", ["declined", "cancelled"])
def test_closed_inquiry_forbids_messages(chat, closed_status):
    conversation, buyer, shaper, _ = chat
    Inquiry.objects.filter(pk=conversation.inquiry_id).update(status=closed_status)
    for client in (buyer, shaper):
        response = client.post(messages_url(conversation), {"body": "ещё"}, format="json")
        assert response.status_code == 409 and response.json()["error"]["code"] == "conversation_closed"
    assert buyer.get(messages_url(conversation)).status_code == 200
    detail = buyer.get(f"/api/v1/conversations/{conversation.pk}").json()
    assert detail["can_send"] is False and detail["send_blocked_reason"] == "conversation_closed"


def test_locked_conversation_forbids_messages(chat):
    conversation, buyer, _shaper, _ = chat
    Conversation.objects.filter(pk=conversation.pk).update(is_locked=True)
    response = buyer.post(messages_url(conversation), {"body": "ещё"}, format="json")
    assert response.status_code == 409 and response.json()["error"]["code"] == "conversation_closed"


def test_block_forbids_messages_both_ways(chat):
    conversation, buyer, shaper, workshop = chat
    AccountBlock.objects.create(blocker=workshop.owner, blocked=buyer.account)
    for client in (buyer, shaper):
        response = client.post(messages_url(conversation), {"body": "x"}, format="json")
        assert response.status_code == 403 and response.json()["error"]["code"] == "blocked"


def test_messaging_restriction(chat):
    conversation, buyer, _shaper, _ = chat
    AccountRestriction.objects.create(account=buyer.account, kind="messaging", reason="спам",
                                      expires_at=timezone.now() + dt.timedelta(days=1))
    response = buyer.post(messages_url(conversation), {"body": "x"}, format="json")
    assert response.status_code == 403 and response.json()["error"]["code"] == "messaging_restricted"
    AccountRestriction.objects.update(expires_at=timezone.now() - dt.timedelta(minutes=1))
    assert buyer.post(messages_url(conversation), {"body": "x"}, format="json").status_code == 201


def test_new_message_notifies_recipients_without_email_by_default(chat, django_capture_on_commit_callbacks):
    conversation, buyer, _shaper, workshop = chat
    with django_capture_on_commit_callbacks(execute=True):
        message_id = buyer.post(messages_url(conversation), {"body": "Когда можно забрать?"}, format="json").json()["id"]
    note = Notification.objects.get(recipient=workshop.owner, kind="message_new")
    assert note.event_id == f"message_new:{message_id}:{workshop.owner_id}"
    assert note.link == f"/account/inquiries/{conversation.inquiry_id}"
    assert note.payload["conversation_id"] == str(conversation.pk) and note.body == "Когда можно забрать?"
    assert not Notification.objects.filter(recipient=buyer.account, kind="message_new").exists()
    assert mail.outbox == []


def test_muted_participant_is_not_notified(chat):
    conversation, buyer, _shaper, workshop = chat
    ConversationParticipant.objects.filter(conversation=conversation, account=workshop.owner).update(is_muted=True)
    buyer.post(messages_url(conversation), {"body": "x"}, format="json")
    assert not Notification.objects.filter(recipient=workshop.owner, kind="message_new").exists()


def test_read_cursor_moves_forward_only_and_clears_message_notifications(chat):
    """BR-10: факт чтения хранится на сервере и одинаков на устройствах."""
    conversation, buyer, shaper, _ = chat
    ids = [buyer.post(messages_url(conversation), {"body": f"m{i}"}, format="json").json()["id"] for i in range(3)]
    assert shaper.get("/api/v1/me/counters").json() == {"unread_messages": 4, "unread_notifications": 4,
                                                        "new_inquiries": 1, "pending_bookings": 0}
    read_url = f"/api/v1/conversations/{conversation.pk}/read"
    response = shaper.post(read_url, {"message_id": ids[0]}, format="json")
    assert response.status_code == 200 and response.json()["unread_count"] == 2
    assert response.json()["counters"]["unread_notifications"] == 3  # inquiry_new + 2 непрочитанных сообщения
    shaper.post(read_url, {}, format="json")
    assert shaper.get("/api/v1/me/counters").json()["unread_messages"] == 0
    shaper.post(read_url, {"message_id": ids[0]}, format="json")  # назад курсор не двигается
    assert shaper.get(f"/api/v1/conversations/{conversation.pk}").json()["unread_count"] == 0
    assert not Notification.objects.filter(recipient=shaper.account, kind="message_new", read_at__isnull=True).exists()
    assert shaper.post(read_url, {"message_id": "00000000-0000-0000-0000-000000000000"}, format="json").status_code == 404


def test_own_and_hidden_messages_are_not_unread(chat):
    conversation, buyer, shaper, _ = chat
    shaper.post(f"/api/v1/conversations/{conversation.pk}/read", {}, format="json")
    shaper.post(messages_url(conversation), {"body": "мой ответ"}, format="json")
    spam = buyer.post(messages_url(conversation), {"body": "спам"}, format="json").json()
    Message.objects.filter(pk=spam["id"]).update(is_hidden=True)
    assert shaper.get("/api/v1/me/counters").json()["unread_messages"] == 0
    hidden = [m for m in shaper.get(messages_url(conversation)).json()["results"] if m["id"] == spam["id"]][0]
    assert hidden["is_hidden"] is True and hidden["body"] == "" and hidden["attachments"] == []


def test_sending_marks_conversation_read_for_sender(chat):
    conversation, buyer, shaper, _ = chat
    assert shaper.get(f"/api/v1/conversations/{conversation.pk}").json()["unread_count"] == 1
    shaper.post(messages_url(conversation), {"body": "ответ"}, format="json")
    assert shaper.get(f"/api/v1/conversations/{conversation.pk}").json()["unread_count"] == 0
    assert buyer.get(f"/api/v1/conversations/{conversation.pk}").json()["unread_count"] == 1


def test_conversation_detail_shape(chat):
    conversation, buyer, _shaper, workshop = chat
    data = buyer.get(f"/api/v1/conversations/{conversation.pk}").json()
    assert data["kind"] == "inquiry" and data["inquiry"]["status"] == "new" and data["inquiry"]["my_role"] == "customer"
    assert data["inquiry"]["actions"] == ["cancel"] and data["can_send"] is True
    assert data["counterpart"]["type"] == "organization" and data["counterpart"]["id"] == str(workshop.pk)
    assert data["context"]["type"] == "board_model" and data["last_message"]["body"] == "Первое"
    roles = {p["account"]["id"]: p["role"] for p in data["participants"]}
    assert roles == {str(buyer.account.pk): "customer", str(workshop.owner_id): "member"}
    assert data["my_last_read_at"] is not None


def test_conversation_list_includes_inquiry_and_direct(chat, make_client):
    conversation, buyer, _shaper, _ = chat
    from apps.accounts.models import UserProfile

    peer = make_client()
    UserProfile.objects.filter(account=peer.account).update(gg_surfer_enabled=True)
    direct = buyer.post("/api/v1/direct-conversations", {"account_id": str(peer.account.pk)}, format="json").json()
    items = results(buyer.get("/api/v1/conversations"))
    assert {i["id"] for i in items} == {str(conversation.pk), direct["id"]}
    assert {i["id"] for i in results(buyer.get("/api/v1/conversations?kind=direct"))} == {direct["id"]}
    assert results(peer.get("/api/v1/conversations"))[0]["counterpart"]["id"] == str(buyer.account.pk)


def test_sending_is_rate_limited_by_messages_scope(chat, monkeypatch):
    """Rate limit scope «messages» действует только на отправку (в тестах троттлинг по умолчанию выключен)."""
    from django.core.cache import cache
    from rest_framework.throttling import ScopedRateThrottle

    from apps.messaging.views import MessageListCreateView

    conversation, buyer, _shaper, _ = chat
    monkeypatch.setattr(MessageListCreateView, "throttle_classes", [ScopedRateThrottle])
    monkeypatch.setattr(ScopedRateThrottle, "THROTTLE_RATES", {"messages": "2/min"})
    cache.clear()
    try:
        codes = [buyer.post(messages_url(conversation), {"body": f"m{i}"}, format="json").status_code for i in range(3)]
        assert codes == [201, 201, 429]
        assert buyer.get(messages_url(conversation)).status_code == 200  # чтение не ограничено
    finally:
        cache.clear()
