"""Конкурентные подтверждения (AT-05, F07, ATX-16, 6.2): реальные параллельные транзакции в разных соединениях."""
import datetime as dt
import threading

from django.db import connection

from apps.commerce.models import Booking
from apps.commerce.tests.helpers import rental_item, rental_window, requested_lesson, requested_rental
from tests.factories import LessonSessionFactory


def _race(clients_and_urls):
    """Запускает POST одновременно из нескольких потоков (у каждого своё соединение с БД)."""
    barrier = threading.Barrier(len(clients_and_urls))
    outcomes = [None] * len(clients_and_urls)

    def worker(index, client, url):
        try:
            barrier.wait(timeout=10)
            response = client.post(url, {}, format="json")
            outcomes[index] = (response.status_code, response.json())
        finally:
            connection.close()

    threads = [threading.Thread(target=worker, args=(i, c, u)) for i, (c, u) in enumerate(clients_and_urls)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    return outcomes


def test_two_customers_confirming_last_board_only_one_succeeds(transactional_db,
                                                               make_client):
    """AT-05 / F07 / ATX-16: две конкурирующие брони последнего борда — подтверждается одна, вторая получает 409."""
    item = rental_item()
    start, end = rental_window()
    first = requested_rental(item, start=start, end=end)
    second = requested_rental(item, start=start + dt.timedelta(hours=1), end=end + dt.timedelta(hours=1))
    owner_a, owner_b = make_client(item.owner_account), make_client(item.owner_account)
    outcomes = _race([(owner_a, f"/api/v1/bookings/{first.pk}/confirm"),
                      (owner_b, f"/api/v1/bookings/{second.pk}/confirm")])
    statuses = sorted(code for code, _ in outcomes)
    assert statuses == [200, 409], outcomes
    conflict = next(body for code, body in outcomes if code == 409)
    assert conflict["error"]["code"] == "resource_taken"
    assert Booking.objects.filter(inventory_item=item, status="confirmed").count() == 1
    assert Booking.objects.filter(inventory_item=item, status="requested").count() == 1


def test_many_parallel_confirmations_of_overlapping_rentals(transactional_db, make_client):
    item = rental_item()
    start, end = rental_window()
    bookings = [requested_rental(item, start=start + dt.timedelta(minutes=10 * i), end=end) for i in range(4)]
    clients = [make_client(item.owner_account) for _ in bookings]
    outcomes = _race([(c, f"/api/v1/bookings/{b.pk}/confirm") for c, b in zip(clients, bookings)])
    assert sorted(code for code, _ in outcomes) == [200, 409, 409, 409], outcomes
    assert Booking.objects.filter(inventory_item=item, status="confirmed").count() == 1


def test_parallel_confirmations_respect_lesson_capacity(transactional_db, make_client):
    """6.2: подтверждение записи — в транзакции с блокировкой строки занятия."""
    session = LessonSessionFactory(capacity=1)
    first, second = requested_lesson(session), requested_lesson(session)
    owner = session.organization.owner
    outcomes = _race([(make_client(owner), f"/api/v1/bookings/{first.pk}/confirm"),
                      (make_client(owner), f"/api/v1/bookings/{second.pk}/confirm")])
    assert sorted(code for code, _ in outcomes) == [200, 409], outcomes
    assert next(body for code, body in outcomes if code == 409)["error"]["code"] == "no_seats"
    assert Booking.objects.filter(lesson_session=session, status="confirmed").count() == 1


def test_parallel_requests_with_same_idempotency_key_create_one_booking(transactional_db,
                                                                        make_client):
    session = LessonSessionFactory(capacity=5)
    customer = make_client()
    barrier = threading.Barrier(2)
    codes = []

    def worker():
        try:
            barrier.wait(timeout=10)
            response = customer.post("/api/v1/bookings", {"lesson_session_id": str(session.pk)}, format="json",
                                     HTTP_IDEMPOTENCY_KEY="same-key")
            codes.append((response.status_code, response.json().get("id")))
        finally:
            connection.close()

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert [c for c, _ in codes] == [201, 201]
    assert codes[0][1] == codes[1][1]
    assert Booking.objects.filter(lesson_session=session).count() == 1
