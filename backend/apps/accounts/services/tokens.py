"""Подписанные токены: подтверждение email (с истечением) и сброс пароля (стандартный генератор Django)."""
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core import signing
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from apps.accounts.models import Account
from apps.common.exceptions import DomainError

EMAIL_VERIFICATION_SALT = "accounts.verify-email"


def email_verification_ttl():
    return int(getattr(settings, "EMAIL_VERIFICATION_TTL_HOURS", 72)) * 3600


def make_email_token(account):
    return signing.dumps({"a": str(account.pk), "e": account.email}, salt=EMAIL_VERIFICATION_SALT, compress=True)


def read_email_token(token):
    """Возвращает аккаунт; токен привязан к адресу — после смены email старая ссылка не работает."""
    try:
        data = signing.loads(token, salt=EMAIL_VERIFICATION_SALT, max_age=email_verification_ttl())
    except signing.SignatureExpired as exc:
        raise DomainError("token_expired", "Срок действия ссылки истёк. Запросите новое письмо.") from exc
    except signing.BadSignature as exc:
        raise DomainError("token_invalid", "Ссылка недействительна.") from exc
    account = Account.objects.filter(pk=data.get("a"), is_active=True).first()
    if account is None or account.email != data.get("e"):
        raise DomainError("token_invalid", "Ссылка недействительна.")
    return account


def verification_link(account):
    return f"{settings.SITE_URL}/verify-email?token={make_email_token(account)}"


def make_password_reset(account):
    return urlsafe_base64_encode(force_bytes(account.pk)), default_token_generator.make_token(account)


def password_reset_link(account):
    uid, token = make_password_reset(account)
    return f"{settings.SITE_URL}/reset-password?uid={uid}&token={token}"


def read_password_reset(uid, token):
    try:
        pk = force_str(urlsafe_base64_decode(uid))
        account = Account.objects.filter(pk=pk, is_active=True, anonymized_at__isnull=True).first()
    except Exception:  # мусор в uid: не base64 / не UUID
        account = None
    if account is None or not default_token_generator.check_token(account, token):
        raise DomainError("token_invalid", "Ссылка для сброса пароля недействительна или устарела.")
    return account
