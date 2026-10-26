"""Избранное ссылается на реальные типизированные объекты (8.6, MSG-11, ATX-11)."""
from django.conf import settings
from django.db import models
from django.db.models import Q


# Поле FK для каждого типа цели.
TARGET_FIELDS = {
    "spot": "spot",
    "instructor": "instructor",
    "organization": "organization",
    "board_model": "board_model",
    "inventory_item": "inventory_item",
}


def _single_target_condition():
    """Ровно одна FK заполнена и она соответствует target_type (прил. Б: без «висячих» target_id)."""
    condition = None
    for target, field in TARGET_FIELDS.items():
        part = Q(target_type=target, **{f"{field}__isnull": False})
        for other in TARGET_FIELDS.values():
            if other != field:
                part &= Q(**{f"{other}__isnull": True})
        condition = part if condition is None else condition | part
    return condition


class Favorite(models.Model):
    class Target(models.TextChoices):
        SPOT = "spot", "Спот"
        INSTRUCTOR = "instructor", "Инструктор"
        ORGANIZATION = "organization", "Школа / мастерская / прокат"
        BOARD_MODEL = "board_model", "Модель доски"
        INVENTORY_ITEM = "inventory_item", "Оборудование"

    account = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="favorites")
    target_type = models.CharField(max_length=20, choices=Target.choices)
    spot = models.ForeignKey("spots.Spot", null=True, blank=True, on_delete=models.CASCADE, related_name="+")
    instructor = models.ForeignKey("learning.InstructorProfile", null=True, blank=True, on_delete=models.CASCADE, related_name="+")
    organization = models.ForeignKey("organizations.Organization", null=True, blank=True, on_delete=models.CASCADE, related_name="+")
    board_model = models.ForeignKey("boards.BoardModel", null=True, blank=True, on_delete=models.CASCADE, related_name="+")
    inventory_item = models.ForeignKey("inventory.InventoryItem", null=True, blank=True, on_delete=models.CASCADE, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = "избранное"
        verbose_name_plural = "избранное"
        indexes = [models.Index(fields=["account", "target_type", "created_at"])]
        constraints = [
            models.CheckConstraint(condition=_single_target_condition(), name="favorite_single_target"),
            models.UniqueConstraint(fields=["account", "spot"], condition=Q(spot__isnull=False), name="uniq_fav_spot"),
            models.UniqueConstraint(fields=["account", "instructor"], condition=Q(instructor__isnull=False), name="uniq_fav_instructor"),
            models.UniqueConstraint(fields=["account", "organization"], condition=Q(organization__isnull=False), name="uniq_fav_org"),
            models.UniqueConstraint(fields=["account", "board_model"], condition=Q(board_model__isnull=False), name="uniq_fav_board"),
            models.UniqueConstraint(fields=["account", "inventory_item"], condition=Q(inventory_item__isnull=False), name="uniq_fav_item"),
        ]

    def __str__(self):
        return f"{self.account_id}:{self.target_type}:{self.target_id}"

    @property
    def target(self):
        return getattr(self, TARGET_FIELDS[self.target_type])

    @property
    def target_id(self):
        return getattr(self, f"{TARGET_FIELDS[self.target_type]}_id")
