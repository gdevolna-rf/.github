"""Блокировки собеседников и ограничения переписки (COM-07, MSG-13, TRUST-07)."""
from django.db.models import Q

from apps.common.exceptions import Forbidden
from apps.messaging.models import AccountBlock


def is_blocked(a, b):
    """Есть ли блокировка между аккаунтами в любую сторону."""
    a_id = getattr(a, "pk", a)
    b_id = getattr(b, "pk", b)
    if not a_id or not b_id or a_id == b_id:
        return False
    return AccountBlock.objects.filter(
        Q(blocker_id=a_id, blocked_id=b_id) | Q(blocker_id=b_id, blocked_id=a_id)
    ).exists()


def has_messaging_restriction(account):
    """Действующее ограничение модератора: запрет сообщений или ограничение профиля (apps.trust.services.restrictions)."""
    from apps.trust.models import AccountRestriction
    from apps.trust.services.restrictions import is_restricted

    return is_restricted(account, AccountRestriction.Kind.MESSAGING)


def require_can_message(account):
    from apps.trust.services.restrictions import require_can_message as _require

    _require(account)


def require_not_blocked(a, b):
    if is_blocked(a, b):
        raise Forbidden("Переписка недоступна: один из участников заблокировал другого.", code="blocked")
