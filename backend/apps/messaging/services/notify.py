"""Системные уведомления (8.6, MSG-12): in-app запись с уникальным event_id + WS + email по настройкам."""
import uuid

from django.db import IntegrityError, transaction

from apps.messaging.models import Notification, NotificationPreference
from apps.messaging.services.counters import push_counters
from apps.messaging.services.realtime import push_to_user

# Каналы по умолчанию, если пользователь не менял настройки (сообщения в чате — без email).
EMAIL_BY_DEFAULT = {
    Notification.Kind.INQUIRY_NEW,
    Notification.Kind.BOOKING_STATUS,
    Notification.Kind.MODERATION_DECISION,
    Notification.Kind.INVITE,
    Notification.Kind.CERTIFICATE_DECISION,
    Notification.Kind.EVENT_STATUS,
    Notification.Kind.PRODUCT_AVAILABLE,
}


def default_channels(kind):
    """(in_app, email, push) по умолчанию для вида уведомления."""
    return True, kind in EMAIL_BY_DEFAULT, False


def _channels(recipient, kind):
    pref = NotificationPreference.objects.filter(account=recipient, kind=kind).first()
    if pref is None:
        in_app, email, _push = default_channels(kind)
        return in_app, email
    return pref.in_app, pref.email


def notify(recipient, kind, title, body="", link="", payload=None, event_id=None, actor=None):
    """Создаёт уведомление один раз на event_id. Возвращает Notification или None (дубль/отключено)."""
    if recipient is None or (actor is not None and getattr(actor, "pk", None) == recipient.pk):
        return None
    if not getattr(recipient, "is_active", True):
        return None
    in_app, email = _channels(recipient, kind)
    event_id = event_id or f"{kind}:{uuid.uuid4()}"
    if not in_app and not email:
        return None
    try:
        with transaction.atomic():
            notification = Notification.objects.create(
                recipient=recipient, kind=kind, title=title[:200], body=body, link=link[:300],
                payload=payload or {}, event_id=f"{event_id}:{recipient.pk}"[:200],
                actor=actor if getattr(actor, "is_authenticated", False) else None,
                read_at=None,
            )
    except IntegrityError:
        return None
    if not in_app:
        notification.read_at = notification.created_at
        notification.save(update_fields=["read_at"])
    else:
        push_to_user(recipient.pk, {
            "type": "notification.new",
            "notification": {"id": str(notification.id), "kind": kind, "title": notification.title, "body": body,
                             "link": notification.link},
        })
        push_counters([recipient.pk])
    if email and recipient.email:
        from apps.messaging.tasks import send_notification_email

        transaction.on_commit(lambda: send_notification_email.delay(str(notification.id)))
    return notification
