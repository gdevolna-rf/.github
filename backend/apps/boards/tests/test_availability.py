"""BRD-13: «В наличии / Под заказ / Нет в наличии» следуют за реальными экземплярами."""
from decimal import Decimal

import pytest

from apps.boards.models import BoardVariant
from apps.boards.services.availability import best_availability, refresh_variant_availability
from apps.inventory.models import InventoryItem
from tests.factories import InventoryItemFactory

from .helpers import published_model, variant, workshop_for

pytestmark = pytest.mark.django_db


def test_sale_item_lifecycle_updates_variant_availability():
    workshop = workshop_for()
    model = published_model(workshop, variants=[{"made_to_order_days": None}])
    v = model.variants.get()
    refresh_variant_availability(v)
    assert v.availability == BoardVariant.Availability.OUT_OF_STOCK

    item = InventoryItemFactory(owner_account=None, owner_organization=workshop, variant=v,
                                purpose=InventoryItem.Purpose.SALE)
    v.refresh_from_db()
    assert v.availability == BoardVariant.Availability.IN_STOCK

    item.status = InventoryItem.Status.SOLD
    item.save()
    v.refresh_from_db()
    assert v.availability == BoardVariant.Availability.OUT_OF_STOCK

    v.made_to_order_days = 30
    v.save()
    refresh_variant_availability(v)
    assert v.availability == BoardVariant.Availability.MADE_TO_ORDER


def test_rental_only_and_unpublished_items_do_not_count_as_stock():
    workshop = workshop_for()
    v = published_model(workshop).variants.get()
    InventoryItemFactory(owner_account=None, owner_organization=workshop, variant=v,
                         purpose=InventoryItem.Purpose.RENTAL)
    InventoryItemFactory(owner_account=None, owner_organization=workshop, variant=v,
                         purpose=InventoryItem.Purpose.SALE, is_published=False)
    v.refresh_from_db()
    assert v.availability != BoardVariant.Availability.IN_STOCK


def test_relinking_and_deleting_items_refresh_both_variants():
    workshop = workshop_for()
    model = published_model(workshop, variants=[{"length_in": Decimal("70")}, {"length_in": Decimal("72")}])
    a, b = model.variants.order_by("length_in")
    item = InventoryItemFactory(owner_account=None, owner_organization=workshop, variant=a, purpose="both")
    a.refresh_from_db()
    assert a.availability == "in_stock"
    item = InventoryItem.objects.get(pk=item.pk)
    item.variant = b
    item.save()
    a.refresh_from_db()
    b.refresh_from_db()
    assert a.availability != "in_stock" and b.availability == "in_stock"
    item.delete()
    b.refresh_from_db()
    assert b.availability != "in_stock"


def test_best_availability_order():
    assert best_availability(["out_of_stock", "made_to_order"]) == "made_to_order"
    assert best_availability(["made_to_order", "in_stock"]) == "in_stock"
    assert best_availability([]) == "out_of_stock"


def test_catalog_card_shows_best_availability(api_client):
    workshop = workshop_for()
    model = published_model(workshop, variants=[{"length_in": Decimal("70")}, {"length_in": Decimal("72")}])
    second = model.variants.order_by("length_in").last()
    InventoryItemFactory(owner_account=None, owner_organization=workshop, variant=second, purpose="sale")
    variant(model, length_in=Decimal("80"), is_active=False, availability="in_stock")
    card = api_client.get("/api/v1/boards").json()["results"][0]
    assert card["availability"] == "in_stock"
