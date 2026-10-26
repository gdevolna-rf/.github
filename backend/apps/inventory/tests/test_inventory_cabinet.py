"""Кабинет инвентаря (RENT-02/03/04): права владельца, сотрудники организаций, фото, статусы, доступность."""
import datetime as dt
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.accounts.models import Specialty
from apps.commerce.models import Booking
from apps.inventory.models import InventoryItem, InventoryItemPhoto
from tests.factories import (AccountFactory, InventoryItemFactory, OrganizationFactory, RegionFactory, SpotFactory,
                             add_member, add_specialty)

from apps.boards.tests.helpers import inquiry_for, photo, published_model, rental_booking, workshop_for

pytestmark = pytest.mark.django_db

URL = "/api/v1/me/inventory"


def renter():
    account = AccountFactory()
    add_specialty(account, Specialty.RENTAL)
    return account


def payload(**extra):
    return {"title": "Софттоп 8'0", "kind": "board", "purpose": "rental", "rental_price_per_day": "2500",
            "condition": "good", **extra}


def test_guest_cannot_use_cabinet(api_client):
    assert api_client.get(URL).status_code == 401
    assert api_client.post(URL, payload(), format="json").status_code == 401


def test_personal_item_requires_rental_specialty(make_client):
    response = make_client(AccountFactory()).post(URL, payload(), format="json")
    assert response.status_code == 403 and response.json()["error"]["code"] == "specialty_required"


def test_renter_creates_personal_item_with_photos(make_client):
    account = renter()
    region = RegionFactory()
    spot = SpotFactory(region=region)
    assets = [photo(account, purpose="item_photo") for _ in range(2)]
    response = make_client(account).post(URL, payload(spot_id=str(spot.pk), pickup_location="Пляж",
                                                      photo_ids=[str(a.pk) for a in assets]), format="json")
    assert response.status_code == 201, response.json()
    data = response.json()
    assert data["owner"]["type"] == "account" and data["organization_id"] is None
    assert data["region"]["id"] == region.pk  # регион подставлен по споту
    assert data["status"] == "available" and data["is_published"] is True
    assert [p["media"]["id"] for p in data["photos"]] == [str(a.pk) for a in assets]


def test_rental_purpose_requires_price_and_spot_region_must_match(make_client):
    client = make_client(renter())
    response = client.post(URL, payload(rental_price_per_day=None), format="json")
    assert response.status_code == 400 and "rental_price_per_day" in response.json()["error"]["fields"]
    response = client.post(URL, payload(region_id=RegionFactory().pk, spot_id=str(SpotFactory().pk)), format="json")
    assert response.status_code == 400 and "spot_id" in response.json()["error"]["fields"]


def test_org_staff_of_any_role_can_add_school_equipment_without_rental_specialty(make_client):
    """RENT-02: школы публикуют оборудование; нужен лишь активный член организации."""
    school = OrganizationFactory()
    instructor = AccountFactory()
    add_member(school, instructor, role="instructor")
    response = make_client(instructor).post(URL, payload(organization_id=str(school.pk)), format="json")
    assert response.status_code == 201
    assert response.json()["owner"]["type"] == "organization" and response.json()["organization_id"] == str(school.pk)
    stranger = make_client(renter()).post(URL, payload(organization_id=str(school.pk)), format="json")
    assert stranger.status_code == 403 and stranger.json()["error"]["code"] == "not_org_member"


def test_list_separates_personal_and_organization_inventory(make_client):
    account = renter()
    school = OrganizationFactory(owner=account)
    personal = InventoryItemFactory(owner_account=account)
    school_item = InventoryItemFactory(owner_account=None, owner_organization=school)
    InventoryItemFactory()
    client = make_client(account)
    assert {r["id"] for r in client.get(URL).json()["results"]} == {str(personal.pk)}
    assert {r["id"] for r in client.get(f"{URL}?organization={school.pk}").json()["results"]} == {str(school_item.pk)}
    foreign_org = OrganizationFactory()
    assert client.get(f"{URL}?organization={foreign_org.pk}").status_code == 403


def test_foreign_items_are_not_found(make_client):
    item = InventoryItemFactory()
    client = make_client(renter())
    assert client.get(f"{URL}/{item.pk}").status_code == 404
    assert client.patch(f"{URL}/{item.pk}", {"title": "Взлом"}, format="json").status_code == 404
    assert client.delete(f"{URL}/{item.pk}").status_code == 404
    item.refresh_from_db()
    assert item.title != "Взлом"


def test_update_item_and_owner_cannot_change(make_client):
    account = renter()
    item = InventoryItemFactory(owner_account=account)
    school = OrganizationFactory(owner=account)
    response = make_client(account).patch(f"{URL}/{item.pk}", {"title": "Новое", "is_published": False,
                                                               "organization_id": str(school.pk)}, format="json")
    assert response.status_code == 200
    item.refresh_from_db()
    assert item.title == "Новое" and item.is_published is False and item.owner_account == account
    assert item.owner_organization is None


def test_link_variant_of_own_workshop_refreshes_availability(make_client):
    workshop = workshop_for()
    variant = published_model(workshop, variants=[{"made_to_order_days": None}]).variants.get()
    client = make_client(workshop.owner)
    response = client.post(URL, payload(organization_id=str(workshop.pk), variant_id=str(variant.pk), title="",
                                        purpose="sale", rental_price_per_day=None, sale_price="60000"), format="json")
    assert response.status_code == 201, response.json()
    data = response.json()
    assert data["variant"]["id"] == str(variant.pk)
    assert data["title"] == variant.model.name and data["size"].startswith("5'10\"")
    variant.refresh_from_db()
    assert variant.availability == "in_stock"
    client.post(f"{URL}/{data['id']}/status", {"status": "sold"}, format="json")
    variant.refresh_from_db()
    assert variant.availability == "out_of_stock"


def test_cannot_link_foreign_variant(make_client):
    foreign_variant = published_model(workshop_for()).variants.get()
    response = make_client(renter()).post(URL, payload(variant_id=str(foreign_variant.pk)), format="json")
    assert response.status_code == 400 and response.json()["error"]["code"] == "variant_invalid"


def test_status_changes_and_active_booking_guard(make_client):
    account = renter()
    item = InventoryItemFactory(owner_account=account)
    client = make_client(account)
    url = f"{URL}/{item.pk}/status"
    assert client.post(url, {"status": "maintenance"}, format="json").json()["status"] == "maintenance"
    assert client.post(url, {"status": "available"}, format="json").json()["status"] == "available"
    assert client.post(url, {"status": "reserved"}, format="json").status_code == 400
    rental_booking(item)
    blocked = client.post(url, {"status": "retired"}, format="json")
    assert blocked.status_code == 409 and blocked.json()["error"]["code"] == "item_has_active_bookings"


def test_sold_item_is_terminal(make_client):
    account = renter()
    item = InventoryItemFactory(owner_account=account, status=InventoryItem.Status.SOLD)
    response = make_client(account).post(f"{URL}/{item.pk}/status", {"status": "available"}, format="json")
    assert response.status_code == 409 and response.json()["error"]["code"] == "item_sold"


def test_delete_without_history_and_retire_with_history(make_client):
    account = renter()
    client = make_client(account)
    fresh = InventoryItemFactory(owner_account=account)
    assert client.delete(f"{URL}/{fresh.pk}").json() == {"result": "deleted"}
    assert not InventoryItem.objects.filter(pk=fresh.pk).exists()
    used = InventoryItemFactory(owner_account=account)
    rental_booking(used, status=Booking.Status.COMPLETED, start=timezone.now() - dt.timedelta(days=3))
    assert client.delete(f"{URL}/{used.pk}").json() == {"result": "retired"}
    used.refresh_from_db()
    assert used.status == "retired" and used.is_published is False


def test_photos_limit_order_and_delete(make_client):
    account = renter()
    item = InventoryItemFactory(owner_account=account)
    client = make_client(account)
    url = f"{URL}/{item.pk}/photos"
    photos = client.post(url, {"media_ids": [str(photo(account, purpose="item_photo").pk) for _ in range(10)]},
                         format="json").json()["photos"]
    assert len(photos) == 10
    over = client.post(url, {"media_ids": [str(photo(account, purpose="item_photo").pk)]}, format="json")
    assert over.status_code == 409 and over.json()["error"]["code"] == "photo_limit"
    wrong = InventoryItemFactory(owner_account=account)
    bad_purpose = client.post(f"{URL}/{wrong.pk}/photos", {"media_ids": [str(photo(account).pk)]}, format="json")
    assert bad_purpose.status_code == 400 and bad_purpose.json()["error"]["code"] == "media_purpose"
    order = [p["id"] for p in reversed(photos)]
    data = client.put(f"{url}/order", {"ids": order}, format="json").json()["photos"]
    assert [p["id"] for p in data] == order
    data = client.delete(f"{url}/{order[0]}").json()["photos"]
    assert len(data) == 9 and [p["position"] for p in data] == list(range(9))
    assert InventoryItemPhoto.objects.filter(item=item).count() == 9


def test_availability_summary_free_and_booked(make_client):
    """RENT-03/04: «Свободных бордов» / «Забронировано» и занятые интервалы по каждому экземпляру."""
    account = renter()
    now = timezone.now().replace(microsecond=0)
    booked_now = InventoryItemFactory(owner_account=account, title="A")
    booked_later = InventoryItemFactory(owner_account=account, title="B")
    InventoryItemFactory(owner_account=account, title="C")
    InventoryItemFactory(owner_account=account, title="D", status=InventoryItem.Status.MAINTENANCE)
    InventoryItemFactory(owner_account=account, title="E", status=InventoryItem.Status.RETIRED)
    InventoryItemFactory(owner_account=account, title="F", purpose="sale")
    rental_booking(booked_now, start=now - dt.timedelta(hours=1), hours=3, status=Booking.Status.IN_PROGRESS)
    rental_booking(booked_later, start=now + dt.timedelta(hours=30), hours=4)
    client = make_client(account)
    data = client.get(f"{URL}/availability").json()
    assert data["summary"] == {"total": 4, "free_now": 2, "booked_now": 1, "maintenance": 1, "free_in_range": 2,
                               "booked_in_range": 1}
    rows = {r["title"]: r for r in data["items"]}
    assert rows["A"]["is_booked_now"] is True and len(rows["A"]["booked"]) == 1
    assert rows["B"]["booked"] == []
    params = {"from": (now + dt.timedelta(days=1)).isoformat(), "to": (now + dt.timedelta(days=2)).isoformat()}
    ranged = client.get(f"{URL}/availability", params).json()
    assert ranged["summary"]["booked_in_range"] == 1 and ranged["summary"]["booked_now"] == 1
    assert len({r["title"]: r for r in ranged["items"]}["B"]["booked"]) == 1


def test_availability_for_organization_requires_membership(make_client):
    school = OrganizationFactory()
    InventoryItemFactory(owner_account=None, owner_organization=school, kind="board")
    InventoryItemFactory(owner_account=None, owner_organization=school, kind="wetsuit")
    data = make_client(school.owner).get(f"{URL}/availability?organization={school.pk}&kind=board").json()
    assert data["summary"]["total"] == 1
    assert make_client().get(f"{URL}/availability?organization={school.pk}").status_code == 403


def test_inquiry_history_prevents_hard_delete(make_client):
    workshop = workshop_for()
    variant = published_model(workshop).variants.get()
    item = InventoryItemFactory(owner_account=None, owner_organization=workshop, variant=variant, purpose="sale",
                                rental_price_per_day=Decimal("1"))
    inquiry = inquiry_for(variant)
    inquiry.inventory_item = item
    inquiry.save()
    assert make_client(workshop.owner).delete(f"{URL}/{item.pk}").json() == {"result": "retired"}
