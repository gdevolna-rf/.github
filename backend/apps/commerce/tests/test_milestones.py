"""Подтверждаемые этапы ремонта / индивидуального заказа (SHO-06)."""
import pytest

from apps.commerce.models import Inquiry, InquiryMilestone
from apps.commerce.tests.helpers import board_inquiry
from apps.messaging.models import Message, Notification

pytestmark = pytest.mark.django_db


@pytest.fixture
def setup(make_client):
    inquiry, customer, workshop = board_inquiry(kind="custom_order")
    return inquiry, make_client(customer), make_client(workshop.owner), workshop


def url(inquiry, suffix=""):
    return f"/api/v1/inquiries/{inquiry.pk}/milestones{suffix}"


def test_provider_manages_milestones_and_customer_confirms(setup):
    inquiry, buyer, shaper, workshop = setup
    response = shaper.post(url(inquiry), {"title": "Шейп болванки", "amount": "20000", "due_date": "2099-02-01"},
                           format="json")
    assert response.status_code == 201, response.json()
    milestone = response.json()
    assert milestone["status"] == "planned" and milestone["position"] == 0 and milestone["amount"] == "20000.00"
    second = shaper.post(url(inquiry), {"title": "Ламинация"}, format="json").json()
    assert second["position"] == 1

    assert [m["title"] for m in buyer.get(url(inquiry)).json()] == ["Шейп болванки", "Ламинация"]
    patched = shaper.patch(url(inquiry, f"/{second['id']}"), {"title": "Ламинация 6+4"}, format="json")
    assert patched.status_code == 200 and patched.json()["title"] == "Ламинация 6+4"

    done = shaper.post(f"/api/v1/milestones/{milestone['id']}/done")
    assert done.status_code == 200 and done.json()["status"] == "done" and done.json()["completed_at"]
    assert Message.objects.filter(conversation=inquiry.conversation, kind="system", body__contains="Шейп").exists()
    assert Notification.objects.filter(recipient=buyer.account, payload__milestone_id=milestone["id"]).exists()
    assert shaper.post(f"/api/v1/milestones/{milestone['id']}/confirm").status_code == 403
    confirmed = buyer.post(f"/api/v1/milestones/{milestone['id']}/confirm")
    assert confirmed.status_code == 200 and confirmed.json()["status"] == "confirmed"
    assert Notification.objects.filter(recipient=workshop.owner, payload__milestone_id=milestone["id"]).exists()
    detail = buyer.get(f"/api/v1/inquiries/{inquiry.pk}").json()
    assert [m["status"] for m in detail["milestones"]] == ["confirmed", "planned"]


def test_customer_cannot_create_or_edit_milestones(setup):
    inquiry, buyer, shaper, _ = setup
    assert buyer.post(url(inquiry), {"title": "Хочу этап"}, format="json").status_code == 403
    milestone = shaper.post(url(inquiry), {"title": "Этап"}, format="json").json()
    assert buyer.patch(url(inquiry, f"/{milestone['id']}"), {"title": "x"}, format="json").status_code == 403
    assert buyer.delete(url(inquiry, f"/{milestone['id']}")).status_code == 403
    assert buyer.post(f"/api/v1/milestones/{milestone['id']}/done").status_code == 403


def test_done_milestone_is_locked(setup):
    inquiry, buyer, shaper, _ = setup
    milestone = shaper.post(url(inquiry), {"title": "Этап"}, format="json").json()
    shaper.post(f"/api/v1/milestones/{milestone['id']}/done")
    assert shaper.patch(url(inquiry, f"/{milestone['id']}"), {"title": "x"}, format="json").status_code == 409
    assert shaper.delete(url(inquiry, f"/{milestone['id']}")).status_code == 409
    assert shaper.post(f"/api/v1/milestones/{milestone['id']}/done").status_code == 409
    assert buyer.post(f"/api/v1/milestones/{milestone['id']}/confirm").status_code == 200
    assert buyer.post(f"/api/v1/milestones/{milestone['id']}/confirm").status_code == 409


def test_planned_milestone_can_be_deleted(setup):
    inquiry, _buyer, shaper, _ = setup
    milestone = shaper.post(url(inquiry), {"title": "Этап"}, format="json").json()
    assert shaper.delete(url(inquiry, f"/{milestone['id']}")).status_code == 204
    assert not InquiryMilestone.objects.exists()


def test_closed_inquiry_rejects_milestone_changes(setup):
    inquiry, _buyer, shaper, _ = setup
    Inquiry.objects.filter(pk=inquiry.pk).update(status="declined")
    response = shaper.post(url(inquiry), {"title": "Этап"}, format="json")
    assert response.status_code == 409 and response.json()["error"]["code"] == "inquiry_closed"


def test_strangers_cannot_see_milestones(setup, make_client):
    inquiry, _buyer, shaper, _ = setup
    milestone = shaper.post(url(inquiry), {"title": "Этап"}, format="json").json()
    stranger = make_client()
    assert stranger.get(url(inquiry)).status_code == 404
    assert stranger.post(f"/api/v1/milestones/{milestone['id']}/confirm").status_code == 404
    assert stranger.get(url(inquiry, f"/{milestone['id']}")).status_code == 404


def test_milestone_validation(setup):
    inquiry, _buyer, shaper, _ = setup
    assert shaper.post(url(inquiry), {}, format="json").status_code == 400
    assert shaper.post(url(inquiry), {"title": "x", "amount": "-1"}, format="json").status_code == 400
