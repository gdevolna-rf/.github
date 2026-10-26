"""Analytics: события пишутся один раз с event_id, субъектом, объектом и контекстом (раздел 10, MET-08)."""
import uuid

from django.conf import settings
from django.db import models

RULE_VERSION = 1  # версия правил дедупликации (10.1)


class AnalyticsEvent(models.Model):
    class Name(models.TextChoices):
        PROFILE_VIEWED = "profile_viewed", "Просмотр профиля"
        BOARD_VIEWED = "board_viewed", "Просмотр модели/варианта"
        SPOT_VIEWED = "spot_viewed", "Просмотр спота"
        ORGANIZATION_VIEWED = "organization_viewed", "Просмотр школы/мастерской"
        ITEM_VIEWED = "item_viewed", "Просмотр объявления"
        INQUIRY_CREATED = "inquiry_created", "Создано обращение"
        BOOKING_CONFIRMED = "booking_confirmed", "Бронь подтверждена"
        BOOKING_CANCELLED = "booking_cancelled", "Бронь отменена"
        SESSION_COMPLETED = "session_completed", "Занятие проведено"
        REVIEW_PUBLISHED = "review_published", "Отзыв опубликован"
        SPOT_PROPOSAL_REVIEWED = "spot_proposal_reviewed", "Правка спота рассмотрена"
        DEAL_COMPLETED = "deal_completed", "Сделка завершена"

    event_id = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=40, choices=Name.choices, db_index=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    anonymous_id = models.CharField(max_length=64, blank=True)
    subject_type = models.CharField(max_length=40)
    subject_id = models.CharField(max_length=64)
    owner_account = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    owner_organization = models.ForeignKey("organizations.Organization", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    context = models.JSONField(default=dict, blank=True)
    dedup_key = models.CharField(max_length=200, unique=True, null=True, blank=True)
    rule_version = models.PositiveSmallIntegerField(default=RULE_VERSION)
    occurred_at = models.DateTimeField(db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["name", "owner_account", "occurred_at"]),
            models.Index(fields=["name", "owner_organization", "occurred_at"]),
            models.Index(fields=["subject_type", "subject_id"]),
        ]
