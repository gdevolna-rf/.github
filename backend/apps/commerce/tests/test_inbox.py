"""Единый inbox (MSG-01/02/06/07, ATX-27), непрочитанность по курсорам (AT-04), доступ сотрудников (AT-09)."""
from decimal import Decimal

import pytest

from apps.commerce.models import Inquiry
from apps.commerce.services.inquiries import create_inquiry
from apps.commerce.tests.helpers import add_manager, board_inquiry, results, revoke
from apps.messaging.models import ConversationParticipant
from apps.messaging.services.conversations import send_message
from apps.organizations.models import Membership
from tests.factories import (
    AccountFactory,
    InstructorOfferFactory,
    InstructorProfileFactory,
    InventoryItemFactory,
    OrganizationFactory,
    SchoolProgramFactory,
    WorkshopFactory,
    add_member,
)

pytestmark = pytest.mark.django_db


def test_shaper_sees_incoming_buyer_sees_only_outgoing(make_client):
    """ATX-27, MSG-02."""
    inquiry, customer, workshop = board_inquiry()
    board_inquiry(workshop=WorkshopFactory())  # чужое обращение другого клиента
    shaper = make_client(workshop.owner)
    buyer = make_client(customer)
    stranger = make_client()

    incoming = results(shaper.get("/api/v1/inquiries?box=incoming"))
    assert [i["id"] for i in incoming] == [str(inquiry.pk)]
    assert incoming[0]["my_role"] == "provider" and incoming[0]["counterpart"]["type"] == "account"
    assert incoming[0]["counterpart"]["id"] == str(customer.pk)
    assert results(shaper.get("/api/v1/inquiries?box=outgoing")) == []

    outgoing = results(buyer.get("/api/v1/inquiries?box=outgoing"))
    assert [i["id"] for i in outgoing] == [str(inquiry.pk)]
    assert results(buyer.get("/api/v1/inquiries?box=incoming")) == []
    assert results(stranger.get("/api/v1/inquiries")) == []
    assert stranger.get(f"/api/v1/inquiries/{inquiry.pk}").status_code == 404


def test_inbox_item_shape(make_client):
    inquiry, customer, workshop = board_inquiry(message="Первое")
    item = results(make_client(workshop.owner).get("/api/v1/inquiries"))[0]
    assert set(item) >= {"id", "kind", "kind_label", "status", "status_label", "subject", "created_at", "updated_at",
                         "my_role", "counterpart", "provider_organization", "context", "last_message", "unread_count",
                         "conversation_id", "agreed_amount", "amount_confirmed", "actions"}
    assert item["kind_label"] == "Покупка доски" and item["actions"] == ["accept", "decline"]
    assert item["provider_organization"] == {"id": str(workshop.pk), "name": workshop.name, "kind": "workshop",
                                             "slug": workshop.slug}
    assert item["last_message"]["body"] == "Первое" and item["last_message"]["is_mine"] is False
    assert item["last_message"]["sender_name"] == "Тест Пользователь"
    assert set(item["context"]) == {"type", "id", "title", "subtitle", "image", "url"}
    assert item["unread_count"] == 1


def test_role_filters_split_one_account_inbox(make_client):
    """MSG-01: один inbox с фильтрами Клиент / Шейпер / Школа / Инструктор / Прокат."""
    pro = InstructorProfileFactory().account
    workshop = WorkshopFactory(owner=pro)
    school_program = SchoolProgramFactory(organization=OrganizationFactory(owner=pro))
    offer = InstructorOfferFactory(instructor=pro.instructor_profile)
    item = InventoryItemFactory(owner_account=pro)
    customer = AccountFactory()
    shaper_inq, _, _ = board_inquiry(customer=customer, workshop=workshop)
    school_inq = create_inquiry(customer, kind="program", message="m", target_type="school_program",
                                target_id=school_program.pk)
    lesson_inq = create_inquiry(customer, kind="lesson", message="m", target_type="instructor_offer", target_id=offer.pk)
    rental_inq = create_inquiry(customer, kind="rental", message="m", target_type="inventory_item", target_id=item.pk)
    outgoing, _, _ = board_inquiry(customer=pro)

    client = make_client(pro)

    def ids(role):
        return {i["id"] for i in results(client.get(f"/api/v1/inquiries?role={role}"))}

    assert ids("shaper") == {str(shaper_inq.pk)}
    assert ids("school") == {str(school_inq.pk)}
    assert ids("instructor") == {str(lesson_inq.pk)}
    assert ids("rental") == {str(rental_inq.pk)}
    assert ids("customer") == {str(outgoing.pk)}
    assert len(results(client.get("/api/v1/inquiries"))) == 5
    assert client.get("/api/v1/inquiries?role=wizard").status_code == 400


def test_status_kind_and_organization_filters(make_client):
    workshop = WorkshopFactory()
    first, _, _ = board_inquiry(workshop=workshop)
    second, _, _ = board_inquiry(workshop=workshop, kind="custom_order")
    Inquiry.objects.filter(pk=second.pk).update(status="in_progress")
    other_org_inquiry, _, other = board_inquiry()
    add_member(other, workshop.owner, role=Membership.Role.STAFF)
    client = make_client(workshop.owner)
    assert {i["id"] for i in results(client.get("/api/v1/inquiries?status=in_progress"))} == {str(second.pk)}
    assert {i["id"] for i in results(client.get("/api/v1/inquiries?status=new,in_progress&kind=board_purchase"))} == {
        str(first.pk), str(other_org_inquiry.pk)}
    assert {i["id"] for i in results(client.get(f"/api/v1/inquiries?organization={other.pk}"))} == {
        str(other_org_inquiry.pk)}


def test_two_unread_before_acceptance_become_zero_after_opening(make_client):
    """AT-04, MSG-06, ATX-10: «2 новых» — это 2 непрочитанных сообщения; после открытия — 0 и в шапке."""
    inquiry, customer, workshop = board_inquiry(message="Первое")
    conversation = inquiry.conversation
    send_message(conversation, customer, body="Второе")
    shaper = make_client(workshop.owner)
    item = results(shaper.get("/api/v1/inquiries"))[0]
    assert item["unread_count"] == 2
    counters = shaper.get("/api/v1/me/counters").json()
    assert counters["unread_messages"] == 2 and counters["new_inquiries"] == 1

    response = shaper.post(f"/api/v1/conversations/{conversation.pk}/read", {}, format="json")
    assert response.status_code == 200
    assert response.json()["unread_count"] == 0 and response.json()["counters"]["unread_messages"] == 0
    assert results(shaper.get("/api/v1/inquiries"))[0]["unread_count"] == 0
    assert shaper.get("/api/v1/me/counters").json()["unread_messages"] == 0
    # Клиент своих сообщений непрочитанными не видит.
    assert make_client(customer).get("/api/v1/me/counters").json()["unread_messages"] == 0


def test_unread_filter(make_client):
    inquiry, customer, workshop = board_inquiry()
    read_one, _, _ = board_inquiry(workshop=workshop)
    shaper = make_client(workshop.owner)
    shaper.post(f"/api/v1/conversations/{read_one.conversation.pk}/read", {}, format="json")
    assert {i["id"] for i in results(shaper.get("/api/v1/inquiries?unread=1"))} == {str(inquiry.pk)}


def test_new_manager_without_participant_row_sees_unread_and_gets_row_on_open(make_client):
    """Сотрудник, назначенный после создания обращения, видит непрочитанное; строка участника создаётся лениво."""
    program = SchoolProgramFactory()
    school = program.organization
    customer = AccountFactory()
    inquiry = create_inquiry(customer, kind="program", message="Раз", target_type="school_program",
                             target_id=program.pk)
    send_message(inquiry.conversation, customer, body="Два")
    manager = add_manager(school)
    client = make_client(manager)
    assert not ConversationParticipant.objects.filter(account=manager).exists()
    assert client.get("/api/v1/me/counters").json() == {"unread_messages": 2, "unread_notifications": 0,
                                                        "new_inquiries": 1, "pending_bookings": 0}
    assert results(client.get("/api/v1/inquiries"))[0]["unread_count"] == 2
    detail = client.get(f"/api/v1/inquiries/{inquiry.pk}")
    assert detail.status_code == 200 and detail.json()["my_role"] == "provider"
    row = ConversationParticipant.objects.get(account=manager)
    assert row.role == "member" and row.organization == school
    client.post(f"/api/v1/conversations/{inquiry.conversation.pk}/read", {}, format="json")
    assert client.get("/api/v1/me/counters").json()["unread_messages"] == 0


def test_revoked_manager_loses_access_immediately(make_client):
    """AT-09, F15: отзыв членства закрывает обращения и чат сразу; история остаётся."""
    program = SchoolProgramFactory()
    school = program.organization
    manager = add_manager(school)
    inquiry = create_inquiry(AccountFactory(), kind="program", message="Раз", target_type="school_program",
                             target_id=program.pk)
    client = make_client(manager)
    assert client.get(f"/api/v1/inquiries/{inquiry.pk}").status_code == 200
    revoke(school, manager)
    assert client.get(f"/api/v1/inquiries/{inquiry.pk}").status_code == 404
    assert results(client.get("/api/v1/inquiries")) == []
    assert client.get(f"/api/v1/conversations/{inquiry.conversation.pk}/messages").status_code == 404
    assert client.post(f"/api/v1/conversations/{inquiry.conversation.pk}/messages", {"body": "x"},
                       format="json").status_code == 404
    assert client.get("/api/v1/me/counters").json()["unread_messages"] == 0
    assert ConversationParticipant.objects.filter(account=manager).exists()  # история не удаляется
    assert inquiry.conversation.messages.count() == 1


def test_school_instructor_role_does_not_see_school_inquiries(make_client):
    program = SchoolProgramFactory()
    instructor = AccountFactory()
    add_member(program.organization, instructor, role=Membership.Role.INSTRUCTOR)
    inquiry = create_inquiry(AccountFactory(), kind="program", message="m", target_type="school_program",
                             target_id=program.pk)
    client = make_client(instructor)
    assert results(client.get("/api/v1/inquiries")) == []
    assert client.get(f"/api/v1/inquiries/{inquiry.pk}").status_code == 404


def test_workshop_staff_member_sees_workshop_inquiries(make_client):
    inquiry, _, workshop = board_inquiry()
    staff = AccountFactory()
    add_member(workshop, staff, role=Membership.Role.STAFF)
    client = make_client(staff)
    assert [i["id"] for i in results(client.get("/api/v1/inquiries?role=shaper"))] == [str(inquiry.pk)]


def test_detail_contains_history_milestones_and_snapshot(make_client):
    inquiry, customer, workshop = board_inquiry()
    data = make_client(customer).get(f"/api/v1/inquiries/{inquiry.pk}").json()
    assert data["history"][0]["to_status"] == "new" and data["history"][0]["to_status_label"] == "Новое"
    assert data["history"][0]["actor"]["id"] == str(customer.pk)
    assert data["milestones"] == [] and data["snapshot"]["type"] == "board_model"
    assert data["customer"]["id"] == str(customer.pk) and "email" not in data["customer"]
    assert data["provider"]["type"] == "organization" and data["message"]
    assert data["agreed_amount"] is None and data["amount_confirmed"] is False


def test_inbox_requires_authentication(api_client):
    assert api_client.get("/api/v1/inquiries").status_code == 401


def test_inbox_orders_by_last_activity(make_client):
    workshop = WorkshopFactory()
    older, customer, _ = board_inquiry(workshop=workshop)
    newer, _, _ = board_inquiry(workshop=workshop)
    send_message(older.conversation, customer, body="Свежий вопрос")
    ids = [i["id"] for i in results(make_client(workshop.owner).get("/api/v1/inquiries"))]
    assert ids == [str(older.pk), str(newer.pk)]


def test_agreed_amount_is_exposed_as_decimal_string(make_client):
    inquiry, customer, _ = board_inquiry()
    Inquiry.objects.filter(pk=inquiry.pk).update(agreed_amount=Decimal("65000"))
    item = results(make_client(customer).get("/api/v1/inquiries"))[0]
    assert item["agreed_amount"] == "65000.00" and item["currency"] == "RUB"


def test_private_board_sale_is_filed_under_rental_not_shaper(make_client):
    seller = AccountFactory()
    from apps.accounts.models import Specialty
    from tests.factories import add_specialty

    add_specialty(seller, Specialty.RENTAL)
    item = InventoryItemFactory(owner_account=seller, purpose="sale", sale_price=Decimal("20000"))
    inquiry = create_inquiry(AccountFactory(), kind="board_purchase", message="Продаёте?", target_type="inventory_item",
                             target_id=item.pk)
    client = make_client(seller)
    assert [i["id"] for i in results(client.get("/api/v1/inquiries?role=rental"))] == [str(inquiry.pk)]
    assert results(client.get("/api/v1/inquiries?role=shaper")) == []
