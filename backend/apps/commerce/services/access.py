"""Кто действует от имени исполнителя (5.2, AT-09, F15).

Права вычисляются по текущему членству при каждом запросе: отзыв доступа сотрудника закрывает обращения,
брони и переписку организации немедленно, история при этом сохраняется.

* Исполнитель-аккаунт — сам этот аккаунт.
* Школа / прокат — активные владелец и менеджеры.
* Мастерская шейпера — все активные участники (мастерская обычно — несколько мастеров без «менеджеров»).
* Бронь занятия дополнительно доступна назначенному на занятие инструктору.
"""
from django.db.models import Q

from apps.organizations.models import Membership, Organization
from apps.organizations.services.access import MANAGE_ROLES

ALL_ROLES = tuple(Membership.Role.values)
CUSTOMER = "customer"
PROVIDER = "provider"


def provider_roles(org_kind):
    return ALL_ROLES if org_kind == Organization.Kind.WORKSHOP else MANAGE_ROLES


def _authenticated(account):
    return account is not None and getattr(account, "is_authenticated", False)


def provider_org_ids(account):
    """Организации, от имени которых аккаунт сейчас работает с обращениями и бронями."""
    if not _authenticated(account):
        return []
    return list(
        Membership.objects.filter(account=account, status=Membership.Status.ACTIVE)
        .filter(Q(role__in=MANAGE_ROLES) | Q(organization__kind=Organization.Kind.WORKSHOP))
        .values_list("organization_id", flat=True)
    )


def is_provider_staff(account, organization):
    if organization is None or not _authenticated(account):
        return False
    return Membership.objects.filter(
        account=account, organization=organization, status=Membership.Status.ACTIVE,
        role__in=provider_roles(organization.kind),
    ).exists()


def is_active_member(account, organization):
    """Любое активное членство — для запрета обращений/броней «к себе» (BR-05, SHP-11)."""
    if organization is None or not _authenticated(account):
        return False
    return Membership.objects.filter(account=account, organization=organization,
                                     status=Membership.Status.ACTIVE).exists()


def provider_staff(organization):
    """Текущие сотрудники организации, которые получают обращения и брони."""
    if organization is None:
        return []
    return [m.account for m in Membership.objects.filter(
        organization=organization, status=Membership.Status.ACTIVE, role__in=provider_roles(organization.kind),
    ).select_related("account__profile").order_by("joined_at")]


def provider_principal(provider_account=None, provider_organization=None):
    """Аккаунт, представляющий исполнителя при проверке блокировок: сам исполнитель или владелец организации."""
    if provider_account is not None:
        return provider_account
    if provider_organization is not None:
        return provider_organization.owner
    return None


# --- обращения -------------------------------------------------------------------------------------------------

def inquiry_side(inquiry, account):
    """customer / provider / None для текущего пользователя."""
    if not _authenticated(account):
        return None
    if inquiry.customer_id == account.pk:
        return CUSTOMER
    if inquiry.provider_account_id and inquiry.provider_account_id == account.pk:
        return PROVIDER
    if inquiry.provider_organization_id and is_provider_staff(account, inquiry.provider_organization):
        return PROVIDER
    return None


def inquiry_provider_accounts(inquiry):
    if inquiry.provider_account_id:
        return [inquiry.provider_account]
    return provider_staff(inquiry.provider_organization)


def inquiry_audience_ids(inquiry):
    return {inquiry.customer_id} | {a.pk for a in inquiry_provider_accounts(inquiry)}


def incoming_inquiries_q(account, org_ids=None):
    org_ids = provider_org_ids(account) if org_ids is None else org_ids
    return Q(provider_account=account) | Q(provider_organization_id__in=org_ids)


def outgoing_inquiries_q(account):
    return Q(customer=account)


def visible_inquiries_q(account, org_ids=None):
    return outgoing_inquiries_q(account) | incoming_inquiries_q(account, org_ids)


# --- брони -----------------------------------------------------------------------------------------------------

def booking_side(booking, account):
    if not _authenticated(account):
        return None
    if booking.customer_id == account.pk:
        return CUSTOMER
    if is_booking_provider(booking, account):
        return PROVIDER
    return None


def is_booking_provider(booking, account):
    if not _authenticated(account):
        return False
    if booking.provider_account_id and booking.provider_account_id == account.pk:
        return True
    if booking.lesson_session_id and booking.lesson_session.instructor_id == account.pk:
        return True
    return bool(booking.provider_organization_id and is_provider_staff(account, booking.provider_organization))


def booking_provider_accounts(booking):
    accounts = []
    if booking.provider_account_id:
        accounts.append(booking.provider_account)
    if booking.provider_organization_id:
        accounts += provider_staff(booking.provider_organization)
    if booking.lesson_session_id and booking.lesson_session.instructor_id:
        accounts.append(booking.lesson_session.instructor)
    seen, unique = set(), []
    for account in accounts:
        if account.pk not in seen:
            seen.add(account.pk)
            unique.append(account)
    return unique


def provider_bookings_q(account, org_ids=None):
    org_ids = provider_org_ids(account) if org_ids is None else org_ids
    return (Q(provider_account=account) | Q(provider_organization_id__in=org_ids)
            | Q(lesson_session__instructor=account))
