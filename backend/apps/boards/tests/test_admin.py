"""Django Admin для boards/inventory: списки и формы открываются, правки через админку не ломают инварианты."""
import pytest
from django.test import Client

from apps.accounts.services.roles import OTP_SESSION_KEY
from apps.boards.models import BoardMedia, BoardType, BoardVariant, Material
from apps.inventory.models import InventoryItem
from tests.factories import AccountFactory, InventoryItemFactory

from .helpers import published_model, rental_booking, workshop_for

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_client_2fa():
    admin_user = AccountFactory(is_staff=True, is_superuser=True)
    client = Client()
    client.force_login(admin_user)
    session = client.session
    session[OTP_SESSION_KEY] = "test"
    session.save()
    return client


def test_admin_pages_render(admin_client_2fa):
    workshop = workshop_for()
    model = published_model(workshop)
    variant = model.variants.get()
    item = InventoryItemFactory(owner_account=None, owner_organization=workshop, variant=variant)
    booking = rental_booking(item)
    from apps.inventory.models import RentalHandover

    handover = RentalHandover.objects.create(booking=booking, kind="issue", condition="good",
                                             recorded_by=workshop.owner)
    objects = {
        "boards/workshopprofile": workshop.pk, "boards/boardtype": BoardType.objects.first().pk,
        "boards/material": Material.objects.first().pk, "boards/boardmodel": model.pk,
        "boards/boardvariant": variant.pk, "boards/boardmedia": BoardMedia.objects.first().pk,
        "inventory/inventoryitem": item.pk, "inventory/rentalhandover": handover.pk,
    }
    for path, pk in objects.items():
        assert admin_client_2fa.get(f"/admin/{path}/").status_code == 200, path
        assert admin_client_2fa.get(f"/admin/{path}/{pk}/change/").status_code == 200, path
    assert admin_client_2fa.get("/admin/boards/boardvariant/add/").status_code == 403


def test_admin_item_edit_refreshes_variant_availability(admin_client_2fa):
    workshop = workshop_for()
    variant = published_model(workshop).variants.get()
    item = InventoryItemFactory(owner_account=None, owner_organization=workshop, variant=variant, purpose="sale")
    variant.refresh_from_db()
    assert variant.availability == BoardVariant.Availability.IN_STOCK
    item = InventoryItem.objects.get(pk=item.pk)
    item.status = InventoryItem.Status.SOLD
    item.save()  # так же сохраняет и ModelAdmin
    variant.refresh_from_db()
    assert variant.availability != BoardVariant.Availability.IN_STOCK
