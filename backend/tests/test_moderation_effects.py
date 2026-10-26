"""Побочные эффекты решений модератора в других приложениях (F14, TRUST-07, BRD-13, CLB-02).

* скрытие события клуба по жалобе = отмена + уведомление записавшимся (event_status), восстановление по апелляции;
* скрытие/восстановление/продажа экземпляра пересчитывают наличие варианта доски (BoardVariant.availability);
* виды уведомлений клуба и магазина — event_status / product_available.
"""
import pytest

from apps.boards.models import BoardVariant
from apps.boards.tests.helpers import published_model, workshop_for
from apps.club.models import ClubEvent, EventRegistration
from apps.club.tests.factories import ClubEventFactory, EventRegistrationFactory, make_organizer
from apps.commerce.models import Inquiry
from apps.inventory.models import InventoryItem
from apps.messaging.models import Notification
from apps.shop.models import ProductInterest
from apps.shop.services.products import notify_back_in_stock
from apps.shop.tests.factories import ProductFactory
from apps.trust.models import AuditEvent
from tests.factories import AccountFactory, InventoryItemFactory

pytestmark = pytest.mark.django_db

K = Notification.Kind


def complain(client, target_type, target_id):
    response = client.post("/api/v1/complaints", {"target_type": target_type, "target_id": str(target_id),
                                                  "reason": "fraud"}, format="json")
    assert response.status_code == 201, response.content
    return response.json()["id"]


def resolve(mod_client, complaint_id, action="hidden"):
    response = mod_client.post(f"/api/v1/moderation/complaints/{complaint_id}/resolve",
                               {"action": action, "note": "Нарушение правил"}, format="json")
    assert response.status_code == 200, response.content
    return response


def grant_appeal(owner_client, mod_client, complaint_id):
    assert owner_client.post(f"/api/v1/complaints/{complaint_id}/appeal", {"text": "Ошибка"},
                             format="json").status_code == 200
    response = mod_client.post(f"/api/v1/moderation/complaints/{complaint_id}/appeal-decision",
                               {"grant": True, "note": "Восстановлено"}, format="json")
    assert response.status_code == 200, response.content


# --- клуб ------------------------------------------------------------------------------------------------------------

def test_hidden_club_event_is_cancelled_and_registrants_notified(make_client, mod_client):
    organizer = make_organizer()
    event = ClubEventFactory(organizer=organizer, capacity=1)
    registered = EventRegistrationFactory(event=event)
    waiting = EventRegistrationFactory(event=event, status=EventRegistration.Status.WAITLIST)
    cancelled = EventRegistrationFactory(event=event, status=EventRegistration.Status.CANCELLED)

    complaint_id = complain(make_client(), "club_event", event.pk)
    resolve(mod_client, complaint_id)

    event.refresh_from_db()
    assert event.status == ClubEvent.Status.CANCELLED
    notes = Notification.objects.filter(kind=K.EVENT_STATUS, payload__club_event_id=str(event.pk))
    assert set(notes.values_list("recipient_id", flat=True)) == {registered.account_id, waiting.account_id}
    assert not notes.filter(recipient=cancelled.account).exists()
    note = notes.get(recipient=registered.account)
    assert "отменено" in note.title and note.link == f"/club/events/{event.slug}"
    assert note.payload["status"] == ClubEvent.Status.CANCELLED
    # Организатор получает решение модератора, журнал фиксирует до/после.
    assert Notification.objects.filter(recipient=organizer, kind=K.MODERATION_DECISION).exists()
    audit = AuditEvent.objects.get(action="complaint.resolved", object_id=complaint_id)
    assert audit.before == {"status": "published"} and audit.after == {"status": "cancelled"}

    grant_appeal(make_client(organizer), mod_client, complaint_id)
    event.refresh_from_db()
    assert event.status == ClubEvent.Status.PUBLISHED
    restored = Notification.objects.filter(kind=K.EVENT_STATUS, recipient=registered.account,
                                           title__contains="снова в силе")
    assert restored.exists()


def test_organizer_cancellation_and_waitlist_promotion_use_event_status_kind(make_client):
    organizer = make_organizer()
    event = ClubEventFactory(organizer=organizer, capacity=1)
    first = make_client()
    second = make_client()
    url = f"/api/v1/club/events/{event.pk}/registration"
    assert first.post(url, {}, format="json").status_code in (200, 201)
    assert second.post(url, {}, format="json").status_code in (200, 201)
    assert first.delete(url).status_code in (200, 204)
    promoted = Notification.objects.get(recipient=second.account)
    assert promoted.kind == K.EVENT_STATUS
    response = make_client(organizer).patch(f"/api/v1/club/manage/events/{event.pk}",
                                            {"status": "cancelled", "cancel_reason": "Шторм"}, format="json")
    assert response.status_code == 200, response.content
    cancelled = Notification.objects.filter(recipient=second.account, kind=K.EVENT_STATUS, title__contains="отменено")
    assert cancelled.exists() and "Шторм" in cancelled.first().body


def test_back_in_stock_uses_product_available_kind():
    product = ProductFactory()
    interest = ProductInterest.objects.create(product=product, account=AccountFactory())
    assert notify_back_in_stock(product) == 1
    assert Notification.objects.get(recipient=interest.account).kind == K.PRODUCT_AVAILABLE


# --- наличие вариантов досок (BRD-13) --------------------------------------------------------------------------------

def _sale_item(workshop, variant):
    return InventoryItemFactory(owner_account=None, owner_organization=workshop, variant=variant,
                                purpose=InventoryItem.Purpose.SALE, sale_price=variant.price)


def test_hiding_and_restoring_sale_item_refreshes_variant_availability(make_client, mod_client):
    workshop = workshop_for()
    variant = published_model(workshop).variants.get()
    item = _sale_item(workshop, variant)
    variant.refresh_from_db()
    assert variant.availability == BoardVariant.Availability.IN_STOCK

    complaint_id = complain(make_client(), "inventory_item", item.pk)
    resolve(mod_client, complaint_id)
    variant.refresh_from_db()
    assert variant.availability == BoardVariant.Availability.OUT_OF_STOCK

    grant_appeal(make_client(workshop.owner), mod_client, complaint_id)
    variant.refresh_from_db()
    assert variant.availability == BoardVariant.Availability.IN_STOCK


def test_completed_sale_inquiry_marks_item_sold_and_refreshes_availability(make_client):
    workshop = workshop_for()
    variant = published_model(workshop).variants.get()
    item = _sale_item(workshop, variant)
    customer = make_client()
    created = customer.post("/api/v1/inquiries", {"kind": "board_purchase", "target_type": "inventory_item",
                                                 "target_id": str(item.pk), "message": "Беру!"}, format="json")
    assert created.status_code == 201, created.content
    inquiry_id = created.json()["id"]
    shaper = make_client(workshop.owner)
    assert shaper.post(f"/api/v1/inquiries/{inquiry_id}/accept", {}, format="json").status_code == 200
    done = shaper.post(f"/api/v1/inquiries/{inquiry_id}/complete", {"agreed_amount": str(variant.price),
                                                                      "amount_confirmed": True}, format="json")
    assert done.status_code == 200, done.content
    item.refresh_from_db()
    variant.refresh_from_db()
    assert Inquiry.objects.get(pk=inquiry_id).status == Inquiry.Status.COMPLETED
    assert item.status == InventoryItem.Status.SOLD
    assert variant.availability == BoardVariant.Availability.OUT_OF_STOCK


def test_stock_quantity_bulk_operations_keep_availability_in_sync(make_client):
    workshop = workshop_for()
    model = published_model(workshop)
    variant = model.variants.get()
    client = make_client(workshop.owner)
    url = f"/api/v1/models/{model.pk}/variants/{variant.pk}"
    assert client.patch(url, {"in_stock_quantity": 2}, format="json").status_code == 200
    variant.refresh_from_db()
    assert variant.availability == BoardVariant.Availability.IN_STOCK
    assert client.patch(url, {"in_stock_quantity": 0}, format="json").status_code == 200
    variant.refresh_from_db()
    assert variant.availability == BoardVariant.Availability.OUT_OF_STOCK
