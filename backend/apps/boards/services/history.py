"""Есть ли у модели/варианта «история» (обращения, брони, продажи) — от этого зависит версия или удаление (F10)."""
from django.db.models import Q

from apps.commerce.models import Booking, Inquiry
from apps.inventory.models import InventoryItem


def variant_has_history(variant):
    """Обращения на вариант, брони его экземпляров или проданные экземпляры."""
    if Inquiry.objects.filter(board_variant=variant).exists():
        return True
    if InventoryItem.objects.filter(variant=variant, status=InventoryItem.Status.SOLD).exists():
        return True
    return Booking.objects.filter(inventory_item__variant=variant).exists()


def model_has_history(model):
    if Inquiry.objects.filter(Q(board_model=model) | Q(board_variant__model=model)).exists():
        return True
    return InventoryItem.objects.filter(variant__model=model).exists()


def free_items_of(variant):
    """Экземпляры без истории (не проданы/не списаны и без броней) — «текущий склад», переходит к новой версии."""
    return (InventoryItem.objects.filter(variant=variant)
            .exclude(status__in=[InventoryItem.Status.SOLD, InventoryItem.Status.RETIRED])
            .exclude(pk__in=Booking.objects.filter(inventory_item__variant=variant).values("inventory_item_id")))


def variants_with_history(variant_ids):
    """Множество id вариантов с историей — тремя запросами вместо трёх на вариант."""
    ids = set(variant_ids)
    if not ids:
        return set()
    found = set(Inquiry.objects.filter(board_variant_id__in=ids).values_list("board_variant_id", flat=True))
    found |= set(InventoryItem.objects.filter(variant_id__in=ids, status=InventoryItem.Status.SOLD)
                 .values_list("variant_id", flat=True))
    found |= set(Booking.objects.filter(inventory_item__variant_id__in=ids)
                 .values_list("inventory_item__variant_id", flat=True))
    return found
