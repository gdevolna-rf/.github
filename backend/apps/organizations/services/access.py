"""Права в рамках членства (5.2, 5.3). Каждое действие проверяет сервер, клиентские флаги не учитываются."""
from apps.common.exceptions import Forbidden
from apps.organizations.models import Membership

MANAGE_ROLES = (Membership.Role.OWNER, Membership.Role.MANAGER)


def active_membership(account, organization):
    if not account or not account.is_authenticated:
        return None
    return Membership.objects.filter(
        organization=organization, account=account, status=Membership.Status.ACTIVE
    ).first()


def member_role(account, organization):
    membership = active_membership(account, organization)
    return membership.role if membership else None


def is_member(account, organization):
    return active_membership(account, organization) is not None


def can_manage(account, organization):
    return member_role(account, organization) in MANAGE_ROLES


def require_role(account, organization, roles=MANAGE_ROLES, message="Нет полномочий в этой организации."):
    role = member_role(account, organization)
    if role not in roles:
        raise Forbidden(message)
    return role


def staff_accounts(organization, roles=MANAGE_ROLES):
    """Активные сотрудники с указанными ролями — получатели обращений организации."""
    return [m.account for m in Membership.objects.filter(
        organization=organization, status=Membership.Status.ACTIVE, role__in=roles
    ).select_related("account")]


def organization_ids_for(account, roles=None):
    qs = Membership.objects.filter(account=account, status=Membership.Status.ACTIVE)
    if roles:
        qs = qs.filter(role__in=roles)
    return list(qs.values_list("organization_id", flat=True))
