"""Варианты: серверный SKU (BRD-05, ATX-08), версии при заказах (F10, BRD-06), таблица (BRD-12), наличие (BRD-13)."""
from decimal import Decimal

import pytest

from apps.boards.models import BoardMedia, BoardModel, BoardVariant
from apps.inventory.models import InventoryItem
from apps.trust.models import AuditEvent
from tests.factories import InventoryItemFactory

from .helpers import inquiry_for, photo, published_model, rental_booking, shaper_account, std_type, workshop_for

pytestmark = pytest.mark.django_db


def make_model(client, workshop, type_code="fish", **extra):
    response = client.post(f"/api/v1/workshops/{workshop.pk}/models",
                           {"name": "Pacific Fish", "board_type_id": std_type(type_code).pk, **extra}, format="json")
    assert response.status_code == 201, response.json()
    return response.json()["id"]


def variants_url(model_id):
    return f"/api/v1/models/{model_id}/variants"


def test_sku_is_generated_by_server_and_human_readable(make_client):
    workshop = workshop_for()
    client = make_client(workshop.owner)
    model_id = make_model(client, workshop)
    response = client.post(variants_url(model_id), {"length": "5'10\"", "width": "20.5", "sku": "HACK"}, format="json")
    assert response.status_code == 201
    data = response.json()
    assert data["sku"] == f"GV-{workshop.workshop.shaper_code}-FSH-5P10-W2050-001"
    assert data["version"] == 1 and data["is_active"] is True and data["versioned"] is False
    assert data["availability"] == "out_of_stock"


def test_duplicate_sku_is_rejected_and_model_uuid_unchanged(make_client):
    """ATX-08: двойной SKU отклоняется сервером (409 sku_conflict); UUID модели неизменен."""
    workshop = workshop_for()
    client = make_client(workshop.owner)
    model_id = make_model(client, workshop)
    payload = {"length_in": "70", "width_in": "20.5", "material_id": None}
    assert client.post(variants_url(model_id), payload, format="json").status_code == 201
    response = client.post(variants_url(model_id), payload, format="json")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "sku_conflict"
    assert "sku_suffix" in response.json()["error"]["fields"]
    assert BoardModel.objects.filter(pk=model_id).exists()
    assert BoardVariant.objects.filter(model_id=model_id).count() == 1
    with_suffix = client.post(variants_url(model_id), {**payload, "sku_suffix": "eps"}, format="json")
    assert with_suffix.status_code == 201 and with_suffix.json()["sku"].endswith("-001-EPS")
    assert client.get(f"/api/v1/models/{model_id}").json()["id"] == model_id


def test_variant_validation_errors(make_client):
    workshop = workshop_for()
    client = make_client(workshop.owner)
    model_id = make_model(client, workshop)
    response = client.post(variants_url(model_id), {"length_in": "70", "width_in": "20", "price": "-1"}, format="json")
    assert response.status_code == 400 and "price" in response.json()["error"]["fields"]
    response = client.post(variants_url(model_id), {"width_in": "60"}, format="json")
    assert response.status_code == 400
    assert {"length_in", "width_in"} <= set(response.json()["error"]["fields"])
    bad_suffix = client.post(variants_url(model_id), {"length_in": "70", "width_in": "20", "sku_suffix": "эпокси"},
                             format="json")
    assert bad_suffix.status_code == 400 and "sku_suffix" in bad_suffix.json()["error"]["fields"]
    foreign_material = client.post(variants_url(model_id), {"length_in": "70", "width_in": "20", "material_id": 99999},
                                   format="json")
    assert foreign_material.status_code == 400 and foreign_material.json()["error"]["code"] == "material_invalid"


def test_edit_dimensions_without_orders_updates_in_place(make_client):
    workshop = workshop_for()
    client = make_client(workshop.owner)
    model_id = make_model(client, workshop)
    created = client.post(variants_url(model_id), {"length_in": "70", "width_in": "20.5"}, format="json").json()
    response = client.patch(f"{variants_url(model_id)}/{created['id']}", {"length": "5'11"}, format="json")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == created["id"] and data["versioned"] is False and data["version"] == 1
    assert "-5P11-" in data["sku"] and data["sku"].endswith("-001")


def test_edit_dimensions_with_inquiry_creates_new_version(make_client):
    """F10: прошлые заказы сохраняют ссылку и снимок, новая версия получает новый UUID и артикул -V2."""
    workshop = workshop_for()
    client = make_client(workshop.owner)
    model_id = make_model(client, workshop)
    created = client.post(variants_url(model_id), {"length_in": "70", "width_in": "20.5", "price": "60000"},
                          format="json").json()
    old = BoardVariant.objects.get(pk=created["id"])
    BoardMedia.objects.create(model_id=model_id, variant=old, media=photo(workshop.owner), position=0, is_cover=True)
    free_item = InventoryItemFactory(owner_account=None, owner_organization=workshop, variant=old, purpose="sale")
    inquiry = inquiry_for(old)

    response = client.patch(f"{variants_url(model_id)}/{old.pk}", {"length_in": "71", "price": "62000"}, format="json")
    assert response.status_code == 200
    data = response.json()
    assert data["versioned"] is True and data["id"] != str(old.pk)
    assert data["version"] == 2 and data["previous_version_id"] == str(old.pk)
    assert data["sku"].endswith("-V2") and "-5P11-" in data["sku"]
    assert data["price"] == "62000.00"
    old.refresh_from_db()
    assert old.is_active is False and old.sku == created["sku"] and old.length_in == Decimal("70")
    inquiry.refresh_from_db()
    assert inquiry.board_variant_id == old.pk and inquiry.object_snapshot["sku"] == created["sku"]
    assert BoardMedia.objects.filter(variant_id=data["id"]).count() == 1  # фото варианта переехали
    free_item.refresh_from_db()
    assert str(free_item.variant_id) == data["id"]  # свободный склад — к актуальной версии
    assert AuditEvent.objects.filter(action="board_variant.versioned", object_id=data["id"]).exists()
    # Модель — та же (UUID модели не меняется)
    assert client.get(f"/api/v1/models/{model_id}").json()["id"] == model_id
    # Архивную версию изменить по размерам нельзя
    again = client.patch(f"{variants_url(model_id)}/{old.pk}", {"length_in": "72"}, format="json")
    assert again.status_code == 409 and again.json()["error"]["code"] == "variant_archived"


def test_booked_item_stays_with_old_version(make_client):
    workshop = workshop_for()
    client = make_client(workshop.owner)
    model_id = make_model(client, workshop)
    created = client.post(variants_url(model_id), {"length_in": "70", "width_in": "20.5"}, format="json").json()
    old = BoardVariant.objects.get(pk=created["id"])
    item = InventoryItemFactory(owner_account=None, owner_organization=workshop, variant=old)
    rental_booking(item)
    data = client.patch(f"{variants_url(model_id)}/{old.pk}", {"material_id": None, "construction": "EPS"},
                        format="json").json()
    assert data["versioned"] is True
    item.refresh_from_db()
    assert item.variant_id == old.pk


def test_price_change_with_history_stays_in_place(make_client):
    workshop = workshop_for()
    client = make_client(workshop.owner)
    model_id = make_model(client, workshop)
    created = client.post(variants_url(model_id), {"length_in": "70", "width_in": "20.5"}, format="json").json()
    inquiry_for(BoardVariant.objects.get(pk=created["id"]))
    data = client.patch(f"{variants_url(model_id)}/{created['id']}", {"price": "70000", "made_to_order_days": 21},
                        format="json").json()
    assert data["id"] == created["id"] and data["versioned"] is False
    assert data["availability"] == "made_to_order" and data["has_orders"] is True


def test_in_stock_quantity_drives_availability(make_client):
    """BRD-13: «В наличии» — по реальным экземплярам на продажу."""
    workshop = workshop_for()
    client = make_client(workshop.owner)
    model_id = make_model(client, workshop)
    created = client.post(variants_url(model_id), {"length_in": "70", "width_in": "20.5", "price": "60000",
                                                   "in_stock_quantity": 2}, format="json").json()
    assert created["availability"] == "in_stock" and created["items_available_for_sale"] == 2
    items = InventoryItem.objects.filter(variant_id=created["id"])
    assert items.count() == 2 and {i.purpose for i in items} == {"sale"}
    assert all(i.owner_organization_id == workshop.pk for i in items)
    data = client.patch(f"{variants_url(model_id)}/{created['id']}", {"in_stock_quantity": 0, "made_to_order_days": 14},
                        format="json").json()
    assert data["availability"] == "made_to_order" and data["items_available_for_sale"] == 0
    assert not InventoryItem.objects.filter(variant_id=created["id"]).exists()


def test_delete_variant_without_history_and_deactivate_with_items(make_client):
    workshop = workshop_for()
    client = make_client(workshop.owner)
    model_id = make_model(client, workshop)
    a = client.post(variants_url(model_id), {"length_in": "70", "width_in": "20"}, format="json").json()
    b = client.post(variants_url(model_id), {"length_in": "72", "width_in": "20"}, format="json").json()
    assert client.delete(f"{variants_url(model_id)}/{a['id']}").json() == {"result": "deleted"}
    InventoryItemFactory(owner_account=None, owner_organization=workshop, variant_id=b["id"])
    assert client.delete(f"{variants_url(model_id)}/{b['id']}").json() == {"result": "deactivated"}
    assert BoardVariant.objects.get(pk=b["id"]).is_active is False
    assert client.get(variants_url(model_id)).json() == []
    assert len(client.get(variants_url(model_id) + "?include_inactive=1").json()) == 1


def test_published_model_keeps_at_least_one_active_variant(make_client):
    workshop = workshop_for()
    model = published_model(workshop)
    only = model.variants.get()
    client = make_client(workshop.owner)
    response = client.delete(f"{variants_url(model.pk)}/{only.pk}")
    assert response.status_code == 409 and response.json()["error"]["code"] == "last_active_variant"
    response = client.patch(f"{variants_url(model.pk)}/{only.pk}", {"is_active": False}, format="json")
    assert response.status_code == 409


def test_foreign_shaper_cannot_touch_variants(make_client):
    workshop = workshop_for()
    model = published_model(workshop)
    v = model.variants.get()
    client = make_client(shaper_account())
    assert client.get(variants_url(model.pk)).status_code == 404
    assert client.post(variants_url(model.pk), {"length_in": "70", "width_in": "20"}, format="json").status_code == 404
    assert client.patch(f"{variants_url(model.pk)}/{v.pk}", {"price": "1"}, format="json").status_code == 404
    other_model = published_model(workshop_for())
    own = make_client(workshop.owner)
    assert own.get(f"{variants_url(other_model.pk)}/{v.pk}").status_code == 404


def test_bulk_update_all_or_nothing(make_client):
    """BRD-12: одна ошибка — ничего не меняется; чужой вариант — ошибка."""
    workshop = workshop_for()
    model = published_model(workshop, variants=[{"length_in": Decimal("70")}, {"length_in": Decimal("72")}])
    a, b = model.variants.order_by("length_in")
    foreign = published_model(workshop_for()).variants.get()
    client = make_client(workshop.owner)
    url = f"/api/v1/workshops/{workshop.pk}/variants/bulk"

    bad = client.patch(url, {"items": [{"id": str(a.pk), "price": "100"}, {"id": str(b.pk), "price": "-5"}]},
                       format="json")
    assert bad.status_code == 400 and "items.1.price" in bad.json()["error"]["fields"]
    alien = client.patch(url, {"items": [{"id": str(a.pk), "price": "100"}, {"id": str(foreign.pk), "price": "1"}]},
                         format="json")
    assert alien.status_code == 400 and "items.1.id" in alien.json()["error"]["fields"]
    a.refresh_from_db()
    assert a.price == Decimal("65000")

    ok = client.patch(url, {"items": [
        {"id": str(a.pk), "price": "55000", "made_to_order_days": 20},
        {"id": str(b.pk), "is_active": False},
    ]}, format="json")
    assert ok.status_code == 200 and ok.json()["updated"] == 2
    a.refresh_from_db()
    b.refresh_from_db()
    assert a.price == Decimal("55000") and a.availability == "made_to_order" and b.is_active is False
    all_off = client.patch(url, {"items": [{"id": str(a.pk), "is_active": False}]}, format="json")
    assert all_off.status_code == 409 and all_off.json()["error"]["code"] == "last_active_variant"


def test_bulk_requires_membership(make_client):
    workshop = workshop_for()
    v = published_model(workshop).variants.get()
    response = make_client(shaper_account()).patch(f"/api/v1/workshops/{workshop.pk}/variants/bulk",
                                                   {"items": [{"id": str(v.pk), "price": "1"}]}, format="json")
    assert response.status_code == 403


def test_bulk_rejects_empty_or_malformed_payload(make_client):
    workshop = workshop_for()
    client = make_client(workshop.owner)
    url = f"/api/v1/workshops/{workshop.pk}/variants/bulk"
    empty = client.patch(url, {"items": []}, format="json")
    assert empty.status_code == 400 and "items" in empty.json()["error"]["fields"]
    missing = client.patch(url, {}, format="json")
    assert missing.status_code == 400 and "items" in missing.json()["error"]["fields"]
    bad_id = client.patch(url, {"items": [{"id": "not-a-uuid"}]}, format="json")
    assert bad_id.status_code == 400 and "items.0.id" in bad_id.json()["error"]["fields"]
