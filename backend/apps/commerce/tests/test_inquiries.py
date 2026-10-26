"""Создание обращений: исполнитель по объекту, запрет «к себе», details, снимок, идемпотентность (7.2, AT-01/03)."""
from decimal import Decimal

import pytest

from apps.analytics.models import AnalyticsEvent
from apps.commerce.models import Inquiry, InquiryStatusChange
from apps.commerce.tests.helpers import attachment, post_inquiry
from apps.mediafiles.models import MediaAsset
from apps.messaging.models import AccountBlock, Conversation, ConversationParticipant, Message, Notification
from apps.organizations.models import Membership
from apps.trust.models import AccountRestriction
from tests.factories import (
    AccountFactory,
    BoardModelFactory,
    BoardVariantFactory,
    InstructorOfferFactory,
    InstructorProfileFactory,
    InventoryItemFactory,
    LessonSessionFactory,
    OrganizationFactory,
    SchoolProgramFactory,
    WorkshopFactory,
    add_member,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def workshop():
    org = WorkshopFactory()
    org.workshop.does_repair = True
    org.workshop.save()
    return org


@pytest.fixture
def board(workshop):
    model = BoardModelFactory(workshop=workshop, name="Fish Twin")
    BoardVariantFactory(model=model, price=Decimal("65000"))
    return model


def test_surfer_sends_board_inquiry_without_shaper_specialty(make_client, workshop, board):
    """AT-01, MSG-03/09: обращение создаёт диалог, первое сообщение, уведомление и событие аналитики."""
    member = AccountFactory()
    add_member(workshop, member, role=Membership.Role.STAFF)
    client = make_client()
    response = post_inquiry(client, kind="board_purchase", target_type="board_model", target_id=str(board.pk),
                            message="Хочу эту доску", details={"preferred_contact": "chat"})
    assert response.status_code == 201, response.json()
    data = response.json()
    inquiry = Inquiry.objects.get(pk=data["id"])
    assert inquiry.customer == client.account
    assert inquiry.provider_organization == workshop and inquiry.provider_account is None
    assert inquiry.board_model == board
    assert inquiry.status == "new" and data["status_label"] == "Новое"
    assert data["my_role"] == "customer" and data["actions"] == ["cancel"]
    assert data["counterpart"] == {**data["counterpart"], "type": "organization", "id": str(workshop.pk),
                                   "slug": workshop.slug}
    assert data["context"]["type"] == "board_model" and data["context"]["title"] == "Fish Twin"
    assert data["context"]["url"] == f"/boards/{board.pk}"
    assert data["last_message"]["body"] == "Хочу эту доску" and data["last_message"]["is_mine"] is True
    assert data["unread_count"] == 0 and data["can_send_messages"] is True
    assert data["details"] == {"preferred_contact": "chat"}

    conversation = Conversation.objects.get(inquiry=inquiry)
    assert data["conversation_id"] == str(conversation.pk)
    assert list(conversation.messages.values_list("body", flat=True)) == ["Хочу эту доску"]
    participants = set(conversation.participants.values_list("account_id", flat=True))
    assert participants == {client.account.pk, workshop.owner_id, member.pk}  # мастерская: все активные участники
    assert InquiryStatusChange.objects.filter(inquiry=inquiry, from_status="", to_status="new").count() == 1

    note = Notification.objects.get(recipient=workshop.owner, kind="inquiry_new")
    assert note.link == f"/account/inquiries/{inquiry.pk}"
    assert Notification.objects.filter(recipient=member, kind="inquiry_new").exists()
    assert not Notification.objects.filter(recipient=client.account).exists()
    event = AnalyticsEvent.objects.get(name="inquiry_created")
    assert event.owner_organization == workshop and event.actor == client.account
    assert event.context["source_channel"] == "boards" and event.context["kind"] == "board_purchase"
    assert event.dedup_key == f"inquiry_created:{inquiry.pk}"


@pytest.mark.parametrize("via", ["target", "provider_organization_id"])
def test_shaper_cannot_send_inquiry_to_own_workshop(make_client, workshop, board, via):
    """AT-03, ATX-03, SHP-11: запрет даже прямым POST."""
    client = make_client(workshop.owner)
    payload = {"kind": "board_purchase"}
    if via == "target":
        payload.update(target_type="board_model", target_id=str(board.pk))
    else:
        payload.update(kind="general", provider_organization_id=str(workshop.pk))
    response = post_inquiry(client, **payload)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "self_inquiry"
    assert not Inquiry.objects.exists()


def test_workshop_member_cannot_inquire_own_workshop(make_client, workshop, board):
    member = AccountFactory()
    add_member(workshop, member, role=Membership.Role.INSTRUCTOR)
    response = post_inquiry(make_client(member), kind="custom_order", target_type="board_model",
                            target_id=str(board.pk))
    assert response.status_code == 403 and response.json()["error"]["code"] == "self_inquiry"


def test_revoked_member_can_inquire_former_workshop(make_client, workshop, board):
    member = AccountFactory()
    add_member(workshop, member, role=Membership.Role.STAFF)
    Membership.objects.filter(account=member).update(status=Membership.Status.REVOKED)
    response = post_inquiry(make_client(member), kind="board_purchase", target_type="board_model",
                            target_id=str(board.pk))
    assert response.status_code == 201


def test_inquiry_to_self_account_forbidden(make_client):
    instructor = InstructorProfileFactory().account
    response = post_inquiry(make_client(instructor), kind="lesson", provider_account_id=str(instructor.pk))
    assert response.status_code == 403 and response.json()["error"]["code"] == "self_inquiry"


def test_inquiry_to_own_rental_item_forbidden(make_client):
    item = InventoryItemFactory()
    response = post_inquiry(make_client(item.owner_account), kind="rental", target_type="inventory_item",
                            target_id=str(item.pk))
    assert response.status_code == 403 and response.json()["error"]["code"] == "self_inquiry"


@pytest.mark.parametrize("direction", ["provider_blocked_customer", "customer_blocked_provider"])
def test_inquiry_blocked_in_either_direction(make_client, workshop, board, direction):
    client = make_client()
    if direction == "provider_blocked_customer":
        AccountBlock.objects.create(blocker=workshop.owner, blocked=client.account)
    else:
        AccountBlock.objects.create(blocker=client.account, blocked=workshop.owner)
    response = post_inquiry(client, kind="board_purchase", target_type="board_model", target_id=str(board.pk))
    assert response.status_code == 403 and response.json()["error"]["code"] == "blocked"


def test_messaging_restriction_blocks_new_inquiries(make_client, workshop, board):
    client = make_client()
    AccountRestriction.objects.create(account=client.account, kind="messaging", reason="спам")
    response = post_inquiry(client, kind="board_purchase", target_type="board_model", target_id=str(board.pk))
    assert response.status_code == 403 and response.json()["error"]["code"] == "messaging_restricted"


def test_lifted_restriction_does_not_block(make_client, workshop, board):
    from django.utils import timezone

    client = make_client()
    AccountRestriction.objects.create(account=client.account, kind="messaging", reason="спам", lifted_at=timezone.now())
    response = post_inquiry(client, kind="board_purchase", target_type="board_model", target_id=str(board.pk))
    assert response.status_code == 201


def test_repair_requires_problem_and_accepts_photos(make_client, workshop):
    """SHO-06: ремонт — проблема обязательна, фото повреждения (repair_photo) прикрепляются к первому сообщению."""
    client = make_client()
    response = post_inquiry(client, kind="repair", provider_organization_id=str(workshop.pk), details={})
    assert response.status_code == 400 and "details.problem" in response.json()["error"]["fields"]

    photo = attachment(client.account, purpose=MediaAsset.Purpose.REPAIR_PHOTO)
    response = post_inquiry(client, kind="repair", provider_organization_id=str(workshop.pk), message="Нужен ремонт",
                            details={"problem": "Вмятина на носу", "desired_date": "2099-01-15",
                                     "photo_ids": [str(photo.pk)]})
    assert response.status_code == 201, response.json()
    details = response.json()["details"]
    assert details["problem"] == "Вмятина на носу" and details["desired_date"] == "2099-01-15"
    assert details["photo_ids"] == [str(photo.pk)]
    assert details["photos"][0]["id"] == str(photo.pk) and "X-Amz-Signature" in details["photos"][0]["signed_url"]
    first = Message.objects.get(conversation__inquiry_id=response.json()["id"])
    assert list(first.attachments.values_list("media_id", flat=True)) == [photo.pk]


def test_repair_rejects_foreign_photo_and_past_date(make_client, workshop):
    client = make_client()
    foreign = attachment(AccountFactory(), purpose=MediaAsset.Purpose.REPAIR_PHOTO)
    response = post_inquiry(client, kind="repair", provider_organization_id=str(workshop.pk),
                            details={"problem": "трещина", "photo_ids": [str(foreign.pk)]})
    assert response.status_code == 400 and response.json()["error"]["code"] == "media_invalid"
    response = post_inquiry(client, kind="repair", provider_organization_id=str(workshop.pk),
                            details={"problem": "трещина", "desired_date": "2000-01-01"})
    assert response.status_code == 400


def test_repair_requires_workshop_doing_repair(make_client):
    workshop = WorkshopFactory()  # does_repair=False
    response = post_inquiry(make_client(), kind="repair", provider_organization_id=str(workshop.pk),
                            details={"problem": "трещина"})
    assert response.status_code == 400 and response.json()["error"]["code"] == "repair_not_offered"


def test_custom_order_only_to_workshop(make_client):
    school = OrganizationFactory()
    response = post_inquiry(make_client(), kind="custom_order", provider_organization_id=str(school.pk))
    assert response.status_code == 400 and response.json()["error"]["code"] == "invalid_target"


def test_custom_order_params_are_validated(make_client, workshop, board):
    client = make_client()
    response = post_inquiry(client, kind="custom_order", target_type="board_model", target_id=str(board.pk),
                            details={"params": {"length": "5'8", "volume_l": 32.5}, "budget": "70000"})
    assert response.status_code == 201
    assert response.json()["details"]["params"] == {"length": "5'8", "volume_l": 32.5}
    assert response.json()["details"]["budget"] == "70000.00"
    response = post_inquiry(client, kind="custom_order", target_type="board_model", target_id=str(board.pk),
                            details={"params": {"nested": {"x": 1}}})
    assert response.status_code == 400


def test_kind_must_match_target(make_client, workshop, board):
    response = post_inquiry(make_client(), kind="program", target_type="board_model", target_id=str(board.pk))
    assert response.status_code == 400 and response.json()["error"]["code"] == "invalid_target"


def test_inventory_item_inquiry_goes_to_owner_account(make_client):
    item = InventoryItemFactory(purpose="both", sale_price=Decimal("30000"))
    response = post_inquiry(make_client(), kind="rental", target_type="inventory_item", target_id=str(item.pk))
    assert response.status_code == 201
    inquiry = Inquiry.objects.get()
    assert inquiry.provider_account == item.owner_account and inquiry.inventory_item == item
    assert response.json()["counterpart"]["type"] == "account"


def test_board_purchase_of_rental_only_item_rejected(make_client):
    item = InventoryItemFactory(purpose="rental")
    response = post_inquiry(make_client(), kind="board_purchase", target_type="inventory_item", target_id=str(item.pk))
    assert response.status_code == 400


def test_instructor_offer_inquiry_goes_to_instructor(make_client):
    offer = InstructorOfferFactory()
    response = post_inquiry(make_client(), kind="lesson", target_type="instructor_offer", target_id=str(offer.pk))
    assert response.status_code == 201
    inquiry = Inquiry.objects.get()
    assert inquiry.provider_account == offer.instructor.account and inquiry.instructor_offer == offer
    assert inquiry.source_channel == "instructors"


def test_school_program_and_session_inquiries_go_to_school(make_client):
    program = SchoolProgramFactory()
    session = LessonSessionFactory(program=program)
    client = make_client()
    assert post_inquiry(client, kind="program", target_type="school_program", target_id=str(program.pk)).status_code == 201
    assert post_inquiry(client, kind="lesson", target_type="lesson_session", target_id=str(session.pk)).status_code == 201
    assert set(Inquiry.objects.values_list("provider_organization_id", flat=True)) == {program.organization_id}
    assert Inquiry.objects.filter(lesson_session=session, school_program=program).exists()


def test_offer_based_session_inquiry_goes_to_private_instructor(make_client):
    offer = InstructorOfferFactory()
    session = LessonSessionFactory(program=None, organization=None, offer=offer, instructor=offer.instructor.account)
    response = post_inquiry(make_client(), kind="lesson", target_type="lesson_session", target_id=str(session.pk))
    assert response.status_code == 201
    assert Inquiry.objects.get().provider_account == offer.instructor.account


def test_assigned_instructor_cannot_inquire_own_session(make_client):
    instructor = AccountFactory()
    session = LessonSessionFactory(instructor=instructor)
    response = post_inquiry(make_client(instructor), kind="lesson", target_type="lesson_session",
                            target_id=str(session.pk))
    assert response.status_code == 403


def test_account_target_must_be_professional(make_client):
    plain = AccountFactory()
    response = post_inquiry(make_client(), kind="general", provider_account_id=str(plain.pk))
    assert response.status_code == 403 and response.json()["error"]["code"] == "provider_not_available"


def test_unpublished_board_is_not_found(make_client, workshop):
    draft = BoardModelFactory(workshop=workshop, status="draft")
    response = post_inquiry(make_client(), kind="board_purchase", target_type="board_model", target_id=str(draft.pk))
    assert response.status_code == 404


def test_validation_errors(make_client, workshop, board, api_client):
    client = make_client()
    assert post_inquiry(client, kind="board_purchase", target_type="board_model", target_id=str(board.pk),
                        message="").status_code == 400
    response = post_inquiry(client, kind="general", target_type="board_model", target_id=str(board.pk),
                            provider_organization_id=str(workshop.pk))
    assert response.status_code == 400
    assert post_inquiry(client, kind="nope", provider_organization_id=str(workshop.pk)).status_code == 400
    assert post_inquiry(api_client, kind="general", provider_organization_id=str(workshop.pk)).status_code == 401


def test_snapshot_keeps_parameters_after_variant_edit(make_client, workshop):
    """F10: заказ сохраняет снимок артикула, размеров и цены."""
    model = BoardModelFactory(workshop=workshop, name="Retro Fish")
    variant = BoardVariantFactory(model=model, sku="FISH-570", length_in=Decimal("68"), price=Decimal("60000"))
    client = make_client()
    response = post_inquiry(client, kind="board_purchase", target_type="board_variant", target_id=str(variant.pk))
    assert response.status_code == 201
    inquiry_id = response.json()["id"]
    variant.sku, variant.length_in, variant.price = "FISH-600", Decimal("72"), Decimal("99000")
    variant.save()
    model.name = "Renamed"
    model.save()
    data = client.get(f"/api/v1/inquiries/{inquiry_id}").json()
    assert data["snapshot"]["sku"] == "FISH-570" and data["snapshot"]["price"] == "60000.00"
    assert data["snapshot"]["length_in"] == "68.00" and data["snapshot"]["name"] == "Retro Fish"
    assert "FISH-570" in data["context"]["subtitle"] and data["context"]["title"].startswith("Retro Fish")
    assert data["board_variant"] == str(variant.pk) and data["board_model"] == str(model.pk)


def test_idempotency_key_prevents_duplicates(make_client, workshop, board):
    client = make_client()
    payload = {"kind": "board_purchase", "target_type": "board_model", "target_id": str(board.pk), "message": "Привет"}
    first = client.post("/api/v1/inquiries", payload, format="json", HTTP_IDEMPOTENCY_KEY="key-1")
    second = client.post("/api/v1/inquiries", payload, format="json", HTTP_IDEMPOTENCY_KEY="key-1")
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] == second.json()["id"] and second["Idempotent-Replay"] == "true"
    assert Inquiry.objects.count() == 1 and Message.objects.count() == 1
    other = client.post("/api/v1/inquiries", {**payload, "message": "Другое"}, format="json",
                        HTTP_IDEMPOTENCY_KEY="key-1")
    assert other.status_code == 409 and other.json()["error"]["code"] == "idempotency_mismatch"


def test_participant_rows_created_for_school_managers_only(make_client):
    program = SchoolProgramFactory()
    school = program.organization
    manager, instructor = AccountFactory(), AccountFactory()
    add_member(school, manager, role=Membership.Role.MANAGER)
    add_member(school, instructor, role=Membership.Role.INSTRUCTOR)
    response = post_inquiry(make_client(), kind="program", target_type="school_program", target_id=str(program.pk))
    assert response.status_code == 201
    rows = ConversationParticipant.objects.filter(conversation__inquiry_id=response.json()["id"])
    assert set(rows.values_list("account_id", flat=True)) == {response.wsgi_request.user.pk, school.owner_id, manager.pk}
    assert Notification.objects.filter(kind="inquiry_new", recipient=manager).exists()
    assert not Notification.objects.filter(kind="inquiry_new", recipient=instructor).exists()
