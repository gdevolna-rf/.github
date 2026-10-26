"""GET me/metrics — формулы 10.1 и MET-01…07 по событиям и транзакционным таблицам (ATX-29: только
подтверждённые суммы)."""
import datetime as dt
import uuid
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.accounts.models import Specialty
from apps.analytics.models import AnalyticsEvent
from apps.commerce.models import Booking, Inquiry
from apps.community.models import SurfSession
from apps.learning.tests.helpers import (
    booking,
    past_start,
    private_session,
    published_instructor,
    school,
    school_instructor,
    school_session,
)
from apps.organizations.models import Membership, Organization
from apps.trust.models import Review
from tests.factories import (
    AccountFactory,
    BoardModelFactory,
    BoardVariantFactory,
    InventoryItemFactory,
    OrganizationFactory,
    SpotFactory,
    WorkshopFactory,
    add_specialty,
)

pytestmark = pytest.mark.django_db
URL = "/api/v1/me/metrics"
S = Booking.Status


def metrics(client, **params):
    response = client.get(URL, params)
    assert response.status_code == 200, response.content
    data = response.json()
    return {m["key"]: m for m in data["metrics"]}, data


def event(name, *, subject_type, subject_id="x", days_ago=1, context=None, **owners):
    return AnalyticsEvent.objects.create(name=name, subject_type=subject_type, subject_id=str(subject_id),
                                         occurred_at=timezone.now() - dt.timedelta(days=days_ago),
                                         context=context or {}, dedup_key=str(uuid.uuid4()), **owners)


def inquiry(provider_org=None, provider_account=None, customer=None, status="new", **kwargs):
    return Inquiry.objects.create(kind=kwargs.pop("kind", Inquiry.Kind.BOARD_PURCHASE), status=status,
                                  customer=customer or AccountFactory(), provider_organization=provider_org,
                                  provider_account=provider_account, subject="Доска", **kwargs)


def test_metrics_require_login_and_valid_scope(api_client, make_client):
    assert api_client.get(URL, {"scope": "surfer"}).status_code == 401
    response = make_client().get(URL, {"scope": "galaxy"})
    assert response.status_code == 400 and "scope" in response.json()["error"]["fields"]


def test_response_shape_and_default_period(make_client):
    _, data = metrics(make_client(), scope="surfer")
    assert set(data) == {"scope", "period", "rule_version", "generated_at", "subject", "metrics", "breakdowns"}
    today = timezone.localdate()
    assert data["period"]["to"] == today.isoformat()
    assert data["period"]["from"] == (today - dt.timedelta(days=29)).isoformat()
    assert data["rule_version"] == 1
    for item in data["metrics"]:
        assert set(item) == {"key", "label", "value", "unit", "formula", "currency"} and item["formula"]


@pytest.mark.parametrize("params", [{"from": "2026-13-01"}, {"from": "2026-10-10", "to": "2026-10-01"},
                                    {"from": "2024-01-01", "to": "2026-01-01"}, {"tz": "Mars/Base"}])
def test_invalid_period_is_400(make_client, params):
    assert make_client().get(URL, {"scope": "surfer", **params}).status_code == 400


# --- инструктор ------------------------------------------------------------------------------------------------

def test_instructor_metrics(make_client):
    profile = published_instructor()
    me = profile.account
    for _ in range(4):
        event("profile_viewed", subject_type="instructor", subject_id=profile.pk, owner_account=me)
    event("profile_viewed", subject_type="instructor", subject_id=profile.pk, owner_account=me, days_ago=60)
    org = school()
    school_instructor(org, me)
    regular, newbie, quitter = AccountFactory(), AccountFactory(), AccountFactory()
    group = school_session(org, instructor=me, start=past_start(48), capacity=4, status="completed")
    booking(group, customer=regular, status=S.COMPLETED)
    booking(group, customer=newbie, status=S.COMPLETED)
    booking(group, customer=quitter, status=S.CANCELLED, cancelled_side="customer")
    booking(group, status=S.DECLINED)
    private = private_session(profile, start=past_start(24), status="completed")
    booking(private, customer=regular, status=S.COMPLETED)
    inquiry(provider_account=me, kind=Inquiry.Kind.LESSON)
    Review.objects.create(author=regular, target_type="instructor", instructor=profile, rating=5, status="published")
    Review.objects.create(author=newbie, target_type="instructor", instructor=profile, rating=4, status="published")
    Review.objects.create(author=quitter, target_type="instructor", instructor=profile, rating=1, status="pending")

    m, data = metrics(make_client(me), scope="instructor")
    assert m["profile_views"]["value"] == 4
    assert m["inquiries"]["value"] == 1
    assert m["bookings"]["value"] == 5
    assert m["unique_students"]["value"] == 2
    assert m["repeat_students"]["value"] == 50.0  # 1 из 2 учеников с ≥2 завершёнными
    assert m["completed_lessons"]["value"] == 2
    assert m["load"]["value"] == 60.0  # 3 подтверждённых места / (4 + 1)
    assert m["cancellation_share"]["value"] == 25.0  # 1 отмена из 4 (отклонённая не считается)
    assert m["rating"]["value"] == 4.5 and m["reviews"]["value"] == 2  # pending не учитывается
    assert m["conversion"]["value"] == 50.0  # 2 клиента (обращение + частная запись) / 4 просмотра
    assert data["breakdowns"]["cancellations_by_side"]["customer"] == 1
    kinds = {row["kind"] for row in data["breakdowns"]["by_organization"]}
    assert kinds == {"school", "private"}


def test_instructor_scope_unavailable_without_profile(make_client):
    response = make_client().get(URL, {"scope": "instructor"})
    assert response.status_code == 403 and response.json()["error"]["code"] == "scope_unavailable"


# --- школа -----------------------------------------------------------------------------------------------------

def test_school_metrics(make_client):
    org = school()
    coach_a, coach_b = school_instructor(org), school_instructor(org)
    loyal = AccountFactory()
    s1 = school_session(org, instructor=coach_a, start=past_start(72), capacity=4, status="completed")
    s2 = school_session(org, instructor=coach_b, start=past_start(30), capacity=4, status="completed")
    school_session(org, start=past_start(20), capacity=10, status="cancelled")
    booking(s1, customer=loyal, status=S.COMPLETED)
    booking(s1, status=S.NO_SHOW)
    booking(s2, customer=loyal, status=S.COMPLETED)
    booking(s2, status=S.COMPLETED, seats=2)
    for _ in range(5):
        event("organization_viewed", subject_type="organization", subject_id=org.pk, owner_organization=org)
    m, data = metrics(make_client(org.owner), scope="school", organization_id=str(org.pk))
    assert m["fill_rate"]["value"] == 62.5  # 5 мест / 8 (отменённое занятие не в знаменателе)
    assert m["programs"]["value"] == 3  # по программе на каждое занятие из фабрики
    assert m["sessions_planned"]["value"] == 2 and m["sessions_confirmed"]["value"] == 2
    assert m["sessions_completed"]["value"] == 2
    assert m["attendance"]["value"] == 75.0  # 3 пришли / (3 + 1 неявка)
    assert m["unique_students"]["value"] == 2 and m["repeat_students"]["value"] == 50.0
    assert m["profile_views"]["value"] == 5 and m["conversion"]["value"] == 60.0  # 3 клиента / 5 просмотров
    table = {row["instructor"]["id"]: row for row in data["breakdowns"]["instructors"]}
    assert table[str(coach_a.pk)]["attendance_pct"] == 50.0 and table[str(coach_a.pk)]["fill_rate_pct"] == 50.0
    assert table[str(coach_b.pk)]["seats_confirmed"] == 3
    assert data["subject"]["organizations"][0]["id"] == str(org.pk)


def test_school_metrics_access(make_client):
    org = school()
    manager = school_instructor(org, role=Membership.Role.MANAGER)
    assert make_client(manager).get(URL, {"scope": "school", "organization_id": str(org.pk)}).status_code == 200
    coach = school_instructor(org)
    assert make_client(coach).get(URL, {"scope": "school", "organization_id": str(org.pk)}).status_code == 403
    assert make_client().get(URL, {"scope": "school", "organization_id": str(org.pk)}).status_code == 403
    Membership.objects.filter(account=manager).update(status=Membership.Status.REVOKED)
    assert make_client(manager).get(URL, {"scope": "school", "organization_id": str(org.pk)}).status_code == 403
    second = OrganizationFactory(owner=org.owner)
    response = make_client(org.owner).get(URL, {"scope": "school"})
    assert response.status_code == 400 and response.json()["error"]["code"] == "organization_required"
    workshop = WorkshopFactory(owner=second.owner)
    response = make_client(org.owner).get(URL, {"scope": "school", "organization_id": str(workshop.pk)})
    assert response.json()["error"]["code"] == "scope_mismatch"


# --- шейпер ----------------------------------------------------------------------------------------------------

def test_shaper_metrics_only_confirmed_revenue(make_client):
    workshop = WorkshopFactory()
    fish = BoardModelFactory(workshop=workshop)
    variant = BoardVariantFactory(model=fish)
    BoardModelFactory(workshop=workshop, status="draft")
    for _ in range(3):
        event("board_viewed", subject_type="board_model", subject_id=fish.pk, owner_organization=workshop,
              context={"model_id": str(fish.pk), "board_type": "shortboard"})
    event("board_viewed", subject_type="board_variant", subject_id=variant.pk, owner_organization=workshop,
          context={"model_id": str(fish.pk), "variant_id": str(variant.pk), "board_type": "shortboard"})
    buyer, other = AccountFactory(), AccountFactory()
    inquiry(workshop, customer=buyer, board_model=fish)
    inquiry(workshop, customer=buyer, board_variant=variant)  # тот же клиент и модель — одно уникальное
    now = timezone.now()
    inquiry(workshop, customer=other, board_model=fish, status="completed", agreed_amount=Decimal("50000"),
            amount_confirmed=True, closed_at=now)
    inquiry(workshop, customer=AccountFactory(), status="completed", agreed_amount=Decimal("100000"),
            amount_confirmed=False, closed_at=now, kind=Inquiry.Kind.CUSTOM_ORDER)
    inquiry(workshop, status="completed", kind=Inquiry.Kind.REPAIR, closed_at=now)
    m, data = metrics(make_client(workshop.owner), scope="shaper")
    assert m["published_models"]["value"] == 1
    assert m["model_views"]["value"] == 4
    assert m["inquiries"]["value"] == 5 and m["inquiries_active"]["value"] == 2
    assert m["inquiries_completed"]["value"] == 3 and m["unique_clients"]["value"] == 4
    assert m["conversion"]["value"] == 50.0  # 2 уникальных обращения из каталога / 4 просмотра
    assert m["revenue_confirmed"]["value"] == "50000.00" and m["revenue_confirmed"]["currency"] == "RUB"
    assert m["average_check"]["value"] == "50000.00"
    assert m["sales"]["value"] == 2 and m["repairs"]["value"] == 1
    assert data["breakdowns"]["deals_unconfirmed"] == 2
    assert data["breakdowns"]["views_by_subject"] == {"board_model": 3, "board_variant": 1}
    by_type = data["breakdowns"]["interest_by_board_type"][0]
    assert by_type["board_type"] == "shortboard" and by_type["views"] == 4 and by_type["inquiries"] == 3


def test_shaper_scope_requires_workshop_membership(make_client):
    response = make_client().get(URL, {"scope": "shaper"})
    assert response.status_code == 403 and response.json()["error"]["code"] == "scope_unavailable"
    workshop = WorkshopFactory()
    assert make_client().get(URL, {"scope": "shaper", "organization_id": str(workshop.pk)}).status_code == 403
    assert make_client().get(URL, {"scope": "shaper", "organization_id": str(uuid.uuid4())}).status_code == 404


# --- прокат ----------------------------------------------------------------------------------------------------

def rental(item, *, start, hours, status, **kwargs):
    return Booking.objects.create(kind=Booking.Kind.RENTAL, inventory_item=item, customer=AccountFactory(),
                                  provider_account=item.owner_account, starts_at=start,
                                  ends_at=start + dt.timedelta(hours=hours), status=status, **kwargs)


def test_rental_metrics(make_client):
    owner = AccountFactory()
    add_specialty(owner, Specialty.RENTAL)
    busy, free = InventoryItemFactory(owner_account=owner), InventoryItemFactory(owner_account=owner)
    InventoryItemFactory(owner_account=owner, purpose="sale")
    now = timezone.now()
    rental(busy, start=now - dt.timedelta(hours=2), hours=24, status=S.IN_PROGRESS)
    rental(free, start=now - dt.timedelta(days=3), hours=24, status=S.COMPLETED, price_amount=Decimal("2500"),
           amount_confirmed=True, completed_at=now - dt.timedelta(days=2))
    rental(free, start=now - dt.timedelta(days=6), hours=24, status=S.COMPLETED, price_amount=Decimal("9000"),
           amount_confirmed=False, completed_at=now - dt.timedelta(days=5))
    rental(free, start=now - dt.timedelta(days=8), hours=24, status=S.CANCELLED, cancelled_side="customer")
    event("item_viewed", subject_type="inventory_item", subject_id=busy.pk, owner_account=owner)
    m, data = metrics(make_client(owner), scope="rental")
    assert m["items"]["value"] == 2  # товар только для продажи не учитывается
    assert m["booked_now"]["value"] == 1 and m["free_now"]["value"] == 1
    assert m["bookings_confirmed"]["value"] == 3
    assert m["revenue_confirmed"]["value"] == "2500.00"  # неподтверждённые 9000 не учитываются
    assert m["cancellation_share"]["value"] == 25.0
    assert m["item_views"]["value"] == 1
    assert m["utilization"]["value"] is not None and 0 < m["utilization"]["value"] < 100
    assert data["breakdowns"]["by_kind"] == [{"kind": "board", "items": 2, "booked_now": 1}]


def test_rental_scope_for_organization_and_unavailable(make_client):
    response = make_client().get(URL, {"scope": "rental"})
    assert response.json()["error"]["code"] == "scope_unavailable"
    org = OrganizationFactory(kind=Organization.Kind.RENTAL)
    InventoryItemFactory(owner_account=None, owner_organization=org)
    m, data = metrics(make_client(org.owner), scope="rental", organization_id=str(org.pk))
    assert m["items"]["value"] == 1 and data["subject"]["organizations"][0]["id"] == str(org.pk)


# --- GG Surfer -------------------------------------------------------------------------------------------------

def test_surfer_metrics(make_client):
    me = AccountFactory()
    spot = SpotFactory()
    today = timezone.localdate()
    SurfSession.objects.create(account=me, spot=spot, date=today, duration_min=90)
    SurfSession.objects.create(account=me, spot=spot, date=today, duration_min=30)
    SurfSession.objects.create(account=me, spot_name="Дикий пляж", date=today - dt.timedelta(days=3))
    SurfSession.objects.create(account=me, spot=spot, date=today - dt.timedelta(days=90))
    SurfSession.objects.create(account=AccountFactory(), spot=spot, date=today)
    m, data = metrics(make_client(me), scope="surfer")
    assert m["ride_days"]["value"] == 2 and m["sessions"]["value"] == 3
    assert m["visited_spots"]["value"] == 2 and m["ride_minutes"]["value"] == 120
    spots = {s["name"]: s for s in data["breakdowns"]["spots"]}
    assert spots[spot.name]["spot"]["slug"] == spot.slug and spots[spot.name]["days"] == 1
    assert spots["Дикий пляж"]["spot"] is None


def test_custom_period_bounds_are_inclusive(make_client):
    me = AccountFactory()
    SurfSession.objects.create(account=me, date=dt.date(2026, 9, 1), spot_name="A")
    SurfSession.objects.create(account=me, date=dt.date(2026, 9, 30), spot_name="B")
    SurfSession.objects.create(account=me, date=dt.date(2026, 10, 1), spot_name="C")
    m, data = metrics(make_client(me), scope="surfer", **{"from": "2026-09-01", "to": "2026-09-30"})
    assert m["ride_days"]["value"] == 2
    assert data["period"]["from"] == "2026-09-01" and data["period"]["to"] == "2026-09-30"
