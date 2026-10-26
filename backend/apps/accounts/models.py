"""Identity: аккаунт (единый UUID), профиль, специальности, серверные роли, согласия (разделы 5, 17)."""
import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.common.models import TimeStampedModel


class AccountManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra):
        if not email:
            raise ValueError("Email обязателен")
        email = self.normalize_email(email).lower()
        account = self.model(email=email, **extra)
        account.set_password(password)
        account.save(using=self._db)
        return account

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email, password, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("email_verified_at", timezone.now())
        return self._create_user(email, password, **extra)


class Account(AbstractBaseUser, PermissionsMixin):
    """Единственная пользовательская идентичность. id никогда не меняется (5.1)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField("email", unique=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField("доступ в Django Admin", default=False)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    date_joined = models.DateTimeField(default=timezone.now)
    deletion_requested_at = models.DateTimeField(null=True, blank=True)
    anonymized_at = models.DateTimeField(null=True, blank=True)
    totp_secret = models.CharField(max_length=64, blank=True)
    totp_enabled = models.BooleanField(default=False)
    is_demo = models.BooleanField("демо/посевной аккаунт", default=False)

    objects = AccountManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = "аккаунт"
        verbose_name_plural = "аккаунты"

    def __str__(self):
        return self.email

    @property
    def is_email_verified(self):
        return self.email_verified_at is not None


class StaffRole(models.Model):
    """Серверные роли (BR-04, ACC-10): не включаются пользовательскими переключателями."""

    class Role(models.TextChoices):
        MODERATOR = "moderator", "Модератор"
        ADMIN = "admin", "Администратор"
        ORGANIZER = "organizer", "Организатор клуба"

    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="staff_roles")
    role = models.CharField(max_length=20, choices=Role.choices)
    granted_by = models.ForeignKey(Account, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    granted_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["account", "role"], condition=Q(revoked_at__isnull=True), name="uniq_active_staff_role"
            )
        ]


class Specialty(models.Model):
    """Подключаемые направления: сёрфер, инструктор, шейпер, прокат (школа — организация, не специальность)."""

    SURFER = "surfer"
    INSTRUCTOR = "instructor"
    SHAPER = "shaper"
    RENTAL = "rental"

    code = models.CharField(primary_key=True, max_length=32)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order"]
        verbose_name = "специальность"
        verbose_name_plural = "специальности"

    def __str__(self):
        return self.name


class UserSpecialty(TimeStampedModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Подключено"
        DISABLED = "disabled", "Отключено"

    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="specialties")
    specialty = models.ForeignKey(Specialty, on_delete=models.PROTECT, related_name="+")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    is_primary = models.BooleanField(default=False)
    activated_at = models.DateTimeField(default=timezone.now)
    disabled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["account", "specialty"], name="uniq_account_specialty")]


class UserProfile(models.Model):
    """Публичные поля профиля + закрытые данные (ACC-14). Закрытые поля не попадают в публичные сериализаторы."""

    class Level(models.TextChoices):
        BEGINNER = "beginner", "Новичок"
        INTERMEDIATE = "intermediate", "Средний"
        ADVANCED = "advanced", "Продвинутый"
        PRO = "pro", "Профи"

    class ContactPolicy(models.TextChoices):
        EVERYONE = "everyone", "Все участники"
        NOBODY = "nobody", "Никто"

    account = models.OneToOneField(Account, primary_key=True, on_delete=models.CASCADE, related_name="profile")
    handle = models.SlugField(max_length=40, unique=True)
    first_name = models.CharField(max_length=80, blank=True)
    last_name = models.CharField(max_length=80, blank=True)
    avatar = models.ForeignKey("mediafiles.MediaAsset", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    region = models.ForeignKey("spots.Region", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    city = models.CharField(max_length=120, blank=True)
    bio = models.TextField("о себе", blank=True)
    fun_facts = ArrayField(models.CharField(max_length=200), default=list, blank=True)
    surfing_since = models.PositiveSmallIntegerField(null=True, blank=True)
    riding_level = models.CharField(max_length=20, choices=Level.choices, blank=True)
    preferred_board_types = ArrayField(models.CharField(max_length=40), default=list, blank=True)
    favorite_spots = models.ManyToManyField("spots.Spot", blank=True, related_name="+")
    interests = ArrayField(models.CharField(max_length=60), default=list, blank=True)
    languages = ArrayField(models.CharField(max_length=8), default=list, blank=True)
    # Закрытые данные
    phone = models.CharField(max_length=32, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    private_contacts = models.TextField(blank=True)
    # GG Surfer — отдельное согласие (BR-12, ACC-06, COM-01)
    gg_surfer_enabled = models.BooleanField(default=False)
    gg_contact_policy = models.CharField(max_length=16, choices=ContactPolicy.choices, default=ContactPolicy.EVERYONE)
    gg_show_region = models.BooleanField(default=True)
    gg_show_age = models.BooleanField(default=False)
    birthday_greetings_consent = models.BooleanField(default=False)
    show_birthday = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "профиль"
        verbose_name_plural = "профили"

    def __str__(self):
        return self.display_name

    @property
    def display_name(self):
        full = f"{self.first_name} {self.last_name}".strip()
        return full or self.handle


class HandleRedirect(models.Model):
    """Старые публичные handle продолжают вести на аккаунт (политика редиректов, 5.1)."""

    old_handle = models.SlugField(max_length=40, unique=True)
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="handle_redirects")
    created_at = models.DateTimeField(auto_now_add=True)


class ConsentRecord(models.Model):
    """Журнал согласий (TRUST-09, ACC-13): каждая выдача/отзыв — отдельная запись."""

    class Kind(models.TextChoices):
        TERMS = "terms", "Пользовательское соглашение"
        PRIVACY = "privacy", "Обработка персональных данных"
        GG_SURFER = "gg_surfer", "Участие в GG Surfer"
        BIRTHDAY = "birthday_greetings", "Поздравления с днём рождения"
        GEOLOCATION = "geolocation", "Геолокация"
        MARKETING = "marketing", "Рассылки"
        GUARDIAN = "guardian", "Согласие законного представителя"

    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="consents")
    kind = models.CharField(max_length=32, choices=Kind.choices)
    granted = models.BooleanField()
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)


class DataExportRequest(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Готовится"
        READY = "ready", "Готово"
        FAILED = "failed", "Ошибка"

    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="data_exports")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    file = models.ForeignKey("mediafiles.MediaAsset", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    completed_at = models.DateTimeField(null=True, blank=True)


class AccountDeletionRequest(TimeStampedModel):
    """AT-10: удаление с сохранением обязательных записей (заказы, журналы) и анонимизацией личных данных."""

    class Status(models.TextChoices):
        REQUESTED = "requested", "Запрошено"
        CANCELLED = "cancelled", "Отменено"
        COMPLETED = "completed", "Выполнено"

    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="deletion_requests")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.REQUESTED)
    reason = models.TextField(blank=True)
    scheduled_for = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)
