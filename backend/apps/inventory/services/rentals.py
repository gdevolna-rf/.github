"""Публичный каталог аренды (RENT-01, 8.5) и доступность по интервалам (RENT-03/04/05).

Источник правды по занятости — подтверждённые/выданные брони (commerce.Booking confirmed|in_progress),
защищённые exclusion-ограничением в БД; статус экземпляра описывает только его физическое состояние.
"""
import datetime as dt
import uuid
from decimal import Decimal, InvalidOperation

from django.db.models import Exists, OuterRef, Prefetch, Q
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from apps.commerce.models import ACTIVE_BOOKING_STATUSES, Booking
from apps.common.exceptions import DomainError
from apps.inventory.models import InventoryItem, InventoryItemPhoto
from apps.inventory.services.items import RENTAL_PURPOSES, list_items
from apps.organizations.models import Organization

HIDDEN_STATUSES = [InventoryItem.Status.RETIRED, InventoryItem.Status.MAINTENANCE, InventoryItem.Status.SOLD]


def visible_owner_q():
    """Владелец объявления виден публично: опубликованная организация или активный аккаунт без ограничения
    профиля (suspended). Одно правило для каталога, поиска, помощника, избранного и создания брони."""
    from apps.trust.services.restrictions import suspended_exists

    personal = (Q(owner_account__isnull=False, owner_account__is_active=True, owner_account__anonymized_at__isnull=True)
                & ~suspended_exists("owner_account_id"))
    return personal | Q(owner_organization__isnull=False, owner_organization__status=Organization.Status.PUBLISHED)


def public_rentals():
    return InventoryItem.objects.filter(
        is_published=True, purpose__in=RENTAL_PURPOSES,
    ).exclude(status__in=HIDDEN_STATUSES).filter(visible_owner_q())


def parse_moment(value, name, end=False):
    """ISO datetime или дата (дата → начало дня / начало следующего дня в часовом поясе проекта)."""
    if value in (None, ""):
        return None
    value = value.strip().replace(" ", "+") if "T" in value else value.strip()  # «+03:00» из query string
    try:
        day = parse_date(value) if len(value) == 10 else None
        moment = None if day else parse_datetime(value)
    except ValueError:
        day = moment = None
    if day is None and moment is None:
        raise DomainError("validation_error", "Некорректная дата.",
                          fields={name: ["Ожидается дата (ГГГГ-ММ-ДД) или дата-время ISO 8601."]})
    if day is not None:
        moment = dt.datetime.combine(day + dt.timedelta(days=1) if end else day, dt.time.min)
    if timezone.is_naive(moment):
        moment = timezone.make_aware(moment, timezone.get_current_timezone())
    return moment


def parse_range(params, required=False):
    start = parse_moment(params.get("from"), "from")
    end = parse_moment(params.get("to"), "to", end=True)
    if (start is None) != (end is None):
        raise DomainError("validation_error", "Укажите обе границы периода.",
                          fields={"from" if start is None else "to": ["Обязательное поле, если задана вторая граница."]})
    if start and end and end <= start:
        raise DomainError("validation_error", "Конец периода должен быть позже начала.", fields={"to": ["Позже from."]})
    if start and end and end - start > dt.timedelta(days=366):
        raise DomainError("validation_error", "Период не длиннее года.", fields={"to": ["Не более 366 дней."]})
    return start, end


def overlapping_bookings(start, end):
    return Booking.objects.filter(status__in=ACTIVE_BOOKING_STATUSES, inventory_item__isnull=False,
                                  starts_at__lt=end, ends_at__gt=start)


def _ref_q(value, field):
    if str(value).isdigit():
        return Q(**{f"{field}_id": int(value)})
    return Q(**{f"{field}__slug": value})


def filter_rentals(qs, params):
    if params.get("kind"):
        qs = qs.filter(kind__in=[k for k in params["kind"].split(",") if k])
    if params.get("region"):
        qs = qs.filter(_ref_q(params["region"], "region"))
    if params.get("spot"):
        qs = qs.filter(_ref_q(params["spot"], "spot"))
    if params.get("organization"):
        value = params["organization"]
        try:
            qs = qs.filter(owner_organization_id=uuid.UUID(value))
        except ValueError:
            qs = qs.filter(owner_organization__slug=value)
    if params.get("owner"):
        qs = qs.filter(owner_account__profile__handle=params["owner"])
    if params.get("price_max"):
        try:
            price = Decimal(str(params["price_max"]).replace(",", "."))
        except InvalidOperation as exc:
            raise DomainError("validation_error", "Некорректный фильтр.", fields={"price_max": ["Ожидается число."]}) from exc
        qs = qs.filter(Q(rental_price_per_day__lte=price)
                       | Q(rental_price_per_day__isnull=True, rental_price_per_hour__lte=price))
    q = (params.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q) | Q(size__icontains=q)
                       | Q(pickup_location__icontains=q) | Q(spot__name__icontains=q) | Q(region__name__icontains=q)
                       | Q(variant__model__name__icontains=q))
    start, end = parse_range(params)
    if start and end:
        qs = qs.exclude(Exists(overlapping_bookings(start, end).filter(inventory_item=OuterRef("pk"))))
    return qs


def card_queryset(qs):
    return qs.select_related(
        "region", "spot", "owner_account", "owner_account__profile", "owner_account__profile__avatar",
        "owner_organization", "owner_organization__logo", "variant", "variant__model", "variant__model__board_type",
        "variant__model__workshop",
    ).prefetch_related(Prefetch("photos", queryset=InventoryItemPhoto.objects.select_related("media")
                                .order_by("position", "id")))


def booked_intervals(item, start=None, end=None, limit=500):
    """Занятые интервалы экземпляра — только время, без данных клиента."""
    qs = Booking.objects.filter(inventory_item=item, status__in=ACTIVE_BOOKING_STATUSES)
    if start and end:
        qs = qs.filter(starts_at__lt=end, ends_at__gt=start)
    else:
        qs = qs.filter(ends_at__gt=timezone.now())
    return list(qs.order_by("starts_at").values("starts_at", "ends_at")[:limit])


def availability_overview(account, organization_id=None, start=None, end=None, kind=None):
    """RENT-03/04: по каждому экземпляру — занятые интервалы; сводка «Свободных бордов» / «Забронировано»."""
    now = timezone.now()
    if start is None:
        start, end = now, now + dt.timedelta(days=1)
    items = list(list_items(account, organization_id).filter(purpose__in=RENTAL_PURPOSES)
                 .exclude(status__in=[InventoryItem.Status.RETIRED, InventoryItem.Status.SOLD])
                 .order_by("title", "created_at"))
    if kind:
        items = [i for i in items if i.kind in kind.split(",")]
    ids = [i.pk for i in items]
    window_start, window_end = min(start, now), max(end, now)
    bookings = list(Booking.objects.filter(
        inventory_item_id__in=ids, status__in=ACTIVE_BOOKING_STATUSES, starts_at__lt=window_end,
        ends_at__gt=window_start,
    ).order_by("starts_at").values("id", "inventory_item_id", "starts_at", "ends_at", "status"))
    by_item = {}
    for booking in bookings:
        by_item.setdefault(booking["inventory_item_id"], []).append(booking)

    rows, summary = [], {"total": len(items), "free_now": 0, "booked_now": 0, "maintenance": 0,
                         "free_in_range": 0, "booked_in_range": 0}
    for item in items:
        item_bookings = by_item.get(item.pk, [])
        in_range = [b for b in item_bookings if b["starts_at"] < end and b["ends_at"] > start]
        booked_now = any(b["starts_at"] <= now < b["ends_at"] for b in item_bookings)
        maintenance = item.status == InventoryItem.Status.MAINTENANCE
        usable = item.status == InventoryItem.Status.AVAILABLE
        summary["booked_now"] += booked_now
        summary["maintenance"] += maintenance
        summary["free_now"] += usable and not booked_now
        summary["booked_in_range"] += bool(in_range)
        summary["free_in_range"] += usable and not in_range
        rows.append({
            "id": item.pk, "title": item.title, "kind": item.kind, "status": item.status, "size": item.size,
            "is_published": item.is_published, "is_booked_now": booked_now, "is_free_in_range": usable and not in_range,
            "booked": [{"booking_id": b["id"], "starts_at": b["starts_at"], "ends_at": b["ends_at"],
                        "status": b["status"]} for b in in_range],
        })
    return {"from": start, "to": end, "summary": summary, "items": rows}
