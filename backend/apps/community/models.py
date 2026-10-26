"""GG Surfer: дневник катания и поздравления по согласию (раздел 23, DATA-05)."""
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.common.models import TimeStampedModel


class SurfSession(TimeStampedModel):
    """Запись дневника / день катания (COM-04, COM-06). Видимость задаётся для каждой записи."""

    class Visibility(models.TextChoices):
        PRIVATE = "private", "Только я"
        COMMUNITY = "community", "Участники GG Surfer"
        PUBLIC = "public", "Все"

    account = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="surf_sessions")
    spot = models.ForeignKey("spots.Spot", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    spot_name = models.CharField(max_length=160, blank=True)
    date = models.DateField(db_index=True)
    duration_min = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(24 * 60)]
    )
    board_note = models.CharField(max_length=160, blank=True)
    conditions = models.CharField(max_length=200, blank=True)
    wave_height_m = models.DecimalField(
        max_digits=4, decimal_places=1, null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(30)]
    )
    mood_rating = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    notes = models.TextField(blank=True)
    visibility = models.CharField(max_length=16, choices=Visibility.choices, default=Visibility.PRIVATE)
    photos = models.ManyToManyField("mediafiles.MediaAsset", blank=True, related_name="+")

    class Meta:
        ordering = ["-date", "-created_at"]
        indexes = [models.Index(fields=["account", "date"]), models.Index(fields=["account", "visibility"])]
        verbose_name = "запись дневника"
        verbose_name_plural = "дневник катания"

    def __str__(self):
        return f"{self.date} · {self.spot.name if self.spot_id else self.spot_name}"


class BirthdayGreeting(models.Model):
    """Факт поздравления; не раскрывает дату рождения (COM-05, ATX-34)."""

    account = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    year = models.PositiveSmallIntegerField()
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["account", "year"], name="uniq_birthday_greeting")]
        verbose_name = "поздравление с днём рождения"
        verbose_name_plural = "поздравления с днём рождения"

    def __str__(self):
        return f"{self.account_id}:{self.year}"
