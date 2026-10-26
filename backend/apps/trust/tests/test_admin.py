"""Django Admin спотов и trust: страницы открываются, журнал аудита неизменяем, правки пишут аудит."""
import pytest
from django.test import Client

from apps.accounts.services.roles import OTP_SESSION_KEY
from apps.trust.models import AuditEvent, Review
from apps.trust.services.audit import record
from tests.factories import AccountFactory, SpotFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_client_2fa():
    admin = AccountFactory(is_staff=True, is_superuser=True)
    client = Client()
    client.force_login(admin)
    session = client.session
    session[OTP_SESSION_KEY] = "test"
    session.save()
    client.account = admin
    return client


@pytest.mark.parametrize("url", [
    "/admin/spots/spot/", "/admin/spots/region/", "/admin/spots/spotchangerequest/", "/admin/spots/spotforecast/",
    "/admin/trust/review/", "/admin/trust/complaint/", "/admin/trust/moderationcase/",
    "/admin/trust/accountrestriction/", "/admin/trust/auditevent/",
])
def test_admin_changelists_open(admin_client_2fa, url):
    SpotFactory()
    assert admin_client_2fa.get(url).status_code == 200


def test_spot_admin_change_page_and_add_page_render(admin_client_2fa):
    spot = SpotFactory()
    assert admin_client_2fa.get(f"/admin/spots/spot/{spot.pk}/change/").status_code == 200
    assert admin_client_2fa.get("/admin/spots/spot/add/").status_code == 200


def test_audit_event_admin_is_read_only(admin_client_2fa):
    event = record(admin_client_2fa.account, "spot.change_approved", SpotFactory(), before={"a": 1})
    assert admin_client_2fa.get(f"/admin/trust/auditevent/{event.pk}/change/").status_code == 200
    assert admin_client_2fa.get("/admin/trust/auditevent/add/").status_code == 403
    assert admin_client_2fa.post(f"/admin/trust/auditevent/{event.pk}/delete/", {"post": "yes"}).status_code == 403
    assert AuditEvent.objects.filter(pk=event.pk).exists()


def test_review_admin_edit_recalculates_rating_and_audits(admin_client_2fa):
    from apps.trust.admin import ReviewAdmin
    from django.contrib.admin.sites import site
    from django.test import RequestFactory

    spot = SpotFactory()
    review = Review.objects.create(author=AccountFactory(), target_type="spot", spot=spot, rating=4, status="pending")
    request = RequestFactory().post("/admin/")
    request.user = admin_client_2fa.account
    review.status = "published"
    ReviewAdmin(Review, site).save_model(request, review, form=None, change=True)
    spot.refresh_from_db()
    assert spot.rating_count == 1
    assert AuditEvent.objects.get(action="review.admin_updated").before["status"] == "pending"
