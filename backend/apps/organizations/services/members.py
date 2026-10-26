"""Команда организации: смена ролей, отзыв доступа, передача владения, выход (AT-09, F15, ATX-18, SCH-09).

Отзыв доступа действует немедленно (права проверяются по активному членству на каждом запросе);
занятия, заказы и история организации не удаляются.
"""
from django.db import transaction
from django.utils import timezone

from apps.common.exceptions import DomainError, Forbidden, NotFound
from apps.organizations.models import Membership, Organization

R = Membership.Role
ASSIGNABLE_ROLES = (R.MANAGER, R.INSTRUCTOR, R.STAFF)
MANAGER_CONTROLLED_ROLES = (R.INSTRUCTOR, R.STAFF)
ROLE_LABELS = dict(Membership.Role.choices)


def _notify(recipient, title, body, org, event_id, actor):
    from apps.messaging.models import Notification
    from apps.messaging.services.notify import notify

    return notify(recipient, Notification.Kind.MEMBERSHIP, title, body, link=f"/account/orgs/{org.pk}",
                  payload={"organization_id": str(org.pk)}, event_id=event_id, actor=actor)


def _get_membership(org, membership_id, lock=True):
    qs = Membership.objects.filter(organization=org, pk=membership_id).select_related("account__profile")
    if lock:
        qs = qs.select_for_update(of=("self",))
    membership = qs.first()
    if membership is None:
        raise NotFound("Участник не найден.")
    return membership


def update_member(org, actor_membership, membership_id, data, request=None):
    """Роль меняет только владелец; должность — владелец или менеджер (для инструкторов/сотрудников)."""
    from apps.trust.services.audit import record

    with transaction.atomic():
        membership = _get_membership(org, membership_id)
        if membership.status != Membership.Status.ACTIVE:
            raise DomainError("membership_inactive", "Доступ этого участника уже отозван.")
        before = {"role": membership.role, "title": membership.title}
        if "role" in data and data["role"] != membership.role:
            if actor_membership.role != R.OWNER:
                raise Forbidden("Менять роли может только владелец организации.")
            if membership.role == R.OWNER:
                raise DomainError("owner_role_locked", "Роль владельца меняется только передачей владения.")
            if data["role"] not in ASSIGNABLE_ROLES:
                raise DomainError("role_invalid", "Недопустимая роль. Владельца назначают передачей владения.",
                                  fields={"role": ["Недопустимое значение."]})
            membership.role = data["role"]
        if "title" in data and data["title"] != membership.title:
            if actor_membership.role == R.MANAGER and membership.role not in MANAGER_CONTROLLED_ROLES \
                    and membership.pk != actor_membership.pk:
                raise Forbidden("Менеджер может менять должность только инструкторов и сотрудников.")
            if actor_membership.role not in (R.OWNER, R.MANAGER):
                raise Forbidden("Недостаточно прав в этой организации.")
            membership.title = data["title"]
        after = {"role": membership.role, "title": membership.title}
        if after != before:
            membership.save(update_fields=["role", "title", "updated_at"])
            record(actor_membership.account, "membership.updated", membership,
                   organization=org, before=before, after=after, request=request)
            if after["role"] != before["role"]:
                _notify(membership.account, f"Новая роль в «{org.name}»",
                        f"Ваша роль: {ROLE_LABELS[membership.role]}.", org,
                        f"membership_role:{membership.pk}:{membership.role}:{timezone.now().timestamp()}",
                        actor_membership.account)
    return membership


def revoke_member(org, actor_membership, membership_id, request=None):
    """Владелец отзывает любого (кроме себя), менеджер — только инструкторов и сотрудников."""
    from apps.trust.services.audit import record

    with transaction.atomic():
        membership = _get_membership(org, membership_id)
        if membership.status != Membership.Status.ACTIVE:
            raise DomainError("membership_inactive", "Доступ этого участника уже отозван.")
        if membership.role == R.OWNER:
            raise DomainError("owner_cannot_be_revoked", "Владельца нельзя удалить. Сначала передайте владение.")
        if membership.pk == actor_membership.pk:
            raise DomainError("use_leave", "Чтобы выйти из организации, используйте «Покинуть организацию».")
        if actor_membership.role == R.MANAGER and membership.role not in MANAGER_CONTROLLED_ROLES:
            raise Forbidden("Менеджер может отзывать доступ только у инструкторов и сотрудников.")
        if actor_membership.role not in (R.OWNER, R.MANAGER):
            raise Forbidden("Недостаточно прав в этой организации.")
        now = timezone.now()
        membership.status = Membership.Status.REVOKED
        membership.revoked_at = now
        membership.revoked_by = actor_membership.account
        membership.save(update_fields=["status", "revoked_at", "revoked_by", "updated_at"])
        record(actor_membership.account, "membership.revoked", membership, organization=org,
               before={"status": "active", "role": membership.role},
               after={"status": membership.status, "account": str(membership.account_id)}, request=request)
        _notify(membership.account, f"Доступ к «{org.name}» отозван",
                "Управление организацией вам больше недоступно. История ваших занятий сохранена.", org,
                f"membership_revoked:{membership.pk}", actor_membership.account)
    return membership


def transfer_ownership(org, actor_membership, account_id, request=None):
    from apps.trust.services.audit import record

    if actor_membership.role != R.OWNER:
        raise Forbidden("Передать владение может только владелец.")
    with transaction.atomic():
        org = Organization.objects.select_for_update().get(pk=org.pk)
        current = Membership.objects.select_for_update().get(pk=actor_membership.pk)
        if current.status != Membership.Status.ACTIVE or current.role != R.OWNER:
            raise Forbidden("Передать владение может только владелец.")
        target = Membership.objects.select_for_update(of=("self",)).select_related("account").filter(
            organization=org, account_id=account_id, status=Membership.Status.ACTIVE).first()
        if target is None:
            raise DomainError("member_required", "Владение можно передать только активному участнику команды.",
                              fields={"account_id": ["Не участник организации."]})
        if target.pk == current.pk:
            raise DomainError("already_owner", "Вы уже владелец организации.")
        if not target.account.is_active or target.account.anonymized_at:
            raise DomainError("member_inactive", "Аккаунт участника неактивен.")
        previous_role = target.role
        current.role = R.MANAGER
        current.save(update_fields=["role", "updated_at"])
        target.role = R.OWNER
        target.save(update_fields=["role", "updated_at"])
        previous_owner = org.owner_id
        org.owner = target.account
        org.save(update_fields=["owner", "updated_at"])
        record(current.account, "organization.ownership_transferred", org, organization=org,
               before={"owner": str(previous_owner), "new_owner_role": previous_role},
               after={"owner": str(target.account_id), "previous_owner_role": R.MANAGER}, request=request)
        _notify(target.account, f"Вы стали владельцем «{org.name}»",
                "Владение организацией передано вам. Прежний владелец остался менеджером.", org,
                f"ownership:{org.pk}:{target.account_id}:{timezone.now().timestamp()}", current.account)
    return org


def leave(org, account, request=None):
    from apps.organizations.services.access import staff_accounts
    from apps.trust.services.audit import record

    with transaction.atomic():
        membership = Membership.objects.select_for_update().filter(
            organization=org, account=account, status=Membership.Status.ACTIVE).first()
        if membership is None:
            raise NotFound("Организация не найдена.")
        if membership.role == R.OWNER:
            raise DomainError("owner_cannot_leave", "Владелец не может покинуть организацию. Сначала передайте владение.")
        membership.status = Membership.Status.LEFT
        membership.revoked_at = timezone.now()
        membership.save(update_fields=["status", "revoked_at", "updated_at"])
        record(account, "membership.left", membership, organization=org, before={"status": "active",
                                                                                "role": membership.role},
               after={"status": membership.status}, request=request)
        name = getattr(getattr(account, "profile", None), "display_name", account.email)
        for manager in staff_accounts(org):
            _notify(manager, f"Участник покинул «{org.name}»", f"{name} вышел из команды.", org,
                    f"membership_left:{membership.pk}", account)
    return membership
