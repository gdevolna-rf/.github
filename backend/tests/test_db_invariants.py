"""Инварианты целостности, обеспеченные самой PostgreSQL (6.2)."""
import datetime as dt

import pytest
from django.db import IntegrityError, transaction

from apps.commerce.models import Booking, Inquiry
from apps.learning.models import LessonSession
from tests.factories import (
    AccountFactory,
    InventoryItemFactory,
    LessonSessionFactory,
    future,
)

pytestmark = pytest.mark.django_db


def test_health(api_client):
    response = api_client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_inventory_item_cannot_have_two_confirmed_overlapping_bookings():
    item = InventoryItemFactory()
    start, end = future(hours=48, duration=4)
    common = dict(kind=Booking.Kind.RENTAL, inventory_item=item, provider_account=item.owner_account)
    Booking.objects.create(customer=AccountFactory(), starts_at=start, ends_at=end, status="confirmed", **common)
    # запрос (requested) на то же время допустим — конфликт проверяется только для подтверждённых
    Booking.objects.create(customer=AccountFactory(), starts_at=start, ends_at=end, status="requested", **common)
    with pytest.raises(IntegrityError), transaction.atomic():
        Booking.objects.create(
            customer=AccountFactory(), starts_at=start + dt.timedelta(hours=1), ends_at=end + dt.timedelta(hours=1),
            status="confirmed", **common,
        )


def test_instructor_cannot_have_overlapping_scheduled_sessions():
    instructor = AccountFactory()
    first = LessonSessionFactory(instructor=instructor)
    LessonSessionFactory(instructor=instructor, starts_at=first.ends_at, ends_at=first.ends_at + dt.timedelta(hours=1))
    with pytest.raises(IntegrityError), transaction.atomic():
        LessonSessionFactory(
            instructor=instructor, starts_at=first.starts_at + dt.timedelta(minutes=30),
            ends_at=first.ends_at + dt.timedelta(minutes=30),
        )
    first.status = LessonSession.Status.CANCELLED
    first.save()
    LessonSessionFactory(instructor=instructor, starts_at=first.starts_at, ends_at=first.ends_at)


def test_inquiry_to_self_is_rejected_by_database():
    account = AccountFactory()
    with pytest.raises(IntegrityError), transaction.atomic():
        Inquiry.objects.create(kind="general", customer=account, provider_account=account, subject="x")
