"""Гонка регистраций: параллельные запросы не превышают лимит мест (select_for_update события)."""
import threading

from django.db import connection

from apps.club.models import EventRegistration
from apps.club.services.events import register
from apps.club.tests.factories import ClubEventFactory
from tests.factories import AccountFactory


def test_parallel_registrations_respect_capacity(transactional_db):
    event = ClubEventFactory(capacity=2)
    accounts = [AccountFactory() for _ in range(6)]
    barrier = threading.Barrier(len(accounts))
    errors = []

    def worker(account):
        try:
            barrier.wait(timeout=10)
            register(event.pk, account)
        except Exception as exc:  # pragma: no cover - диагностика
            errors.append(exc)
        finally:
            connection.close()

    threads = [threading.Thread(target=worker, args=(a,)) for a in accounts]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert not errors
    statuses = list(EventRegistration.objects.filter(event=event).values_list("status", flat=True))
    assert statuses.count("registered") == 2
    assert statuses.count("waitlist") == 4


def test_parallel_duplicate_registration_of_same_user_is_single(transactional_db):
    event = ClubEventFactory(capacity=5)
    account = AccountFactory()
    barrier = threading.Barrier(4)

    def worker():
        try:
            barrier.wait(timeout=10)
            register(event.pk, account)
        finally:
            connection.close()

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert EventRegistration.objects.filter(event=event, account=account).count() == 1
