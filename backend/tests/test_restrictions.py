"""Ограничения модератора действуют во всех приложениях (TRUST-07, F14; docs/dev/INTEGRATION_NOTES.md).

publishing/suspended → 403 account_restricted на создание/изменение/публикацию публичного контента;
messaging/suspended → 403 messaging_restricted на сообщения, обращения, личные диалоги.
Снятие своего контента с публикации, личный дневник, жалобы и апелляции остаются доступны.
"""
import datetime as dt

import pytest
from django.utils import timezone

from apps.accounts.models import Specialty, UserProfile
from apps.boards.models import BoardModel
from apps.boards.tests.helpers import photo, published_model, std_type, workshop_for
from apps.club.models import ClubEvent
from apps.club.tests.factories import ClubEventFactory, make_organizer
from apps.community.models import SurfSession
from apps.inventory.models import InventoryItem
from apps.learning.tests.helpers import instructor_account, published_instructor
from apps.organizations.models import Organization
from apps.trust.models import AccountRestriction
from tests.factories import (
    AccountFactory,
    InstructorOfferFactory,
    InventoryItemFactory,
    OrganizationFactory,
    RegionFactory,
    SchoolProgramFactory,
    SpotFactory,
    add_specialty,
    future,
)

pytestmark = pytest.mark.django_db

PUBLISH = "account_restricted"
MESSAGE = "messaging_restricted"


def restrict(account, kind=AccountRestriction.Kind.SUSPENDED, **kwargs):
    return AccountRestriction.objects.create(account=account, kind=kind, reason="Тест", **kwargs)


def assert_code(response, code):
    assert response.status_code == 403, response.content
    assert response.json()["error"]["code"] == code


# --- restrictions service --------------------------------------------------------------------------------------------

def test_expired_and_lifted_restrictions_do_not_block(make_client):
    workshop = workshop_for()
    client = make_client(workshop.owner)
    restrict(workshop.owner, expires_at=timezone.now() - dt.timedelta(minutes=1))
    restrict(workshop.owner, lifted_at=timezone.now())
    response = client.post(f"/api/v1/workshops/{workshop.pk}/models",
                           {"name": "Free", "board_type_id": std_type().pk}, format="json")
    assert response.status_code == 201, response.content


def test_messaging_restriction_does_not_block_publishing(make_client):
    workshop = workshop_for()
    restrict(workshop.owner, AccountRestriction.Kind.MESSAGING)
    response = make_client(workshop.owner).post(f"/api/v1/workshops/{workshop.pk}/models",
                                                {"name": "Still ok", "board_type_id": std_type().pk}, format="json")
    assert response.status_code == 201


# --- boards ----------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("kind", [AccountRestriction.Kind.SUSPENDED, AccountRestriction.Kind.PUBLISHING])
def test_shaper_cannot_create_edit_or_publish_boards(make_client, kind):
    workshop = workshop_for()
    model = published_model(workshop)
    draft = BoardModel.objects.create(workshop=workshop, name="Draft", slug="draft", board_type=std_type())
    client = make_client(workshop.owner)
    restrict(workshop.owner, kind)
    base = f"/api/v1/workshops/{workshop.pk}"
    assert_code(client.post(f"{base}/models", {"name": "X", "board_type_id": std_type().pk}, format="json"), PUBLISH)
    assert_code(client.patch(f"/api/v1/models/{model.pk}", {"name": "Spam"}, format="json"), PUBLISH)
    assert_code(client.post(f"/api/v1/models/{draft.pk}/publish"), PUBLISH)
    assert_code(client.post(f"/api/v1/models/{model.pk}/variants", {"length_in": "70", "width_in": "20"},
                            format="json"), PUBLISH)
    assert_code(client.post(f"/api/v1/models/{model.pk}/media", {"media_ids": [str(photo(workshop.owner).pk)]},
                            format="json"), PUBLISH)
    assert_code(client.put("/api/v1/me/workshop", {"lead_time": "завтра"}, format="json"), PUBLISH)
    assert_code(client.post(f"/api/v1/workshops/{workshop.pk}/publish"), PUBLISH)
    # Снять свою модель с публикации можно.
    assert client.post(f"/api/v1/models/{model.pk}/unpublish").status_code == 200
    draft.refresh_from_db()
    assert draft.status == BoardModel.Status.DRAFT


# --- inventory -------------------------------------------------------------------------------------------------------

def test_renter_cannot_create_or_publish_listing_but_can_take_it_down(make_client):
    owner = AccountFactory()
    add_specialty(owner, Specialty.RENTAL)
    hidden = InventoryItemFactory(owner_account=owner, is_published=False)
    listed = InventoryItemFactory(owner_account=owner)
    client = make_client(owner)
    restrict(owner)
    payload = {"title": "Софттоп", "kind": "board", "purpose": "rental", "rental_price_per_day": "2500"}
    assert_code(client.post("/api/v1/me/inventory", payload, format="json"), PUBLISH)
    assert_code(client.patch(f"/api/v1/me/inventory/{hidden.pk}", {"is_published": True}, format="json"), PUBLISH)
    assert_code(client.patch(f"/api/v1/me/inventory/{listed.pk}", {"title": "Спам"}, format="json"), PUBLISH)
    assert client.patch(f"/api/v1/me/inventory/{listed.pk}", {"is_published": False}, format="json").status_code == 200
    assert client.post(f"/api/v1/me/inventory/{listed.pk}/status", {"status": "maintenance"},
                       format="json").status_code == 200
    listed.refresh_from_db()
    assert (listed.is_published, listed.status) == (False, InventoryItem.Status.MAINTENANCE)


# --- learning --------------------------------------------------------------------------------------------------------

def test_instructor_cannot_publish_profile_offers_or_private_sessions(make_client):
    profile = published_instructor()
    offer = InstructorOfferFactory(instructor=profile)
    client = make_client(profile.account)
    restrict(profile.account)
    me = "/api/v1/me/instructor"
    assert_code(client.post(f"{me}/publish"), PUBLISH)
    assert_code(client.patch(me, {"headline": "Спам"}, format="json"), PUBLISH)
    assert_code(client.post(f"{me}/offers", {"title": "Урок", "price": "2500", "format": "individual"},
                            format="json"), PUBLISH)
    assert_code(client.patch(f"{me}/offers/{offer.pk}", {"price": "1"}, format="json"), PUBLISH)
    start = future(hours=30)[0]
    assert_code(client.post(f"{me}/sessions", {"offer_id": str(offer.pk), "starts_at": start.isoformat()},
                            format="json"), PUBLISH)
    assert client.post(f"{me}/unpublish").json()["status"] == "draft"


def test_school_manager_cannot_publish_programs_or_sessions(make_client):
    org = OrganizationFactory()
    program = SchoolProgramFactory(organization=org)
    client = make_client(org.owner)
    restrict(org.owner, AccountRestriction.Kind.PUBLISHING)
    base = f"/api/v1/organizations/{org.pk}"
    assert_code(client.post(f"{base}/programs", {"title": "Новая", "price": "3000"}, format="json"), PUBLISH)
    assert_code(client.patch(f"{base}/programs/{program.pk}", {"title": "Спам"}, format="json"), PUBLISH)
    start = future(hours=30)[0]
    assert_code(client.post(f"{base}/sessions", {"program_id": str(program.pk), "starts_at": start.isoformat()},
                            format="json"), PUBLISH)


# --- organizations ---------------------------------------------------------------------------------------------------

def test_restricted_account_cannot_create_submit_or_edit_organization(make_client):
    draft = OrganizationFactory(status=Organization.Status.DRAFT, description="Школа", region=RegionFactory(),
                                address="Пляж")
    client = make_client(draft.owner)
    restrict(draft.owner)
    assert_code(client.post("/api/v1/organizations", {"kind": "school", "name": "Новая школа"}, format="json"), PUBLISH)
    assert_code(client.post(f"/api/v1/organizations/{draft.pk}/submit"), PUBLISH)
    assert_code(client.patch(f"/api/v1/organizations/{draft.pk}/manage", {"name": "Спам"}, format="json"), PUBLISH)
    draft.refresh_from_db()
    assert draft.status == Organization.Status.DRAFT


# --- club ------------------------------------------------------------------------------------------------------------

def test_organizer_cannot_publish_events_but_can_cancel_own(make_client):
    organizer = make_organizer()
    event = ClubEventFactory(organizer=organizer)
    client = make_client(organizer)
    restrict(organizer)
    start = timezone.now() + dt.timedelta(days=5)
    assert_code(client.post("/api/v1/club/manage/events", {
        "title": "Сессия", "starts_at": start.isoformat(), "ends_at": (start + dt.timedelta(hours=2)).isoformat(),
    }, format="json"), PUBLISH)
    assert_code(client.patch(f"/api/v1/club/manage/events/{event.pk}", {"title": "Спам"}, format="json"), PUBLISH)
    assert_code(client.post("/api/v1/club/manage/announcements", {"title": "A", "body": "B"}, format="json"), PUBLISH)
    response = client.patch(f"/api/v1/club/manage/events/{event.pk}", {"status": "cancelled"}, format="json")
    assert response.status_code == 200, response.content
    assert ClubEvent.objects.get(pk=event.pk).status == ClubEvent.Status.CANCELLED


# --- community -------------------------------------------------------------------------------------------------------

def test_diary_shared_entries_blocked_private_allowed(make_client):
    client = make_client()
    restrict(client.account, AccountRestriction.Kind.PUBLISHING)
    day = timezone.localdate().isoformat()
    for visibility in ("public", "community"):
        assert_code(client.post("/api/v1/me/diary", {"spot_name": "Бухта", "date": day, "visibility": visibility},
                                format="json"), PUBLISH)
    private = client.post("/api/v1/me/diary", {"spot_name": "Бухта", "date": day}, format="json")
    assert private.status_code == 201
    entry_id = private.json()["id"]
    assert_code(client.patch(f"/api/v1/me/diary/{entry_id}", {"visibility": "public"}, format="json"), PUBLISH)
    assert client.patch(f"/api/v1/me/diary/{entry_id}", {"notes": "Только для себя"}, format="json").status_code == 200
    assert SurfSession.objects.get(pk=entry_id).visibility == SurfSession.Visibility.PRIVATE


# --- trust -----------------------------------------------------------------------------------------------------------

def test_review_blocked_complaint_allowed(make_client):
    client = make_client()
    restrict(client.account)
    spot = SpotFactory()
    assert_code(client.post("/api/v1/reviews", {"target_type": "spot", "target_id": str(spot.pk), "rating": 4,
                                                "text": "Отличный спот"},
                            format="json"), PUBLISH)
    complaint = client.post("/api/v1/complaints", {"target_type": "spot", "target_id": str(spot.pk),
                                                   "reason": "wrong_info", "text": "Неверные координаты"}, format="json")
    assert complaint.status_code == 201, complaint.content


# --- messaging / commerce --------------------------------------------------------------------------------------------

@pytest.mark.parametrize("kind", [AccountRestriction.Kind.SUSPENDED, AccountRestriction.Kind.MESSAGING])
def test_messaging_restriction_blocks_inquiries_messages_and_direct(make_client, kind):
    workshop = workshop_for()
    model = published_model(workshop)
    customer = make_client()
    created = customer.post("/api/v1/inquiries", {"kind": "board_purchase", "target_type": "board_model",
                                                 "target_id": str(model.pk), "message": "Есть в наличии?"},
                            format="json")
    assert created.status_code == 201
    conversation_id = created.json()["conversation_id"]
    peer = AccountFactory()
    UserProfile.objects.filter(account=peer).update(gg_surfer_enabled=True, gg_contact_policy="everyone")
    restrict(customer.account, kind)
    assert_code(customer.post("/api/v1/inquiries", {"kind": "board_purchase", "target_type": "board_model",
                                                   "target_id": str(model.pk), "message": "Ещё раз"}, format="json"),
                MESSAGE)
    assert_code(customer.post(f"/api/v1/conversations/{conversation_id}/messages", {"body": "Спам"}, format="json"),
                MESSAGE)
    assert_code(customer.post("/api/v1/direct-conversations", {"account_id": str(peer.pk)}, format="json"), MESSAGE)
    conversation = customer.get(f"/api/v1/conversations/{conversation_id}").json()
    assert conversation["can_send"] is False


def test_messaging_restricted_owner_cannot_send_invites(make_client):
    org = OrganizationFactory()
    restrict(org.owner, AccountRestriction.Kind.MESSAGING)
    response = make_client(org.owner).post(f"/api/v1/organizations/{org.pk}/invites",
                                           {"email": "coach@example.com", "role": "instructor", "message": "Спам"},
                                           format="json")
    assert_code(response, MESSAGE)


def test_instructor_account_helper_is_unrestricted_by_default(make_client):
    """Контроль: без ограничений те же действия проходят (тесты выше не ложноположительны)."""
    account = instructor_account()
    profile = published_instructor(account)
    client = make_client(account)
    assert client.post("/api/v1/me/instructor/publish").status_code == 200
    assert client.post("/api/v1/me/instructor/offers", {"title": "Урок", "price": "2500", "format": "individual"},
                       format="json").status_code == 201
    assert profile.pk
