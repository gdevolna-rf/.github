"""Кабинет мастерской: me/workshop (SHP-01..05), публикация, доступ только по активному членству (AT-09, F15)."""
import pytest
from django.utils import timezone

from apps.boards.models import WorkshopProfile
from apps.organizations.models import Membership, Organization
from apps.trust.models import AuditEvent
from tests.factories import AccountFactory, RegionFactory, add_member

from .helpers import photo, published_model, shaper_account, video, workshop_for

pytestmark = pytest.mark.django_db


def test_guest_cannot_access_cabinet(api_client):
    assert api_client.get("/api/v1/me/workshop").status_code == 401
    assert api_client.put("/api/v1/me/workshop", {"name": "X"}, format="json").status_code == 401


def test_get_without_workshop_returns_no_workshop(make_client):
    response = make_client(shaper_account()).get("/api/v1/me/workshop")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "no_workshop"


def test_creating_workshop_requires_shaper_specialty(make_client):
    response = make_client(AccountFactory()).put("/api/v1/me/workshop", {"name": "Kamchatka Boards"}, format="json")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "specialty_required"
    assert not Organization.objects.filter(kind=Organization.Kind.WORKSHOP).exists()


def test_register_as_shaper_creates_workshop_then_saves_changes(make_client):
    """SHP-01: первый PUT создаёт (created=true, 201), следующий сохраняет (created=false, 200)."""
    account = shaper_account()
    client = make_client(account)
    region = RegionFactory()
    response = client.put("/api/v1/me/workshop", {
        "name": "Kamchatka Boards", "region_id": region.pk, "city": "Петропавловск-Камчатский",
        "specialization": "Фиши", "services": ["Новые доски", " ", "Ремонт досок"], "does_repair": True,
        "lead_time": "2–4 недели", "experience_since": 2012,
    }, format="json")
    assert response.status_code == 201, response.json()
    data = response.json()
    assert data["created"] is True
    assert data["slug"] == "kamchatka-boards" and data["status"] == "draft"
    assert data["shaper_code"] == "KBA01"
    assert data["services"] == ["Новые доски", "Ремонт досок"]
    assert data["region"]["id"] == region.pk and data["does_repair"] is True
    assert data["my_role"] == "owner" and data["can_manage"] is True
    assert data["public_url"] == "/shapers/kamchatka-boards"
    org = Organization.objects.get(pk=data["id"])
    assert org.kind == Organization.Kind.WORKSHOP and org.owner == account
    assert Membership.objects.filter(organization=org, account=account, role="owner", status="active").exists()
    assert AuditEvent.objects.filter(action="workshop.created", object_id=str(org.pk)).exists()

    response = client.put("/api/v1/me/workshop", {"lead_time": "1–2 месяца"}, format="json")
    assert response.status_code == 200
    assert response.json()["created"] is False and response.json()["lead_time"] == "1–2 месяца"
    assert response.json()["name"] == "Kamchatka Boards"  # частичное обновление
    assert Organization.objects.filter(kind="workshop", owner=account).count() == 1

    got = client.get("/api/v1/me/workshop").json()
    assert got["id"] == data["id"] and got["created"] is False


def test_creation_requires_name(make_client):
    response = make_client(shaper_account()).put("/api/v1/me/workshop", {"city": "Сочи"}, format="json")
    assert response.status_code == 400
    assert "name" in response.json()["error"]["fields"]


def test_custom_shaper_code_validated_and_unique(make_client):
    WorkshopProfile.objects.filter(organization=workshop_for()).update(shaper_code="TAKEN")
    client = make_client(shaper_account())
    bad = client.put("/api/v1/me/workshop", {"name": "A", "shaper_code": "a-1"}, format="json")
    assert bad.status_code == 400
    taken = client.put("/api/v1/me/workshop", {"name": "A", "shaper_code": "taken"}, format="json")
    assert taken.status_code == 409 and taken.json()["error"]["code"] == "shaper_code_taken"
    ok = client.put("/api/v1/me/workshop", {"name": "A", "shaper_code": "abc12"}, format="json")
    assert ok.status_code == 201 and ok.json()["shaper_code"] == "ABC12"


def test_shaper_code_locked_once_skus_exist(make_client):
    workshop = workshop_for()
    client = make_client(workshop.owner)
    assert client.put("/api/v1/me/workshop", {"shaper_code": "NEW01"}, format="json").status_code == 200
    published_model(workshop)
    response = client.put("/api/v1/me/workshop", {"shaper_code": "NEW02"}, format="json")
    assert response.status_code == 409 and response.json()["error"]["code"] == "shaper_code_locked"
    assert WorkshopProfile.objects.get(organization=workshop).shaper_code == "NEW01"


def test_logo_cover_and_promo_video_are_claimed_with_purpose_checks(make_client):
    workshop = workshop_for()
    owner = workshop.owner
    client = make_client(owner)
    logo = photo(owner, purpose="org_logo")
    promo = video(owner, purpose="promo_video")
    response = client.put("/api/v1/me/workshop", {"logo_id": str(logo.pk), "promo_video_id": str(promo.pk)},
                          format="json")
    assert response.status_code == 200
    assert response.json()["logo"]["id"] == str(logo.pk)
    assert response.json()["promo_video"]["id"] == str(promo.pk)
    wrong = client.put("/api/v1/me/workshop", {"promo_video_id": str(photo(owner).pk)}, format="json")
    assert wrong.status_code == 400 and wrong.json()["error"]["code"] == "media_purpose"
    foreign = client.put("/api/v1/me/workshop", {"logo_id": str(photo(AccountFactory(), purpose="org_logo").pk)},
                         format="json")
    assert foreign.status_code == 400 and foreign.json()["error"]["code"] == "media_invalid"
    cleared = client.put("/api/v1/me/workshop", {"promo_video_id": None}, format="json")
    assert cleared.json()["promo_video"] is None


def test_staff_member_sees_workshop_but_cannot_edit_profile(make_client):
    workshop = workshop_for()
    staff = AccountFactory()
    add_member(workshop, staff, role=Membership.Role.STAFF)
    client = make_client(staff)
    data = client.get("/api/v1/me/workshop").json()
    assert data["id"] == str(workshop.pk) and data["can_manage"] is False
    response = client.put("/api/v1/me/workshop", {"name": "Захват"}, format="json")
    assert response.status_code == 403
    workshop.refresh_from_db()
    assert workshop.name != "Захват"


def test_revoked_member_loses_access_immediately(make_client):
    """AT-09 / F15: отзыв членства немедленно закрывает кабинет."""
    workshop = workshop_for()
    manager = AccountFactory()
    membership = add_member(workshop, manager, role=Membership.Role.MANAGER)
    client = make_client(manager)
    assert client.get(f"/api/v1/workshops/{workshop.pk}/models").status_code == 200
    membership.status = Membership.Status.REVOKED
    membership.revoked_at = timezone.now()
    membership.save()
    assert client.get("/api/v1/me/workshop").status_code == 404
    assert client.get(f"/api/v1/workshops/{workshop.pk}/models").status_code == 403


def test_publish_requires_verified_email_and_required_fields(make_client):
    owner = shaper_account(email_verified_at=None)
    client = make_client(owner)
    workshop_id = client.put("/api/v1/me/workshop", {"name": "Volna"}, format="json").json()["id"]
    response = client.post(f"/api/v1/workshops/{workshop_id}/publish")
    assert response.status_code == 403 and response.json()["error"]["code"] == "email_not_verified"
    owner.email_verified_at = timezone.now()
    owner.save()
    response = client.post(f"/api/v1/workshops/{workshop_id}/publish")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "workshop_incomplete"
    assert set(response.json()["error"]["fields"]) == {"region", "specialization"}
    client.put("/api/v1/me/workshop", {"region_id": RegionFactory().pk, "specialization": "Лонгборды"}, format="json")
    response = client.post(f"/api/v1/workshops/{workshop_id}/publish")
    assert response.status_code == 200 and response.json()["status"] == "published"
    assert response.json()["is_public"] is True
    assert client.post(f"/api/v1/workshops/{workshop_id}/unpublish").json()["status"] == "draft"


def test_publish_checklist_reported_for_ui(make_client):
    client = make_client(shaper_account())
    data = client.put("/api/v1/me/workshop", {"name": "A"}, format="json").json()
    codes = {item["code"]: item["ok"] for item in data["publish_requirements"]}
    assert codes == {"name": True, "region": False, "specialization": False, "email_verified": True}


def test_suspended_workshop_cannot_self_publish(make_client):
    workshop = workshop_for()
    Organization.objects.filter(pk=workshop.pk).update(status=Organization.Status.SUSPENDED)
    response = make_client(workshop.owner).post(f"/api/v1/workshops/{workshop.pk}/publish")
    assert response.status_code == 409 and response.json()["error"]["code"] == "workshop_suspended"


def test_foreign_shaper_cannot_publish_or_manage(make_client):
    workshop = workshop_for()
    client = make_client(shaper_account())
    assert client.post(f"/api/v1/workshops/{workshop.pk}/publish").status_code == 403
    assert client.get(f"/api/v1/workshops/{workshop.pk}/board-types").status_code == 403
    assert client.get("/api/v1/workshops/00000000-0000-0000-0000-000000000000/models").status_code == 404


def test_school_organization_is_not_a_workshop(make_client):
    from tests.factories import OrganizationFactory

    school = OrganizationFactory()
    response = make_client(school.owner).get(f"/api/v1/workshops/{school.pk}/models")
    assert response.status_code == 404


def test_workshop_created_elsewhere_gets_profile_lazily(make_client):
    """POST organizations (kind=workshop) из другого приложения — профиль мастерской создаётся при первом обращении."""
    owner = shaper_account()
    org = Organization.objects.create(kind=Organization.Kind.WORKSHOP, name="Surf Lab", slug="surf-lab", owner=owner)
    Membership.objects.create(organization=org, account=owner, role=Membership.Role.OWNER)
    data = make_client(owner).get("/api/v1/me/workshop").json()
    assert data["id"] == str(org.pk) and data["shaper_code"] == "SLU01"


def test_repeated_registration_does_not_create_second_workshop(make_client):
    account = shaper_account()
    client = make_client(account)
    first = client.put("/api/v1/me/workshop", {"name": "Один"}, format="json")
    assert first.status_code == 201
    from apps.boards.services.workshops import save_workshop

    workshop, created = save_workshop(account, {"name": "Один"}, None)  # как если бы второй запрос не увидел первую
    assert created is False and str(workshop.pk) == first.json()["id"]
    assert Organization.objects.filter(kind="workshop", owner=account).count() == 1
