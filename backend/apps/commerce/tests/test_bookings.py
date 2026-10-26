"""Бронирования занятий и аренды: создание, цены, переходы 7.3 (SCH-11, F06, F13, ATX-14, RENT-05/06)."""
import datetime as dt
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.accounts.models import ConsentRecord
from apps.analytics.models import AnalyticsEvent
from apps.commerce.models import Booking, BookingStatusChange
from apps.commerce.services.bookings import compute_rental_price
from apps.commerce.tests.helpers import add_manager, rental_item, rental_window, requested_lesson, requested_rental, results
from apps.learning.models import WaitlistEntry
from apps.messaging.models import Notification
from apps.organizations.models import Membership
from tests.factories import (
    AccountFactory,
    InstructorOfferFactory,
    InventoryItemFactory,
    LessonSessionFactory,
    OrganizationFactory,
    SchoolProgramFactory,
    add_member,
)

pytestmark = pytest.mark.django_db


def book_lesson(client, session, **extra):
    return client.post("/api/v1/bookings", {"lesson_session_id": str(session.pk), **extra}, format="json")


def book_rental(client, item, start, end, **extra):
    return client.post("/api/v1/bookings", {"inventory_item_id": str(item.pk), "starts_at": start.isoformat(),
                                            "ends_at": end.isoformat(), **extra}, format="json")


def act(client, booking_id, action, **body):
    return client.post(f"/api/v1/bookings/{booking_id}/{action}", body, format="json")


@pytest.fixture
def session():
    return LessonSessionFactory(program=SchoolProgramFactory(price=Decimal("3500")), capacity=2)


# --- создание: занятие ---------------------------------------------------------------------------------------------


def test_lesson_booking_is_requested_with_server_price_and_provider_notified(make_client, session):
    manager = add_manager(session.organization)
    client = make_client()
    response = book_lesson(client, session, seats=2, customer_note="Первый раз")
    assert response.status_code == 201, response.json()
    data = response.json()
    assert data["status"] == "requested" and data["kind"] == "lesson" and data["my_role"] == "customer"
    assert data["price_amount"] == "7000.00" and data["currency"] == "RUB"
    assert data["participant_name"] == "Тест Пользователь" and data["seats"] == 2
    assert data["lesson"]["session_id"] == str(session.pk) and data["lesson"]["free_seats"] == 2
    assert data["lesson"]["program"]["title"] == session.program.title
    assert data["provider"]["type"] == "organization" and data["actions"] == ["cancel"]
    assert [h["to_status"] for h in data["history"]] == ["requested"]
    for account in (session.organization.owner, manager):
        note = Notification.objects.get(recipient=account, kind="booking_new")
        assert note.link == f"/account/bookings/{data['id']}"
    owner = make_client(session.organization.owner)
    assert owner.get("/api/v1/me/counters").json()["pending_bookings"] == 1


def test_offer_based_session_is_provided_by_instructor_account(make_client):
    offer = InstructorOfferFactory(price=Decimal("4000"))
    session = LessonSessionFactory(program=None, organization=None, offer=offer, instructor=offer.instructor.account)
    response = book_lesson(make_client(), session)
    assert response.status_code == 201
    booking = Booking.objects.get()
    assert booking.provider_account == offer.instructor.account and booking.provider_organization is None
    assert booking.price_amount == Decimal("4000.00")


@pytest.mark.parametrize("who", ["owner", "manager", "instructor_member", "assigned_instructor"])
def test_cannot_book_own_session(make_client, session, who):
    if who == "owner":
        account = session.organization.owner
    elif who == "assigned_instructor":
        account = AccountFactory()
        session.instructor = account
        session.save()
    else:
        account = AccountFactory()
        add_member(session.organization, account,
                   role=Membership.Role.MANAGER if who == "manager" else Membership.Role.INSTRUCTOR)
    response = book_lesson(make_client(account), session)
    assert response.status_code == 403 and response.json()["error"]["code"] == "self_booking"


def test_session_must_be_scheduled_and_in_future(make_client, session):
    client = make_client()
    session.status = "cancelled"
    session.save()
    assert book_lesson(client, session).json()["error"]["code"] == "session_unavailable"
    past = LessonSessionFactory(starts_at=timezone.now() - dt.timedelta(hours=1),
                                ends_at=timezone.now() + dt.timedelta(hours=1))
    response = book_lesson(client, past)
    assert response.status_code == 409 and response.json()["error"]["code"] == "session_started"


def test_not_enough_free_seats(make_client, session):
    requested_lesson(session, status="confirmed")
    response = book_lesson(make_client(), session, seats=2)
    assert response.status_code == 409 and response.json()["error"]["code"] == "no_seats"
    assert book_lesson(make_client(), session, seats=1).status_code == 201


def test_unpublished_school_session_not_found(make_client):
    session = LessonSessionFactory(program=SchoolProgramFactory(organization=OrganizationFactory(status="draft")))
    assert book_lesson(make_client(), session).status_code == 404


def test_minor_requires_guardian_consent(make_client, session):
    """SCH-11: несовершеннолетнего записывает законный представитель."""
    client = make_client()
    response = book_lesson(client, session, participant_is_minor=True, participant_name="Маша")
    assert response.status_code == 400 and response.json()["error"]["code"] == "guardian_consent_required"
    response = book_lesson(client, session, participant_is_minor=True, participant_name="", guardian_consent=True)
    assert response.status_code == 400
    response = book_lesson(client, session, participant_is_minor=True, participant_name="Маша", guardian_consent=True)
    assert response.status_code == 201
    assert response.json()["guardian_consent_at"] and response.json()["participant_is_minor"] is True
    assert ConsentRecord.objects.filter(account=client.account, kind="guardian", granted=True).count() == 1


def test_duplicate_request_for_same_participant_rejected(make_client, session):
    client = make_client()
    assert book_lesson(client, session).status_code == 201
    response = book_lesson(client, session)
    assert response.status_code == 409 and response.json()["error"]["code"] == "duplicate_booking"
    assert book_lesson(client, session, participant_name="Сын").status_code == 201


def test_group_with_links_lesson_and_rental(make_client, session):
    """F06: занятие + аренда доски — связанные брони."""
    client = make_client()
    lesson = book_lesson(client, session).json()
    item = rental_item()
    response = book_rental(client, item, session.starts_at, session.ends_at, group_with=lesson["id"])
    assert response.status_code == 201
    keys = set(Booking.objects.values_list("group_key", flat=True))
    assert len(keys) == 1 and None not in keys
    detail = client.get(f"/api/v1/bookings/{lesson['id']}").json()
    assert [g["id"] for g in detail["group"]] == [response.json()["id"]]
    foreign = requested_rental(rental_item())
    bad = book_lesson(make_client(), session, group_with=str(foreign.pk))
    assert bad.status_code == 400


def test_idempotent_booking(make_client, session):
    client = make_client()
    body = {"lesson_session_id": str(session.pk)}
    first = client.post("/api/v1/bookings", body, format="json", HTTP_IDEMPOTENCY_KEY="b-1")
    second = client.post("/api/v1/bookings", body, format="json", HTTP_IDEMPOTENCY_KEY="b-1")
    assert first.status_code == second.status_code == 201 and first.json()["id"] == second.json()["id"]
    assert Booking.objects.count() == 1


def test_create_validation(make_client, session):
    client = make_client()
    assert client.post("/api/v1/bookings", {}, format="json").status_code == 400
    item = rental_item()
    both = {"lesson_session_id": str(session.pk), "inventory_item_id": str(item.pk)}
    assert client.post("/api/v1/bookings", both, format="json").status_code == 400
    assert client.post("/api/v1/bookings", {"inventory_item_id": str(item.pk)}, format="json").status_code == 400


# --- создание: аренда ----------------------------------------------------------------------------------------------


@pytest.mark.parametrize("per_day,per_hour,hours,expected", [
    ("2500", None, 4, "2500.00"),       # только суточный тариф: неполные сутки = сутки
    ("2500", None, 30, "5000.00"),
    (None, "500", 3, "1500.00"),
    ("2500", "500", 3, "1500.00"),      # часы дешевле суток
    ("2500", "500", 8, "2500.00"),      # не дороже суток
    ("2500", "500", 26, "3500.00"),     # сутки + 2 часа
    (None, None, 5, None),
])
def test_rental_price_is_computed_on_server(per_day, per_hour, hours, expected):
    item = InventoryItemFactory.build(rental_price_per_day=Decimal(per_day) if per_day else None,
                                      rental_price_per_hour=Decimal(per_hour) if per_hour else None)
    start = timezone.now()
    price = compute_rental_price(item, start, start + dt.timedelta(hours=hours))
    assert (str(price) if price is not None else None) == expected


def test_rental_booking_created_with_server_price(make_client):
    item = rental_item(rental_price_per_hour=Decimal("500"), min_rental_hours=2)
    start, end = rental_window(duration_hours=3)
    client = make_client()
    response = book_rental(client, item, start, end, price_amount="1")  # клиентская цена игнорируется (9.1)
    assert response.status_code == 201, response.json()
    data = response.json()
    assert data["price_amount"] == "1500.00" and data["rental"]["item_id"] == str(item.pk)
    assert data["provider"]["type"] == "account" and data["provider"]["id"] == str(item.owner_account_id)
    assert Notification.objects.filter(recipient=item.owner_account, kind="booking_new").exists()


def test_rental_rules(make_client):
    client = make_client()
    item = rental_item(min_rental_hours=4)
    start, end = rental_window(duration_hours=2)
    assert book_rental(client, item, start, end).json()["error"]["code"] == "rental_too_short"
    assert book_rental(client, item, end, start).status_code == 400
    past_start = timezone.now() - dt.timedelta(days=1)
    assert book_rental(client, item, past_start, past_start + dt.timedelta(hours=5)).status_code == 400
    assert book_rental(client, item, start, start + dt.timedelta(days=61)).json()["error"]["code"] == "rental_too_long"
    sale_only = rental_item(purpose="sale")
    assert book_rental(client, sale_only, start, start + dt.timedelta(hours=5)).json()["error"]["code"] == "not_for_rent"
    broken = rental_item(status="maintenance")
    assert book_rental(client, broken, start, start + dt.timedelta(hours=5)).status_code == 409
    hidden = rental_item(is_published=False)
    assert book_rental(client, hidden, start, start + dt.timedelta(hours=5)).status_code == 404


def test_rental_overlapping_confirmed_booking_is_rejected_early(make_client):
    item = rental_item()
    start, end = rental_window()
    taken = requested_rental(item, start=start, end=end)
    Booking.objects.filter(pk=taken.pk).update(status="confirmed")
    response = book_rental(make_client(), item, start + dt.timedelta(hours=1), end + dt.timedelta(hours=1))
    assert response.status_code == 409 and response.json()["error"]["code"] == "resource_taken"
    assert book_rental(make_client(), item, end, end + dt.timedelta(hours=2)).status_code == 201  # стык допустим


def test_cannot_rent_own_or_own_organization_item(make_client):
    item = rental_item()
    start, end = rental_window()
    assert book_rental(make_client(item.owner_account), item, start, end).json()["error"]["code"] == "self_booking"
    org = OrganizationFactory(kind="rental")
    org_item = InventoryItemFactory(owner_account=None, owner_organization=org)
    staff = AccountFactory()
    add_member(org, staff, role=Membership.Role.STAFF)
    assert book_rental(make_client(staff), org_item, start, end).status_code == 403


# --- переходы ------------------------------------------------------------------------------------------------------


def test_provider_confirms_lesson_booking(make_client, session):
    """ATX-14: запись подтверждена — свободных мест меньше, событие booking_confirmed."""
    customer = make_client()
    booking_id = book_lesson(customer, session).json()["id"]
    assert act(customer, booking_id, "confirm").status_code == 403
    assert act(make_client(), booking_id, "confirm").status_code == 404
    owner = make_client(session.organization.owner)
    response = act(owner, booking_id, "confirm")
    assert response.status_code == 200, response.json()
    data = response.json()
    assert data["status"] == "confirmed" and data["confirmed_at"] and data["lesson"]["free_seats"] == 1
    assert data["my_role"] == "provider" and data["customer"]["id"] == str(customer.account.pk)
    assert AnalyticsEvent.objects.filter(name="booking_confirmed", subject_id=booking_id).count() == 1
    note = Notification.objects.get(recipient=customer.account, kind="booking_status")
    assert note.title == "Бронь подтверждена" and note.link == f"/account/bookings/{booking_id}"
    assert owner.get("/api/v1/me/counters").json()["pending_bookings"] == 0


def test_assigned_instructor_can_confirm_and_sees_booking(make_client, session):
    instructor = AccountFactory()
    add_member(session.organization, instructor, role=Membership.Role.INSTRUCTOR)
    session.instructor = instructor
    session.save()
    booking_id = book_lesson(make_client(), session).json()["id"]
    client = make_client(instructor)
    assert [b["id"] for b in results(client.get("/api/v1/bookings?box=provider"))] == [booking_id]
    assert client.get("/api/v1/me/counters").json()["pending_bookings"] == 1
    assert act(client, booking_id, "confirm").status_code == 200


def test_school_instructor_not_assigned_cannot_see_or_confirm(make_client, session):
    other = AccountFactory()
    add_member(session.organization, other, role=Membership.Role.INSTRUCTOR)
    booking_id = book_lesson(make_client(), session).json()["id"]
    client = make_client(other)
    assert results(client.get("/api/v1/bookings?box=provider")) == []
    assert act(client, booking_id, "confirm").status_code == 404


def test_confirm_rechecks_capacity(make_client):
    session = LessonSessionFactory(capacity=1)
    first = requested_lesson(session)
    second = requested_lesson(session)
    owner = make_client(session.organization.owner)
    assert act(owner, first.pk, "confirm").status_code == 200
    response = act(owner, second.pk, "confirm")
    assert response.status_code == 409 and response.json()["error"]["code"] == "no_seats"
    second.refresh_from_db()
    assert second.status == "requested"


def test_confirm_rental_overlap_returns_resource_taken(make_client):
    """AT-05 (последовательно): второе подтверждение пересекающейся аренды → 409."""
    item = rental_item()
    start, end = rental_window()
    first = requested_rental(item, start=start, end=end)
    second = requested_rental(item, start=start + dt.timedelta(hours=1), end=end + dt.timedelta(hours=1))
    owner = make_client(item.owner_account)
    assert act(owner, first.pk, "confirm").status_code == 200
    response = act(owner, second.pk, "confirm")
    assert response.status_code == 409 and response.json()["error"]["code"] == "resource_taken"
    assert not BookingStatusChange.objects.filter(booking=second, to_status="confirmed").exists()


def test_exclusion_constraint_is_last_line_of_defence(make_client, monkeypatch):
    """Даже если предварительная проверка пропустила пересечение, PostgreSQL не даст подтвердить вторую бронь."""
    item = rental_item()
    start, end = rental_window()
    first = requested_rental(item, start=start, end=end)
    second = requested_rental(item, start=start, end=end)
    owner = make_client(item.owner_account)
    assert act(owner, first.pk, "confirm").status_code == 200
    monkeypatch.setattr("apps.commerce.services.bookings.rental_overlap_exists", lambda *a, **k: False)
    response = act(owner, second.pk, "confirm")
    assert response.status_code == 409 and response.json()["error"]["code"] == "resource_taken"
    second.refresh_from_db()
    assert second.status == "requested"


def test_confirm_after_start_is_rejected(make_client):
    item = rental_item()
    booking = requested_rental(item)
    Booking.objects.filter(pk=booking.pk).update(starts_at=timezone.now() - dt.timedelta(minutes=1))
    response = act(make_client(item.owner_account), booking.pk, "confirm")
    assert response.status_code == 409 and response.json()["error"]["code"] == "booking_started"


def test_decline_requires_reason_and_notifies_customer(make_client, session):
    booking = requested_lesson(session)
    owner = make_client(session.organization.owner)
    assert act(owner, booking.pk, "decline").status_code == 400
    response = act(owner, booking.pk, "decline", reason="Группа переполнена")
    assert response.status_code == 200 and response.json()["decline_reason"] == "Группа переполнена"
    note = Notification.objects.get(recipient=booking.customer, kind="booking_status")
    assert note.title == "Бронь отклонена" and "Группа переполнена" in note.body


def test_customer_cancel_releases_seat_and_offers_waitlist(make_client):
    """F13 + SCH-08: отмена освобождает место, первый в листе ожидания получает предложение."""
    session = LessonSessionFactory(capacity=1)
    booking = requested_lesson(session, status="confirmed")
    waiting = WaitlistEntry.objects.create(session=session, account=AccountFactory())
    customer = make_client(booking.customer)
    response = act(customer, booking.pk, "cancel", reason="Заболел")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "cancelled" and data["cancelled_side"] == "customer" and data["cancel_reason"] == "Заболел"
    event = AnalyticsEvent.objects.get(name="booking_cancelled")
    assert event.context["side"] == "customer" and event.context["reason"] == "Заболел"
    waiting.refresh_from_db()
    assert waiting.status == "offered"
    assert Notification.objects.filter(recipient=session.organization.owner, kind="booking_status").exists()
    assert book_lesson(make_client(), session).status_code == 201  # место снова свободно


def test_customer_cannot_cancel_after_start(make_client):
    item = rental_item()
    booking = requested_rental(item)
    Booking.objects.filter(pk=booking.pk).update(status="confirmed", starts_at=timezone.now() - dt.timedelta(hours=1))
    response = act(make_client(booking.customer), booking.pk, "cancel")
    assert response.status_code == 409 and response.json()["error"]["code"] == "cancel_too_late"


def test_provider_cancel_requires_reason_and_frees_rental_slot(make_client):
    item = rental_item()
    start, end = rental_window()
    booking = requested_rental(item, start=start, end=end)
    owner = make_client(item.owner_account)
    act(owner, booking.pk, "confirm")
    assert act(owner, booking.pk, "cancel").status_code == 400
    response = act(owner, booking.pk, "cancel", reason="Доска повреждена")
    assert response.status_code == 200 and response.json()["cancelled_side"] == "provider"
    assert book_rental(make_client(), item, start, end).status_code == 201  # ресурс освобождён


def test_rental_issue_and_return_flow(make_client):
    """RENT-06: запрос → подтверждение → выдача → возврат."""
    item = rental_item()
    booking = requested_rental(item)
    owner = make_client(item.owner_account)
    act(owner, booking.pk, "confirm")
    assert act(owner, booking.pk, "complete").json()["error"]["code"] == "not_issued"
    response = act(owner, booking.pk, "start")
    assert response.status_code == 200 and response.json()["status"] == "in_progress"
    assert response.json()["actions"] == ["complete"]
    assert act(make_client(booking.customer), booking.pk, "complete").status_code == 403
    response = act(owner, booking.pk, "complete", amount_confirmed=True)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed" and data["completed_at"] and data["amount_confirmed"] is True
    assert [h["to_status"] for h in data["history"]] == ["confirmed", "in_progress", "completed"]
    assert Notification.objects.filter(recipient=booking.customer, title="Инвентарь возвращён").exists()


def test_lesson_complete_and_no_show_only_after_start(make_client, session):
    first = requested_lesson(session, status="confirmed")
    second = requested_lesson(session, status="confirmed")
    owner = make_client(session.organization.owner)
    assert act(owner, first.pk, "complete").json()["error"]["code"] == "too_early"
    assert act(owner, second.pk, "no-show").json()["error"]["code"] == "too_early"
    Booking.objects.filter(pk__in=[first.pk, second.pk]).update(starts_at=timezone.now() - dt.timedelta(minutes=5))
    assert act(owner, first.pk, "complete").json()["status"] == "completed"
    assert act(owner, second.pk, "no-show").json()["status"] == "no_show"
    assert act(owner, second.pk, "cancel", reason="x").status_code == 409


def test_actions_reflect_role_and_time(make_client, session):
    booking = requested_lesson(session)
    assert make_client(booking.customer).get(f"/api/v1/bookings/{booking.pk}").json()["actions"] == ["cancel"]
    owner = make_client(session.organization.owner)
    assert owner.get(f"/api/v1/bookings/{booking.pk}").json()["actions"] == ["confirm", "decline"]
    act(owner, booking.pk, "confirm")
    assert owner.get(f"/api/v1/bookings/{booking.pk}").json()["actions"] == ["start", "cancel"]


# --- списки --------------------------------------------------------------------------------------------------------


def test_lists_mine_and_provider_with_filters(make_client, session):
    customer = make_client()
    lesson_id = book_lesson(customer, session).json()["id"]
    item = rental_item()
    start, end = rental_window(hours_from_now=24 * 10)
    rental_id = book_rental(customer, item, start, end).json()["id"]
    requested_lesson(LessonSessionFactory())  # чужая

    mine = results(customer.get("/api/v1/bookings"))
    assert {b["id"] for b in mine} == {lesson_id, rental_id}
    assert {b["id"] for b in results(customer.get("/api/v1/bookings?kind=rental"))} == {rental_id}
    assert {b["id"] for b in results(customer.get("/api/v1/bookings?status=confirmed"))} == set()
    day = (timezone.localdate() + dt.timedelta(days=5)).isoformat()
    assert {b["id"] for b in results(customer.get(f"/api/v1/bookings?from={day}"))} == {rental_id}
    assert {b["id"] for b in results(customer.get(f"/api/v1/bookings?to={day}"))} == {lesson_id}
    assert customer.get("/api/v1/bookings?from=not-a-date").status_code == 400

    owner = make_client(session.organization.owner)
    provider_items = results(owner.get("/api/v1/bookings?box=provider"))
    assert [b["id"] for b in provider_items] == [lesson_id]
    assert provider_items[0]["customer"]["id"] == str(customer.account.pk)
    assert provider_items[0]["participant_name"] and "email" not in provider_items[0]["customer"]
    assert results(owner.get(f"/api/v1/bookings?box=provider&organization={session.organization_id}"))
    assert results(owner.get("/api/v1/bookings")) == []
    assert owner.get("/api/v1/bookings?box=everything").status_code == 400
    assert make_client().get(f"/api/v1/bookings/{lesson_id}").status_code == 404


def test_rental_card_has_item_info(make_client):
    item = rental_item(pickup_location="Халактырский пляж", size="7'0\"")
    start, end = rental_window()
    client = make_client()
    data = book_rental(client, item, start, end).json()
    assert data["rental"]["pickup_location"] == "Халактырский пляж" and data["rental"]["url"] == f"/rentals/{item.pk}"
    assert data["title"] == item.title and data["lesson"] is None
