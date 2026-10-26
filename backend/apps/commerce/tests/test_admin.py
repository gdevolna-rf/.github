"""Django Admin commerce/messaging открывается у администратора с 2FA."""
import pytest

from apps.commerce.tests.helpers import board_inquiry, rental_item, requested_rental
from apps.messaging.services.conversations import send_message
from tests.factories import AccountFactory

pytestmark = pytest.mark.django_db

PAGES = [
    "commerce/inquiry", "commerce/booking", "messaging/conversation", "messaging/message",
    "messaging/notification", "messaging/notificationpreference", "messaging/accountblock", "messaging/pushdevice",
]


@pytest.fixture
def admin_client(make_client):
    admin = AccountFactory(is_staff=True, is_superuser=True)
    return make_client(admin, two_factor=True)


@pytest.mark.parametrize("page", PAGES)
def test_admin_changelists_render(admin_client, page):
    inquiry, customer, _ = board_inquiry()
    send_message(inquiry.conversation, customer, body="Ещё вопрос")
    requested_rental(rental_item())
    assert admin_client.get(f"/admin/{page}/").status_code == 200


def test_admin_change_pages_render(admin_client):
    inquiry, _customer, _ = board_inquiry()
    booking = requested_rental(rental_item())
    assert admin_client.get(f"/admin/commerce/inquiry/{inquiry.pk}/change/").status_code == 200
    assert admin_client.get(f"/admin/commerce/booking/{booking.pk}/change/").status_code == 200
    assert admin_client.get(f"/admin/messaging/conversation/{inquiry.conversation.pk}/change/").status_code == 200


def test_admin_hides_message_with_audit(admin_client):
    from apps.messaging.models import Message
    from apps.trust.models import AuditEvent

    inquiry, _customer, _ = board_inquiry()
    message = Message.objects.get(conversation=inquiry.conversation)
    response = admin_client.post("/admin/messaging/message/", {"action": "hide_messages",
                                                               "_selected_action": [str(message.pk)]},
                                 format="multipart")
    assert response.status_code == 302
    message.refresh_from_db()
    assert message.is_hidden is True
    assert AuditEvent.objects.filter(action="message.hidden", object_id=str(message.pk)).exists()
