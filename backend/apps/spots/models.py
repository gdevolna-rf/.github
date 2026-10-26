"""Locations: регионы, споты, фото, источники, прогнозы, предложения правок (разделы 8.1, 18)."""
from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models

from apps.common.models import TimeStampedModel

COMPASS_POINTS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
COMPASS_CHOICES = [(p, p) for p in COMPASS_POINTS]


class Region(models.Model):
    slug = models.SlugField(max_length=60, unique=True)
    name = models.CharField(max_length=120)
    timezone = models.CharField(max_length=64, default="Europe/Moscow")
    center_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    center_lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    map_zoom = models.PositiveSmallIntegerField(default=7)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name = "регион"
        verbose_name_plural = "регионы"

    def __str__(self):
        return self.name


class Spot(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Черновик"
        PUBLISHED = "published", "Опубликован"
        HIDDEN = "hidden", "Скрыт модератором"
        CLOSED = "closed", "Закрыт"

    class Difficulty(models.TextChoices):
        BEGINNER = "beginner", "Для новичков"
        INTERMEDIATE = "intermediate", "Средний"
        ADVANCED = "advanced", "Продвинутый"
        EXPERT = "expert", "Эксперт"

    class Bottom(models.TextChoices):
        SAND = "sand", "Песок"
        ROCK = "rock", "Камни"
        REEF = "reef", "Риф"
        PEBBLE = "pebble", "Галька"
        MIXED = "mixed", "Смешанное"

    class Break(models.TextChoices):
        BEACH = "beach", "Бич-брейк"
        REEF = "reef", "Риф-брейк"
        POINT = "point", "Пойнт-брейк"
        RIVER_MOUTH = "river_mouth", "Устье реки"
        JETTY = "jetty", "У волнореза"

    class Precision(models.TextChoices):
        EXACT = "exact", "Точная точка"
        APPROXIMATE = "approximate", "Округлённо"
        REGION_ONLY = "region_only", "Только район"

    slug = models.SlugField(max_length=80, unique=True)
    name = models.CharField(max_length=160)
    region = models.ForeignKey(Region, on_delete=models.PROTECT, related_name="spots")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PUBLISHED, db_index=True)
    lat = models.DecimalField(max_digits=9, decimal_places=6)
    lng = models.DecimalField(max_digits=9, decimal_places=6)
    location_precision = models.CharField(max_length=16, choices=Precision.choices, default=Precision.EXACT)
    is_sensitive = models.BooleanField("чувствительная геоточка", default=False)
    short_description = models.CharField(max_length=300, blank=True)
    description = models.TextField(blank=True)
    difficulty = models.CharField(max_length=16, choices=Difficulty.choices, default=Difficulty.INTERMEDIATE)
    bottom_type = models.CharField(max_length=16, choices=Bottom.choices, default=Bottom.SAND)
    break_type = models.CharField(max_length=16, choices=Break.choices, default=Break.BEACH)
    wave_character = models.CharField("характер волн", max_length=200, blank=True)
    wave_power = models.CharField("мощность волн", max_length=120, blank=True)
    season = models.CharField(max_length=120, blank=True)
    best_months = ArrayField(models.PositiveSmallIntegerField(), default=list, blank=True)
    best_wind_directions = ArrayField(models.CharField(max_length=3, choices=COMPASS_CHOICES), default=list, blank=True)
    best_swell_directions = ArrayField(models.CharField(max_length=3, choices=COMPASS_CHOICES), default=list, blank=True)
    best_tide = models.CharField(max_length=120, blank=True)
    typical_conditions = models.TextField("типичные условия", blank=True)
    hazards = ArrayField(models.CharField(max_length=32), default=list, blank=True)
    hazard_notes = models.TextField(blank=True)
    entry_exit = models.TextField("вход/выход", blank=True)
    access = models.TextField("подъезд", blank=True)
    infrastructure = models.JSONField(default=list, blank=True)  # [{"type": "parking", "name": "", "distance_m": 100}]
    water_temp_note = models.CharField(max_length=200, blank=True)
    seasonal_warning = models.CharField(max_length=300, blank=True)
    closed_until = models.DateField(null=True, blank=True)
    cover = models.ForeignKey("mediafiles.MediaAsset", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    webcam_url = models.URLField(blank=True)
    webcam_is_premium = models.BooleanField(default=False)
    data_source = models.CharField("происхождение данных", max_length=300, blank=True)
    last_confirmed_at = models.DateTimeField(null=True, blank=True)
    rating_avg = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    rating_count = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    is_demo = models.BooleanField(default=False)

    class Meta:
        ordering = ["region__sort_order", "name"]
        verbose_name = "спот"
        verbose_name_plural = "споты"

    def __str__(self):
        return self.name


class SpotPhoto(models.Model):
    spot = models.ForeignKey(Spot, on_delete=models.CASCADE, related_name="photos")
    media = models.ForeignKey("mediafiles.MediaAsset", on_delete=models.CASCADE, related_name="+")
    position = models.PositiveSmallIntegerField(default=0)
    caption = models.CharField(max_length=200, blank=True)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position", "created_at"]


class SpotSourceRecord(models.Model):
    """Журнал источников сведений о споте (8.1, SPT-11)."""

    spot = models.ForeignKey(Spot, on_delete=models.CASCADE, related_name="sources")
    source = models.CharField(max_length=200)
    url = models.URLField(blank=True)
    note = models.TextField(blank=True)
    confirmed_at = models.DateTimeField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["-confirmed_at"]


class SpotForecast(models.Model):
    """Прогноз от внешнего провайдера (GEO-04). Отдельно от «типичных условий» (SPT-04)."""

    spot = models.ForeignKey(Spot, on_delete=models.CASCADE, related_name="forecasts")
    provider = models.CharField(max_length=60)
    issued_at = models.DateTimeField()
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField()
    wave_height_m = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    wave_period_s = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    wave_direction = models.CharField(max_length=3, blank=True)
    wind_speed_ms = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    wind_direction = models.CharField(max_length=3, blank=True)
    water_temp_c = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    tide_note = models.CharField(max_length=120, blank=True)
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["valid_from"]
        indexes = [models.Index(fields=["spot", "valid_from"])]


class SpotChangeRequest(TimeStampedModel):
    """Предложение правки спота (7.4, SPT-07/08, TRUST-04). Публичная карточка меняется только после approve."""

    class Status(models.TextChoices):
        SUBMITTED = "submitted", "На модерации"
        NEEDS_INFO = "needs_info", "Нужны уточнения"
        APPROVED = "approved", "Принято"
        REJECTED = "rejected", "Отклонено"
        WITHDRAWN = "withdrawn", "Отозвано автором"

    spot = models.ForeignKey(Spot, on_delete=models.CASCADE, related_name="change_requests")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="spot_change_requests")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.SUBMITTED, db_index=True)
    changes = models.JSONField()  # {"field": {"old": ..., "new": ...}}
    comment = models.TextField(blank=True)
    source = models.CharField(max_length=300, blank=True)
    evidence = models.ManyToManyField("mediafiles.MediaAsset", blank=True, related_name="+")
    moderator = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    moderator_comment = models.TextField(blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    reverted_at = models.DateTimeField(null=True, blank=True)
    reverted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")


# Поля спота, которые пользователь может предложить изменить через форму (SPT-08).
EDITABLE_SPOT_FIELDS = [
    "short_description",
    "description",
    "difficulty",
    "bottom_type",
    "break_type",
    "wave_character",
    "wave_power",
    "season",
    "best_months",
    "best_wind_directions",
    "best_swell_directions",
    "best_tide",
    "typical_conditions",
    "hazards",
    "hazard_notes",
    "entry_exit",
    "access",
    "infrastructure",
    "water_temp_note",
    "seasonal_warning",
]
