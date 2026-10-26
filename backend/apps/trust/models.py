"""Trust: отзывы, очередь модерации, жалобы, ограничения, журнал аудита (7.5, 26)."""
import uuid

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from apps.common.models import TimeStampedModel


class Review(TimeStampedModel):
    """Отзыв: один текущий на автора и объект; правка опубликованного проходит модерацию (14, 7.5)."""

    class Target(models.TextChoices):
        SPOT = "spot", "Спот"
        INSTRUCTOR = "instructor", "Инструктор"
        ORGANIZATION = "organization", "Школа / мастерская / прокат"

    class Status(models.TextChoices):
        PENDING = "pending", "На модерации"
        PUBLISHED = "published", "Опубликован"
        REJECTED = "rejected", "Отклонён"
        HIDDEN = "hidden", "Скрыт модератором"

    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews")
    target_type = models.CharField(max_length=16, choices=Target.choices)
    spot = models.ForeignKey("spots.Spot", null=True, blank=True, on_delete=models.CASCADE, related_name="reviews")
    instructor = models.ForeignKey("learning.InstructorProfile", null=True, blank=True, on_delete=models.CASCADE, related_name="reviews")
    organization = models.ForeignKey("organizations.Organization", null=True, blank=True, on_delete=models.CASCADE, related_name="reviews")
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    text = models.TextField(blank=True)
    pending_rating = models.PositiveSmallIntegerField(null=True, blank=True)
    pending_text = models.TextField(blank=True)
    has_pending_revision = models.BooleanField(default=False)
    booking = models.ForeignKey("commerce.Booking", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    inquiry = models.ForeignKey("commerce.Inquiry", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    context_label = models.CharField(max_length=200, blank=True)
    photos = models.ManyToManyField("mediafiles.MediaAsset", blank=True, related_name="+")
    # Фото pending-ревизии опубликованного отзыва: применяются вместе с pending_rating/pending_text после approve.
    pending_photos = models.ManyToManyField("mediafiles.MediaAsset", blank=True, related_name="+")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    moderator = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    moderation_note = models.CharField(max_length=300, blank=True)
    moderated_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    is_demo = models.BooleanField(default=False)

    class Meta:
        ordering = ["-published_at", "-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(target_type="spot", spot__isnull=False, instructor__isnull=True, organization__isnull=True)
                    | Q(target_type="instructor", spot__isnull=True, instructor__isnull=False, organization__isnull=True)
                    | Q(target_type="organization", spot__isnull=True, instructor__isnull=True, organization__isnull=False)
                ),
                name="review_single_target",
            ),
            models.UniqueConstraint(fields=["author", "spot"], condition=Q(spot__isnull=False), name="uniq_review_spot"),
            models.UniqueConstraint(fields=["author", "instructor"], condition=Q(instructor__isnull=False), name="uniq_review_instructor"),
            models.UniqueConstraint(fields=["author", "organization"], condition=Q(organization__isnull=False), name="uniq_review_org"),
        ]


class Complaint(TimeStampedModel):
    """Жалоба на материал/человека (TRUST-07, MSG-13). target_id проверяется доменным сервисом (прил. Б)."""

    class Target(models.TextChoices):
        SPOT = "spot", "Спот"
        ACCOUNT = "account", "Пользователь"
        REVIEW = "review", "Отзыв"
        MESSAGE = "message", "Сообщение"
        BOARD_MODEL = "board_model", "Модель доски"
        INVENTORY_ITEM = "inventory_item", "Объявление аренды"
        ORGANIZATION = "organization", "Организация"
        MEDIA = "media", "Медиафайл"
        CLUB_EVENT = "club_event", "Событие клуба"

    class Reason(models.TextChoices):
        SPAM = "spam", "Спам"
        FRAUD = "fraud", "Мошенничество"
        OFFENSIVE = "offensive", "Оскорбления"
        WRONG_INFO = "wrong_info", "Недостоверные сведения"
        SAFETY = "safety", "Угроза безопасности"
        COPYRIGHT = "copyright", "Нарушение прав"
        OTHER = "other", "Другое"

    class Status(models.TextChoices):
        OPEN = "open", "Открыта"
        RESOLVED = "resolved", "Решена"
        DISMISSED = "dismissed", "Отклонена"

    class Action(models.TextChoices):
        NONE = "none", "Без действий"
        WARNING = "warning", "Предупреждение"
        HIDDEN = "hidden", "Материал скрыт"
        SUSPENDED = "suspended", "Профиль ограничен"

    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="complaints")
    target_type = models.CharField(max_length=20, choices=Target.choices)
    target_id = models.CharField(max_length=64)
    reason = models.CharField(max_length=16, choices=Reason.choices)
    text = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN, db_index=True)
    action_taken = models.CharField(max_length=16, choices=Action.choices, default=Action.NONE)
    target_owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    appeal_text = models.TextField(blank=True)
    appealed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            # Повторная открытая жалоба того же автора на ту же цель не создаётся (TRUST-08: защита от повторов).
            models.UniqueConstraint(fields=["reporter", "target_type", "target_id"], condition=Q(status="open"),
                                    name="uniq_open_complaint"),
        ]


class ModerationCase(TimeStampedModel):
    """Единая очередь модератора (TRUST-04): правки спотов, отзывы, сертификаты, жалобы, публикации организаций."""

    class Kind(models.TextChoices):
        SPOT_CHANGE = "spot_change", "Правка спота"
        REVIEW = "review", "Отзыв"
        CERTIFICATE = "certificate", "Сертификат инструктора"
        COMPLAINT = "complaint", "Жалоба"
        ORGANIZATION = "organization", "Публикация организации"
        APPEAL = "appeal", "Апелляция"

    class Status(models.TextChoices):
        OPEN = "open", "Открыт"
        IN_REVIEW = "in_review", "В работе"
        RESOLVED = "resolved", "Решён"

    kind = models.CharField(max_length=16, choices=Kind.choices, db_index=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN, db_index=True)
    summary = models.CharField(max_length=300)
    spot_change_request = models.ForeignKey("spots.SpotChangeRequest", null=True, blank=True, on_delete=models.CASCADE, related_name="cases")
    review = models.ForeignKey(Review, null=True, blank=True, on_delete=models.CASCADE, related_name="cases")
    certificate = models.ForeignKey("learning.InstructorCertificate", null=True, blank=True, on_delete=models.CASCADE, related_name="cases")
    complaint = models.ForeignKey(Complaint, null=True, blank=True, on_delete=models.CASCADE, related_name="cases")
    organization = models.ForeignKey("organizations.Organization", null=True, blank=True, on_delete=models.CASCADE, related_name="moderation_cases")
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    resolution = models.CharField(max_length=32, blank=True)
    resolution_note = models.TextField(blank=True)
    resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    resolved_at = models.DateTimeField(null=True, blank=True)
    due_at = models.DateTimeField("срок по SLA", null=True, blank=True)

    class Meta:
        ordering = ["status", "created_at"]


class AccountRestriction(TimeStampedModel):
    class Kind(models.TextChoices):
        MESSAGING = "messaging", "Запрет сообщений"
        PUBLISHING = "publishing", "Запрет публикаций"
        SUSPENDED = "suspended", "Профиль ограничен"

    account = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="restrictions")
    kind = models.CharField(max_length=16, choices=Kind.choices)
    reason = models.CharField(max_length=300)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    expires_at = models.DateTimeField(null=True, blank=True)
    lifted_at = models.DateTimeField(null=True, blank=True)


class AuditEvent(models.Model):
    """Неизменяемый журнал действий (5.3, 7.4, DATA-09)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    action = models.CharField(max_length=80, db_index=True)
    object_type = models.CharField(max_length=40)
    object_id = models.CharField(max_length=64, db_index=True)
    organization = models.ForeignKey("organizations.Organization", null=True, blank=True, on_delete=models.SET_NULL, related_name="audit_events")
    before = models.JSONField(null=True, blank=True, encoder=DjangoJSONEncoder)
    after = models.JSONField(null=True, blank=True, encoder=DjangoJSONEncoder)
    metadata = models.JSONField(default=dict, blank=True, encoder=DjangoJSONEncoder)
    ip = models.GenericIPAddressField(null=True, blank=True)
    request_id = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
