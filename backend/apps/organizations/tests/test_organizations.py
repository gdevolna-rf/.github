"""Организации: создание, каталог, публичная карточка школы, кабинет, отправка на проверку (BR-03, SCH-01/02/13)."""
import pytest

from apps.commerce.models import Booking
from apps.learning.models import InstructorProfile, LessonSession
from apps.mediafiles.models import MediaAsset
from apps.organizations.models import Membership, Organization
from apps.trust.models import AuditEvent, ModerationCase
from tests.factories import (
    AccountFactory,
    InstructorProfileFactory,
    LessonSessionFactory,
    MediaAssetFactory,
    OrganizationFactory,
    RegionFactory,
    SchoolProgramFactory,
    SpotFactory,
    add_member,
    add_specialty,
)

pytestmark = pytest.mark.django_db


def manage(org):
    return f"/api/v1/organizations/{org.pk}/manage"


# --- создание ---------------------------------------------------------------------------------------------

def test_create_school_makes_creator_owner(auth_client):
    response = auth_client.post("/api/v1/organizations", {"kind": "school", "name": "Сёрф-школа Волна"},
                                format="json")
    assert response.status_code == 201, response.json()
    body = response.json()
    org = Organization.objects.get(pk=body["id"])
    assert org.slug == "serf-shkola-volna"
    assert org.status == Organization.Status.DRAFT
    assert org.owner == auth_client.account
    assert Membership.objects.get(organization=org).role == Membership.Role.OWNER
    assert body["my_role"] == "owner" and body["missing_fields"] == ["description", "region", "spots_or_address"]
    assert AuditEvent.objects.filter(action="organization.created", object_id=str(org.pk)).exists()
    # Одинаковое название — уникальный slug.
    second = auth_client.post("/api/v1/organizations", {"kind": "school", "name": "Сёрф-школа Волна"},
                              format="json")
    assert second.json()["slug"] == "serf-shkola-volna-2"


def test_workshop_requires_shaper_specialty(auth_client):
    response = auth_client.post("/api/v1/organizations", {"kind": "workshop", "name": "Доски"}, format="json")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "specialty_required"
    add_specialty(auth_client.account, "shaper")
    assert auth_client.post("/api/v1/organizations", {"kind": "workshop", "name": "Доски"},
                            format="json").status_code == 201


def test_rental_requires_rental_specialty(auth_client):
    assert auth_client.post("/api/v1/organizations", {"kind": "rental", "name": "Прокат"},
                            format="json").status_code == 403
    add_specialty(auth_client.account, "rental")
    assert auth_client.post("/api/v1/organizations", {"kind": "rental", "name": "Прокат"},
                            format="json").status_code == 201


def test_guest_cannot_create(api_client):
    assert api_client.post("/api/v1/organizations", {"kind": "school", "name": "X"},
                           format="json").status_code == 401


def test_create_with_relations_and_media(auth_client):
    region = RegionFactory()
    spot = SpotFactory(region=region)
    logo = MediaAssetFactory(owner=auth_client.account, purpose=MediaAsset.Purpose.ORG_LOGO)
    response = auth_client.post("/api/v1/organizations", {
        "kind": "school", "name": "Школа", "description": "Учим", "region_id": region.pk, "spot_ids": [str(spot.pk)],
        "logo_id": str(logo.pk), "formats": ["group"], "price_from": "3500.00",
    }, format="json")
    assert response.status_code == 201, response.json()
    body = response.json()
    assert body["logo"]["id"] == str(logo.pk)
    assert [s["id"] for s in body["spots"]] == [str(spot.pk)]
    assert body["missing_fields"] == []
    logo.refresh_from_db()
    assert str(logo.organization_id) == body["id"]


def test_create_with_foreign_logo_is_rejected(auth_client):
    logo = MediaAssetFactory(purpose=MediaAsset.Purpose.ORG_LOGO)
    response = auth_client.post("/api/v1/organizations", {"kind": "school", "name": "Школа",
                                                          "logo_id": str(logo.pk)}, format="json")
    assert response.status_code == 400
    assert not Organization.objects.exists()


# --- каталог и публичная карточка -------------------------------------------------------------------------

def test_public_list_only_published_with_filters(api_client):
    region = RegionFactory(slug="kamchatka")
    school = OrganizationFactory(name="Камчатская школа", region=region)
    OrganizationFactory(name="Черновик", status=Organization.Status.DRAFT)
    workshop = OrganizationFactory(kind=Organization.Kind.WORKSHOP, name="Мастерская")
    body = api_client.get("/api/v1/organizations").json()
    assert {o["id"] for o in body["results"]} == {str(school.pk), str(workshop.pk)}
    assert "phone" not in body["results"][0] and "email" not in body["results"][0]
    by_kind = api_client.get("/api/v1/organizations", {"kind": "school"}).json()["results"]
    assert [o["id"] for o in by_kind] == [str(school.pk)]
    by_region = api_client.get("/api/v1/organizations", {"region": "kamchatka"}).json()["results"]
    assert [o["id"] for o in by_region] == [str(school.pk)]
    by_q = api_client.get("/api/v1/organizations", {"q": "мастер"}).json()["results"]
    assert [o["id"] for o in by_q] == [str(workshop.pk)]


def test_unpublished_detail_is_404(api_client):
    draft = OrganizationFactory(status=Organization.Status.DRAFT)
    assert api_client.get(f"/api/v1/organizations/{draft.slug}").status_code == 404


def test_school_public_card_with_programs_sessions_team(api_client):
    """SCH-02, ATX-14, ATX-35: свободные места, один инструктор — один id."""
    org = OrganizationFactory(phone="+7999", email="school@example.com")
    spot = SpotFactory()
    org.spots.add(spot)
    program = SchoolProgramFactory(organization=org)
    SchoolProgramFactory(organization=org, is_active=False, title="Архив")
    instructor = InstructorProfileFactory(status=InstructorProfile.Status.PUBLISHED)
    add_member(org, instructor.account, Membership.Role.INSTRUCTOR)
    other_school = OrganizationFactory()
    add_member(other_school, instructor.account, Membership.Role.INSTRUCTOR)
    session = LessonSessionFactory(program=program, organization=org, capacity=6, instructor=instructor.account,
                                   spot=spot)
    LessonSessionFactory(program=program, organization=org, status=LessonSession.Status.CANCELLED,
                         starts_at=session.starts_at.replace(year=session.starts_at.year + 1),
                         ends_at=session.ends_at.replace(year=session.ends_at.year + 1))
    for seats, state in ((2, "confirmed"), (1, "requested"), (1, "cancelled")):
        Booking.objects.create(kind="lesson", customer=AccountFactory(), provider_organization=org,
                               lesson_session=session, starts_at=session.starts_at, ends_at=session.ends_at,
                               seats=seats, status=state)
    body = api_client.get(f"/api/v1/organizations/{org.slug}").json()
    assert "phone" not in body and "email" not in body
    assert [p["id"] for p in body["programs"]] == [str(program.pk)]
    assert len(body["upcoming_sessions"]) == 1
    upcoming = body["upcoming_sessions"][0]
    assert upcoming["free_seats"] == 4 and upcoming["capacity"] == 6
    assert upcoming["spot"]["slug"] == spot.slug
    assert upcoming["instructor"]["id"] == str(instructor.account.pk)
    team = {m["account"]["id"]: m for m in body["team"]}
    assert set(team) == {str(org.owner.pk), str(instructor.account.pk)}
    assert team[str(instructor.account.pk)]["instructor_profile"]["id"] == str(instructor.pk)
    assert team[str(org.owner.pk)]["role"] == "owner"
    assert [s["slug"] for s in body["spots"]] == [spot.slug]
    assert body["viewer_role"] is None
    # Тот же инструктор в другой школе — тот же account.id (не клон).
    other = api_client.get(f"/api/v1/organizations/{other_school.slug}").json()
    assert str(instructor.account.pk) in {m["account"]["id"] for m in other["team"]}


def test_revoked_member_not_in_public_team(api_client):
    org = OrganizationFactory()
    membership = add_member(org, AccountFactory())
    membership.status = Membership.Status.REVOKED
    membership.save()
    team = api_client.get(f"/api/v1/organizations/{org.slug}").json()["team"]
    assert [m["role"] for m in team] == ["owner"]


# --- кабинет --------------------------------------------------------------------------------------------

def test_manage_access_matrix(make_client, api_client):
    org = OrganizationFactory(phone="+7999")
    manager, instructor = AccountFactory(), AccountFactory()
    add_member(org, manager, Membership.Role.MANAGER)
    add_member(org, instructor, Membership.Role.INSTRUCTOR)
    assert make_client(org.owner).get(manage(org)).json()["phone"] == "+7999"
    assert make_client(manager).get(manage(org)).status_code == 200
    assert make_client(instructor).get(manage(org)).status_code == 403
    assert make_client().get(manage(org)).status_code == 404
    assert api_client.get(manage(org)).status_code == 401


def test_manager_patches_profile_with_audit(make_client):
    org = OrganizationFactory()
    manager = AccountFactory()
    add_member(org, manager, Membership.Role.MANAGER)
    client = make_client(manager)
    cover = MediaAssetFactory(owner=manager, purpose=MediaAsset.Purpose.ORG_COVER)
    gallery = [MediaAssetFactory(owner=manager, purpose=MediaAsset.Purpose.ORG_GALLERY) for _ in range(2)]
    response = client.patch(manage(org), {
        "description": "Новое описание", "cover_id": str(cover.pk), "gallery_ids": [str(g.pk) for g in gallery],
        "social_links": {"vk": "https://vk.com/school"},
    }, format="json")
    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["description"] == "Новое описание"
    assert body["cover"]["id"] == str(cover.pk)
    assert [g["id"] for g in body["gallery"]] == [str(g.pk) for g in gallery] or \
        {g["id"] for g in body["gallery"]} == {str(g.pk) for g in gallery}
    event = AuditEvent.objects.get(action="organization.updated")
    assert "description" in event.after and event.actor == manager
    # Другой сотрудник может сохранить галерею, загруженную коллегой.
    owner_patch = make_client(org.owner).patch(manage(org), {"gallery_ids": [str(gallery[0].pk)]}, format="json")
    assert owner_patch.status_code == 200 and len(owner_patch.json()["gallery"]) == 1


def test_kind_cannot_be_changed(make_client):
    org = OrganizationFactory()
    make_client(org.owner).patch(manage(org), {"kind": "workshop"}, format="json")
    org.refresh_from_db()
    assert org.kind == Organization.Kind.SCHOOL


def test_instructor_cannot_patch(make_client):
    """ATX-18: сотрудник без прав не редактирует организацию."""
    org = OrganizationFactory()
    instructor = AccountFactory()
    add_member(org, instructor)
    assert make_client(instructor).patch(manage(org), {"name": "Взлом"}, format="json").status_code == 403
    org.refresh_from_db()
    assert org.name != "Взлом"


def test_my_organizations(make_client):
    account = AccountFactory()
    org = OrganizationFactory(owner=account)
    other = OrganizationFactory()
    add_member(other, account, Membership.Role.MANAGER)
    body = make_client(account).get("/api/v1/me/organizations").json()
    assert {(m["organization"]["id"], m["role"]) for m in body} == {(str(org.pk), "owner"), (str(other.pk), "manager")}


# --- отправка на проверку -------------------------------------------------------------------------------

def ready_draft(owner=None, **kwargs):
    org = OrganizationFactory(status=Organization.Status.DRAFT, description="Описание", region=RegionFactory(),
                              address="Пляж, 1", **({"owner": owner} if owner else {}), **kwargs)
    return org


def test_submit_creates_moderation_case(make_client):
    org = ready_draft()
    response = make_client(org.owner).post(f"/api/v1/organizations/{org.pk}/submit")
    assert response.status_code == 200, response.json()
    org.refresh_from_db()
    assert org.status == Organization.Status.PENDING_REVIEW
    assert org.verification_status == Organization.Verification.PENDING
    case = ModerationCase.objects.get(organization=org)
    assert case.kind == ModerationCase.Kind.ORGANIZATION and case.status == "open"
    again = make_client(org.owner).post(f"/api/v1/organizations/{org.pk}/submit")
    assert again.status_code == 400 and again.json()["error"]["code"] == "already_pending"


def test_submit_requires_verified_email(make_client):
    owner = AccountFactory(email_verified_at=None)
    org = ready_draft(owner=owner)
    response = make_client(owner).post(f"/api/v1/organizations/{org.pk}/submit")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "email_not_verified"


def test_submit_requires_mandatory_fields(make_client):
    org = OrganizationFactory(status=Organization.Status.DRAFT)
    response = make_client(org.owner).post(f"/api/v1/organizations/{org.pk}/submit")
    assert response.status_code == 400
    assert set(response.json()["error"]["fields"]) == {"description", "region", "spots_or_address"}
    assert not ModerationCase.objects.exists()


def test_only_owner_submits(make_client):
    org = ready_draft()
    manager = AccountFactory()
    add_member(org, manager, Membership.Role.MANAGER)
    assert make_client(manager).post(f"/api/v1/organizations/{org.pk}/submit").status_code == 403


def test_published_cannot_be_resubmitted(make_client):
    org = OrganizationFactory()
    response = make_client(org.owner).post(f"/api/v1/organizations/{org.pk}/submit")
    assert response.json()["error"]["code"] == "already_published"
