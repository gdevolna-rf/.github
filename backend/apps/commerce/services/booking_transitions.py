"""Переходы статусов брони (7.3) — единая точка для commerce и learning (завершение/отмена занятия).

``transition()`` меняет статус, пишет историю, аналитику (booking_confirmed / booking_cancelled), отправляет
WS ``booking.updated`` и счётчики. Уведомления сторонам отправляет вызывающий сервис — для типовых случаев
есть ``notify_booking_status()`` (commerce вызывает её на каждом переходе).
"""
from django.utils import timezone

from apps.analytics.services import track
from apps.commerce.models import Booking, BookingStatusChange
from apps.common.exceptions import Conflict
from apps.messaging.services.realtime import push_to_users

S = Booking.Status
ALLOWED = {
    S.REQUESTED: {S.CONFIRMED, S.DECLINED, S.CANCELLED},
    S.CONFIRMED: {S.IN_PROGRESS, S.CANCELLED, S.NO_SHOW, S.COMPLETED},
    S.IN_PROGRESS: {S.COMPLETED},
}


def provider_owner_kwargs(booking):
    return {"owner_account": booking.provider_account, "owner_organization": booking.provider_organization}


def booking_audience_ids(booking):
    from apps.commerce.services.access import booking_provider_accounts

    return {booking.customer_id} | {a.pk for a in booking_provider_accounts(booking)}


def transition(booking, to_status, actor, comment="", **fields):
    """Меняет статус брони с проверкой допустимости, историей, аналитикой и WS-событием.

    Вызывать внутри transaction.atomic() после select_for_update() брони. Проверки прав и вместимости —
    ответственность вызывающего сервиса. Доп. поля (decline_reason, cancel_reason, cancelled_side, ...)
    передаются через **fields.
    """
    from apps.messaging.services.counters import push_counters

    if to_status not in ALLOWED.get(booking.status, set()):
        raise Conflict(f"Нельзя перевести бронь из «{booking.get_status_display()}» в «{S(to_status).label}».",
                       code="invalid_transition")
    from_status = booking.status
    booking.status = to_status
    now = timezone.now()
    if to_status == S.CONFIRMED:
        booking.confirmed_at = now
    if to_status == S.COMPLETED:
        booking.completed_at = now
    if to_status == S.CANCELLED and getattr(actor, "is_authenticated", False) and "cancelled_by" not in fields:
        booking.cancelled_by = actor
    for key, value in fields.items():
        setattr(booking, key, value)
    booking.save()
    BookingStatusChange.objects.create(booking=booking, from_status=from_status, to_status=to_status,
                                       actor=actor if getattr(actor, "is_authenticated", False) else None,
                                       comment=(comment or "")[:300])
    if to_status == S.CONFIRMED:
        track("booking_confirmed", subject_type="booking", subject_id=booking.pk, actor=actor,
              context={"kind": booking.kind, "seats": booking.seats}, dedup_key=f"booking_confirmed:{booking.pk}",
              **provider_owner_kwargs(booking))
    elif to_status == S.CANCELLED:
        track("booking_cancelled", subject_type="booking", subject_id=booking.pk, actor=actor,
              context={"kind": booking.kind, "reason": booking.cancel_reason, "side": booking.cancelled_side,
                       "was": from_status},
              dedup_key=f"booking_cancelled:{booking.pk}", **provider_owner_kwargs(booking))
    recipients = booking_audience_ids(booking)
    push_to_users(recipients, {"type": "booking.updated", "booking_id": str(booking.pk), "status": to_status})
    if S.REQUESTED in (from_status, to_status):
        push_counters(recipients)  # pending_bookings
    return booking


_TITLES = {
    S.CONFIRMED: "Бронь подтверждена",
    S.DECLINED: "Бронь отклонена",
    S.CANCELLED: "Бронь отменена",
    S.NO_SHOW: "Отмечена неявка",
}


def booking_title(booking):
    if booking.lesson_session_id:
        return booking.lesson_session.title
    if booking.inventory_item_id:
        return booking.inventory_item.title
    return "Бронирование"


def status_title(booking):
    if booking.status == S.IN_PROGRESS:
        return "Инвентарь выдан" if booking.kind == Booking.Kind.RENTAL else "Занятие началось"
    if booking.status == S.COMPLETED:
        return "Инвентарь возвращён" if booking.kind == Booking.Kind.RENTAL else "Занятие проведено"
    return _TITLES.get(booking.status, f"Статус брони: {booking.get_status_display()}")


def notify_booking_status(booking, actor, *, to_customer=True, to_provider=True, reason="", title=None, body=None,
                          event_id=None, payload=None):
    """Уведомление сторон о текущем статусе брони (booking_status, ссылка /account/bookings/{id}).

    Единая точка для commerce, inventory (акты) и learning (отмена/перенос/проведение занятия): title/body/event_id
    можно переопределить для событий без смены статуса (перенос), payload дополняется (session_id и т.п.).
    """
    from apps.commerce.services.access import booking_provider_accounts
    from apps.messaging.models import Notification
    from apps.messaging.services.notify import notify

    if body is None:
        when = timezone.localtime(booking.starts_at).strftime("%d.%m.%Y %H:%M")
        body = f"«{booking_title(booking)}», {when}."
        if reason:
            body += f" Причина: {reason}"
    recipients = []
    if to_customer:
        recipients.append(booking.customer)
    if to_provider:
        recipients += booking_provider_accounts(booking)
    data = {"booking_id": str(booking.pk), "status": booking.status, "kind": booking.kind, **(payload or {})}
    for recipient in recipients:
        notify(recipient, Notification.Kind.BOOKING_STATUS, title or status_title(booking), body=body,
               link=f"/account/bookings/{booking.pk}", payload=data,
               event_id=event_id or f"booking_status:{booking.pk}:{booking.status}", actor=actor)
