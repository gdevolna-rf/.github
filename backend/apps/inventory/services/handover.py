"""Акты выдачи/возврата аренды (RENT-06): confirmed → in_progress («выдано») → completed («возвращено»).

Всё в одной транзакции: select_for_update экземпляра, затем брони (как в commerce); смена статуса — только через
apps.commerce.services.booking_transitions.transition (история, аналитика, WS).
"""
from django.db import IntegrityError, transaction

from apps.commerce.models import Booking
from apps.commerce.services.booking_transitions import notify_booking_status, transition
from apps.common.exceptions import Conflict, DomainError, Forbidden, NotFound
from apps.inventory.models import InventoryItem, RentalHandover
from apps.mediafiles.models import MediaAsset
from apps.mediafiles.services import claim_many
from apps.organizations.services.access import is_member
from apps.trust.services.audit import record

MAX_PHOTOS = 10


def is_provider(account, booking):
    if booking.provider_account_id and booking.provider_account_id == account.pk:
        return True
    return bool(booking.provider_organization_id and is_member(account, booking.provider_organization))


def is_participant(account, booking):
    return booking.customer_id == account.pk or is_provider(account, booking)


def _booking_for(account, booking_id, lock=False):
    qs = Booking.objects.filter(pk=booking_id)
    if lock:
        qs = qs.select_for_update(of=("self",))
    booking = qs.select_related("provider_organization", "inventory_item").first()
    if booking is None or not is_participant(account, booking):
        raise NotFound("Бронирование не найдено.", code="booking_not_found")
    return booking


@transaction.atomic
def record_handover(account, booking_id, data, request=None):
    booking = _booking_for(account, booking_id)  # 404 до блокировок
    if booking.kind != Booking.Kind.RENTAL or booking.inventory_item_id is None:
        raise DomainError("not_rental", "Акт выдачи/возврата оформляется только для аренды.")
    if not is_provider(account, booking):
        raise Forbidden("Акт оформляет исполнитель аренды.", code="not_provider")
    kind = data["kind"]
    if data.get("damage_reported") and not (data.get("damage_description") or "").strip():
        raise DomainError("validation_error", "Опишите повреждение.",
                          fields={"damage_description": ["Обязательно при отметке о повреждении."]})
    photo_ids = data.get("photo_ids") or []
    if len(photo_ids) > MAX_PHOTOS:
        raise Conflict(f"Можно приложить не более {MAX_PHOTOS} фото.", code="photo_limit")
    photos = claim_many(photo_ids, account, purposes=[MediaAsset.Purpose.HANDOVER_PHOTO],
                        kinds=[MediaAsset.Kind.IMAGE]) if photo_ids else []

    # Порядок блокировок тот же, что в commerce.services.bookings.booking_action: экземпляр → бронь.
    # Обратный порядок (бронь → экземпляр) при параллельном подтверждении другой брони того же экземпляра
    # даёт взаимную блокировку (deadlock).
    item = InventoryItem.objects.select_for_update().get(pk=booking.inventory_item_id)
    booking = _booking_for(account, booking_id, lock=True)
    damaged = bool(data.get("damage_reported"))
    if kind == RentalHandover.Kind.ISSUE:
        if booking.status != Booking.Status.CONFIRMED:
            raise Conflict("Выдать можно только подтверждённую бронь.", code="invalid_status")
        transition(booking, Booking.Status.IN_PROGRESS, account, comment="Акт выдачи")
    else:
        if booking.status != Booking.Status.IN_PROGRESS:
            raise Conflict("Оформить возврат можно только после выдачи.", code="invalid_status")
        transition(booking, Booking.Status.COMPLETED, account, comment="Акт возврата",
                   damage_reported=booking.damage_reported or damaged)
        item.condition = data["condition"]
        update_fields = ["condition", "updated_at"]
        if damaged:
            item.status = InventoryItem.Status.MAINTENANCE
            update_fields.append("status")
        item.save(update_fields=update_fields)

    try:
        with transaction.atomic():
            handover = RentalHandover.objects.create(
                booking=booking, kind=kind, condition=data["condition"], notes=data.get("notes", ""),
                damage_reported=damaged, damage_description=data.get("damage_description", ""), recorded_by=account,
            )
    except IntegrityError as exc:
        raise Conflict("Такой акт по брони уже оформлен.", code="handover_exists") from exc
    if photos:
        handover.photos.set(photos)

    record(account, f"rental.handover_{kind}", booking,
           after={"handover_id": str(handover.pk), "condition": handover.condition, "damage_reported": damaged},
           organization=booking.provider_organization, request=request)
    reason = f"при возврате отмечено повреждение — {handover.damage_description.strip()}" if damaged else ""
    notify_booking_status(booking, account, reason=reason)
    return handover


def list_handovers(account, booking_id):
    booking = _booking_for(account, booking_id)
    return (RentalHandover.objects.filter(booking=booking).select_related("recorded_by", "recorded_by__profile")
            .prefetch_related("photos").order_by("created_at"))
