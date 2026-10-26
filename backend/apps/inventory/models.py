"""Inventory: физические экземпляры для продажи/аренды и акты выдачи/возврата (BRD-07, раздел 22)."""
from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.common.models import TimeStampedModel


class InventoryItem(TimeStampedModel):
    class Kind(models.TextChoices):
        BOARD = "board", "Доска"
        WETSUIT = "wetsuit", "Гидрокостюм"
        SUP = "sup", "SUP"
        FINS = "fins", "Плавники"
        ACCESSORY = "accessory", "Аксессуар"
        OTHER = "other", "Другое"

    class Purpose(models.TextChoices):
        SALE = "sale", "Продажа"
        RENTAL = "rental", "Аренда"
        BOTH = "both", "Продажа и аренда"

    class Status(models.TextChoices):
        AVAILABLE = "available", "Доступен"
        RESERVED = "reserved", "Зарезервирован"
        SOLD = "sold", "Продан"
        MAINTENANCE = "maintenance", "На обслуживании"
        RETIRED = "retired", "Списан"

    class Condition(models.TextChoices):
        NEW = "new", "Новое"
        EXCELLENT = "excellent", "Отличное"
        GOOD = "good", "Хорошее"
        FAIR = "fair", "Рабочее"

    owner_account = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="inventory_items")
    owner_organization = models.ForeignKey("organizations.Organization", null=True, blank=True, on_delete=models.PROTECT, related_name="inventory_items")
    variant = models.ForeignKey("boards.BoardVariant", null=True, blank=True, on_delete=models.PROTECT, related_name="items")
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.BOARD)
    purpose = models.CharField(max_length=16, choices=Purpose.choices, default=Purpose.RENTAL)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.AVAILABLE, db_index=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    size = models.CharField(max_length=60, blank=True)
    condition = models.CharField(max_length=16, choices=Condition.choices, default=Condition.GOOD)
    region = models.ForeignKey("spots.Region", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    spot = models.ForeignKey("spots.Spot", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    pickup_location = models.CharField("место получения", max_length=300, blank=True)
    available_hours = models.CharField("время доступности", max_length=120, blank=True)
    rental_price_per_day = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    rental_price_per_hour = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    sale_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    deposit_note = models.CharField(max_length=200, blank=True)
    currency = models.CharField(max_length=3, default="RUB")
    min_rental_hours = models.PositiveSmallIntegerField(default=1)
    restrictions = models.TextField("ограничения", blank=True)
    serial_number = models.CharField(max_length=80, blank=True)
    is_published = models.BooleanField(default=True)
    is_demo = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(Q(owner_account__isnull=False, owner_organization__isnull=True)
                           | Q(owner_account__isnull=True, owner_organization__isnull=False)),
                name="inventory_single_owner",
            )
        ]
        verbose_name = "экземпляр инвентаря"
        verbose_name_plural = "инвентарь"

    def __str__(self):
        return self.title


class InventoryItemPhoto(models.Model):
    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name="photos")
    media = models.ForeignKey("mediafiles.MediaAsset", on_delete=models.CASCADE, related_name="+")
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]
        verbose_name = "фото инвентаря"
        verbose_name_plural = "фото инвентаря"


class RentalHandover(TimeStampedModel):
    """Акт выдачи/возврата (RENT-06): состояние, повреждения, фото."""

    class Kind(models.TextChoices):
        ISSUE = "issue", "Выдача"
        RETURN = "return", "Возврат"

    booking = models.ForeignKey("commerce.Booking", on_delete=models.CASCADE, related_name="handovers")
    kind = models.CharField(max_length=16, choices=Kind.choices)
    condition = models.CharField(max_length=16, choices=InventoryItem.Condition.choices)
    notes = models.TextField(blank=True)
    damage_reported = models.BooleanField(default=False)
    damage_description = models.TextField(blank=True)
    photos = models.ManyToManyField("mediafiles.MediaAsset", blank=True, related_name="+")
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    class Meta:
        ordering = ["created_at"]
        constraints = [models.UniqueConstraint(fields=["booking", "kind"], name="uniq_handover_kind_per_booking")]
        verbose_name = "акт выдачи/возврата"
        verbose_name_plural = "акты выдачи/возврата"
