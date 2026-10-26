"""Акты выдачи/возврата (RENT-06): confirmed → in_progress → completed, повреждение → обслуживание."""
import pytest

from apps.commerce.models import Booking, BookingStatusChange
from apps.inventory.models import InventoryItem, RentalHandover
from apps.messaging.models import Notification
from apps.trust.models import AuditEvent
from tests.factories import AccountFactory, InventoryItemFactory, LessonSessionFactory, OrganizationFactory, add_member

from apps.boards.tests.helpers import photo, rental_booking

pytestmark = pytest.mark.django_db


def url(booking, suffix="handover"):
    return f"/api/v1/bookings/{booking.pk}/{suffix}"


def issue(**extra):
    return {"kind": "issue", "condition": "good", "notes": "Выдано с лишем", **extra}


def test_issue_then_return_with_damage(make_client):
    item = InventoryItemFactory()
    owner = item.owner_account
    booking = rental_booking(item)
    client = make_client(owner)

    response = client.post(url(booking), issue(photo_ids=[str(photo(owner, purpose="handover_photo").pk)]),
                           format="json")
    assert response.status_code == 201, response.json()
    assert response.json()["kind"] == "issue" and len(response.json()["photos"]) == 1
    booking.refresh_from_db()
    assert booking.status == Booking.Status.IN_PROGRESS
    assert BookingStatusChange.objects.filter(booking=booking, to_status="in_progress", actor=owner).exists()

    response = client.post(url(booking), {"kind": "return", "condition": "fair", "damage_reported": True,
                                          "damage_description": "Скол на носу"}, format="json")
    assert response.status_code == 201, response.json()
    booking.refresh_from_db()
    item.refresh_from_db()
    assert booking.status == Booking.Status.COMPLETED and booking.damage_reported is True
    assert item.status == InventoryItem.Status.MAINTENANCE and item.condition == "fair"
    assert AuditEvent.objects.filter(action="rental.handover_return", object_id=str(booking.pk)).exists()
    assert Notification.objects.filter(recipient=booking.customer, kind="booking_status").count() == 2


def test_return_without_damage_keeps_item_available(make_client):
    item = InventoryItemFactory()
    booking = rental_booking(item)
    client = make_client(item.owner_account)
    client.post(url(booking), issue(), format="json")
    response = client.post(url(booking), {"kind": "return", "condition": "good"}, format="json")
    assert response.status_code == 201
    item.refresh_from_db()
    booking.refresh_from_db()
    assert item.status == InventoryItem.Status.AVAILABLE and booking.damage_reported is False


def test_issue_requires_confirmed_and_return_requires_issued(make_client):
    item = InventoryItemFactory()
    client = make_client(item.owner_account)
    requested = rental_booking(item, status=Booking.Status.REQUESTED)
    response = client.post(url(requested), issue(), format="json")
    assert response.status_code == 409 and response.json()["error"]["code"] == "invalid_status"
    confirmed = InventoryItemFactory(owner_account=item.owner_account)
    booking = rental_booking(confirmed)
    early_return = client.post(url(booking), {"kind": "return", "condition": "good"}, format="json")
    assert early_return.status_code == 409
    client.post(url(booking), issue(), format="json")
    twice = client.post(url(booking), issue(), format="json")
    assert twice.status_code == 409
    assert RentalHandover.objects.filter(booking=booking).count() == 1


def test_damage_requires_description(make_client):
    item = InventoryItemFactory()
    booking = rental_booking(item, status=Booking.Status.IN_PROGRESS)
    response = make_client(item.owner_account).post(url(booking), {"kind": "return", "condition": "fair",
                                                                   "damage_reported": True}, format="json")
    assert response.status_code == 400 and "damage_description" in response.json()["error"]["fields"]
    booking.refresh_from_db()
    assert booking.status == Booking.Status.IN_PROGRESS


def test_customer_and_strangers_cannot_record_acts(make_client):
    item = InventoryItemFactory()
    booking = rental_booking(item)
    customer = make_client(booking.customer)
    assert customer.post(url(booking), issue(), format="json").status_code == 403
    assert make_client().post(url(booking), issue(), format="json").status_code == 404
    booking.refresh_from_db()
    assert booking.status == Booking.Status.CONFIRMED


def test_org_staff_records_acts_for_organization_rental(make_client):
    school = OrganizationFactory()
    staff = AccountFactory()
    add_member(school, staff, role="staff")
    item = InventoryItemFactory(owner_account=None, owner_organization=school)
    booking = rental_booking(item)
    assert make_client(staff).post(url(booking), issue(), format="json").status_code == 201


def test_lesson_booking_is_not_a_rental(make_client):
    session = LessonSessionFactory()
    booking = Booking.objects.create(kind=Booking.Kind.LESSON, status=Booking.Status.CONFIRMED,
                                     customer=AccountFactory(), provider_organization=session.organization,
                                     lesson_session=session, starts_at=session.starts_at, ends_at=session.ends_at)
    response = make_client(session.organization.owner).post(url(booking), issue(), format="json")
    assert response.status_code == 400 and response.json()["error"]["code"] == "not_rental"


def test_handover_photos_must_be_handover_purpose(make_client):
    item = InventoryItemFactory()
    booking = rental_booking(item)
    response = make_client(item.owner_account).post(
        url(booking), issue(photo_ids=[str(photo(item.owner_account, purpose="item_photo").pk)]), format="json")
    assert response.status_code == 400 and response.json()["error"]["code"] == "media_purpose"
    booking.refresh_from_db()
    assert booking.status == Booking.Status.CONFIRMED


def test_both_parties_see_handovers_strangers_do_not(make_client):
    item = InventoryItemFactory()
    booking = rental_booking(item)
    make_client(item.owner_account).post(url(booking), issue(), format="json")
    for account in (item.owner_account, booking.customer):
        data = make_client(account).get(url(booking, "handovers")).json()
        assert len(data) == 1 and data[0]["kind_label"] == "Выдача"
        assert data[0]["recorded_by"]["id"] == str(item.owner_account.pk)
    assert make_client().get(url(booking, "handovers")).status_code == 404
