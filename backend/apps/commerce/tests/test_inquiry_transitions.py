"""Машина состояний обращения 7.2 (ATX-09/28/29, MET-07, BRD-13)."""
from decimal import Decimal

import pytest

from apps.analytics.models import AnalyticsEvent
from apps.boards.models import BoardVariant
from apps.commerce.models import Inquiry
from apps.commerce.services.inquiries import create_inquiry
from apps.commerce.tests.helpers import board_inquiry
from apps.inventory.models import InventoryItem
from apps.messaging.models import Message, Notification
from apps.trust.models import AuditEvent
from tests.factories import AccountFactory, BoardVariantFactory, InventoryItemFactory, WorkshopFactory

pytestmark = pytest.mark.django_db


def act(client, inquiry, action, **body):
    return client.post(f"/api/v1/inquiries/{inquiry.pk}/{action}", body, format="json")


def send(client, inquiry, body="Сообщение"):
    return client.post(f"/api/v1/conversations/{inquiry.conversation.pk}/messages", {"body": body}, format="json")


def test_accept_moves_to_in_progress_with_history_system_message_and_notification(make_client):
    inquiry, customer, workshop = board_inquiry()
    shaper = make_client(workshop.owner)
    response = act(shaper, inquiry, "accept")
    assert response.status_code == 200, response.json()
    data = response.json()
    assert data["status"] == "in_progress" and data["status_label"] == "В работе"
    assert data["actions"] == ["decline", "complete"]
    assert [h["to_status"] for h in data["history"]] == ["new", "in_progress"]
    system = Message.objects.get(conversation=inquiry.conversation, kind="system")
    assert system.body == "Обращение принято в работу." and system.sender == workshop.owner
    note = Notification.objects.get(recipient=customer, kind="inquiry_status")
    assert note.link == f"/account/inquiries/{inquiry.pk}" and note.payload["status"] == "in_progress"
    assert act(shaper, inquiry, "accept").status_code == 409  # повтор
    assert make_client(workshop.owner).get("/api/v1/me/counters").json()["new_inquiries"] == 0


def test_customer_cannot_accept_and_provider_cannot_cancel(make_client):
    inquiry, customer, workshop = board_inquiry()
    assert act(make_client(customer), inquiry, "accept").status_code == 403
    assert act(make_client(workshop.owner), inquiry, "cancel").status_code == 403
    assert act(make_client(), inquiry, "accept").status_code == 404


def test_chat_works_before_and_after_acceptance_and_after_completion(make_client):
    """ATX-09, BR-06, MSG-03: писать можно до принятия, после — и после завершения."""
    inquiry, customer, workshop = board_inquiry()
    buyer, shaper = make_client(customer), make_client(workshop.owner)
    assert send(buyer, inquiry, "до принятия").status_code == 201
    act(shaper, inquiry, "accept")
    assert send(shaper, inquiry, "ответ").status_code == 201
    assert send(buyer, inquiry, "после принятия").status_code == 201
    act(shaper, inquiry, "complete")
    assert send(buyer, inquiry, "спасибо").status_code == 201
    bodies = [m["body"] for m in buyer.get(f"/api/v1/conversations/{inquiry.conversation.pk}/messages").json()["results"]]
    assert "ответ" in bodies and "спасибо" in bodies


@pytest.mark.parametrize("start_status", ["new", "in_progress"])
def test_decline_closes_chat_but_keeps_history(make_client, start_status):
    inquiry, customer, workshop = board_inquiry()
    Inquiry.objects.filter(pk=inquiry.pk).update(status=start_status)
    shaper = make_client(workshop.owner)
    response = act(shaper, inquiry, "decline", reason="Нет материала")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "declined" and data["decline_reason"] == "Нет материала" and data["closed_at"]
    assert data["can_send_messages"] is False and data["send_blocked_reason"] == "conversation_closed"
    for client in (shaper, make_client(customer)):
        response = send(client, inquiry)
        assert response.status_code == 409 and response.json()["error"]["code"] == "conversation_closed"
    messages = make_client(customer).get(f"/api/v1/conversations/{inquiry.conversation.pk}/messages").json()["results"]
    assert messages[-1]["kind"] == "system" and "Нет материала" in messages[-1]["body"]
    assert act(shaper, inquiry, "accept").status_code == 409


def test_complete_requires_in_progress_and_records_confirmed_amount(make_client):
    """MET-07, ATX-29: выручка — только подтверждённая сумма завершённой сделки."""
    inquiry, customer, workshop = board_inquiry()
    shaper = make_client(workshop.owner)
    assert act(shaper, inquiry, "complete").status_code == 409
    act(shaper, inquiry, "accept")
    response = act(shaper, inquiry, "complete", amount_confirmed=True)
    assert response.status_code == 400  # подтверждать нечего
    response = act(shaper, inquiry, "complete", agreed_amount="65000.00", amount_confirmed=True)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed" and data["agreed_amount"] == "65000.00" and data["amount_confirmed"] is True
    event = AnalyticsEvent.objects.get(name="deal_completed")
    assert event.context == {"amount": "65000.00", "confirmed": True, "currency": "RUB", "kind": "board_purchase"}
    assert event.owner_organization == workshop
    assert Notification.objects.filter(recipient=customer, kind="inquiry_status", payload__status="completed").exists()
    assert act(shaper, inquiry, "decline").status_code == 409


def test_complete_with_unconfirmed_amount(make_client):
    inquiry, _customer, workshop = board_inquiry()
    shaper = make_client(workshop.owner)
    act(shaper, inquiry, "accept")
    data = act(shaper, inquiry, "complete", agreed_amount="1000").json()
    assert data["agreed_amount"] == "1000.00" and data["amount_confirmed"] is False
    assert AnalyticsEvent.objects.get(name="deal_completed").context["confirmed"] is False


def test_negative_amount_rejected(make_client):
    inquiry, _customer, workshop = board_inquiry()
    shaper = make_client(workshop.owner)
    act(shaper, inquiry, "accept")
    assert act(shaper, inquiry, "complete", agreed_amount="-5").status_code == 400


def test_customer_cancel_notifies_provider_staff(make_client):
    inquiry, customer, workshop = board_inquiry()
    response = act(make_client(customer), inquiry, "cancel", reason="Передумал")
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled" and response.json()["cancel_reason"] == "Передумал"
    assert Notification.objects.filter(recipient=workshop.owner, kind="inquiry_status").exists()
    assert act(make_client(customer), inquiry, "cancel").status_code == 409


def test_completing_board_purchase_marks_item_sold_and_refreshes_availability(make_client):
    """BRD-13: продажа экземпляра обновляет наличие варианта."""
    workshop = WorkshopFactory()
    variant = BoardVariantFactory(model__workshop=workshop, availability=BoardVariant.Availability.IN_STOCK,
                                  made_to_order_days=None)
    item = InventoryItemFactory(owner_account=None, owner_organization=workshop, variant=variant, purpose="sale",
                                sale_price=Decimal("50000"), rental_price_per_day=None)
    customer = AccountFactory()
    inquiry = create_inquiry(customer, kind="board_purchase", message="Беру", target_type="inventory_item",
                             target_id=item.pk)
    assert inquiry.board_variant == variant and inquiry.provider_organization == workshop
    shaper = make_client(workshop.owner)
    act(shaper, inquiry, "accept")
    assert act(shaper, inquiry, "complete", agreed_amount="50000", amount_confirmed=True).status_code == 200
    item.refresh_from_db()
    variant.refresh_from_db()
    assert item.status == InventoryItem.Status.SOLD
    assert variant.availability == BoardVariant.Availability.OUT_OF_STOCK
    assert AuditEvent.objects.filter(action="inventory.sold", object_id=str(item.pk)).exists()
    # проданный экземпляр больше нельзя заказать
    response = make_client().post("/api/v1/inquiries", {"kind": "board_purchase", "target_type": "inventory_item",
                                                        "target_id": str(item.pk), "message": "Ещё есть?"},
                                  format="json")
    assert response.status_code == 409 and response.json()["error"]["code"] == "item_unavailable"


def test_statuses_history_and_actions_stay_in_sync(make_client):
    """ATX-28: «В работе / Завершить / Отказать» синхронны по статусам, журналу и UI."""
    inquiry, customer, workshop = board_inquiry()
    shaper, buyer = make_client(workshop.owner), make_client(customer)

    def state(client):
        data = client.get(f"/api/v1/inquiries/{inquiry.pk}").json()
        return data["status"], data["actions"], [h["to_status"] for h in data["history"]]

    assert state(shaper) == ("new", ["accept", "decline"], ["new"])
    assert state(buyer) == ("new", ["cancel"], ["new"])
    act(shaper, inquiry, "accept")
    assert state(shaper) == ("in_progress", ["decline", "complete"], ["new", "in_progress"])
    assert state(buyer) == ("in_progress", ["cancel"], ["new", "in_progress"])
    act(shaper, inquiry, "complete")
    assert state(shaper) == ("completed", [], ["new", "in_progress", "completed"])
    assert state(buyer)[1] == []


def test_inquiry_updated_events_for_all_parties(make_client, django_capture_on_commit_callbacks, monkeypatch):
    sent = []
    monkeypatch.setattr("apps.messaging.services.realtime.async_to_sync",
                        lambda fn: (lambda group, event: sent.append((group, event["payload"]))))
    inquiry, customer, workshop = board_inquiry()
    with django_capture_on_commit_callbacks(execute=True):
        act(make_client(workshop.owner), inquiry, "accept")
    updates = {g for g, p in sent if p["type"] == "inquiry.updated" and p["status"] == "in_progress"}
    assert updates == {f"user.{customer.pk}", f"user.{workshop.owner_id}"}
    assert any(p["type"] == "message.new" and p["message"]["kind"] == "system" for _, p in sent)
