"""Статус «В наличии / Под заказ / Нет в наличии» вычисляется из реального инвентаря (BRD-13).

- «В наличии» — есть опубликованный экземпляр для продажи (sale/both) в статусе available;
- «Под заказ» — экземпляров нет, но у варианта задан срок изготовления made_to_order_days (0 = «срок по договорённости»);
- «Нет в наличии» — иначе.

Синхронизация: сигналы apps.inventory.signals вызывают refresh_* при save/delete экземпляра; массовые
QuerySet.update() по InventoryItem сигналы не вызывают — после них вызывайте refresh_variants(ids) явно.
"""
from apps.boards.models import BoardVariant
from apps.inventory.models import InventoryItem

SALE_PURPOSES = [InventoryItem.Purpose.SALE, InventoryItem.Purpose.BOTH]
AVAILABILITY_RANK = {
    BoardVariant.Availability.IN_STOCK: 0,
    BoardVariant.Availability.MADE_TO_ORDER: 1,
    BoardVariant.Availability.OUT_OF_STOCK: 2,
}


def sale_items_available(variant):
    return variant.items.filter(purpose__in=SALE_PURPOSES, status=InventoryItem.Status.AVAILABLE, is_published=True)


def compute_variant_availability(variant):
    if sale_items_available(variant).exists():
        return BoardVariant.Availability.IN_STOCK
    if variant.made_to_order_days is not None:
        return BoardVariant.Availability.MADE_TO_ORDER
    return BoardVariant.Availability.OUT_OF_STOCK


def refresh_variant_availability(variant):
    """Вызывать после изменения экземпляров варианта (создание, продажа, списание) или срока изготовления."""
    if variant is None:
        return None
    value = compute_variant_availability(variant)
    if value != variant.availability:
        variant.availability = value
        variant.save(update_fields=["availability", "updated_at"])
    return value


def refresh_variants(variant_ids):
    for variant in BoardVariant.objects.filter(pk__in=[v for v in set(variant_ids) if v]):
        refresh_variant_availability(variant)


def best_availability(values):
    """Лучший статус среди вариантов модели (для карточки каталога)."""
    values = [v for v in values if v]
    if not values:
        return BoardVariant.Availability.OUT_OF_STOCK
    return min(values, key=lambda v: AVAILABILITY_RANK.get(v, 9))
