"""Организации (школа, мастерская, прокат), членства и приглашения (разделы 5.3, 20, ACC-11, SCH-09)."""
from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models import Q

from apps.common.models import TimeStampedModel


class Organization(TimeStampedModel):
    class Kind(models.TextChoices):
        SCHOOL = "school", "Сёрф-школа"
        WORKSHOP = "workshop", "Мастерская шейпера"
        RENTAL = "rental", "Прокат"

    class Status(models.TextChoices):
        DRAFT = "draft", "Черновик"
        PENDING_REVIEW = "pending_review", "На проверке"
        PUBLISHED = "published", "Опубликована"
        SUSPENDED = "suspended", "Ограничена модератором"
        ARCHIVED = "archived", "В архиве"

    class Verification(models.TextChoices):
        NONE = "none", "Не подтверждена"
        PENDING = "pending", "На проверке"
        VERIFIED = "verified", "Подтверждена"
        REJECTED = "rejected", "Отклонена"

    kind = models.CharField(max_length=16, choices=Kind.choices)
    name = models.CharField(max_length=160)
    slug = models.SlugField(max_length=80, unique=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="owned_organizations")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    verification_status = models.CharField(max_length=16, choices=Verification.choices, default=Verification.NONE)
    short_description = models.CharField(max_length=300, blank=True)
    description = models.TextField(blank=True)
    region = models.ForeignKey("spots.Region", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    city = models.CharField(max_length=120, blank=True)
    address = models.CharField(max_length=300, blank=True)
    spots = models.ManyToManyField("spots.Spot", blank=True, related_name="organizations")
    logo = models.ForeignKey("mediafiles.MediaAsset", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    cover = models.ForeignKey("mediafiles.MediaAsset", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    gallery = models.ManyToManyField("mediafiles.MediaAsset", blank=True, related_name="+")
    phone = models.CharField(max_length=32, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    social_links = models.JSONField(default=dict, blank=True)
    formats = ArrayField(models.CharField(max_length=32), default=list, blank=True)
    languages = ArrayField(models.CharField(max_length=8), default=list, blank=True)
    price_from = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, default="RUB")
    rating_avg = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    rating_count = models.PositiveIntegerField(default=0)
    published_at = models.DateTimeField(null=True, blank=True)
    moderation_note = models.TextField(blank=True)
    is_demo = models.BooleanField(default=False)

    class Meta:
        indexes = [models.Index(fields=["kind", "status"])]
        verbose_name = "организация"
        verbose_name_plural = "организации"

    def __str__(self):
        return self.name


class Membership(TimeStampedModel):
    """Связь аккаунта с организацией. Роль активна только после принятия приглашения (5.3)."""

    class Role(models.TextChoices):
        OWNER = "owner", "Владелец"
        MANAGER = "manager", "Менеджер"
        INSTRUCTOR = "instructor", "Инструктор"
        STAFF = "staff", "Сотрудник"

    class Status(models.TextChoices):
        ACTIVE = "active", "Активно"
        REVOKED = "revoked", "Доступ отозван"
        LEFT = "left", "Вышел"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="memberships")
    account = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=16, choices=Role.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    title = models.CharField("должность", max_length=120, blank=True)
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    joined_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "account"], condition=Q(status="active"), name="uniq_active_membership"
            )
        ]


class OrganizationInvite(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Ожидает ответа"
        ACCEPTED = "accepted", "Принято"
        DECLINED = "declined", "Отклонено"
        REVOKED = "revoked", "Отозвано"
        EXPIRED = "expired", "Истекло"

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="invites")
    email = models.EmailField()
    account = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name="org_invites")
    role = models.CharField(max_length=16, choices=Membership.Role.choices)
    token = models.CharField(max_length=64, unique=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    message = models.TextField(blank=True)
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    expires_at = models.DateTimeField()
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "email"], condition=Q(status="pending"), name="uniq_pending_invite"
            )
        ]
