"""Бронирования занятий и аренды (7.3, 6.2, 22, RENT-05, SCH-11, F06/F07/F13, AT-05, ATX-14/16).

* Цена, вместимость и доступность считаются только на сервере (9.1).
* Подтверждение занятия — в транзакции с ``select_for_update`` строки LessonSession (6.2).
* Пересечение подтверждённых аренд одного экземпляра запрещает exclusion-ограничение PostgreSQL;
  ``IntegrityError`` превращается в 409 ``resource_taken``.
"""
import datetime as dt
import math
import uuid
from decimal import ROUND_HALF_UP, Decimal

from django.db import IntegrityError, OperationalError, transaction
from django.db.models import Q, Sum
from django.utils import timezone

from apps.commerce.models import ACTIVE_BOOKING_STATUSES, Booking, BookingStatusChange
from apps.commerce.services import access
from apps.commerce.services.booking_transitions import (
    booking_audience_ids,
    notify_booking_status,
    transition,
)
from apps.common.exceptions import Conflict, DomainError, Forbidden, NotFound
from apps.messaging.models import Notification
from apps.messaging.services.counters import push_counters
from apps.messaging.services.notify import notify
from apps.messaging.services.realtime import push_to_users

S = Booking.Status
MAX_RENTAL_DAYS = 60
START_SKEW = dt.timedelta(minutes=5)
CENT = Decimal("0.01")


# --- вместимость и цена ---------------------------------------------------------------------------------------------

def taken_seats(session, exclude_pk=None):
    qs = Booking.objects.filter(lesson_session=session, status__in=ACTIVE_BOOKING_STATUSES)
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    return qs.aggregate(total=Sum("seats"))["total"] or 0


def free_seats(session):
    return max(session.capacity - taken_seats(session), 0)


def session_price(session):
    if session.price is not None:
        return session.price
    if session.program_id:
        return session.program.price
    if session.offer_id:
        return session.offer.price
    return None


def compute_rental_price(item, starts_at, ends_at):
    """Тариф по часам и суткам (RENT-01, 9.1): полные сутки по суточной цене, остаток — по часам, но не дороже суток."""
    hours = math.ceil((ends_at - starts_at).total_seconds() / 3600)
    per_day, per_hour = item.rental_price_per_day, item.rental_price_per_hour
    if per_day is None and per_hour is None:
        return None
    if per_hour is None:
        total = per_day * math.ceil(hours / 24)
    elif per_day is None:
        total = per_hour * hours
    else:
        days, rest = divmod(hours, 24)
        total = per_day * days + min(per_hour * rest, per_day)
    return Decimal(total).quantize(CENT, rounding=ROUND_HALF_UP)


# --- создание -------------------------------------------------------------------------------------------------------

def _require_not_self(customer, *, provider_account=None, provider_organization=None, instructor_id=None):
    message = "Нельзя забронировать собственное занятие или инвентарь."
    if provider_account is not None and provider_account.pk == customer.pk:
        raise Forbidden(message, code="self_booking")
    if provider_organization is not None and access.is_active_member(customer, provider_organization):
        raise Forbidden(message, code="self_booking")
    if instructor_id and instructor_id == customer.pk:
        raise Forbidden(message, code="self_booking")


def _group_key(customer, group_with):
    if not group_with:
        return None
    other = Booking.objects.select_for_update().filter(pk=group_with, customer=customer).first()
    if other is None:
        raise DomainError("validation_error", "Связанная бронь не найдена.",
                          fields={"group_with": ["Укажите одну из своих броней."]})
    if other.status not in (S.REQUESTED, S.CONFIRMED, S.IN_PROGRESS):
        raise DomainError("validation_error", "Связать можно только с активной бронью.",
                          fields={"group_with": ["Бронь уже закрыта."]})
    if other.group_key is None:
        other.group_key = uuid.uuid4()
        other.save(update_fields=["group_key", "updated_at"])
    return other.group_key


def _after_create(booking, customer):
    BookingStatusChange.objects.create(booking=booking, from_status="", to_status=S.REQUESTED, actor=customer)
    when = timezone.localtime(booking.starts_at).strftime("%d.%m.%Y %H:%M")
    from apps.accounts.serializers_public import PublicAccountSerializer
    from apps.commerce.services.booking_transitions import booking_title

    name = PublicAccountSerializer(customer).data["display_name"]
    for account in access.booking_provider_accounts(booking):
        notify(account, Notification.Kind.BOOKING_NEW, "Новая заявка на бронирование",
               body=f"{name}: «{booking_title(booking)}», {when}.", link=f"/account/bookings/{booking.pk}",
               payload={"booking_id": str(booking.pk), "kind": booking.kind},
               event_id=f"booking_new:{booking.pk}", actor=customer)
    audience = booking_audience_ids(booking)
    push_to_users(audience, {"type": "booking.updated", "booking_id": str(booking.pk), "status": booking.status})
    push_counters(audience)


def create_lesson_booking(customer, *, lesson_session_id, seats=1, participant_name="", participant_is_minor=False,
                          guardian_consent=False, customer_note="", group_with=None, request=None):
    from apps.accounts.models import ConsentRecord
    from apps.learning.models import LessonSession
    from apps.organizations.models import Organization

    session = (LessonSession.objects.select_related("organization", "program", "offer__instructor__account", "spot")
               .filter(pk=lesson_session_id).first())
    if session is None:
        raise NotFound("Занятие не найдено.")
    provider_account, provider_org = None, None
    if session.organization_id:
        provider_org = session.organization
        if provider_org.status != Organization.Status.PUBLISHED:
            raise NotFound("Занятие не найдено.")
    else:
        from apps.learning.services.catalog import is_profile_public

        if not is_profile_public(session.offer.instructor):
            raise NotFound("Занятие не найдено.")
        provider_account = session.offer.instructor.account
    _require_not_self(customer, provider_account=provider_account, provider_organization=provider_org,
                      instructor_id=session.instructor_id)
    if session.status != LessonSession.Status.SCHEDULED:
        raise Conflict("Запись на это занятие закрыта.", code="session_unavailable")
    if session.starts_at <= timezone.now():
        raise Conflict("Занятие уже началось.", code="session_started")
    seats = int(seats or 1)
    if seats < 1 or seats > session.capacity:
        raise DomainError("validation_error", "Неверное число мест.", fields={"seats": [f"От 1 до {session.capacity}."]})
    if free_seats(session) < seats:
        raise Conflict("Свободных мест на занятии не осталось.", code="no_seats")
    participant_name = (participant_name or "").strip()[:160]
    if participant_is_minor:
        if not participant_name:
            raise DomainError("validation_error", "Укажите имя ученика.",
                              fields={"participant_name": ["Обязательно для несовершеннолетнего."]})
        if not guardian_consent:
            raise DomainError("guardian_consent_required",
                              "Запись несовершеннолетнего оформляет законный представитель — подтвердите согласие.",
                              fields={"guardian_consent": ["Нужно согласие законного представителя."]})
    if not participant_name:
        from apps.accounts.serializers_public import PublicAccountSerializer

        participant_name = PublicAccountSerializer(customer).data["display_name"][:160]
    duplicate = Booking.objects.filter(customer=customer, lesson_session=session, participant_name=participant_name,
                                       status__in=[S.REQUESTED, S.CONFIRMED]).exists()
    if duplicate:
        raise Conflict("У вас уже есть заявка на это занятие для этого участника.", code="duplicate_booking")
    price = session_price(session)
    with transaction.atomic():
        group_key = _group_key(customer, group_with)
        booking = Booking.objects.create(
            kind=Booking.Kind.LESSON, customer=customer, provider_account=provider_account,
            provider_organization=provider_org, lesson_session=session, starts_at=session.starts_at,
            ends_at=session.ends_at, seats=seats, participant_name=participant_name,
            participant_is_minor=bool(participant_is_minor),
            guardian_consent_at=timezone.now() if participant_is_minor else None,
            price_amount=(price * seats).quantize(CENT) if price is not None else None,
            currency=session.currency, customer_note=(customer_note or "").strip()[:2000], group_key=group_key,
        )
        if participant_is_minor:
            ConsentRecord.objects.create(
                account=customer, kind=ConsentRecord.Kind.GUARDIAN, granted=True,
                ip=_ip(request), user_agent=(request.META.get("HTTP_USER_AGENT", "")[:300] if request else ""),
            )
        _after_create(booking, customer)
    return booking


def _ip(request):
    if request is None:
        return None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    return (forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")) or None


def rental_overlap_exists(item, starts_at, ends_at, exclude_pk=None):
    qs = Booking.objects.filter(inventory_item=item, status__in=ACTIVE_BOOKING_STATUSES,
                                starts_at__lt=ends_at, ends_at__gt=starts_at)
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    return qs.exists()


def create_rental_booking(customer, *, inventory_item_id, starts_at, ends_at, customer_note="", group_with=None,
                          request=None):
    from apps.inventory.models import InventoryItem

    from apps.inventory.services.rentals import visible_owner_q

    # Те же правила видимости владельца, что у каталога /rentals (черновик организации, удалённый или
    # ограниченный аккаунт → объявления «нет»).
    item = (InventoryItem.objects.select_related("owner_account", "owner_organization")
            .filter(visible_owner_q(), pk=inventory_item_id, is_published=True).first())
    if item is None:
        raise NotFound("Объявление не найдено.")
    _require_not_self(customer, provider_account=item.owner_account, provider_organization=item.owner_organization)
    if item.purpose not in (InventoryItem.Purpose.RENTAL, InventoryItem.Purpose.BOTH):
        raise DomainError("not_for_rent", "Этот экземпляр не сдаётся в аренду.")
    if item.status != InventoryItem.Status.AVAILABLE:
        raise Conflict("Экземпляр сейчас недоступен для аренды.", code="item_unavailable")
    now = timezone.now()
    if ends_at <= starts_at:
        raise DomainError("validation_error", "Окончание аренды должно быть позже начала.",
                          fields={"ends_at": ["Позже начала."]})
    if starts_at < now - START_SKEW:
        raise DomainError("validation_error", "Начало аренды уже прошло.", fields={"starts_at": ["Время в прошлом."]})
    duration = ends_at - starts_at
    if duration < dt.timedelta(hours=item.min_rental_hours or 1):
        raise DomainError("rental_too_short", f"Минимальный срок аренды — {item.min_rental_hours} ч.",
                          fields={"ends_at": [f"Не меньше {item.min_rental_hours} ч."]})
    if duration > dt.timedelta(days=MAX_RENTAL_DAYS):
        raise DomainError("rental_too_long", f"Максимальный срок аренды — {MAX_RENTAL_DAYS} дней.",
                          fields={"ends_at": [f"Не больше {MAX_RENTAL_DAYS} дней."]})
    if rental_overlap_exists(item, starts_at, ends_at):
        raise Conflict("Экземпляр уже забронирован на это время.", code="resource_taken")
    duplicate = Booking.objects.filter(customer=customer, inventory_item=item, status=S.REQUESTED,
                                       starts_at__lt=ends_at, ends_at__gt=starts_at).exists()
    if duplicate:
        raise Conflict("У вас уже есть заявка на этот экземпляр в это время.", code="duplicate_booking")
    with transaction.atomic():
        group_key = _group_key(customer, group_with)
        booking = Booking.objects.create(
            kind=Booking.Kind.RENTAL, customer=customer, provider_account=item.owner_account,
            provider_organization=item.owner_organization, inventory_item=item, starts_at=starts_at, ends_at=ends_at,
            price_amount=compute_rental_price(item, starts_at, ends_at), currency=item.currency,
            customer_note=(customer_note or "").strip()[:2000], group_key=group_key,
        )
        _after_create(booking, customer)
    return booking


# --- доступ и выборки -----------------------------------------------------------------------------------------------

def get_booking_for(account, pk):
    booking = (Booking.objects.select_related("lesson_session", "provider_organization", "provider_account",
                                              "customer", "inventory_item")
               .filter(pk=pk).first())
    if booking is None:
        raise NotFound("Бронирование не найдено.")
    side = access.booking_side(booking, account)
    if side is None:
        raise NotFound("Бронирование не найдено.")
    return booking, side


def available_actions(booking, side, now=None):
    now = now or timezone.now()
    started = booking.starts_at <= now
    actions = []
    if side == access.PROVIDER:
        if booking.status == S.REQUESTED:
            actions += ["confirm", "decline"]
        elif booking.status == S.CONFIRMED:
            actions.append("start")
            if booking.kind == Booking.Kind.LESSON and started:
                actions.append("complete")
            if started:
                actions.append("no_show")
            actions.append("cancel")
        elif booking.status == S.IN_PROGRESS:
            actions.append("complete")
    elif side == access.CUSTOMER:
        if booking.status == S.REQUESTED or (booking.status == S.CONFIRMED and not started):
            actions.append("cancel")
    return actions


# --- переходы -------------------------------------------------------------------------------------------------------

def _maybe_offer_waitlist(booking):
    """Освободилось место на занятии → первому в листе ожидания (SCH-08)."""
    from apps.learning.models import LessonSession
    from apps.learning.services.waitlist import offer_next_seat

    if booking.kind != Booking.Kind.LESSON:
        return
    session = LessonSession.objects.filter(pk=booking.lesson_session_id).first()
    if session is None or session.status != LessonSession.Status.SCHEDULED or session.starts_at <= timezone.now():
        return
    if free_seats(session) > 0:
        offer_next_seat(session)


def booking_action(account, pk, action, *, reason="", amount_confirmed=None, request=None):
    """confirm / decline / start / complete / no_show / cancel по 7.3."""
    from apps.inventory.models import InventoryItem
    from apps.learning.models import LessonSession

    reason = (reason or "").strip()
    if len(reason) > 300:
        raise DomainError("validation_error", "Причина слишком длинная.", fields={"reason": ["Не более 300 символов."]})
    get_booking_for(account, pk)  # 404 до блокировок
    with transaction.atomic():
        head = Booking.objects.filter(pk=pk).values("lesson_session_id", "inventory_item_id").first()
        session = item = None
        # Порядок блокировок одинаков во всех переходах: ресурс (занятие / экземпляр) → бронь.
        # Блокировка экземпляра сериализует подтверждения его броней: без неё две транзакции взаимно ждут
        # друг друга внутри проверки exclusion-ограничения (deadlock вместо понятного 409).
        if head and head["lesson_session_id"]:
            session = LessonSession.objects.select_for_update().get(pk=head["lesson_session_id"])
        elif head and head["inventory_item_id"]:
            item = InventoryItem.objects.select_for_update().get(pk=head["inventory_item_id"])
        booking = Booking.objects.select_for_update().get(pk=pk)
        side = access.booking_side(booking, account)
        if side is None:
            raise NotFound("Бронирование не найдено.")
        now = timezone.now()
        fields, comment = {}, reason
        if action == "cancel":
            if side == access.CUSTOMER:
                if booking.status == S.CONFIRMED and booking.starts_at <= now:
                    raise Conflict("Занятие или аренда уже начались — отмена недоступна.", code="cancel_too_late")
                fields["cancelled_side"] = Booking.Side.CUSTOMER
            else:
                if not reason:
                    raise DomainError("validation_error", "Укажите причину отмены.",
                                      fields={"reason": ["Обязательное поле."]})
                fields["cancelled_side"] = Booking.Side.PROVIDER
            fields["cancel_reason"] = reason
            to_status = S.CANCELLED
        else:
            if side != access.PROVIDER:
                raise Forbidden("Это действие выполняет исполнитель.", code="forbidden")
            if action == "confirm":
                to_status = S.CONFIRMED
                if booking.status == S.REQUESTED:
                    _check_confirmable(booking, session, now)
            elif action == "decline":
                if not reason:
                    raise DomainError("validation_error", "Укажите причину отказа.",
                                      fields={"reason": ["Обязательное поле."]})
                fields["decline_reason"] = reason
                to_status = S.DECLINED
            elif action == "start":
                to_status = S.IN_PROGRESS
            elif action == "complete":
                to_status = S.COMPLETED
                if booking.status == S.CONFIRMED:
                    if booking.kind == Booking.Kind.RENTAL:
                        raise Conflict("Сначала отметьте выдачу инвентаря.", code="not_issued")
                    if booking.starts_at > now:
                        raise Conflict("Занятие ещё не началось.", code="too_early")
                if amount_confirmed is not None:
                    fields["amount_confirmed"] = bool(amount_confirmed)
            elif action == "no_show":
                to_status = S.NO_SHOW
                if booking.status == S.CONFIRMED and booking.starts_at > now:
                    raise Conflict("Неявку можно отметить только после начала.", code="too_early")
            else:
                raise NotFound("Неизвестное действие.")
        if booking.kind == Booking.Kind.RENTAL and to_status == S.CONFIRMED and booking.status == S.REQUESTED:
            if item is None or item.status != InventoryItem.Status.AVAILABLE or not item.is_published:
                raise Conflict("Экземпляр сейчас недоступен для аренды.", code="item_unavailable")
            taken = Conflict("Экземпляр уже забронирован на это время другим клиентом.", code="resource_taken")
            if rental_overlap_exists(item, booking.starts_at, booking.ends_at, exclude_pk=booking.pk):
                raise taken
            try:
                with transaction.atomic():
                    transition(booking, to_status, account, comment=comment, **fields)
            except IntegrityError:  # exclusion-ограничение — последняя линия защиты (AT-05)
                raise taken from None
            except OperationalError as exc:
                if getattr(exc.__cause__, "sqlstate", None) == "40P01":  # deadlock: победила другая транзакция
                    raise taken from None
                raise
        else:
            transition(booking, to_status, account, comment=comment, **fields)
        if to_status in (S.CANCELLED, S.DECLINED):
            _maybe_offer_waitlist(booking)
        _notify_transition(booking, account, side, reason)
    return booking


def _check_confirmable(booking, session, now):
    from apps.learning.models import LessonSession

    if booking.starts_at <= now:
        raise Conflict("Время начала уже прошло — подтвердить бронь нельзя.", code="booking_started")
    if session is not None:
        if session.status != LessonSession.Status.SCHEDULED:
            raise Conflict("Занятие отменено или уже проходит.", code="session_unavailable")
        if taken_seats(session, exclude_pk=booking.pk) + booking.seats > session.capacity:
            raise Conflict("Свободных мест на занятии не осталось.", code="no_seats")


def _notify_transition(booking, actor, side, reason):
    if side == access.CUSTOMER:
        notify_booking_status(booking, actor, to_customer=False, to_provider=True, reason=reason)
        return
    notify_booking_status(booking, actor, to_customer=True, to_provider=False, reason=reason)
    # Назначенный инструктор узнаёт об изменениях, сделанных менеджером школы.
    instructor = booking.lesson_session.instructor if booking.lesson_session_id else None
    if instructor is not None and instructor.pk != actor.pk:
        from apps.commerce.services.booking_transitions import status_title

        notify(instructor, Notification.Kind.BOOKING_STATUS, status_title(booking),
               body=f"«{booking.lesson_session.title}»", link=f"/account/bookings/{booking.pk}",
               payload={"booking_id": str(booking.pk), "status": booking.status},
               event_id=f"booking_status:{booking.pk}:{booking.status}", actor=actor)


# --- удаление аккаунта (AT-10) --------------------------------------------------------------------------------------

DELETED_ACCOUNT_REASON = "Аккаунт участника удалён — бронь отменена автоматически."


def cancel_for_deleted_account(account, now=None):
    """Будущие запросы и подтверждённые брони удалённого аккаунта (клиент или исполнитель-аккаунт) отменяются
    системой: ресурс освобождается, вторая сторона уведомляется, история и аналитика сохраняются.
    Вызывать внутри транзакции анонимизации (apps.accounts.services.deletion)."""
    from apps.inventory.models import InventoryItem
    from apps.learning.models import LessonSession

    now = now or timezone.now()
    ids = list(Booking.objects.filter(Q(customer=account) | Q(provider_account=account),
                                      status__in=[S.REQUESTED, S.CONFIRMED], starts_at__gt=now)
               .order_by("starts_at").values_list("pk", flat=True))
    cancelled = []
    for pk in ids:
        head = Booking.objects.filter(pk=pk).values("lesson_session_id", "inventory_item_id").first()
        # Порядок блокировок как в booking_action: ресурс → бронь.
        if head["lesson_session_id"]:
            LessonSession.objects.select_for_update().filter(pk=head["lesson_session_id"]).first()
        elif head["inventory_item_id"]:
            InventoryItem.objects.select_for_update().filter(pk=head["inventory_item_id"]).first()
        booking = Booking.objects.select_for_update().filter(pk=pk, status__in=[S.REQUESTED, S.CONFIRMED]).first()
        if booking is None:
            continue
        transition(booking, S.CANCELLED, None, comment=DELETED_ACCOUNT_REASON, cancel_reason=DELETED_ACCOUNT_REASON,
                   cancelled_side=Booking.Side.SYSTEM)
        _maybe_offer_waitlist(booking)
        customer_left = booking.customer_id == account.pk
        notify_booking_status(booking, None, to_customer=not customer_left, to_provider=customer_left,
                              reason=DELETED_ACCOUNT_REASON)
        cancelled.append(booking)
    return cancelled


# --- периодические задачи -------------------------------------------------------------------------------------------

def expire_stale_requests(now=None, limit=500):
    from django.conf import settings

    now = now or timezone.now()
    cutoff = now - dt.timedelta(hours=settings.BOOKING_REQUEST_TTL_HOURS)
    ids = list(Booking.objects.filter(status=S.REQUESTED).filter(Q(created_at__lt=cutoff) | Q(starts_at__lte=now))
               .values_list("pk", flat=True)[:limit])
    done = 0
    for pk in ids:
        with transaction.atomic():
            booking = Booking.objects.select_for_update(skip_locked=True).filter(pk=pk, status=S.REQUESTED).first()
            if booking is None:
                continue
            if booking.starts_at <= now:
                reason = "Время начала прошло, а заявка не была подтверждена."
            else:
                reason = f"Исполнитель не ответил на заявку за {settings.BOOKING_REQUEST_TTL_HOURS} ч."
            transition(booking, S.CANCELLED, None, comment=reason, cancel_reason=reason,
                       cancelled_side=Booking.Side.SYSTEM)
            notify_booking_status(booking, None, reason=reason)
            done += 1
    return done


def mark_overdue_rentals(now=None, limit=500):
    now = now or timezone.now()
    ids = list(Booking.objects.filter(kind=Booking.Kind.RENTAL, status=S.IN_PROGRESS, ends_at__lt=now,
                                      is_overdue=False).values_list("pk", flat=True)[:limit])
    done = 0
    for pk in ids:
        with transaction.atomic():
            booking = (Booking.objects.select_for_update(skip_locked=True)
                       .filter(pk=pk, status=S.IN_PROGRESS, is_overdue=False).first())
            if booking is None:
                continue
            booking.is_overdue = True
            booking.save(update_fields=["is_overdue", "updated_at"])
            from apps.commerce.services.access import booking_provider_accounts
            from apps.commerce.services.booking_transitions import booking_title

            when = timezone.localtime(booking.ends_at).strftime("%d.%m.%Y %H:%M")
            for recipient in [booking.customer] + booking_provider_accounts(booking):
                notify(recipient, Notification.Kind.BOOKING_STATUS, "Просрочен возврат инвентаря",
                       body=f"«{booking_title(booking)}»: срок аренды истёк {when}.",
                       link=f"/account/bookings/{booking.pk}",
                       payload={"booking_id": str(booking.pk), "status": booking.status, "is_overdue": True},
                       event_id=f"booking_overdue:{booking.pk}")
            push_to_users(booking_audience_ids(booking), {"type": "booking.updated", "booking_id": str(booking.pk),
                                                          "status": booking.status, "is_overdue": True})
            done += 1
    return done
