"""Learning: инструкторы, сертификаты, предложения, программы школ, занятия (разделы 8.2, 8.3, 19, 20)."""
from django.conf import settings
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import ArrayField, DateTimeRangeField, RangeOperators
from django.db import models
from django.db.models import F, Func, Q

from apps.common.models import TimeStampedModel


class TsTzRange(Func):
    function = "TSTZRANGE"
    output_field = DateTimeRangeField()


class InstructorProfile(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Черновик"
        PUBLISHED = "published", "Опубликован"
        HIDDEN = "hidden", "Скрыт"

    account = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="instructor_profile")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT, db_index=True)
    headline = models.CharField(max_length=200, blank=True)
    about = models.TextField(blank=True)
    fun_facts = ArrayField(models.CharField(max_length=200), default=list, blank=True)
    regions = models.ManyToManyField("spots.Region", blank=True, related_name="+")
    spots = models.ManyToManyField("spots.Spot", blank=True, related_name="instructors")
    surfing_since = models.PositiveSmallIntegerField(null=True, blank=True)
    teaching_since = models.PositiveSmallIntegerField(null=True, blank=True)
    riding_level = models.CharField(max_length=20, blank=True)
    formats = ArrayField(models.CharField(max_length=32), default=list, blank=True)
    student_levels = ArrayField(models.CharField(max_length=20), default=list, blank=True)
    board_types = ArrayField(models.CharField(max_length=40), default=list, blank=True)
    languages = ArrayField(models.CharField(max_length=8), default=list, blank=True)
    price_from = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, default="RUB")
    contact_note = models.CharField(max_length=300, blank=True)
    allow_overlap = models.BooleanField("разрешать совмещение занятий", default=False)
    rating_avg = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    rating_count = models.PositiveIntegerField(default=0)
    published_at = models.DateTimeField(null=True, blank=True)
    is_demo = models.BooleanField(default=False)

    class Meta:
        verbose_name = "профиль инструктора"
        verbose_name_plural = "профили инструкторов"

    def __str__(self):
        return f"Инструктор {self.account_id}"

    @property
    def certificate_status(self):
        """none / uploaded / verified (INS-03, BR-07, TRUST-03).

        «verified» — только действующий (не истёкший) сертификат, проверенный модератором. Истёкший проверенный
        документ и документ на проверке дают «uploaded». Если queryset аннотирован ``cert_status`` — берётся он.
        """
        annotated = getattr(self, "cert_status", None)
        if annotated:
            return annotated
        return compute_certificate_status(self.certificates.all())


def compute_certificate_status(certificates, today=None):
    from django.utils import timezone

    today = today or timezone.localdate()
    status = "none"
    for cert in certificates:
        if cert.status == InstructorCertificate.Status.VERIFIED:
            if cert.valid_until is None or cert.valid_until >= today:
                return "verified"
            status = "uploaded"
        elif cert.status == InstructorCertificate.Status.UPLOADED:
            status = "uploaded"
    return status


class InstructorMedia(models.Model):
    """Фото и видео инструктора (INS-12)."""

    profile = models.ForeignKey(InstructorProfile, on_delete=models.CASCADE, related_name="media_items")
    media = models.ForeignKey("mediafiles.MediaAsset", on_delete=models.CASCADE, related_name="+")
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]


class InstructorCertificate(TimeStampedModel):
    class Status(models.TextChoices):
        UPLOADED = "uploaded", "Загружен, на проверке"
        VERIFIED = "verified", "Проверен"
        REJECTED = "rejected", "Отклонён"
        REVOKED = "revoked", "Отозван"

    instructor = models.ForeignKey(InstructorProfile, on_delete=models.CASCADE, related_name="certificates")
    title = models.CharField(max_length=200)
    issuer = models.CharField(max_length=200, blank=True)
    issued_on = models.DateField(null=True, blank=True)
    valid_until = models.DateField(null=True, blank=True)
    document = models.ForeignKey("mediafiles.MediaAsset", on_delete=models.PROTECT, related_name="+")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.UPLOADED, db_index=True)
    allow_public_scan = models.BooleanField(default=False)
    moderator = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    moderator_comment = models.TextField(blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.title


class InstructorOffer(TimeStampedModel):
    """Объект предложения независимого инструктора (INS-08)."""

    class Format(models.TextChoices):
        INDIVIDUAL = "individual", "Индивидуально"
        GROUP = "group", "Группа"

    instructor = models.ForeignKey(InstructorProfile, on_delete=models.CASCADE, related_name="offers")
    title = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    format = models.CharField(max_length=16, choices=Format.choices, default=Format.INDIVIDUAL)
    level = models.CharField(max_length=20, blank=True)
    duration_min = models.PositiveSmallIntegerField(default=90)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="RUB")
    capacity = models.PositiveSmallIntegerField(default=1)
    spot = models.ForeignKey("spots.Spot", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    equipment_included = models.BooleanField(default=False)
    equipment_note = models.CharField(max_length=300, blank=True)
    rules = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.title


class SchoolProgram(TimeStampedModel):
    class AgeCategory(models.TextChoices):
        KIDS = "kids", "Дети"
        TEENS = "teens", "Подростки"
        ADULTS = "adults", "Взрослые"
        ALL = "all", "Все возрасты"

    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="programs")
    title = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    level = models.CharField(max_length=20, blank=True)
    age_category = models.CharField(max_length=16, choices=AgeCategory.choices, default=AgeCategory.ALL)
    format = models.CharField(max_length=16, choices=InstructorOffer.Format.choices, default=InstructorOffer.Format.GROUP)
    duration_min = models.PositiveSmallIntegerField(default=120)
    sessions_count = models.PositiveSmallIntegerField("занятий в курсе", default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="RUB")
    max_group_size = models.PositiveSmallIntegerField(default=8)
    equipment_included = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.title


class LessonSession(TimeStampedModel):
    """Конкретное занятие. Брони занимают места; у инструктора нет пересечений (6.2, INS-07, AT-06, F11)."""

    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Запланировано"
        IN_PROGRESS = "in_progress", "Идёт"
        COMPLETED = "completed", "Проведено"
        CANCELLED = "cancelled", "Отменено"

    organization = models.ForeignKey("organizations.Organization", null=True, blank=True, on_delete=models.PROTECT, related_name="sessions")
    program = models.ForeignKey(SchoolProgram, null=True, blank=True, on_delete=models.PROTECT, related_name="sessions")
    offer = models.ForeignKey(InstructorOffer, null=True, blank=True, on_delete=models.PROTECT, related_name="sessions")
    instructor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="lesson_sessions")
    spot = models.ForeignKey("spots.Spot", null=True, blank=True, on_delete=models.SET_NULL, related_name="sessions")
    title = models.CharField(max_length=200)
    starts_at = models.DateTimeField(db_index=True)
    ends_at = models.DateTimeField()
    capacity = models.PositiveSmallIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, default="RUB")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.SCHEDULED, db_index=True)
    allow_overlap = models.BooleanField(default=False)
    reschedule_reason = models.CharField(max_length=300, blank=True)
    cancel_reason = models.CharField(max_length=300, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    rescheduled_from = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["starts_at"]
        constraints = [
            models.CheckConstraint(condition=Q(ends_at__gt=F("starts_at")), name="session_ends_after_start"),
            models.CheckConstraint(
                condition=Q(organization__isnull=False) | Q(offer__isnull=False), name="session_has_owner"
            ),
            ExclusionConstraint(
                name="no_instructor_overlap",
                expressions=[
                    ("instructor", RangeOperators.EQUAL),
                    (TsTzRange("starts_at", "ends_at"), RangeOperators.OVERLAPS),
                ],
                condition=Q(status__in=["scheduled", "in_progress"], instructor__isnull=False, allow_overlap=False),
            ),
        ]

    def __str__(self):
        return f"{self.title} · {self.starts_at:%Y-%m-%d %H:%M}"


class WaitlistEntry(TimeStampedModel):
    """Лист ожидания на занятие (SCH-08)."""

    class Status(models.TextChoices):
        WAITING = "waiting", "В очереди"
        OFFERED = "offered", "Предложено место"
        CONVERTED = "converted", "Записан"
        CANCELLED = "cancelled", "Отменено"

    session = models.ForeignKey(LessonSession, on_delete=models.CASCADE, related_name="waitlist")
    account = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.WAITING)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["session", "account"], condition=Q(status="waiting"), name="uniq_waiting_entry"
            )
        ]


class StudentNote(TimeStampedModel):
    """Комментарий преподавателя о прогрессе ученика (SCH-10). Видят автор, ученик и менеджмент школы."""

    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="student_notes")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    organization = models.ForeignKey("organizations.Organization", null=True, blank=True, on_delete=models.CASCADE, related_name="+")
    session = models.ForeignKey(LessonSession, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    level = models.CharField(max_length=20, blank=True)
    comment = models.TextField()
    visible_to_student = models.BooleanField(default=True)
