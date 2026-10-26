"""Кабинет инвентаря (RENT-02, 8.5): личные экземпляры — при направлении «Прокат», экземпляры организации —
любому активному сотруднику этой организации (школа, прокат, мастерская)."""
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import Specialty
from apps.accounts.services.specialties import require_specialty
from apps.boards.models import BoardVariant
from apps.boards.services.access import member_workshop_ids
from apps.boards.services.dimensions import format_dimensions
from apps.commerce.models import ACTIVE_BOOKING_STATUSES, Booking, Inquiry
from apps.common.exceptions import Conflict, DomainError, Forbidden, NotFound
from apps.inventory.models import InventoryItem, InventoryItemPhoto
from apps.mediafiles.models import MediaAsset
from apps.mediafiles.services import claim_many
from apps.organizations.models import Organization
from apps.organizations.services.access import is_member, organization_ids_for
from apps.trust.services.audit import record
from apps.trust.services.restrictions import require_can_publish

MAX_PHOTOS = 10
RENTAL_PURPOSES = [InventoryItem.Purpose.RENTAL, InventoryItem.Purpose.BOTH]
EDITABLE_FIELDS = ["kind", "purpose", "title", "description", "size", "condition", "region", "spot", "pickup_location",
                   "available_hours", "rental_price_per_day", "rental_price_per_hour", "sale_price", "deposit_note",
                   "currency", "min_rental_hours", "restrictions", "serial_number", "is_published"]
# Статусы, которые владелец меняет вручную. reserved выставляет продажа (commerce).
MANUAL_STATUSES = [InventoryItem.Status.AVAILABLE, InventoryItem.Status.MAINTENANCE, InventoryItem.Status.RETIRED,
                   InventoryItem.Status.SOLD]


def manageable_items(account):
    """IDOR: личные экземпляры + экземпляры организаций, где я активный участник."""
    return InventoryItem.objects.filter(
        Q(owner_account=account) | Q(owner_organization_id__in=organization_ids_for(account)))


def list_items(account, organization_id=None):
    if organization_id:
        organization = get_organization(organization_id)
        if not is_member(account, organization):
            raise Forbidden("Вы не состоите в этой организации.", code="not_org_member")
        return InventoryItem.objects.filter(owner_organization=organization)
    return InventoryItem.objects.filter(owner_account=account)


def get_organization(organization_id):
    organization = Organization.objects.filter(pk=organization_id).first()
    if organization is None:
        raise NotFound("Организация не найдена.", code="organization_not_found")
    return organization


def item_for_manager(account, item_id, lock=False):
    qs = manageable_items(account).filter(pk=item_id)
    if lock:
        qs = qs.select_for_update(of=("self",))
    item = qs.first()
    if item is None:
        raise NotFound("Экземпляр не найден.", code="item_not_found")
    return item


def _resolve_owner(account, organization_id):
    if organization_id:
        organization = get_organization(organization_id)
        if not is_member(account, organization):
            raise Forbidden("Добавлять инвентарь организации могут только её активные сотрудники.",
                            code="not_org_member")
        return None, organization
    require_specialty(account, Specialty.RENTAL,
                      "Подключите направление «Прокат» в разделе «Мои направления», чтобы сдавать снаряжение.")
    return account, None


def _resolve_variant(account, variant_id):
    if variant_id is None:
        return None
    variant = (BoardVariant.objects.select_related("model", "model__workshop")
               .filter(pk=variant_id, is_active=True, model__workshop_id__in=member_workshop_ids(account)).first())
    if variant is None:
        raise DomainError("variant_invalid", "Привязать можно только активный вариант доски вашей мастерской.",
                          fields={"variant_id": ["Вариант недоступен."]})
    return variant


def _validate(item):
    errors = {}
    if item.purpose in RENTAL_PURPOSES and item.rental_price_per_day is None and item.rental_price_per_hour is None:
        errors["rental_price_per_day"] = ["Укажите цену аренды за день или за час."]
    if item.spot_id and item.region_id and item.spot.region_id != item.region_id:
        errors["spot_id"] = ["Спот находится в другом регионе."]
    if item.variant_id and item.kind != InventoryItem.Kind.BOARD:
        errors["variant_id"] = ["Вариант доски можно указать только для доски."]
    if errors:
        raise DomainError("validation_error", "Проверьте данные экземпляра.", fields=errors)


def _apply(item, data):
    for field in EDITABLE_FIELDS:
        if field in data:
            value = data[field]
            setattr(item, field, value.strip() if isinstance(value, str) and field != "description" else value)
    if item.spot_id and not item.region_id:
        item.region_id = item.spot.region_id


@transaction.atomic
def create_item(account, data, request=None):
    require_can_publish(account)
    owner_account, owner_organization = _resolve_owner(account, data.get("organization_id"))
    item = InventoryItem(owner_account=owner_account, owner_organization=owner_organization)
    _apply(item, data)
    if "variant_id" in data:
        item.variant = _resolve_variant(account, data["variant_id"])
    if item.variant and not item.size:
        item.size = format_dimensions(item.variant.length_in, item.variant.width_in, item.variant.thickness_in)
    if item.variant and not item.title:
        item.title = item.variant.model.name
    if not item.title:
        raise DomainError("validation_error", "Укажите название.", fields={"title": ["Обязательное поле."]})
    if item.region_id is None and owner_organization is not None:
        item.region_id = owner_organization.region_id
    _validate(item)
    item.save()
    if data.get("photo_ids"):
        add_photos(item, account, data["photo_ids"])
    record(account, "inventory.item_created", item, after={"title": item.title, "purpose": item.purpose},
           organization=owner_organization, request=request)
    return item


@transaction.atomic
def update_item(account, item, data, request=None):
    item = InventoryItem.objects.select_for_update().get(pk=item.pk)
    if _changes_public_content(item, data):
        require_can_publish(account)
    if item.status == InventoryItem.Status.SOLD and set(data) - {"is_published"}:
        raise Conflict("Проданный экземпляр не редактируется.", code="item_sold")
    before = {"status": item.status, "is_published": item.is_published, "variant_id": str(item.variant_id or "")}
    _apply(item, data)
    if "variant_id" in data:
        item.variant = _resolve_variant(account, data["variant_id"]) if data["variant_id"] else None
    if "status" in data and data["status"] != item.status:
        _check_status_change(item, data["status"])
        item.status = data["status"]
    _validate(item)
    item.save()
    record(account, "inventory.item_updated", item, before=before,
           after={"status": item.status, "is_published": item.is_published, "variant_id": str(item.variant_id or "")},
           organization=item.owner_organization, request=request)
    return item


def _changes_public_content(item, data):
    """Правка объявления или его публикация; смена физического статуса и снятие с публикации — нет."""
    content = set(data) - {"status", "is_published"}
    return bool(content) or (data.get("is_published") is True and not item.is_published)


def active_future_bookings(item):
    return Booking.objects.filter(inventory_item=item, status__in=ACTIVE_BOOKING_STATUSES, ends_at__gt=timezone.now())


def _check_status_change(item, new_status):
    if new_status not in MANUAL_STATUSES:
        raise DomainError("status_invalid", "Недопустимый статус.", fields={"status": ["Недопустимый статус."]})
    if item.status == InventoryItem.Status.SOLD:
        raise Conflict("Экземпляр уже продан.", code="item_sold")
    if new_status != InventoryItem.Status.AVAILABLE and active_future_bookings(item).exists():
        raise Conflict("У экземпляра есть подтверждённые брони. Сначала отмените или завершите их.",
                       code="item_has_active_bookings")


@transaction.atomic
def change_status(account, item, new_status, request=None):
    return update_item(account, item, {"status": new_status}, request=request)


@transaction.atomic
def delete_item(account, item, request=None):
    """С бронями/обращениями — списание и снятие с публикации (история сохраняется), иначе удаление."""
    item = InventoryItem.objects.select_for_update().get(pk=item.pk)
    has_history = (Booking.objects.filter(inventory_item=item).exists()
                   or Inquiry.objects.filter(inventory_item=item).exists())
    if has_history:
        if active_future_bookings(item).exists():
            raise Conflict("У экземпляра есть подтверждённые брони. Сначала отмените или завершите их.",
                           code="item_has_active_bookings")
        if item.status != InventoryItem.Status.SOLD:
            item.status = InventoryItem.Status.RETIRED
        item.is_published = False
        item.save(update_fields=["status", "is_published", "updated_at"])
        record(account, "inventory.item_retired", item, organization=item.owner_organization, request=request)
        return "retired"
    record(account, "inventory.item_deleted", item, before={"title": item.title}, organization=item.owner_organization,
           request=request)
    item.delete()
    return "deleted"


# ---------------------------------------------------------------- фото

def _lock(item):
    InventoryItem.objects.select_for_update().filter(pk=item.pk).first()


def _renumber(item):
    for index, photo in enumerate(InventoryItemPhoto.objects.filter(item=item).order_by("position", "id")):
        if photo.position != index:
            photo.position = index
            photo.save(update_fields=["position"])


@transaction.atomic
def add_photos(item, account, media_ids):
    require_can_publish(account)
    _lock(item)
    count = InventoryItemPhoto.objects.filter(item=item).count()
    if count + len(media_ids) > MAX_PHOTOS:
        raise Conflict(f"Можно загрузить не более {MAX_PHOTOS} фотографий (сейчас {count}).", code="photo_limit")
    if len(set(media_ids)) != len(media_ids):
        raise DomainError("validation_error", "Одно и то же фото указано несколько раз.",
                          fields={"media_ids": ["Повторяющиеся id."]})
    assets = claim_many(media_ids, account, purposes=[MediaAsset.Purpose.ITEM_PHOTO], kinds=[MediaAsset.Kind.IMAGE])
    if InventoryItemPhoto.objects.filter(item=item, media__in=assets).exists():
        raise Conflict("Это фото уже добавлено.", code="media_in_use")
    for offset, asset in enumerate(assets):
        InventoryItemPhoto.objects.create(item=item, media=asset, position=count + offset)
    _renumber(item)


@transaction.atomic
def reorder_photos(item, ids):
    _lock(item)
    current = list(InventoryItemPhoto.objects.filter(item=item).values_list("pk", flat=True))
    if sorted(current) != sorted(ids) or len(ids) != len(set(ids)):
        raise DomainError("order_mismatch", "Передайте все фото ровно по одному разу.",
                          fields={"ids": ["Список не совпадает с фото экземпляра."]})
    for index, pk in enumerate(ids):
        InventoryItemPhoto.objects.filter(pk=pk).update(position=index)


@transaction.atomic
def delete_photo(item, photo_id):
    _lock(item)
    photo = InventoryItemPhoto.objects.filter(item=item, pk=photo_id).first()
    if photo is None:
        raise NotFound("Фото не найдено.", code="photo_not_found")
    photo.delete()
    _renumber(item)
