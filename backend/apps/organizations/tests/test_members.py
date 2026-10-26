"""Команда: роли, отзыв доступа, передача владения, выход (AT-09, F15, ATX-18, SCH-09, 5.3)."""
import pytest

from apps.commerce.models import Booking
from apps.learning.models import LessonSession
from apps.messaging.models import Notification
from apps.organizations.models import Membership, Organization
from apps.trust.models import AuditEvent
from tests.factories import AccountFactory, LessonSessionFactory, OrganizationFactory, add_member

pytestmark = pytest.mark.django_db

R = Membership.Role


@pytest.fixture
def team():
    org = OrganizationFactory()
    manager, instructor, staff = AccountFactory(), AccountFactory(), AccountFactory()
    return {
        "org": org,
        "owner": org.owner,
        "owner_m": Membership.objects.get(organization=org, account=org.owner),
        "manager": manager,
        "manager_m": add_member(org, manager, R.MANAGER),
        "instructor": instructor,
        "instructor_m": add_member(org, instructor, R.INSTRUCTOR),
        "staff": staff,
        "staff_m": add_member(org, staff, R.STAFF),
    }


def members_url(org, membership=None):
    base = f"/api/v1/organizations/{org.pk}/members"
    return f"{base}/{membership.pk}" if membership else base


def test_any_member_sees_team_but_not_outsider(make_client, team):
    org = team["org"]
    body = make_client(team["instructor"]).get(members_url(org)).json()
    assert len(body) == 4 and "email" not in str(body)
    assert make_client().get(members_url(org)).status_code == 404


def test_history_only_for_management(make_client, team):
    org = team["org"]
    assert make_client(team["instructor"]).get(members_url(org), {"status": "all"}).status_code == 403
    assert make_client(team["manager"]).get(members_url(org), {"status": "all"}).status_code == 200


def test_owner_changes_role_with_audit_and_notification(make_client, team):
    response = make_client(team["owner"]).patch(members_url(team["org"], team["instructor_m"]),
                                                {"role": "manager", "title": "Старший тренер"}, format="json")
    assert response.status_code == 200
    assert response.json()["role"] == "manager" and response.json()["title"] == "Старший тренер"
    assert AuditEvent.objects.filter(action="membership.updated", object_id=str(team["instructor_m"].pk)).exists()
    assert Notification.objects.filter(recipient=team["instructor"], kind="membership").exists()


def test_manager_cannot_change_roles(make_client, team):
    """ATX-18: без прав owner нельзя менять организационные полномочия."""
    response = make_client(team["manager"]).patch(members_url(team["org"], team["instructor_m"]),
                                                  {"role": "manager"}, format="json")
    assert response.status_code == 403
    team["instructor_m"].refresh_from_db()
    assert team["instructor_m"].role == R.INSTRUCTOR


def test_manager_can_edit_instructor_title_only(make_client, team):
    client = make_client(team["manager"])
    ok = client.patch(members_url(team["org"], team["instructor_m"]), {"title": "Тренер"}, format="json")
    assert ok.status_code == 200
    owner_title = client.patch(members_url(team["org"], team["owner_m"]), {"title": "x"}, format="json")
    assert owner_title.status_code == 403


def test_instructor_cannot_manage_members(make_client, team):
    client = make_client(team["instructor"])
    assert client.patch(members_url(team["org"], team["staff_m"]), {"title": "x"}, format="json").status_code == 403
    assert client.delete(members_url(team["org"], team["staff_m"])).status_code == 403


def test_owner_role_assignment_goes_through_transfer(make_client, team):
    client = make_client(team["owner"])
    response = client.patch(members_url(team["org"], team["manager_m"]), {"role": "owner"}, format="json")
    assert response.status_code == 400
    own = client.patch(members_url(team["org"], team["owner_m"]), {"role": "manager"}, format="json")
    assert own.status_code == 400


def test_revoking_manager_closes_access_immediately_and_keeps_history(make_client, team):
    """AT-09 / F15: доступ исчезает сразу, занятия и история остаются."""
    org, manager = team["org"], team["manager"]
    manager_client = make_client(manager)
    session = LessonSessionFactory(program__organization=org, organization=org, created_by=manager)
    booking = Booking.objects.create(kind="lesson", customer=AccountFactory(), provider_organization=org,
                                     lesson_session=session, starts_at=session.starts_at, ends_at=session.ends_at,
                                     status="confirmed")
    assert manager_client.get(f"/api/v1/organizations/{org.pk}/manage").status_code == 200
    response = make_client(team["owner"]).delete(members_url(org, team["manager_m"]))
    assert response.status_code == 200 and response.json()["status"] == "revoked"
    assert manager_client.get(f"/api/v1/organizations/{org.pk}/manage").status_code == 404
    assert manager_client.patch(f"/api/v1/organizations/{org.pk}/manage", {"name": "x"},
                                format="json").status_code == 404
    assert LessonSession.objects.filter(pk=session.pk, created_by=manager).exists()
    assert Booking.objects.filter(pk=booking.pk, status="confirmed").exists()
    membership = Membership.objects.get(pk=team["manager_m"].pk)
    assert membership.revoked_by == team["owner"] and membership.revoked_at
    assert AuditEvent.objects.filter(action="membership.revoked", object_id=str(membership.pk)).exists()
    assert Notification.objects.filter(recipient=manager, kind="membership").exists()
    assert make_client(manager).get("/api/v1/me").json()["organizations"] == []


def test_manager_revokes_instructor_but_not_manager_or_owner(make_client, team):
    client = make_client(team["manager"])
    assert client.delete(members_url(team["org"], team["instructor_m"])).status_code == 200
    other_manager = add_member(team["org"], AccountFactory(), R.MANAGER)
    assert client.delete(members_url(team["org"], other_manager)).status_code == 403
    assert client.delete(members_url(team["org"], team["owner_m"])).status_code == 400


def test_owner_cannot_revoke_self(make_client, team):
    response = make_client(team["owner"]).delete(members_url(team["org"], team["owner_m"]))
    assert response.status_code == 400


def test_revoke_twice(make_client, team):
    client = make_client(team["owner"])
    client.delete(members_url(team["org"], team["staff_m"]))
    assert client.delete(members_url(team["org"], team["staff_m"])).status_code == 400


def test_membership_of_other_org_is_404(make_client, team):
    other = OrganizationFactory()
    foreign = add_member(other, AccountFactory())
    response = make_client(team["owner"]).delete(members_url(team["org"], foreign))
    assert response.status_code == 404


def test_transfer_ownership(make_client, team):
    org = team["org"]
    response = make_client(team["owner"]).post(f"/api/v1/organizations/{org.pk}/transfer-ownership",
                                               {"account_id": str(team["instructor"].pk)}, format="json")
    assert response.status_code == 200, response.json()
    org.refresh_from_db()
    assert org.owner == team["instructor"]
    assert Membership.objects.get(pk=team["instructor_m"].pk).role == R.OWNER
    assert Membership.objects.get(pk=team["owner_m"].pk).role == R.MANAGER
    assert AuditEvent.objects.filter(action="organization.ownership_transferred").exists()
    # Бывший владелец теперь не может передать владение повторно.
    again = make_client(team["owner"]).post(f"/api/v1/organizations/{org.pk}/transfer-ownership",
                                            {"account_id": str(team["staff"].pk)}, format="json")
    assert again.status_code == 403


def test_transfer_to_non_member_or_by_manager_fails(make_client, team):
    org = team["org"]
    outsider = AccountFactory()
    response = make_client(team["owner"]).post(f"/api/v1/organizations/{org.pk}/transfer-ownership",
                                               {"account_id": str(outsider.pk)}, format="json")
    assert response.status_code == 400
    by_manager = make_client(team["manager"]).post(f"/api/v1/organizations/{org.pk}/transfer-ownership",
                                                   {"account_id": str(team["staff"].pk)}, format="json")
    assert by_manager.status_code == 403
    assert Organization.objects.get(pk=org.pk).owner == team["owner"]


def test_member_leaves_and_owner_cannot(make_client, team):
    org = team["org"]
    response = make_client(team["staff"]).post(f"/api/v1/organizations/{org.pk}/leave")
    assert response.status_code == 204
    assert Membership.objects.get(pk=team["staff_m"].pk).status == Membership.Status.LEFT
    assert Notification.objects.filter(recipient__in=[team["owner"], team["manager"]], kind="membership").count() == 2
    owner = make_client(team["owner"]).post(f"/api/v1/organizations/{org.pk}/leave")
    assert owner.status_code == 400
    assert make_client().post(f"/api/v1/organizations/{org.pk}/leave").status_code == 404


def test_access_service_reflects_revocation():
    from apps.organizations.services.access import can_manage, is_member

    org = OrganizationFactory()
    manager = AccountFactory()
    membership = add_member(org, manager, R.MANAGER)
    assert can_manage(manager, org)
    membership.status = Membership.Status.REVOKED
    membership.save()
    assert not can_manage(manager, org) and not is_member(manager, org)
