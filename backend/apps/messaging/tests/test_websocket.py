"""WebSocket /ws/events/: сессионная аутентификация, счётчики при подключении, доставка между устройствами
(MSG-10, ATX-09/10, AT-04). Используется настоящее ASGI-приложение (config.asgi) и InMemory channel layer."""
import pytest
from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async
from channels.layers import channel_layers
from channels.testing import WebsocketCommunicator
from django.conf import settings

from apps.commerce.tests.helpers import board_inquiry
from apps.messaging.services.conversations import mark_read, send_message

ORIGIN = (b"origin", b"http://localhost:8080")


@pytest.fixture(autouse=True)
def fresh_channel_layer():
    channel_layers.backends = {}
    yield
    channel_layers.backends = {}


def _headers(client):
    session_key = client.cookies[settings.SESSION_COOKIE_NAME].value
    return [ORIGIN, (b"cookie", f"{settings.SESSION_COOKIE_NAME}={session_key}".encode())]


def _app():
    from config.asgi import application

    return application


async def _connect(client):
    communicator = WebsocketCommunicator(_app(), "/ws/events/", headers=_headers(client))
    connected, _ = await communicator.connect()
    assert connected
    first = await communicator.receive_json_from(timeout=3)
    assert first["type"] == "counters"
    return communicator, first["counters"]


async def _drain(communicator, wait=0.5):
    frames = []
    while not await communicator.receive_nothing(timeout=wait):
        frames.append(await communicator.receive_json_from(timeout=2))
    return frames


def test_anonymous_and_foreign_origin_connections_are_rejected(transactional_db,
                                                               make_client):
    client = make_client()

    async def scenario():
        anonymous = WebsocketCommunicator(_app(), "/ws/events/", headers=[ORIGIN])
        connected, code = await anonymous.connect()
        assert not connected and code == 4401
        foreign = WebsocketCommunicator(_app(), "/ws/events/",
                                        headers=[(b"origin", b"http://evil.example"), _headers(client)[1]])
        connected, _ = await foreign.connect()
        assert not connected

    async_to_sync(scenario)()


def test_counters_on_connect_and_ping(transactional_db, make_client):
    inquiry, _customer, workshop = board_inquiry()
    shaper = make_client(workshop.owner)

    async def scenario():
        communicator, counters = await _connect(shaper)
        assert counters == {"unread_messages": 1, "unread_notifications": 1, "new_inquiries": 1, "pending_bookings": 0}
        await communicator.send_json_to({"type": "ping"})
        assert await communicator.receive_json_from(timeout=2) == {"type": "pong"}
        await communicator.send_json_to({"type": "counters"})
        assert (await communicator.receive_json_from(timeout=2))["type"] == "counters"
        await communicator.disconnect()

    async_to_sync(scenario)()


def test_message_reaches_other_participant_and_senders_other_devices(transactional_db,
                                                                     make_client):
    """ATX-09 / MSG-10: ответ виден на втором устройстве; сообщения идут между реальными аккаунтами."""
    inquiry, customer, workshop = board_inquiry()
    buyer, shaper_phone, shaper_laptop = make_client(customer), make_client(workshop.owner), make_client(workshop.owner)

    async def scenario():
        buyer_ws, _ = await _connect(buyer)
        phone_ws, _ = await _connect(shaper_phone)
        laptop_ws, _ = await _connect(shaper_laptop)
        await database_sync_to_async(send_message)(inquiry.conversation, customer, body="Есть 5'8?", client_id="cid-7")
        for ws in (phone_ws, laptop_ws):
            frames = await _drain(ws)
            new = [f for f in frames if f["type"] == "message.new"]
            assert len(new) == 1 and new[0]["message"]["body"] == "Есть 5'8?"
            assert new[0]["message"]["is_mine"] is False and new[0]["message"]["client_id"] == ""
            assert new[0]["conversation_id"] == str(inquiry.conversation.pk)
            assert any(f["type"] == "notification.new" and f["notification"]["kind"] == "message_new" for f in frames)
            counters = [f for f in frames if f["type"] == "counters"]
            assert counters and counters[-1]["counters"]["unread_messages"] == 2
        own = [f for f in await _drain(buyer_ws) if f["type"] == "message.new"]
        assert own[0]["message"]["is_mine"] is True and own[0]["message"]["client_id"] == "cid-7"
        for ws in (buyer_ws, phone_ws, laptop_ws):
            await ws.disconnect()

    async_to_sync(scenario)()


def test_reading_on_one_device_syncs_other_devices(transactional_db, make_client):
    """BR-10, ATX-10: прочтение на одном устройстве обнуляет счётчик на всех."""
    inquiry, customer, workshop = board_inquiry()
    phone, laptop, buyer = make_client(workshop.owner), make_client(workshop.owner), make_client(customer)

    async def scenario():
        phone_ws, counters = await _connect(phone)
        assert counters["unread_messages"] == 1
        laptop_ws, _ = await _connect(laptop)
        buyer_ws, _ = await _connect(buyer)
        await database_sync_to_async(mark_read)(inquiry.conversation, workshop.owner)
        for ws in (phone_ws, laptop_ws):
            frames = await _drain(ws)
            read = [f for f in frames if f["type"] == "conversation.read"]
            assert read and read[0]["account_id"] == str(workshop.owner_id) and read[0]["last_read_at"]
            assert [f for f in frames if f["type"] == "counters"][-1]["counters"]["unread_messages"] == 0
        receipt = [f for f in await _drain(buyer_ws) if f["type"] == "conversation.read"]
        assert receipt and receipt[0]["conversation_id"] == str(inquiry.conversation.pk)  # отметка прочтения
        for ws in (phone_ws, laptop_ws, buyer_ws):
            await ws.disconnect()

    async_to_sync(scenario)()


def test_status_change_pushes_inquiry_updated(transactional_db, make_client):
    from apps.commerce.services.inquiries import transition_inquiry

    inquiry, customer, workshop = board_inquiry()
    buyer = make_client(customer)

    async def scenario():
        buyer_ws, _ = await _connect(buyer)
        await database_sync_to_async(transition_inquiry)(workshop.owner, inquiry.pk, "accept")
        frames = await _drain(buyer_ws)
        assert {"type": "inquiry.updated", "inquiry_id": str(inquiry.pk), "status": "in_progress"} in frames
        system = [f for f in frames if f["type"] == "message.new"]
        assert system and system[0]["message"]["kind"] == "system"
        await buyer_ws.disconnect()

    async_to_sync(scenario)()
