"""Приглашения (5.3, ACC-11, SCH-09): роль активна только после принятия адресатом."""
import datetime as dt

import pytest
from django.core import mail
from django.utils import timezone

from apps.messaging.models import Notification
from apps.organizations.models import Membership, OrganizationInvite
from apps.organizations.tasks import expire_invites
from apps.trust.models import AuditEvent
from tests.factories import AccountFactory, OrganizationFactory, add_member

pytestmark = pytest.mark.django_db

R = Membership.Role


def invite(client, org, email, role="instructor", run_on_commit=None, **extra):
    url = f"/api/v1/organizations/{org.pk}/invites"
    data = {"email": email, "role": role, **extra}
    if run_on_commit:
        return run_on_commit(client.post, url, data, format="json")
    return client.post(url, data, format="json")


def test_owner_invites_existing_account_with_email_and_notification(make_client, run_on_commit, settings):
    org = OrganizationFactory()
    target = AccountFactory(email="coach@example.com")
    response = invite(make_client(org.owner), org, "Coach@Example.com", "manager", run_on_commit,
                      message="Ждём в команде")
    assert response.status_code == 201, response.json()
    body = response.json()
    assert body["email"] == "coach@example.com" and body["role"] == "manager" and body["has_account"] is True
    assert "token" not in body
    item = OrganizationInvite.objects.get(pk=body["id"])
    assert item.account == target
    assert (item.expires_at - timezone.now()).days in (settings.INVITE_TTL_DAYS - 1, settings.INVITE_TTL_DAYS)
    notification = Notification.objects.get(recipient=target, kind="invite")
    assert notification.link == "/account/invites"
    invite_mail = [m for m in mail.outbox if f"/invites/{item.token}" in m.body]
    assert len(invite_mail) == 1 and invite_mail[0].to == ["coach@example.com"]
    assert AuditEvent.objects.filter(action="invite.created", object_id=str(item.pk)).exists()
    # Членство не создаётся до принятия.
    assert not Membership.objects.filter(organization=org, account=target).exists()


def test_invite_to_unregistered_email_sends_mail_only(make_client, run_on_commit):
    org = OrganizationFactory()
    response = invite(make_client(org.owner), org, "new@example.com", run_on_commit=run_on_commit)
    assert response.json()["has_account"] is False
    assert len(mail.outbox) == 1 and "зарегистрируйтесь" in mail.outbox[0].body
    assert not Notification.objects.exists()


def test_manager_invites_only_instructors_and_staff(make_client):
    org = OrganizationFactory()
    manager = AccountFactory()
    add_member(org, manager, R.MANAGER)
    client = make_client(manager)
    assert invite(client, org, "i@example.com", "instructor").status_code == 201
    assert invite(client, org, "s@example.com", "staff").status_code == 201
    assert invite(client, org, "m@example.com", "manager").status_code == 403


def test_instructor_and_outsider_cannot_invite(make_client):
    org = OrganizationFactory()
    instructor = AccountFactory()
    add_member(org, instructor)
    assert invite(make_client(instructor), org, "x@example.com").status_code == 403
    assert invite(make_client(), org, "x@example.com").status_code == 404


def test_owner_role_cannot_be_invited(make_client):
    org = OrganizationFactory()
    response = invite(make_client(org.owner), org, "x@example.com", "owner")
    assert response.status_code == 400


def test_duplicate_pending_invite_and_existing_member(make_client):
    org = OrganizationFactory()
    client = make_client(org.owner)
    assert invite(client, org, "dup@example.com").status_code == 201
    duplicate = invite(client, org, "DUP@example.com")
    assert duplicate.status_code == 409 and duplicate.json()["error"]["code"] == "invite_exists"
    member = AccountFactory(email="member@example.com")
    add_member(org, member)
    assert invite(client, org, "member@example.com").json()["error"]["code"] == "already_member"


def test_org_invite_list_and_revoke(make_client):
    org = OrganizationFactory()
    client = make_client(org.owner)
    invite_id = invite(client, org, "a@example.com").json()["id"]
    assert [i["id"] for i in client.get(f"/api/v1/organizations/{org.pk}/invites").json()] == [invite_id]
    response = client.delete(f"/api/v1/invites/{invite_id}")
    assert response.status_code == 200 and response.json()["status"] == "revoked"
    assert client.get(f"/api/v1/organizations/{org.pk}/invites").json() == []
    assert client.delete(f"/api/v1/invites/{invite_id}").status_code == 400
    assert make_client().delete(f"/api/v1/invites/{invite_id}").status_code == 404


def test_manager_cannot_revoke_manager_invite(make_client):
    org = OrganizationFactory()
    manager = AccountFactory()
    add_member(org, manager, R.MANAGER)
    invite_id = invite(make_client(org.owner), org, "boss@example.com", "manager").json()["id"]
    assert make_client(manager).delete(f"/api/v1/invites/{invite_id}").status_code == 403


def test_addressee_sees_and_accepts_invite(make_client, run_on_commit):
    org = OrganizationFactory()
    target = AccountFactory(email="coach@example.com")
    invite(make_client(org.owner), org, "coach@example.com", "instructor")
    client = make_client(target)
    listed = client.get("/api/v1/me/invites").json()
    assert len(listed) == 1 and listed[0]["organization"]["id"] == str(org.pk)
    token = listed[0]["token"]
    assert client.get(f"/api/v1/invites/{token}").json()["role"] == "instructor"
    response = run_on_commit(client.post, f"/api/v1/invites/{token}/accept")
    assert response.status_code == 200, response.json()
    assert response.json()["role"] == "instructor" and response.json()["organization"]["id"] == str(org.pk)
    membership = Membership.objects.get(organization=org, account=target, status="active")
    assert membership.invited_by == org.owner
    item = OrganizationInvite.objects.get(token=token)
    assert item.status == "accepted" and item.responded_at
    assert Notification.objects.filter(recipient=org.owner, kind="membership").exists()
    assert AuditEvent.objects.filter(action="invite.accepted").exists()
    assert client.get("/api/v1/me/invites").json() == []
    # Повторное принятие — ошибка, второе членство не создаётся.
    again = client.post(f"/api/v1/invites/{token}/accept")
    assert again.status_code == 400
    assert Membership.objects.filter(organization=org, account=target).count() == 1
    assert [o["id"] for o in client.get("/api/v1/me").json()["organizations"]] == [str(org.pk)]


def test_invite_for_email_registered_later_is_visible(make_client):
    org = OrganizationFactory()
    invite(make_client(org.owner), org, "later@example.com")
    target = AccountFactory(email="later@example.com")
    assert len(make_client(target).get("/api/v1/me/invites").json()) == 1


def test_other_account_cannot_accept_or_view(make_client):
    org = OrganizationFactory()
    AccountFactory(email="coach@example.com")
    invite(make_client(org.owner), org, "coach@example.com")
    token = OrganizationInvite.objects.get().token
    intruder = make_client()
    assert intruder.get(f"/api/v1/invites/{token}").status_code == 403
    response = intruder.post(f"/api/v1/invites/{token}/accept")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "invite_wrong_account"
    assert intruder.post(f"/api/v1/invites/{token}/decline").status_code == 403
    assert not Membership.objects.filter(organization=org, account=intruder.account).exists()
    assert make_client().post("/api/v1/invites/not-a-real-token/accept").status_code == 404


def test_unverified_email_cannot_accept(make_client):
    """Нельзя принять приглашение, зарегистрировав чужой email без подтверждения."""
    org = OrganizationFactory()
    invite(make_client(org.owner), org, "victim@example.com", "manager")
    squatter = AccountFactory(email="victim@example.com", email_verified_at=None)
    token = OrganizationInvite.objects.get().token
    response = make_client(squatter).post(f"/api/v1/invites/{token}/accept")
    assert response.status_code == 403 and response.json()["error"]["code"] == "email_not_verified"
    assert not Membership.objects.filter(account=squatter).exists()


def test_expired_invite_cannot_be_accepted(make_client):
    org = OrganizationFactory()
    target = AccountFactory(email="late@example.com")
    invite(make_client(org.owner), org, "late@example.com")
    item = OrganizationInvite.objects.get()
    OrganizationInvite.objects.filter(pk=item.pk).update(expires_at=timezone.now() - dt.timedelta(minutes=1))
    response = make_client(target).post(f"/api/v1/invites/{item.token}/accept")
    assert response.status_code == 400 and response.json()["error"]["code"] == "invite_expired"
    assert OrganizationInvite.objects.get(pk=item.pk).status == "expired"
    assert make_client(target).get("/api/v1/me/invites").json() == []


def test_decline_notifies_inviter(make_client, run_on_commit):
    org = OrganizationFactory()
    target = AccountFactory(email="no@example.com")
    invite(make_client(org.owner), org, "no@example.com")
    token = OrganizationInvite.objects.get().token
    response = make_client(target).post(f"/api/v1/invites/{token}/decline")
    assert response.status_code == 200 and response.json()["status"] == "declined"
    assert not Membership.objects.filter(organization=org, account=target).exists()
    assert Notification.objects.filter(recipient=org.owner, kind="invite").exists()
    assert make_client(target).post(f"/api/v1/invites/{token}/accept").status_code == 400


def test_revoked_invite_cannot_be_accepted(make_client):
    org = OrganizationFactory()
    target = AccountFactory(email="r@example.com")
    client = make_client(org.owner)
    invite_id = invite(client, org, "r@example.com").json()["id"]
    client.delete(f"/api/v1/invites/{invite_id}")
    token = OrganizationInvite.objects.get(pk=invite_id).token
    assert make_client(target).post(f"/api/v1/invites/{token}/accept").status_code == 400


def test_new_invite_allowed_after_previous_declined(make_client):
    org = OrganizationFactory()
    target = AccountFactory(email="again@example.com")
    client = make_client(org.owner)
    invite(client, org, "again@example.com")
    make_client(target).post(f"/api/v1/invites/{OrganizationInvite.objects.get().token}/decline")
    assert invite(client, org, "again@example.com").status_code == 201


def test_expire_invites_task():
    org = OrganizationFactory()
    old = OrganizationInvite.objects.create(organization=org, email="a@example.com", role="staff", token="t1",
                                            invited_by=org.owner, expires_at=timezone.now() - dt.timedelta(days=1))
    fresh = OrganizationInvite.objects.create(organization=org, email="b@example.com", role="staff", token="t2",
                                              invited_by=org.owner, expires_at=timezone.now() + dt.timedelta(days=1))
    assert expire_invites() == 1
    assert OrganizationInvite.objects.get(pk=old.pk).status == "expired"
    assert OrganizationInvite.objects.get(pk=fresh.pk).status == "pending"
