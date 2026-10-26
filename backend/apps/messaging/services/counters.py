"""Счётчики шапки/навигации (MSG-06/07, ATX-10): агрегаты по серверным данным, одинаковые на всех устройствах.

``GET /me/counters`` — источник правды; WS ``counters`` — ускоритель. Внутри одной транзакции повторные вызовы
``push_counters`` сливаются в одну отправку после коммита (без двойных пересчётов на каждое уведомление).
"""
import logging

from django.db import transaction

from apps.messaging.services.realtime import push_to_user

logger = logging.getLogger(__name__)


def get_counters(account):
    from apps.commerce.models import Booking, Inquiry
    from apps.commerce.services.access import incoming_inquiries_q, provider_bookings_q, provider_org_ids
    from apps.messaging.models import Notification
    from apps.messaging.services.conversations import unread_messages_count

    org_ids = provider_org_ids(account)
    return {
        "unread_messages": unread_messages_count(account, org_ids),
        "unread_notifications": Notification.objects.filter(recipient=account, read_at__isnull=True).count(),
        "new_inquiries": Inquiry.objects.filter(incoming_inquiries_q(account, org_ids),
                                                status=Inquiry.Status.NEW).count(),
        "pending_bookings": Booking.objects.filter(provider_bookings_q(account, org_ids),
                                                   status=Booking.Status.REQUESTED).count(),
    }


def send_counters(account_ids):
    """Пересчитать и отправить немедленно (вызывается после коммита)."""
    from apps.accounts.models import Account

    for account in Account.objects.filter(pk__in=set(account_ids), is_active=True):
        try:
            push_to_user(account.pk, {"type": "counters", "counters": get_counters(account)})
        except Exception:  # WS — ускоритель, ошибка не должна ломать бизнес-операцию
            logger.warning("counters push failed", exc_info=True)


class _CountersFlush:
    """on_commit-колбэк, накапливающий получателей в пределах транзакции."""

    def __init__(self, ids):
        self.ids = set(ids)

    def __call__(self):
        send_counters(self.ids)


def push_counters(account_ids):
    ids = {i for i in account_ids if i}
    if not ids:
        return
    connection = transaction.get_connection()
    if connection.in_atomic_block:
        for entry in getattr(connection, "run_on_commit", []):
            func = entry[1] if isinstance(entry, (tuple, list)) and len(entry) > 1 else None
            if isinstance(func, _CountersFlush):
                func.ids |= ids
                return
        transaction.on_commit(_CountersFlush(ids), robust=True)
    else:
        send_counters(ids)
