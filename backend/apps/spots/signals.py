"""Инвалидация кеша маркеров карты при изменении спотов, их фото, регионов и обложек."""
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.mediafiles.models import MediaAsset
from apps.spots.models import Region, Spot, SpotPhoto
from apps.spots.services.catalog import invalidate_map_cache


@receiver(post_save, sender=Spot, dispatch_uid="spots_map_spot_saved")
@receiver(post_delete, sender=Spot, dispatch_uid="spots_map_spot_deleted")
@receiver(post_save, sender=SpotPhoto, dispatch_uid="spots_map_photo_saved")
@receiver(post_delete, sender=SpotPhoto, dispatch_uid="spots_map_photo_deleted")
@receiver(post_save, sender=Region, dispatch_uid="spots_map_region_saved")
@receiver(post_delete, sender=Region, dispatch_uid="spots_map_region_deleted")
def _spot_changed(sender, **kwargs):
    invalidate_map_cache()


@receiver(post_save, sender=MediaAsset, dispatch_uid="spots_map_media_saved")
def _media_changed(sender, instance, created=False, **kwargs):
    """Миниатюра маркера меняется, когда фото спота дообработано/отклонено/удалено."""
    if created:
        return
    if instance.purpose == MediaAsset.Purpose.SPOT_PHOTO or Spot.objects.filter(cover=instance).exists():
        invalidate_map_cache()

