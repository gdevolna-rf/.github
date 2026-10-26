"""Сквозной сценарий F12 и Django Admin GG Surfer."""
import datetime as dt

import pytest
from django.utils import timezone

from apps.accounts.models import UserProfile
from apps.community.models import BirthdayGreeting
from apps.community.tasks import send_birthday_greetings
from apps.community.tests.factories import SurfSessionFactory, gg_account
from apps.messaging.models import Notification
from tests.factories import AccountFactory, SpotFactory

pytestmark = pytest.mark.django_db


def test_f12_gg_surfer_diary_visibility_and_birthday_with_consent(make_client, api_client):
    """F12: включает GG Surfer, ведёт дневник, скрывает видимость, поздравление — только при согласии."""
    surfer = make_client()
    handle = surfer.account.profile.handle
    assert api_client.get(f"/api/v1/surfers/{handle}").status_code == 404  # без согласия анкеты нет (BR-12)
    UserProfile.objects.filter(pk=surfer.account.pk).update(gg_surfer_enabled=True,
                                                             birth_date=timezone.localdate().replace(year=1992))
    assert api_client.get(f"/api/v1/surfers/{handle}").status_code == 200

    spot = SpotFactory()
    created = surfer.post("/api/v1/me/diary", {"spot_id": str(spot.pk), "date": timezone.localdate().isoformat(),
                                               "visibility": "public"}, format="json").json()
    assert api_client.get(f"/api/v1/surfers/{handle}/diary").json()["count"] == 1
    surfer.patch(f"/api/v1/me/diary/{created['id']}", {"visibility": "private"}, format="json")
    assert api_client.get(f"/api/v1/surfers/{handle}/diary").json()["count"] == 0
    assert api_client.get(f"/api/v1/surfers/{handle}").json()["diary"]["ride_days"] == 0
    assert surfer.get("/api/v1/me/diary/stats").json()["ride_days"] == 1

    today = timezone.localdate()
    assert send_birthday_greetings(today.isoformat()) == 0  # согласия нет
    UserProfile.objects.filter(pk=surfer.account.pk).update(birthday_greetings_consent=True)
    if (today.month, today.day) != (2, 29):
        assert send_birthday_greetings(today.isoformat()) == 1
        assert Notification.objects.filter(recipient=surfer.account, kind="birthday").count() == 1
        assert BirthdayGreeting.objects.filter(account=surfer.account).exists()


def test_admin_pages_load(make_client):
    admin = make_client(AccountFactory(is_staff=True, is_superuser=True), two_factor=True)
    entry = SurfSessionFactory(account=gg_account(), date=timezone.localdate() - dt.timedelta(days=1))
    BirthdayGreeting.objects.create(account=entry.account, year=2026)
    for url in ("/admin/community/surfsession/", f"/admin/community/surfsession/{entry.pk}/change/",
                "/admin/community/birthdaygreeting/"):
        assert admin.get(url).status_code == 200, url
