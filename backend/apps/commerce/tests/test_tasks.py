"""Периодические задачи commerce (ARCHITECTURE §5)."""
import datetime as dt

import pytest
from django.utils import timezone

from apps.commerce.models import Booking
from apps.commerce.tasks import expire_stale_booking_requests, mark_overdue_rentals
from apps.commerce.tests.helpers import rental_item, requested_lesson, requested_rental
from apps.messaging.models import Notification
from tests.factories import LessonSessionFactory

pytestmark = pytest.mark.django_db


def test_tasks_are_registered_under_contract_names():
    from config.celery import app

    app.loader.import_default_modules()
    assert "commerce.expire_stale_booking_requests" in app.tasks
    assert "commerce.mark_overdue_rentals" in app.tasks


def test_stale_and_started_requests_are_cancelled_by_system(settings):
    settings.BOOKING_REQUEST_TTL_HOURS = 48
    item = rental_item()
    stale = requested_rental(item)
    Booking.objects.filter(pk=stale.pk).update(created_at=timezone.now() - dt.timedelta(hours=49))
    session = LessonSessionFactory()
    started = requested_lesson(session)
    Booking.objects.filter(pk=started.pk).update(starts_at=timezone.now() - dt.timedelta(minutes=1))
    fresh = requested_rental(rental_item())
    confirmed = requested_rental(rental_item())
    Booking.objects.filter(pk=confirmed.pk).update(status="confirmed",
                                                   created_at=timezone.now() - dt.timedelta(days=5))

    assert expire_stale_booking_requests() == 2
    for booking in (stale, started):
        booking.refresh_from_db()
        assert booking.status == "cancelled" and booking.cancelled_side == "system" and booking.cancel_reason
        assert booking.history.get().to_status == "cancelled"
        assert Notification.objects.filter(recipient=booking.customer, kind="booking_status").exists()
    assert Notification.objects.filter(recipient=item.owner_account, kind="booking_status").exists()
    assert Notification.objects.filter(recipient=session.organization.owner, kind="booking_status").exists()
    fresh.refresh_from_db()
    confirmed.refresh_from_db()
    assert fresh.status == "requested" and confirmed.status == "confirmed"
    assert expire_stale_booking_requests() == 0


def test_overdue_rentals_flagged_and_notified_once():
    item = rental_item()
    overdue = requested_rental(item)
    Booking.objects.filter(pk=overdue.pk).update(status="in_progress", ends_at=timezone.now() - dt.timedelta(hours=1),
                                                 starts_at=timezone.now() - dt.timedelta(hours=5))
    on_time = requested_rental(rental_item())
    Booking.objects.filter(pk=on_time.pk).update(status="in_progress")

    assert mark_overdue_rentals() == 1
    overdue.refresh_from_db()
    on_time.refresh_from_db()
    assert overdue.is_overdue is True and overdue.status == "in_progress" and on_time.is_overdue is False
    customer_notes = Notification.objects.filter(recipient=overdue.customer, title="Просрочен возврат инвентаря")
    assert customer_notes.count() == 1
    assert Notification.objects.filter(recipient=item.owner_account, title="Просрочен возврат инвентаря").count() == 1
    assert mark_overdue_rentals() == 0
    assert customer_notes.count() == 1
