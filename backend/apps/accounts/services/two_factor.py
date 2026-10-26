"""TOTP-2FA (pyotp): настройка, включение, отключение, подтверждение сессии (5.3, 11, DATA-09).

Защита: код нельзя использовать повторно (кеш на окно действия), не более MAX_ATTEMPTS неудачных попыток
за ATTEMPT_WINDOW секунд на аккаунт.
"""
import pyotp
from django.conf import settings
from django.core.cache import cache
from django.db import transaction

from apps.accounts.models import StaffRole
from apps.accounts.services.roles import OTP_SESSION_KEY, active_roles, is_session_2fa_verified, mark_session_2fa_verified
from apps.common.exceptions import DomainError

MAX_ATTEMPTS = 10
ATTEMPT_WINDOW = 10 * 60
CODE_REUSE_TTL = 120
STAFF_ROLES_REQUIRING_2FA = {StaffRole.Role.MODERATOR, StaffRole.Role.ADMIN}


def is_required(account):
    """2FA обязательна для служебных ролей (модератор/администратор) и доступа в Django Admin."""
    if not settings.STAFF_2FA_REQUIRED or not account or not account.is_authenticated:
        return False
    return bool(active_roles(account) & STAFF_ROLES_REQUIRING_2FA) or account.is_staff


def state(account, request):
    return {
        "enabled": bool(account.totp_enabled),
        "verified": bool(request is not None and is_session_2fa_verified(request)),
        "required": is_required(account),
    }


def provisioning_uri(account, secret):
    return pyotp.TOTP(secret).provisioning_uri(name=account.email, issuer_name=settings.OTP_ISSUER)


def _attempts_key(account):
    return f"2fa:attempts:{account.pk}"


def _check_code(account, secret, code):
    code = "".join(ch for ch in str(code or "") if ch.isdigit())
    attempts_key = _attempts_key(account)
    if cache.get(attempts_key, 0) >= MAX_ATTEMPTS:
        raise DomainError("too_many_attempts", "Слишком много попыток. Попробуйте через несколько минут.",
                          status_code=429)
    valid = len(code) == 6 and secret and pyotp.TOTP(secret).verify(code, valid_window=1)
    if valid and not cache.add(f"2fa:used:{account.pk}:{code}", 1, CODE_REUSE_TTL):
        valid = False  # повтор уже использованного кода
    if not valid:
        if cache.add(attempts_key, 1, ATTEMPT_WINDOW) is False:
            try:
                cache.incr(attempts_key)
            except ValueError:
                cache.set(attempts_key, 1, ATTEMPT_WINDOW)
        raise DomainError("two_factor_code_invalid", "Неверный или устаревший код.",
                          fields={"code": ["Неверный код."]})
    cache.delete(attempts_key)
    return True


def setup(account):
    """Новый секрет (до подтверждения кодом 2FA не включается)."""
    if account.totp_enabled:
        raise DomainError("two_factor_already_enabled", "Двухфакторная аутентификация уже включена.")
    secret = pyotp.random_base32()
    account.totp_secret = secret
    account.save(update_fields=["totp_secret"])
    return {"secret": secret, "otpauth_uri": provisioning_uri(account, secret)}


def enable(account, code, request=None):
    from apps.trust.services.audit import record

    if account.totp_enabled:
        raise DomainError("two_factor_already_enabled", "Двухфакторная аутентификация уже включена.")
    if not account.totp_secret:
        raise DomainError("two_factor_not_setup", "Сначала получите секрет для приложения-аутентификатора.")
    _check_code(account, account.totp_secret, code)
    with transaction.atomic():
        account.totp_enabled = True
        account.save(update_fields=["totp_enabled"])
        record(account, "account.2fa_enabled", account, request=request)
    if request is not None:
        mark_session_2fa_verified(request)
    return account


def disable(account, code, request=None):
    from apps.trust.services.audit import record

    if not account.totp_enabled:
        raise DomainError("two_factor_not_enabled", "Двухфакторная аутентификация не включена.")
    _check_code(account, account.totp_secret, code)
    with transaction.atomic():
        account.totp_enabled = False
        account.totp_secret = ""
        account.save(update_fields=["totp_enabled", "totp_secret"])
        record(account, "account.2fa_disabled", account, request=request)
    if request is not None:
        request.session.pop(OTP_SESSION_KEY, None)
    return account


def verify_session(account, code, request):
    """Подтверждение текущей сессии кодом (для модераторских и админских действий)."""
    if not account.totp_enabled:
        raise DomainError("two_factor_not_enabled",
                          "Сначала включите двухфакторную аутентификацию в настройках аккаунта.")
    _check_code(account, account.totp_secret, code)
    mark_session_2fa_verified(request)
    return True
