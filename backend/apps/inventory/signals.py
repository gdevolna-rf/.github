"""Синхронизация наличия варианта доски с экземплярами (BRD-13): любое сохранение/удаление экземпляра
(сервисы, Django Admin, другие приложения) пересчитывает BoardVariant.availability старого и нового варианта."""
from django.db.models.signals import post_delete, post_init, post_save
from django.dispatch import receiver

from apps.inventory.models import InventoryItem


@receiver(post_init, sender=InventoryItem)
def remember_variant(sender, instance, **kwargs):
    instance._initial_variant_id = instance.__dict__.get("variant_id")


def _refresh(*variant_ids):
    from apps.boards.services.availability import refresh_variants

    ids = [v for v in variant_ids if v]
    if ids:
        refresh_variants(ids)


@receiver(post_save, sender=InventoryItem)
def sync_after_save(sender, instance, raw=False, **kwargs):
    if raw:
        return
    _refresh(instance.variant_id, getattr(instance, "_initial_variant_id", None))
    instance._initial_variant_id = instance.variant_id


@receiver(post_delete, sender=InventoryItem)
def sync_after_delete(sender, instance, **kwargs):
    _refresh(instance.variant_id, getattr(instance, "_initial_variant_id", None))
