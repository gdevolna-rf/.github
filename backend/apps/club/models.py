"""Клуб: анонсы, события, регистрации (раздел 24.1, DATA-06)."""
from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.common.models import TimeStampedModel


class ClubEvent(TimeStampedModel):
    class Kind(models.TextChoices):
        RIDE = "ride", "Совместное катание"
        MEETUP = "meetup", "Встреча"
        CONTEST = "contest", "Соревнование"
        WORKSHOP = "workshop", "Мастер-класс"
        TRIP = "trip", "Сёрф-трип"

    class Status(models.TextChoices):
        DRAFT = "draft", "Черновик"
        PUBLISHED = "published", "Опубликовано"
        CANCELLED = "cancelled", "Отменено"
        COMPLETED = "completed", "Прошло"

    slug = models.SlugField(max_length=80, unique=True)
    title = models.CharField(max_length=200)
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.RIDE)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT, db_index=True)
    description = models.TextField(blank=True)
    spot = models.ForeignKey("spots.Spot", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    region = models.ForeignKey("spots.Region", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    location_note = models.CharField(max_length=300, blank=True)
    starts_at = models.DateTimeField(db_index=True)
    ends_at = models.DateTimeField()
    capacity = models.PositiveSmallIntegerField(null=True, blank=True)
    registration_open = models.BooleanField(default=True)
    organizer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="organized_events")
    organizer_organization = models.ForeignKey("organizations.Organization", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    cover = models.ForeignKey("mediafiles.MediaAsset", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    reminder_sent_at = models.DateTimeField(null=True, blank=True)
    is_demo = models.BooleanField(default=False)

    class Meta:
        ordering = ["starts_at"]
        constraints = [
            models.CheckConstraint(condition=Q(ends_at__gt=models.F("starts_at")), name="club_event_ends_after_start"),
        ]
        verbose_name = "событие клуба"
        verbose_name_plural = "события клуба"

    def __str__(self):
        return self.title


class EventRegistration(TimeStampedModel):
    class Status(models.TextChoices):
        REGISTERED = "registered", "Зарегистрирован"
        WAITLIST = "waitlist", "Лист ожидания"
        CANCELLED = "cancelled", "Отменено"

    event = models.ForeignKey(ClubEvent, on_delete=models.CASCADE, related_name="registrations")
    account = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="event_registrations")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.REGISTERED, db_index=True)
    promoted_at = models.DateTimeField("переведён из листа ожидания", null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    reminder_sent_at = models.DateTimeField("напоминание отправлено", null=True, blank=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["event", "account"], condition=~Q(status="cancelled"), name="uniq_active_registration"
            )
        ]
        verbose_name = "регистрация на событие"
        verbose_name_plural = "регистрации на события"

    def __str__(self):
        return f"{self.event_id}:{self.account_id}:{self.status}"


class ClubAnnouncement(TimeStampedModel):
    title = models.CharField(max_length=200)
    body = models.TextField()
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    is_pinned = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ["-is_pinned", "-published_at"]
        verbose_name = "анонс клуба"
        verbose_name_plural = "анонсы клуба"

    def __str__(self):
        return self.title
