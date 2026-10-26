"""Серверные роли и проверка 2FA для служебных действий (BR-04, 5.3, DATA-09)."""
from django.conf import settings
from django.utils import timezone

from apps.accounts.models import StaffRole

OTP_SESSION_KEY = "otp_verified_at"


def active_roles(account):
    if not account or not account.is_authenticated:
        return set()
    roles = set(account.staff_roles.filter(revoked_at__isnull=True).values_list("role", flat=True))
    if StaffRole.Role.ADMIN in roles:
        roles.add(StaffRole.Role.MODERATOR)
    return roles


def has_role(account, role):
    return role in active_roles(account)


def is_session_2fa_verified(request):
    return bool(request.session.get(OTP_SESSION_KEY))


def mark_session_2fa_verified(request):
    request.session[OTP_SESSION_KEY] = timezone.now().isoformat()


def has_verified_staff_role(request, role):
    user = getattr(request, "user", None)
    if not has_role(user, role):
        return False
    if settings.STAFF_2FA_REQUIRED and not is_session_2fa_verified(request):
        return False
    return True
