"""Публичный каталог аренды (RENT-01/05, 8.5): свободные экземпляры, занятые интервалы без данных клиентов."""
import datetime as dt
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.commerce.models import Booking
from apps.inventory.models import InventoryItem, InventoryItemPhoto
from apps.organizations.models import Organization
from tests.factories import AccountFactory, InventoryItemFactory, OrganizationFactory, RegionFactory, SpotFactory

from apps.boards.tests.helpers import photo, published_model, rental_booking, workshop_for

pytestmark = pytest.mark.django_db


def ids(response):
    assert response.status_code == 200, response.json()
    return {r["id"] for r in response.json()["results"]}


def test_guest_sees_published_rental_items_only(api_client):
    visible = InventoryItemFactory()
    both = InventoryItemFactory(purpose=InventoryItem.Purpose.BOTH)
    InventoryItemFactory(purpose=InventoryItem.Purpose.SALE)
    InventoryItemFactory(status=InventoryItem.Status.MAINTENANCE)
    InventoryItemFactory(status=InventoryItem.Status.RETIRED)
    InventoryItemFactory(status=InventoryItem.Status.SOLD)
    InventoryItemFactory(is_published=False)
    deleted_owner = AccountFactory(anonymized_at=timezone.now())
    InventoryItemFactory(owner_account=deleted_owner)
    draft_org = OrganizationFactory(status=Organization.Status.DRAFT)
    InventoryItemFactory(owner_account=None, owner_organization=draft_org)
    assert ids(api_client.get("/api/v1/rentals")) == {str(visible.pk), str(both.pk)}


def test_rental_card_shape_for_account_and_organization_owners(api_client):
    region = RegionFactory()
    spot = SpotFactory(region=region)
    person_item = InventoryItemFactory(
        kind=InventoryItem.Kind.WETSUIT, size="M", condition=InventoryItem.Condition.EXCELLENT, region=region,
        spot=spot, pickup_location="Халактырский пляж", available_hours="09:00–20:00",
        rental_price_per_hour=Decimal("500"), deposit_note="Залог 5000 ₽",
    )
    InventoryItemPhoto.objects.create(item=person_item, media=photo(person_item.owner_account, purpose="item_photo"))
    school = OrganizationFactory(name="Школа Волна")
    org_item = InventoryItemFactory(owner_account=None, owner_organization=school)
    results = {r["id"]: r for r in api_client.get("/api/v1/rentals").json()["results"]}
    card = results[str(person_item.pk)]
    assert card["kind"] == "wetsuit" and card["kind_label"] == "Гидрокостюм"
    assert card["condition_label"] == "Отличное" and card["size"] == "M"
    assert card["region"]["id"] == region.pk and card["spot"]["slug"] == spot.slug
    assert card["rental_price_per_day"] == "2500.00" and card["rental_price_per_hour"] == "500.00"
    assert card["deposit_note"] == "Залог 5000 ₽" and card["currency"] == "RUB"
    assert card["cover"]["purpose"] == "item_photo" and card["photos_count"] == 1
    assert card["owner"]["type"] == "account" and card["owner"]["handle"]
    assert "email" not in card["owner"]
    org_card = results[str(org_item.pk)]
    assert org_card["owner"] == {"type": "organization", "id": str(school.pk), "name": "Школа Волна", "handle": None,
                                 "slug": school.slug, "kind": "school", "avatar": None}
    assert org_card["variant"] is None and org_card["is_own"] is False


def test_board_item_shows_variant_short_info(api_client):
    workshop = workshop_for()
    variant = published_model(workshop, variants=[{"length_in": Decimal("70"), "width_in": Decimal("20.5")}]).variants.get()
    item = InventoryItemFactory(owner_account=None, owner_organization=workshop, variant=variant)
    card = api_client.get(f"/api/v1/rentals/{item.pk}").json()
    assert card["variant"]["sku"] == variant.sku
    assert card["variant"]["dimensions_display"].startswith("5'10\" × 20 1/2\"")
    assert card["variant"]["shaper"]["slug"] == workshop.slug


def test_filters_kind_region_spot_price_q(api_client):
    region = RegionFactory(slug="kamchatka")
    spot = SpotFactory(region=region, slug="khalaktyr")
    board = InventoryItemFactory(region=region, spot=spot, title="Софттоп 8'0", rental_price_per_day=Decimal("2000"))
    suit = InventoryItemFactory(kind="wetsuit", title="Гидрокостюм 5/4", rental_price_per_day=Decimal("1500"))
    hourly = InventoryItemFactory(title="SUP", kind="sup", rental_price_per_day=None,
                                  rental_price_per_hour=Decimal("700"))
    assert ids(api_client.get("/api/v1/rentals?kind=wetsuit")) == {str(suit.pk)}
    assert ids(api_client.get("/api/v1/rentals?kind=wetsuit,sup")) == {str(suit.pk), str(hourly.pk)}
    assert ids(api_client.get("/api/v1/rentals?region=kamchatka")) == {str(board.pk)}
    assert ids(api_client.get(f"/api/v1/rentals?spot={spot.slug}")) == {str(board.pk)}
    assert ids(api_client.get("/api/v1/rentals?price_max=1600")) == {str(suit.pk), str(hourly.pk)}
    assert ids(api_client.get("/api/v1/rentals?q=софттоп")) == {str(board.pk)}


def test_filter_by_owner_organization(api_client):
    school = OrganizationFactory()
    mine = InventoryItemFactory(owner_account=None, owner_organization=school)
    InventoryItemFactory()
    assert ids(api_client.get(f"/api/v1/rentals?organization={school.slug}")) == {str(mine.pk)}
    assert ids(api_client.get(f"/api/v1/rentals?organization={school.pk}")) == {str(mine.pk)}


def test_period_filter_hides_items_with_confirmed_overlap_only(api_client):
    """RENT-05: при from/to — только свободные; запросы и отмены не занимают экземпляр."""
    start = timezone.now().replace(microsecond=0) + dt.timedelta(days=2)
    busy = InventoryItemFactory()
    issued = InventoryItemFactory()
    requested = InventoryItemFactory()
    free = InventoryItemFactory()
    rental_booking(busy, start=start, hours=4)
    rental_booking(issued, start=start - dt.timedelta(hours=2), hours=3, status=Booking.Status.IN_PROGRESS)
    rental_booking(requested, start=start, status=Booking.Status.REQUESTED)
    rental_booking(free, start=start + dt.timedelta(hours=5), hours=2)
    params = {"from": start.isoformat(), "to": (start + dt.timedelta(hours=4)).isoformat()}
    assert ids(api_client.get("/api/v1/rentals", params)) == {str(requested.pk), str(free.pk)}
    by_day = {"from": (start + dt.timedelta(days=3)).date().isoformat(),
              "to": (start + dt.timedelta(days=3)).date().isoformat()}
    assert len(ids(api_client.get("/api/v1/rentals", by_day))) == 4


def test_period_validation(api_client):
    assert api_client.get("/api/v1/rentals?from=2026-11-02").status_code == 400
    assert api_client.get("/api/v1/rentals?from=2026-11-05&to=2026-11-01").status_code == 400
    assert api_client.get("/api/v1/rentals?from=завтра&to=потом").status_code == 400


def test_detail_shows_booked_intervals_without_customer_data(api_client):
    item = InventoryItemFactory(restrictions="Только опытным райдерам", description="Отличная доска")
    customer = AccountFactory(email="secret-customer@example.com")
    booking = rental_booking(item, customer=customer)
    rental_booking(item, status=Booking.Status.CANCELLED, start=booking.ends_at + dt.timedelta(hours=1))
    response = api_client.get(f"/api/v1/rentals/{item.pk}")
    assert response.status_code == 200
    data = response.json()
    assert data["restrictions"] == "Только опытным райдерам"
    assert len(data["booked_intervals"]) == 1
    assert set(data["booked_intervals"][0]) == {"starts_at", "ends_at"}
    assert "secret-customer" not in response.content.decode()


def test_detail_404_for_hidden_items(api_client):
    item = InventoryItemFactory(status=InventoryItem.Status.MAINTENANCE)
    assert api_client.get(f"/api/v1/rentals/{item.pk}").status_code == 404


def test_is_own_for_owner_and_org_staff(make_client):
    item = InventoryItemFactory()
    school = OrganizationFactory()
    org_item = InventoryItemFactory(owner_account=None, owner_organization=school)
    assert make_client(item.owner_account).get(f"/api/v1/rentals/{item.pk}").json()["is_own"] is True
    assert make_client(school.owner).get(f"/api/v1/rentals/{org_item.pk}").json()["is_own"] is True
    assert make_client().get(f"/api/v1/rentals/{item.pk}").json()["is_own"] is False


def test_rentals_list_has_no_n_plus_one(api_client):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    def count():
        with CaptureQueriesContext(connection) as ctx:
            assert api_client.get("/api/v1/rentals").status_code == 200
        return len(ctx.captured_queries)

    InventoryItemFactory()
    before = count()
    workshop = workshop_for()
    variant = published_model(workshop).variants.get()
    for _ in range(4):
        item = InventoryItemFactory()
        InventoryItemPhoto.objects.create(item=item, media=photo(item.owner_account, purpose="item_photo"))
        InventoryItemFactory(owner_account=None, owner_organization=OrganizationFactory())
        InventoryItemFactory(owner_account=None, owner_organization=workshop, variant=variant)
    assert count() == before
