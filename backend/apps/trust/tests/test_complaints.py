"""Жалобы, меры, апелляции и ограничения аккаунтов (TRUST-07, MSG-13, F14)."""
import datetime as dt
import uuid
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.club.models import ClubEvent
from apps.mediafiles.models import MediaAsset
from apps.messaging.models import Notification
from apps.organizations.models import Organization
from apps.spots.models import Spot
from apps.trust.models import AccountRestriction, AuditEvent, Complaint, ModerationCase, Review
from apps.trust.services.moderation_queue import open_case
from apps.trust.services.ratings import recalculate
from apps.trust.tests.helpers import conversation_message
from tests.factories import (
    AccountFactory,
    BoardModelFactory,
    InventoryItemFactory,
    MediaAssetFactory,
    OrganizationFactory,
    SpotFactory,
    make_moderator,
)

pytestmark = pytest.mark.django_db


def _complain(client, target_type, target_id, reason="spam", text=""):
    return client.post("/api/v1/complaints", {"target_type": target_type, "target_id": str(target_id), "reason": reason,
                                              "text": text}, format="json")


def _event(organizer):
    start = timezone.now() + dt.timedelta(days=3)
    return ClubEvent.objects.create(slug=f"ev-{uuid.uuid4().hex[:6]}", title="Катание", status="published",
                                    starts_at=start, ends_at=start + dt.timedelta(hours=3), organizer=organizer)


def _targets(reporter):
    """(target_type, объект, ожидаемый владелец)."""
    owner = AccountFactory()
    review = Review.objects.create(author=owner, target_type="spot", spot=SpotFactory(), rating=1, status="published")
    org_item = InventoryItemFactory(owner_account=None, owner_organization=OrganizationFactory(owner=owner))
    return [
        ("spot", SpotFactory(), None),
        ("account", owner, owner),
        ("review", review, owner),
        ("message", conversation_message(owner, reporter), owner),
        ("board_model", BoardModelFactory(workshop__owner=owner), owner),
        ("inventory_item", InventoryItemFactory(owner_account=owner), owner),
        ("inventory_item", org_item, owner),
        ("organization", OrganizationFactory(owner=owner), owner),
        ("media", MediaAssetFactory(owner=owner), owner),
        ("club_event", _event(owner), owner),
    ]


def test_guest_cannot_complain(api_client):
    assert _complain(api_client, "spot", SpotFactory().id).status_code == 401


def test_complaint_resolves_target_owner_for_every_type_and_opens_case(make_client):
    client = make_client()
    for target_type, obj, owner in _targets(client.account):
        response = _complain(client, target_type, obj.pk)
        assert response.status_code == 201, (target_type, response.json())
        complaint = Complaint.objects.get(pk=response.json()["id"])
        assert complaint.target_owner == owner, target_type
        case = ModerationCase.objects.get(complaint=complaint)
        assert case.kind == "complaint" and case.due_at
    assert client.get("/api/v1/me/complaints").json()["count"] == 10


def test_complaint_on_missing_or_invisible_target_is_404(make_client):
    client = make_client()
    stranger_message = conversation_message(AccountFactory(), AccountFactory())
    hidden_spot = SpotFactory(status=Spot.Status.HIDDEN)
    private_media = MediaAssetFactory(visibility=MediaAsset.Visibility.PRIVATE)
    for target_type, target_id in (("spot", uuid.uuid4()), ("message", stranger_message.id), ("spot", hidden_spot.id),
                                   ("media", private_media.id), ("organization", OrganizationFactory(status="draft").id)):
        response = _complain(client, target_type, target_id)
        assert response.status_code == 404, target_type


def test_cannot_complain_about_own_content(make_client):
    client = make_client()
    response = _complain(client, "account", client.account.id)
    assert response.status_code == 400 and response.json()["error"]["code"] == "self_complaint"


def test_duplicate_open_complaint_is_conflict_and_other_reason_requires_text(make_client):
    client = make_client()
    spot = SpotFactory()
    assert _complain(client, "spot", spot.id, reason="wrong_info").status_code == 201
    response = _complain(client, "spot", spot.id, reason="spam")
    assert response.status_code == 409 and response.json()["error"]["code"] == "complaint_exists"
    assert _complain(client, "spot", SpotFactory().id, reason="other").status_code == 400
    assert _complain(client, "spot", SpotFactory().id, reason="bogus").status_code == 400


def _resolve(mod_client, complaint_id, action, note="Нарушение правил", **extra):
    return mod_client.post(f"/api/v1/moderation/complaints/{complaint_id}/resolve",
                           {"action": action, "note": note, **extra}, format="json")


@pytest.mark.parametrize("index,check", [
    (0, lambda o: o.status == Spot.Status.HIDDEN),
    (2, lambda o: o.status == Review.Status.HIDDEN),
    (3, lambda o: o.is_hidden is True),
    (4, lambda o: o.status == "hidden"),
    (5, lambda o: o.is_published is False),
    (7, lambda o: o.status == Organization.Status.SUSPENDED),
    (8, lambda o: o.status == MediaAsset.Status.REJECTED),
    (9, lambda o: o.status == ClubEvent.Status.CANCELLED),
])
def test_resolve_hidden_hides_target_of_each_type(make_client, mod_client, index, check):
    """F14: модератор скрывает объявление/материал, действие в журнале."""
    client = make_client()
    target_type, obj, _ = _targets(client.account)[index]
    complaint_id = _complain(client, target_type, obj.pk).json()["id"]
    response = _resolve(mod_client, complaint_id, "hidden")
    assert response.status_code == 200, response.json()
    assert response.json()["action_taken"]["code"] == "hidden"
    obj.refresh_from_db()
    assert check(obj)
    audit = AuditEvent.objects.get(action="complaint.resolved", object_id=complaint_id)
    assert audit.metadata["action"] == "hidden" and audit.before and audit.after
    assert Notification.objects.filter(recipient=client.account, kind="complaint").exists()
    assert ModerationCase.objects.get(complaint_id=complaint_id).status == "resolved"


def test_hiding_review_recalculates_rating_and_drops_pending_revision(make_client, mod_client):
    spot = SpotFactory()
    review = Review.objects.create(author=AccountFactory(), target_type="spot", spot=spot, rating=1, status="published",
                                   has_pending_revision=True, pending_rating=2, pending_text="правка")
    revision_case = open_case("review", "Правка", review=review)
    Review.objects.create(author=AccountFactory(), target_type="spot", spot=spot, rating=5, status="published")
    recalculate("spot", spot.id)
    complaint_id = _complain(make_client(), "review", review.id, reason="offensive").json()["id"]
    _resolve(mod_client, complaint_id, "hidden")
    spot.refresh_from_db()
    assert (spot.rating_avg, spot.rating_count) == (Decimal("5.00"), 1)
    review.refresh_from_db()
    assert review.has_pending_revision is False
    revision_case.refresh_from_db()
    assert revision_case.status == "resolved" and revision_case.resolution == "hidden"


def test_concurrent_duplicate_complaint_is_blocked_by_database(make_client):
    from django.db import IntegrityError, transaction

    client = make_client()
    spot = SpotFactory()
    Complaint.objects.create(reporter=client.account, target_type="spot", target_id=str(spot.id), reason="spam")
    with pytest.raises(IntegrityError), transaction.atomic():
        Complaint.objects.create(reporter=client.account, target_type="spot", target_id=str(spot.id), reason="fraud")


def test_hidden_not_applicable_to_account(make_client, mod_client):
    complaint_id = _complain(make_client(), "account", AccountFactory().id).json()["id"]
    response = _resolve(mod_client, complaint_id, "hidden")
    assert response.status_code == 400 and response.json()["error"]["code"] == "action_not_applicable"
    assert Complaint.objects.get(pk=complaint_id).status == "open"


def test_suspend_owner_blocks_publishing_but_keeps_account_active(make_client, mod_client):
    owner_client = make_client()
    complaint_id = _complain(make_client(), "account", owner_client.account.id, reason="fraud").json()["id"]
    response = _resolve(mod_client, complaint_id, "suspended", note="Мошенничество")
    assert response.status_code == 200
    restriction = AccountRestriction.objects.get(account=owner_client.account)
    assert restriction.kind == "suspended" and restriction.reason == "Мошенничество"
    owner_client.account.refresh_from_db()
    assert owner_client.account.is_active is True
    review = owner_client.post("/api/v1/reviews", {"target_type": "spot", "target_id": str(SpotFactory().id),
                                                   "rating": 5, "text": "x"}, format="json")
    assert review.status_code == 403 and review.json()["error"]["code"] == "account_restricted"
    note = Notification.objects.get(recipient=owner_client.account, kind="moderation_decision")
    assert note.payload["can_appeal"] is True and note.payload["complaint_id"] == complaint_id


def test_warning_and_suspension_need_target_owner(make_client, mod_client):
    complaint_id = _complain(make_client(), "spot", SpotFactory().id).json()["id"]
    assert _resolve(mod_client, complaint_id, "warning").status_code == 400
    assert _resolve(mod_client, complaint_id, "suspended").status_code == 400
    assert _resolve(mod_client, complaint_id, "none").status_code == 200


def test_resolving_closes_all_open_complaints_on_same_target(make_client, mod_client):
    spot = SpotFactory()
    first = _complain(make_client(), "spot", spot.id).json()["id"]
    second = _complain(make_client(), "spot", spot.id).json()["id"]
    _resolve(mod_client, first, "hidden")
    assert Complaint.objects.get(pk=second).status == "resolved"
    assert not ModerationCase.objects.filter(status="open").exists()


def test_dismiss_and_repeat_decision(make_client, mod_client):
    complaint_id = _complain(make_client(), "spot", SpotFactory().id).json()["id"]
    response = mod_client.post(f"/api/v1/moderation/complaints/{complaint_id}/dismiss", {"note": "Нет нарушения"},
                               format="json")
    assert response.status_code == 200 and response.json()["status"]["code"] == "dismissed"
    assert _resolve(mod_client, complaint_id, "hidden").status_code == 409


def test_moderator_cannot_resolve_complaint_about_self(make_client):
    moderator = make_moderator(AccountFactory())
    complaint_id = _complain(make_client(), "account", moderator.id).json()["id"]
    response = _resolve(make_client(moderator, two_factor=True), complaint_id, "none")
    assert response.status_code == 403


def test_complaint_case_detail_has_target_snapshot(make_client, mod_client):
    reporter = make_client()
    owner = AccountFactory()
    message = conversation_message(owner, reporter.account, body="Купи крипту")
    complaint_id = _complain(reporter, "message", message.id, reason="spam").json()["id"]
    case = ModerationCase.objects.get(complaint_id=complaint_id)
    data = mod_client.get(f"/api/v1/moderation/cases/{case.id}").json()
    target = data["target"]
    assert target["type"] == "complaint" and target["target_snapshot"]["body"] == "Купи крипту"
    assert target["target_owner"]["id"] == str(owner.id) and target["reporter"]["id"] == str(reporter.account.id)
    assert data["available_actions"] == ["resolve", "dismiss"]
    assert AuditEvent.objects.filter(action="message.viewed_by_moderator", object_id=str(message.id)).exists()


# --- апелляции -----------------------------------------------------------------------------------

def test_owner_appeals_and_granted_appeal_restores_target(make_client, mod_client):
    owner_client = make_client()
    item = InventoryItemFactory(owner_account=owner_client.account)
    complaint_id = _complain(make_client(), "inventory_item", item.id).json()["id"]
    # до решения владелец не видит жалобу и не может её обжаловать
    assert owner_client.get("/api/v1/me/complaints?box=against").json()["count"] == 0
    assert owner_client.post(f"/api/v1/complaints/{complaint_id}/appeal", {"text": "x"}, format="json").status_code == 409
    _resolve(mod_client, complaint_id, "hidden")
    against = owner_client.get("/api/v1/me/complaints?box=against").json()["results"][0]
    assert against["can_appeal"] is True and "text" not in against and "reporter" not in against

    assert make_client().post(f"/api/v1/complaints/{complaint_id}/appeal", {"text": "x"}, format="json").status_code == 404
    response = owner_client.post(f"/api/v1/complaints/{complaint_id}/appeal", {"text": "Доска на месте, фото свои"},
                                 format="json")
    assert response.status_code == 200
    appeal_case = ModerationCase.objects.get(complaint_id=complaint_id, kind="appeal")
    assert appeal_case.status == "open"
    assert owner_client.post(f"/api/v1/complaints/{complaint_id}/appeal", {"text": "ещё"}, format="json").status_code == 409
    detail = mod_client.get(f"/api/v1/moderation/cases/{appeal_case.id}").json()
    assert detail["available_actions"] == ["appeal_grant", "appeal_deny"]

    response = mod_client.post(f"/api/v1/moderation/complaints/{complaint_id}/appeal-decision",
                               {"grant": True, "note": "Ошиблись"}, format="json")
    assert response.status_code == 200, response.json()
    item.refresh_from_db()
    assert item.is_published is True
    assert Complaint.objects.get(pk=complaint_id).action_taken == "none"
    appeal_case.refresh_from_db()
    assert appeal_case.status == "resolved" and appeal_case.resolution == "appeal_granted"
    assert AuditEvent.objects.filter(action="complaint.appeal_granted").exists()
    assert mod_client.post(f"/api/v1/moderation/complaints/{complaint_id}/appeal-decision", {"grant": False},
                           format="json").status_code == 409


def test_granted_appeal_lifts_suspension_denied_keeps_it(make_client, mod_client):
    owner_client = make_client()
    first = _complain(make_client(), "account", owner_client.account.id).json()["id"]
    _resolve(mod_client, first, "suspended")
    owner_client.post(f"/api/v1/complaints/{first}/appeal", {"text": "Это не я"}, format="json")
    mod_client.post(f"/api/v1/moderation/complaints/{first}/appeal-decision", {"grant": False}, format="json")
    assert AccountRestriction.objects.get(account=owner_client.account).lifted_at is None
    assert Complaint.objects.get(pk=first).action_taken == "suspended"


def test_suspension_lifted_after_granted_appeal(make_client, mod_client):
    owner_client = make_client()
    complaint_id = _complain(make_client(), "account", owner_client.account.id).json()["id"]
    _resolve(mod_client, complaint_id, "suspended")
    owner_client.post(f"/api/v1/complaints/{complaint_id}/appeal", {"text": "Это не я"}, format="json")
    mod_client.post(f"/api/v1/moderation/complaints/{complaint_id}/appeal-decision", {"grant": True}, format="json")
    assert AccountRestriction.objects.get(account=owner_client.account).lifted_at is not None


# --- ограничения аккаунтов вручную ---------------------------------------------------------------

def test_restrict_lift_and_account_summary(mod_client, make_client, moderator):
    target = make_client()
    url = f"/api/v1/moderation/accounts/{target.account.id}"
    assert make_client().post(f"{url}/restrict", {"kind": "messaging", "reason": "Спам"}, format="json").status_code == 403
    past = (timezone.now() - dt.timedelta(days=1)).isoformat()
    assert mod_client.post(f"{url}/restrict", {"kind": "messaging", "reason": "x", "expires_at": past},
                           format="json").status_code == 400
    response = mod_client.post(f"{url}/restrict", {"kind": "publishing", "reason": "Спам в отзывах"}, format="json")
    assert response.status_code == 201
    restriction_id = response.json()["id"]
    assert response.json()["is_active"] is True and response.json()["kind"]["code"] == "publishing"
    again = mod_client.post(f"{url}/restrict", {"kind": "publishing", "reason": "ещё"}, format="json")
    assert again.status_code == 409
    assert AuditEvent.objects.filter(action="account.restricted", object_id=str(target.account.id)).exists()
    assert Notification.objects.filter(recipient=target.account, title="Аккаунт ограничен").exists()

    summary = mod_client.get(url).json()
    assert summary["account"]["id"] == str(target.account.id)
    assert summary["restrictions"][0]["id"] == restriction_id
    assert summary["summary"]["is_active"] is True and "email" not in summary["account"]

    response = mod_client.post(f"/api/v1/moderation/restrictions/{restriction_id}/lift", {"note": "Исправился"},
                               format="json")
    assert response.status_code == 200 and response.json()["is_active"] is False
    assert mod_client.post(f"/api/v1/moderation/restrictions/{restriction_id}/lift").status_code == 409
    assert mod_client.get(f"/api/v1/moderation/accounts/{uuid.uuid4()}").status_code == 404


def test_moderator_cannot_restrict_self_or_other_staff(mod_client, moderator, make_client):
    assert mod_client.post(f"/api/v1/moderation/accounts/{moderator.id}/restrict",
                           {"kind": "messaging", "reason": "x"}, format="json").status_code == 403
    colleague = make_moderator(AccountFactory())
    assert mod_client.post(f"/api/v1/moderation/accounts/{colleague.id}/restrict",
                           {"kind": "messaging", "reason": "x"}, format="json").status_code == 403
    admin = make_client(make_moderator(AccountFactory(), role="admin"), two_factor=True)
    assert admin.post(f"/api/v1/moderation/accounts/{colleague.id}/restrict",
                      {"kind": "messaging", "reason": "x"}, format="json").status_code == 201
