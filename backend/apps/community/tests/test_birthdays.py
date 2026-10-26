"""Поздравления с днём рождения: только по согласию, раз в год, без раскрытия даты (COM-05, F12, ATX-34)."""
import datetime as dt

import pytest

from apps.community.models import BirthdayGreeting
from apps.community.tasks import send_birthday_greetings
from apps.messaging.models import Notification, NotificationPreference
from tests.factories import AccountFactory

pytestmark = pytest.mark.django_db


def person(birth_date, consent=True, **extra):
    account = AccountFactory(**extra)
    account.profile.birth_date = birth_date
    account.profile.birthday_greetings_consent = consent
    account.profile.save()
    return account


def test_greets_consenting_account_once_per_year():
    account = person(dt.date(1990, 10, 21))
    assert send_birthday_greetings("2026-10-21") == 1
    assert send_birthday_greetings("2026-10-21") == 0  # повторный запуск того же дня
    notification = Notification.objects.get(recipient=account)
    assert notification.kind == Notification.Kind.BIRTHDAY
    assert notification.title == "С днём рождения от ГДеволна!"
    assert BirthdayGreeting.objects.filter(account=account, year=2026).count() == 1
    # в следующем году — снова
    assert send_birthday_greetings("2027-10-21") == 1


def test_no_greeting_without_consent():
    """ATX-34: без согласия поздравление не отправляется."""
    account = person(dt.date(1990, 10, 21), consent=False)
    assert send_birthday_greetings("2026-10-21") == 0
    assert not Notification.objects.filter(recipient=account).exists()
    assert not BirthdayGreeting.objects.exists()


def test_greeting_text_does_not_reveal_birth_date_or_age():
    account = person(dt.date(1990, 10, 21))
    send_birthday_greetings("2026-10-21")
    notification = Notification.objects.get(recipient=account)
    text = f"{notification.title} {notification.body} {notification.link} {notification.payload}"
    for fragment in ("1990", "21", "октябр", "10.", "36"):
        assert fragment not in text


def test_only_todays_birthdays_are_greeted():
    person(dt.date(1990, 10, 22))
    person(dt.date(1990, 9, 21))
    person(None)
    assert send_birthday_greetings("2026-10-21") == 0


def test_feb_29_is_greeted_on_feb_28_in_non_leap_year():
    account = person(dt.date(2000, 2, 29))
    assert send_birthday_greetings("2027-02-28") == 1
    assert send_birthday_greetings("2027-03-01") == 0
    assert BirthdayGreeting.objects.get(account=account).year == 2027


def test_feb_29_waits_for_feb_29_in_leap_year():
    person(dt.date(2000, 2, 29))
    assert send_birthday_greetings("2028-02-28") == 0
    assert send_birthday_greetings("2028-02-29") == 1


def test_inactive_and_anonymized_accounts_are_skipped():
    from django.utils import timezone

    person(dt.date(1990, 10, 21), is_active=False)
    anonymized = person(dt.date(1990, 10, 21))
    anonymized.anonymized_at = timezone.now()
    anonymized.save()
    assert send_birthday_greetings("2026-10-21") == 0


def test_in_app_disabled_still_records_greeting_without_duplicates():
    account = person(dt.date(1990, 10, 21))
    NotificationPreference.objects.create(account=account, kind=Notification.Kind.BIRTHDAY, in_app=False, email=False)
    assert send_birthday_greetings("2026-10-21") == 1
    assert not Notification.objects.filter(recipient=account).exists()
    assert send_birthday_greetings("2026-10-21") == 0


def test_default_today_uses_moscow_date(monkeypatch):
    from django.utils import timezone

    today = timezone.localdate()
    person(dt.date(1991, today.month, min(today.day, 28)))
    expected = 1 if today.day <= 28 else 0
    assert send_birthday_greetings() == expected
