"""Размерные варианты: серверный артикул, версии при изменении конструкции после заказов (6.2, BRD-05/06, F10)."""
from django.db import IntegrityError, transaction

from apps.boards.models import BoardMedia, BoardModel, BoardVariant
from apps.boards.services.availability import refresh_variant_availability, refresh_variants
from apps.boards.services.dimensions import format_dimensions, format_length
from apps.boards.services.history import free_items_of, variant_has_history
from apps.boards.services.sku import compute_variant_sku
from apps.boards.services.types import resolve_material
from apps.common.exceptions import Conflict, DomainError
from apps.inventory.models import InventoryItem
from apps.trust.services.audit import record
from apps.trust.services.restrictions import require_can_publish

# Изменение этих полей у варианта с историей создаёт новую версию (новый UUID, version+1, старая — is_active=False).
SPEC_FIELDS = ["length_in", "width_in", "thickness_in", "volume_l", "material_id", "construction", "fin_system",
               "sku_suffix"]
PLAIN_FIELDS = ["fin_setup", "price", "currency", "made_to_order_days", "is_active"]
COPY_FIELDS = SPEC_FIELDS + PLAIN_FIELDS


def sku_conflict():
    return Conflict("Вариант с таким артикулом уже существует: у модели есть вариант с теми же типом, длиной и "
                    "шириной. Укажите суффикс артикула (например, материал).", code="sku_conflict",
                    fields={"sku_suffix": ["Артикул занят — добавьте суффикс."]})


def _save_with_sku(variant, **sku_kwargs):
    variant.sku = compute_variant_sku(variant, **sku_kwargs)
    try:
        with transaction.atomic():
            variant.save()
    except IntegrityError as exc:
        if "sku" in str(exc):
            raise sku_conflict() from exc
        raise


def _ensure_not_last_active(model, leaving_ids):
    if model.status != BoardModel.Status.PUBLISHED:
        return
    still_active = BoardVariant.objects.filter(model=model, is_active=True).exclude(pk__in=leaving_ids).exists()
    if not still_active:
        raise Conflict("У опубликованной модели должен остаться хотя бы один активный вариант. Добавьте другой "
                       "вариант или снимите модель с публикации.", code="last_active_variant")


def _material_value(model, data):
    return resolve_material(model.workshop, data["material_id"]).pk if data.get("material_id") is not None else None


@transaction.atomic
def create_variant(model, account, data, request=None):
    require_can_publish(account)
    BoardModel.objects.select_for_update().filter(pk=model.pk).first()
    if model.status == BoardModel.Status.ARCHIVED:
        raise Conflict("Модель в архиве.", code="model_archived")
    variant = BoardVariant(model=model)
    for field in COPY_FIELDS:
        if field == "material_id":
            variant.material_id = _material_value(model, data)
        elif field in data:
            setattr(variant, field, data[field])
    _save_with_sku(variant, model=model)
    if data.get("in_stock_quantity") is not None:
        set_stock_quantity(variant, data["in_stock_quantity"])
    refresh_variant_availability(variant)
    record(account, "board_variant.created", variant, after={"sku": variant.sku}, organization=model.workshop,
           request=request)
    return variant


def _changed(variant, field, value):
    return getattr(variant, field) != value


@transaction.atomic
def update_variant(variant, account, data, request=None):
    """Возвращает (variant, versioned). При versioned=True возвращается новая версия."""
    require_can_publish(account)
    variant = BoardVariant.objects.select_for_update().select_related("model__workshop", "model__board_type").get(pk=variant.pk)
    model = variant.model
    if "material_id" in data:
        data = {**data, "material_id": _material_value(model, data)}
    spec_changes = {f: data[f] for f in SPEC_FIELDS if f in data and _changed(variant, f, data[f])}
    plain_changes = {f: data[f] for f in PLAIN_FIELDS if f in data and _changed(variant, f, data[f])}

    if plain_changes.get("is_active") is False:
        _ensure_not_last_active(model, [variant.pk])

    if spec_changes and variant_has_history(variant):
        if not variant.is_active:
            raise Conflict("Это архивная версия варианта: по ней были заказы. Измените актуальную версию.",
                           code="variant_archived")
        new = create_new_version(variant, account, {**spec_changes, **plain_changes}, request=request)
        if data.get("in_stock_quantity") is not None:
            set_stock_quantity(new, data["in_stock_quantity"])
            refresh_variant_availability(new)
        return new, True

    before = {"sku": variant.sku, **{f: str(getattr(variant, f)) for f in {**spec_changes, **plain_changes}}}
    for field, value in {**spec_changes, **plain_changes}.items():
        setattr(variant, field, value)
    if spec_changes:
        _save_with_sku(variant, model=model)
    else:
        variant.save()
    if data.get("in_stock_quantity") is not None:
        set_stock_quantity(variant, data["in_stock_quantity"])
    refresh_variant_availability(variant)
    if spec_changes or plain_changes:
        record(account, "board_variant.updated", variant, before=before,
               after={"sku": variant.sku, **{f: str(getattr(variant, f)) for f in {**spec_changes, **plain_changes}}},
               organization=model.workshop, request=request)
    return variant, False


def create_new_version(old, account, changes, request=None, board_type=None):
    """Новая версия варианта: прошлые обращения/брони продолжают ссылаться на старый UUID и его снимок (F10)."""
    model = old.model
    new = BoardVariant(model=model, previous_version=old, version=old.version + 1, is_active=True)
    for field in COPY_FIELDS:
        setattr(new, field, getattr(old, field))
    for field, value in changes.items():
        setattr(new, field, value)
    new.is_active = True
    old.is_active = False
    old.save(update_fields=["is_active", "updated_at"])
    _save_with_sku(new, model=model, board_type=board_type)
    # Фото варианта и свободный склад относятся к актуальному предложению; экземпляры с бронями/продажами остаются.
    BoardMedia.objects.filter(variant=old).update(variant=new)
    free_ids = list(free_items_of(old).values_list("pk", flat=True))
    if free_ids:
        InventoryItem.objects.filter(pk__in=free_ids).update(variant=new)
    refresh_variants([old.pk, new.pk])
    new.refresh_from_db()
    record(account, "board_variant.versioned", new, before={"id": str(old.pk), "sku": old.sku, "version": old.version},
           after={"id": str(new.pk), "sku": new.sku, "version": new.version, "changes": sorted(changes)},
           organization=model.workshop, request=request)
    return new


@transaction.atomic
def delete_variant(variant, account, request=None):
    """Без истории и экземпляров — удаление; иначе деактивация (история и ссылки сохраняются)."""
    variant = BoardVariant.objects.select_for_update().select_related("model__workshop").get(pk=variant.pk)
    model = variant.model
    if variant.is_active:
        _ensure_not_last_active(model, [variant.pk])
    if variant_has_history(variant) or variant.items.exists():
        if variant.is_active:
            variant.is_active = False
            variant.save(update_fields=["is_active", "updated_at"])
        record(account, "board_variant.deactivated", variant, organization=model.workshop, request=request)
        return "deactivated"
    record(account, "board_variant.deleted", variant, before={"sku": variant.sku}, organization=model.workshop,
           request=request)
    variant.delete()
    return "deleted"


def set_stock_quantity(variant, quantity):
    """«В наличии: N» — число свободных экземпляров мастерской на продажу по этому варианту (BRD-07/13).

    Добавляет недостающие экземпляры (InventoryItem purpose=sale владельца-мастерской) или убирает лишние:
    без истории — удаляются, с историей — списываются (retired).
    """
    from apps.commerce.models import Booking, Inquiry

    if quantity < 0 or quantity > 100:
        raise DomainError("validation_error", "Количество в наличии — от 0 до 100.",
                          fields={"in_stock_quantity": ["От 0 до 100."]})
    model = variant.model
    workshop = model.workshop
    items = list(InventoryItem.objects.select_for_update().filter(
        variant=variant, owner_organization=workshop, purpose=InventoryItem.Purpose.SALE,
        status=InventoryItem.Status.AVAILABLE,
    ).order_by("-created_at"))
    current = len(items)
    if quantity > current:
        InventoryItem.objects.bulk_create([
            InventoryItem(
                owner_organization=workshop, variant=variant, kind=InventoryItem.Kind.BOARD,
                purpose=InventoryItem.Purpose.SALE, status=InventoryItem.Status.AVAILABLE,
                title=f"{model.name} {format_length(variant.length_in)}", size=format_dimensions(
                    variant.length_in, variant.width_in, variant.thickness_in),
                condition=InventoryItem.Condition.NEW, sale_price=variant.price, currency=variant.currency,
                region_id=workshop.region_id, is_published=True,
            )
            for _ in range(quantity - current)
        ])
    elif quantity < current:
        surplus = items[: current - quantity]
        ids = [i.pk for i in surplus]
        with_history = set(Booking.objects.filter(inventory_item_id__in=ids).values_list("inventory_item_id", flat=True))
        with_history |= set(Inquiry.objects.filter(inventory_item_id__in=ids).values_list("inventory_item_id", flat=True))
        InventoryItem.objects.filter(pk__in=[i for i in ids if i in with_history]).update(
            status=InventoryItem.Status.RETIRED, is_published=False)
        InventoryItem.objects.filter(pk__in=[i for i in ids if i not in with_history]).delete()
    refresh_variant_availability(variant)


@transaction.atomic
def bulk_update_variants(workshop, account, rows, request=None):
    """Табличное редактирование (BRD-12): все строки валидны и принадлежат мастерской — иначе ничего не меняется."""
    require_can_publish(account)
    ids = [row["id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise DomainError("validation_error", "Вариант указан в списке несколько раз.",
                          fields={"items": ["Повторяющиеся id."]})
    variants = {v.pk: v for v in BoardVariant.objects.select_for_update().filter(pk__in=ids, model__workshop=workshop)}
    missing = {f"items.{i}.id": ["Вариант не найден в этой мастерской."] for i, row in enumerate(rows)
               if row["id"] not in variants}
    if missing:
        raise DomainError("validation_error", "Некоторые варианты не найдены в вашей мастерской.", fields=missing)
    deactivating = [row["id"] for row in rows if row.get("is_active") is False]
    if deactivating:
        for model in BoardModel.objects.filter(variants__pk__in=deactivating).distinct():
            _ensure_not_last_active(model, deactivating)
    updated = []
    for row in rows:
        variant = variants[row["id"]]
        changes = {f: row[f] for f in PLAIN_FIELDS if f in row}
        for field, value in changes.items():
            setattr(variant, field, value)
        variant.save()
        if row.get("in_stock_quantity") is not None:
            set_stock_quantity(variant, row["in_stock_quantity"])
        refresh_variant_availability(variant)
        updated.append(variant)
    record(account, "board_variant.bulk_updated", workshop, object_type="boards.boardvariant",
           object_id=str(workshop.pk), after={"ids": [str(i) for i in ids]}, organization=workshop, request=request)
    return updated
