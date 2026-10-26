"""Ограничения аккаунта (TRUST-07, F14). Аккаунт остаётся активным (вход, апелляции, жалобы, свои данные,
снятие своих материалов с публикации), но публикации/сообщения блокируются.

Единственная точка проверки для всех приложений (docs/dev/INTEGRATION_NOTES.md):

* ``require_can_publish(account)`` — перед созданием/изменением/публикацией публично видимого контента
  (карточки, модели досок, объявления, занятия, события клуба, отзывы, правки спотов, записи дневника
  с видимостью community/public). Ошибка 403 ``account_restricted``.
* ``require_can_message(account)`` — перед отправкой сообщений и созданием обращений/личных диалогов.
  Ошибка 403 ``messaging_restricted``.
"""
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from apps.common.exceptions import Forbidden
from apps.trust.models import AccountRestriction

_MESSAGES = {
    AccountRestriction.Kind.PUBLISHING: "Публикации для вашего аккаунта ограничены модератором.",
    AccountRestriction.Kind.MESSAGING: "Отправка сообщений для вашего аккаунта ограничена модератором.",
    AccountRestriction.Kind.SUSPENDED: "Профиль ограничен модератором: публикации и сообщения недоступны.",
}


def active_restrictions(account, kinds=None, now=None):
    if account is None or not getattr(account, "is_authenticated", False):
        return AccountRestriction.objects.none()
    now = now or timezone.now()
    qs = AccountRestriction.objects.filter(account=account, lifted_at__isnull=True).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=now)
    )
    if kinds:
        qs = qs.filter(kind__in=list(kinds))
    return qs


def restriction_exists(kinds, account_ref="account_id", now=None):
    """Exists() для queryset: у аккаунта ``OuterRef(account_ref)`` есть действующее ограничение одного из kinds."""
    now = now or timezone.now()
    kinds = [kinds] if isinstance(kinds, str) else list(kinds)
    return Exists(AccountRestriction.objects.filter(
        account_id=OuterRef(account_ref), kind__in=kinds, lifted_at__isnull=True,
    ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now)))


def suspended_exists(account_ref="account_id"):
    """Профиль ограничен (suspended): публичное присутствие аккаунта скрыто во всех каталогах — карточка
    инструктора, анкета GG Surfer, личные объявления аренды и частные слоты (F14)."""
    return restriction_exists(AccountRestriction.Kind.SUSPENDED, account_ref)


def is_restriction_active(restriction, now=None):
    now = now or timezone.now()
    return restriction.lifted_at is None and (restriction.expires_at is None or restriction.expires_at > now)


def is_restricted(account, kind):
    """kind=publishing|messaging; suspended включает оба запрета."""
    return active_restrictions(account, {kind, AccountRestriction.Kind.SUSPENDED}).exists()


PUBLISH_CODE = "account_restricted"
MESSAGE_CODE = "messaging_restricted"


def restriction_message(account, kind):
    """Текст для пользователя или None, если ограничения нет."""
    restriction = active_restrictions(account, {kind, AccountRestriction.Kind.SUSPENDED}).order_by("-created_at").first()
    if restriction is None:
        return None
    message = _MESSAGES[restriction.kind]
    if restriction.expires_at:
        message += f" До {timezone.localtime(restriction.expires_at):%d.%m.%Y %H:%M}."
    return message


def _require(account, kind, code):
    message = restriction_message(account, kind)
    if message is not None:
        raise Forbidden(message, code=code)


def require_can_publish(account):
    """Публично видимый контент — запрещён при publishing/suspended (403 account_restricted)."""
    _require(account, AccountRestriction.Kind.PUBLISHING, PUBLISH_CODE)


def require_can_message(account):
    """Сообщения, обращения, личные диалоги — запрещены при messaging/suspended (403 messaging_restricted)."""
    _require(account, AccountRestriction.Kind.MESSAGING, MESSAGE_CODE)
