"""Boards: мастерская шейпера, типы досок, материалы, модель → вариант (BR-09, раздел 21)."""
from django.db import models
from django.db.models import Q

from apps.common.models import TimeStampedModel


class WorkshopProfile(models.Model):
    """Профессиональные данные мастерской шейпера, привязанной к организации kind=workshop."""

    organization = models.OneToOneField(
        "organizations.Organization", primary_key=True, on_delete=models.CASCADE, related_name="workshop"
    )
    shaper_code = models.CharField("код шейпера для артикула", max_length=8, unique=True)
    specialization = models.CharField(max_length=300, blank=True)
    services = models.JSONField(default=list, blank=True)  # ["Новые доски", "Индивидуальный заказ", ...]
    lead_time = models.CharField("сроки изготовления", max_length=120, blank=True)
    does_repair = models.BooleanField("делаю ремонт", default=False)
    repair_note = models.CharField(max_length=300, blank=True)
    promo_video = models.ForeignKey("mediafiles.MediaAsset", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    experience_since = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        verbose_name = "мастерская шейпера"
        verbose_name_plural = "мастерские шейперов"

    def __str__(self):
        return f"{self.organization.name} ({self.shaper_code})"


class BoardType(models.Model):
    """Стандартные (workshop=null) и пользовательские типы досок мастерской (SHP-05/06, ATX-07)."""

    workshop = models.ForeignKey(
        "organizations.Organization", null=True, blank=True, on_delete=models.CASCADE, related_name="custom_board_types"
    )
    code = models.SlugField(max_length=40)
    name = models.CharField(max_length=80)
    silhouette = models.CharField(max_length=32, default="shortboard")
    sku_code = models.CharField("код типа в артикуле", max_length=4, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=100)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name = "тип доски"
        verbose_name_plural = "типы досок"
        constraints = [
            models.UniqueConstraint(fields=["code"], condition=Q(workshop__isnull=True), name="uniq_std_board_type"),
            models.UniqueConstraint(fields=["workshop", "code"], name="uniq_workshop_board_type"),
        ]

    def __str__(self):
        return self.name


class Material(models.Model):
    workshop = models.ForeignKey(
        "organizations.Organization", null=True, blank=True, on_delete=models.CASCADE, related_name="custom_materials"
    )
    name = models.CharField(max_length=80)

    class Meta:
        ordering = ["name"]
        verbose_name = "материал"
        verbose_name_plural = "материалы"
        constraints = [
            models.UniqueConstraint(fields=["name"], condition=Q(workshop__isnull=True), name="uniq_std_material"),
            models.UniqueConstraint(fields=["workshop", "name"], name="uniq_workshop_material"),
        ]

    def __str__(self):
        return self.name


class BoardModel(TimeStampedModel):
    """Линейка изделия. UUID стабилен и не зависит от названия/размеров (BRD-06)."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Черновик"
        PUBLISHED = "published", "Опубликована"
        HIDDEN = "hidden", "Скрыта модератором"
        ARCHIVED = "archived", "В архиве"

    workshop = models.ForeignKey("organizations.Organization", on_delete=models.PROTECT, related_name="board_models")
    name = models.CharField(max_length=160)
    slug = models.SlugField(max_length=80)
    board_type = models.ForeignKey(BoardType, on_delete=models.PROTECT, related_name="+")
    description = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT, db_index=True)
    video = models.ForeignKey("mediafiles.MediaAsset", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    tags = models.JSONField(default=list, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    serial = models.PositiveIntegerField("постоянный порядковый номер модели в мастерской", null=True, blank=True)
    is_demo = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["workshop", "slug"], name="uniq_model_slug_per_workshop"),
            models.UniqueConstraint(fields=["workshop", "serial"], condition=Q(serial__isnull=False),
                                    name="uniq_model_serial_per_workshop"),
        ]
        verbose_name = "модель доски"
        verbose_name_plural = "модели досок"

    def __str__(self):
        return self.name


class BoardVariant(TimeStampedModel):
    """Размерная конфигурация. SKU уникален; смена конструкции после заказов — новая версия (6.2, F10)."""

    class FinSystem(models.TextChoices):
        FCS2 = "fcs2", "FCS II"
        FCS = "fcs", "FCS"
        FUTURES = "futures", "Futures"
        SINGLE_BOX = "single_box", "Single box"
        GLASS_ON = "glass_on", "Вклеенные (glass-on)"
        NONE = "none", "Без плавников"

    class Availability(models.TextChoices):
        IN_STOCK = "in_stock", "В наличии"
        MADE_TO_ORDER = "made_to_order", "Под заказ"
        OUT_OF_STOCK = "out_of_stock", "Нет в наличии"

    model = models.ForeignKey(BoardModel, on_delete=models.PROTECT, related_name="variants")
    sku = models.CharField(max_length=64, unique=True)
    sku_suffix = models.CharField(max_length=12, blank=True)
    version = models.PositiveSmallIntegerField(default=1)
    previous_version = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="next_versions")
    is_active = models.BooleanField(default=True)
    length_in = models.DecimalField("длина, дюймы", max_digits=5, decimal_places=2)
    width_in = models.DecimalField("ширина, дюймы", max_digits=5, decimal_places=2)
    thickness_in = models.DecimalField("толщина, дюймы", max_digits=4, decimal_places=2, null=True, blank=True)
    volume_l = models.DecimalField("объём, л", max_digits=5, decimal_places=2, null=True, blank=True)
    material = models.ForeignKey(Material, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    construction = models.CharField(max_length=80, blank=True)
    fin_system = models.CharField(max_length=16, choices=FinSystem.choices, default=FinSystem.FCS2)
    fin_setup = models.CharField(max_length=40, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, default="RUB")
    made_to_order_days = models.PositiveSmallIntegerField(null=True, blank=True)
    availability = models.CharField(max_length=16, choices=Availability.choices, default=Availability.MADE_TO_ORDER)

    class Meta:
        ordering = ["model", "length_in"]
        verbose_name = "вариант доски"
        verbose_name_plural = "варианты досок"

    def __str__(self):
        return self.sku


class BoardMedia(models.Model):
    """Фото модели/варианта: до 10 на галерею, обложка, порядок (BRD-03, UX-08)."""

    MAX_PHOTOS = 10

    model = models.ForeignKey(BoardModel, on_delete=models.CASCADE, related_name="media_items")
    variant = models.ForeignKey(BoardVariant, null=True, blank=True, on_delete=models.CASCADE, related_name="media_items")
    media = models.ForeignKey("mediafiles.MediaAsset", on_delete=models.CASCADE, related_name="+")
    position = models.PositiveSmallIntegerField(default=0)
    is_cover = models.BooleanField(default=False)

    class Meta:
        ordering = ["position", "id"]
        constraints = [
            # Одна обложка на галерею (галерея модели — variant=NULL, у каждого варианта — своя).
            models.UniqueConstraint(fields=["model", "variant"], condition=Q(is_cover=True),
                                    nulls_distinct=False, name="uniq_board_media_cover"),
        ]
        verbose_name = "фото доски"
        verbose_name_plural = "фото досок"
