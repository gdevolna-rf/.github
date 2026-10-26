"""Доставка событий в WebSocket пользователя (после коммита транзакции)."""
import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction

from apps.messaging.consumers import user_group

logger = logging.getLogger(__name__)


def push_to_user(account_id, payload):
    """payload: {"type": "message.new" | "notification.new" | "counters" | ..., ...}."""

    def _send():
        layer = get_channel_layer()
        if layer is None:
            return
        try:
            async_to_sync(layer.group_send)(user_group(account_id), {"type": "push_event", "payload": payload})
        except Exception:  # realtime — best effort, источник правды остаётся в БД
            logger.warning("realtime push failed", exc_info=True)

    transaction.on_commit(_send)


def push_to_users(account_ids, payload):
    for account_id in set(account_ids):
        push_to_user(account_id, payload)
