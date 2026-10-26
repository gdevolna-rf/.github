"""POST analytics/views — квалифицированные просмотры (раздел 10, MET-08): боты, самопросмотры, повторы."""
import pytest
from rest_framework.test import APIClient

from apps.analytics.models import AnalyticsEvent
from apps.boards.models import BoardModel
from apps.learning.tests.helpers import published_instructor
from apps.organizations.models import Organization
from tests.factories import (
    AccountFactory,
    BoardModelFactory,
    BoardVariantFactory,
    InventoryItemFactory,
    OrganizationFactory,
    SpotFactory,
)

pytestmark = pytest.mark.django_db
URL = "/api/v1/analytics/views"
BROWSER = {"HTTP_USER_AGENT": "Mozilla/5.0 (iPhone) Safari/605.1"}


def view(client, subject_type, subject_id, **extra):
    return client.post(URL, {"subject_type": subject_type, "subject_id": str(subject_id)}, format="json",
                       **{**BROWSER, **extra})


def test_anonymous_view_counted_once_per_day_and_cookie_issued(api_client):
    profile = published_instructor()
    first = view(api_client, "instructor", profile.pk)
    assert first.status_code == 200
    assert first.json() == {"counted": True, "event": "profile_viewed", "subject_type": "instructor",
                            "subject_id": str(profile.pk)}
    cookie = first.cookies["gv_aid"]
    assert cookie.value and cookie["httponly"]
    second = view(api_client, "instructor", profile.pk)  # cookie уже у клиента
    assert second.json()["counted"] is False and "gv_aid" not in second.cookies
    event = AnalyticsEvent.objects.get(name="profile_viewed")
    assert event.owner_account == profile.account and event.anonymous_id == cookie.value
    assert event.actor is None and event.rule_version == 1


def test_cookieless_client_is_not_counted_repeatedly(db):
    profile = published_instructor()
    for _ in range(3):
        view(APIClient(), "instructor", profile.pk)  # новый клиент без cookie, тот же IP и UA
    assert AnalyticsEvent.objects.filter(name="profile_viewed").count() == 1


def test_bots_and_self_views_are_excluded(api_client, make_client):
    profile = published_instructor()
    bot = view(api_client, "instructor", profile.pk, HTTP_USER_AGENT="Googlebot/2.1")
    assert bot.json()["counted"] is False
    assert view(make_client(profile.account), "instructor", profile.pk).json()["counted"] is False
    viewer = make_client(AccountFactory())
    assert view(viewer, "instructor", profile.account.profile.handle).json()["counted"] is True  # по handle
    assert view(viewer, "instructor", profile.pk).json()["counted"] is False  # повтор того же зрителя
    assert AnalyticsEvent.objects.get().actor == viewer.account


def test_staff_of_owner_organization_are_excluded(make_client):
    org = OrganizationFactory()
    assert view(make_client(org.owner), "organization", org.slug).json()["counted"] is False
    assert view(make_client(), "organization", org.pk).json()["counted"] is True
    event = AnalyticsEvent.objects.get(name="organization_viewed")
    assert event.owner_organization == org and event.subject_id == str(org.pk)


def test_board_views_carry_model_variant_and_type(make_client):
    model = BoardModelFactory()
    variant = BoardVariantFactory(model=model)
    client = make_client()
    assert view(client, "board_model", model.pk).json()["event"] == "board_viewed"
    assert view(client, "board_variant", variant.pk).json()["counted"] is True
    model_event = AnalyticsEvent.objects.get(subject_type="board_model")
    assert model_event.context == {"model_id": str(model.pk), "variant_id": None, "board_type": "shortboard",
                                   "board_type_name": model.board_type.name}
    assert model_event.owner_organization == model.workshop
    variant_event = AnalyticsEvent.objects.get(subject_type="board_variant")
    assert variant_event.context["variant_id"] == str(variant.pk)


def test_spot_item_and_surfer_subjects(make_client):
    client = make_client()
    spot = SpotFactory()
    assert view(client, "spot", spot.slug).json()["counted"] is True
    item = InventoryItemFactory()
    assert view(client, "inventory_item", item.pk).json()["event"] == "item_viewed"
    assert AnalyticsEvent.objects.get(name="item_viewed").owner_account == item.owner_account
    surfer = AccountFactory()
    assert view(client, "surfer", surfer.pk).status_code == 404  # без согласия GG Surfer
    surfer.profile.gg_surfer_enabled = True
    surfer.profile.save()
    assert view(client, "surfer", surfer.profile.handle).json()["subject_id"] == str(surfer.pk)


@pytest.mark.parametrize("make_subject,subject_type", [
    (lambda: published_instructor(status="draft").pk, "instructor"),
    (lambda: OrganizationFactory(status=Organization.Status.DRAFT).pk, "organization"),
    (lambda: BoardModelFactory(status=BoardModel.Status.DRAFT).pk, "board_model"),
    (lambda: "00000000-0000-0000-0000-000000000000", "inventory_item"),
    (lambda: "not-a-uuid", "board_variant"),
])
def test_unpublished_or_unknown_subjects_are_404(api_client, make_subject, subject_type):
    response = view(api_client, subject_type, make_subject())
    assert response.status_code == 404 and response.json()["error"]["code"] == "subject_not_found"
    assert not AnalyticsEvent.objects.exists()


def test_invalid_subject_type_is_400(api_client):
    response = api_client.post(URL, {"subject_type": "planet", "subject_id": "x"}, format="json")
    assert response.status_code == 400 and "subject_type" in response.json()["error"]["fields"]
