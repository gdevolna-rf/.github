"""Celery-напоминания за 24 ч (ARCHITECTURE §5) и Django Admin learning/analytics."""
import datetime as dt

import pytest
from django.urls import reverse

from apps.accounts.models import Account
from apps.commerce.models import Booking
from apps.learning.tasks import send_lesson_reminders
from apps.messaging.models import Notification

from .helpers import (
    booking,
    certificate,
    private_session,
    published_instructor,
    school,
    school_instructor,
    school_session,
)

pytestmark = pytest.mark.django_db


def reminders():
    return Notification.objects.filter(kind=Notification.Kind.LESSON_REMINDER)


def test_reminders_sent_once_for_confirmed_bookings_within_24h():
    org = school()
    coach = school_instructor(org)
    soon = school_session(org, instructor=coach, hours=5)
    confirmed = booking(soon)
    booking(soon, status=Booking.Status.REQUESTED)
    booking(soon, status=Booking.Status.CANCELLED)
    later = school_session(org, hours=48)
    booking(later)
    send_lesson_reminders()
    assert set(reminders().values_list("recipient_id", flat=True)) == {confirmed.customer_id, coach.pk}
    customer_note = reminders().get(recipient=confirmed.customer)
    assert customer_note.link == f"/account/bookings/{confirmed.pk}"
    send_lesson_reminders()  # повторный запуск не дублирует
    assert reminders().count() == 2


def test_reminder_resent_after_reschedule():
    session = school_session(school(), hours=10)
    booking(session)
    send_lesson_reminders()
    session.starts_at += dt.timedelta(hours=2)
    session.ends_at += dt.timedelta(hours=2)
    session.save()
    send_lesson_reminders()
    assert reminders().count() == 2


def test_no_reminders_for_cancelled_or_empty_sessions():
    cancelled = school_session(school(), hours=5, status="cancelled")
    booking(cancelled)
    school_session(school(), hours=6)
    assert send_lesson_reminders() == 0


def test_admin_pages_load(client):
    admin = Account.objects.create_superuser("root@example.com", "Passw0rd!x")
    client.force_login(admin)
    session = client.session
    session["otp_verified_at"] = "test"
    session.save()
    profile = published_instructor()
    certificate(profile)
    private_session(profile)
    for model in ("instructorprofile", "instructorcertificate", "instructoroffer", "schoolprogram", "lessonsession",
                  "waitlistentry", "studentnote"):
        assert client.get(reverse(f"admin:learning_{model}_changelist")).status_code == 200, model
    assert client.get(reverse("admin:learning_instructorprofile_change", args=[profile.pk])).status_code == 200
    assert client.get(reverse("admin:analytics_analyticsevent_changelist")).status_code == 200
    assert client.get(reverse("admin:analytics_analyticsevent_add")).status_code == 403
