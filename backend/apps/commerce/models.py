"""Commerce: обращения и бронирования — серверные машины состояний (разделы 7.2, 7.3, 22, 27)."""
from django.conf import settings
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import RangeOperators
from django.db import models
from django.db.models import F, Q

from apps.common.models import TimeStampedModel
from apps.learning.models import TsTzRange

_SINGLE_PROVIDER = (
    Q(provider_account__isnull=False, provider_organization__isnull=True)
    | Q(provider_account__isnull=True, provider_organization__isnull=False)
)


class Inquiry(TimeStampedModel):
    class Kind(models.TextChoices):
        BOARD_PURCHASE = "board_purchase", "Покупка доски"
        CUSTOM_ORDER = "custom_order", "Индивидуальное изготовление"
        REPAIR = "repair", "Ремонт"
        LESSON = "lesson", "Занятие с инструктором"
        PROGRAM = "program", "Программа школы"
        RENTAL = "rental", "Аренда"
        MERCH = "merch", "Фирменные товары"
        GENERAL = "general", "Вопрос"

    class Status(models.TextChoices):
        NEW = "new", "Новое"
        IN_PROGRESS = "in_progress", "В работе"
        DECLINED = "declined", "Отказано"
        COMPLETED = "completed", "Завершено"
        CANCELLED = "cancelled", "Отменено клиентом"

    kind = models.CharField(max_length=20, choices=Kind.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.NEW, db_index=True)
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="inquiries_sent")
    provider_account = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="inquiries_received")
    provider_organization = models.ForeignKey("organizations.Organization", null=True, blank=True, on_delete=models.PROTECT, related_name="inquiries")
    # Строго типизированные ссылки на объект обращения (MSG-08, приложение Б)
    board_model = models.ForeignKey("boards.BoardModel", null=True, blank=True, on_delete=models.SET_NULL, related_name="inquiries")
    board_variant = models.ForeignKey("boards.BoardVariant", null=True, blank=True, on_delete=models.SET_NULL, related_name="inquiries")
    inventory_item = models.ForeignKey("inventory.InventoryItem", null=True, blank=True, on_delete=models.SET_NULL, related_name="inquiries")
    instructor_offer = models.ForeignKey("learning.InstructorOffer", null=True, blank=True, on_delete=models.SET_NULL, related_name="inquiries")
    school_program = models.ForeignKey("learning.SchoolProgram", null=True, blank=True, on_delete=models.SET_NULL, related_name="inquiries")
    lesson_session = models.ForeignKey("learning.LessonSession", null=True, blank=True, on_delete=models.SET_NULL, related_name="inquiries")
    subject = models.CharField(max_length=200)
    message = models.TextField(blank=True)
    details = models.JSONField(default=dict, blank=True)
    object_snapshot = models.JSONField(default=dict, blank=True)
    source_channel = models.CharField(max_length=32, blank=True)
    agreed_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, default="RUB")
    amount_confirmed = models.BooleanField("сумма подтверждена исполнителем", default=False)
    decline_reason = models.CharField(max_length=300, blank=True)
    cancel_reason = models.CharField(max_length=300, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(condition=_SINGLE_PROVIDER, name="inquiry_single_provider"),
            models.CheckConstraint(
                condition=Q(provider_account__isnull=True) | ~Q(provider_account=F("customer")),
                name="inquiry_not_to_self",
            ),
        ]
        verbose_name = "обращение"
        verbose_name_plural = "обращения"

    def __str__(self):
        return self.subject or f"{self.get_kind_display()} {self.pk}"


class InquiryStatusChange(models.Model):
    inquiry = models.ForeignKey(Inquiry, on_delete=models.CASCADE, related_name="history")
    from_status = models.CharField(max_length=16, blank=True)
    to_status = models.CharField(max_length=16)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    comment = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "смена статуса обращения"
        verbose_name_plural = "история статусов обращений"


class InquiryMilestone(TimeStampedModel):
    """Подтверждаемые этапы ремонта / индивидуального заказа (SHO-06)."""

    class Status(models.TextChoices):
        PLANNED = "planned", "Запланирован"
        DONE = "done", "Выполнен исполнителем"
        CONFIRMED = "confirmed", "Подтверждён клиентом"

    inquiry = models.ForeignKey(Inquiry, on_delete=models.CASCADE, related_name="milestones")
    title = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PLANNED)
    position = models.PositiveSmallIntegerField(default=0)
    completed_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["position", "created_at"]
        verbose_name = "этап обращения"
        verbose_name_plural = "этапы обращений"

    def __str__(self):
        return self.title


ACTIVE_BOOKING_STATUSES = ["confirmed", "in_progress"]


class Booking(TimeStampedModel):
    class Kind(models.TextChoices):
        LESSON = "lesson", "Занятие"
        RENTAL = "rental", "Аренда"

    class Status(models.TextChoices):
        REQUESTED = "requested", "Запрошено"
        CONFIRMED = "confirmed", "Подтверждено"
        IN_PROGRESS = "in_progress", "Идёт / выдано"
        COMPLETED = "completed", "Завершено"
        DECLINED = "declined", "Отклонено"
        CANCELLED = "cancelled", "Отменено"
        NO_SHOW = "no_show", "Неявка"

    class Side(models.TextChoices):
        CUSTOMER = "customer", "Клиент"
        PROVIDER = "provider", "Исполнитель"
        SYSTEM = "system", "Система"

    kind = models.CharField(max_length=16, choices=Kind.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.REQUESTED, db_index=True)
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="bookings")
    provider_account = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="provided_bookings")
    provider_organization = models.ForeignKey("organizations.Organization", null=True, blank=True, on_delete=models.PROTECT, related_name="bookings")
    lesson_session = models.ForeignKey("learning.LessonSession", null=True, blank=True, on_delete=models.PROTECT, related_name="bookings")
    inventory_item = models.ForeignKey("inventory.InventoryItem", null=True, blank=True, on_delete=models.PROTECT, related_name="bookings")
    inquiry = models.ForeignKey(Inquiry, null=True, blank=True, on_delete=models.SET_NULL, related_name="bookings")
    group_key = models.UUIDField("связанные брони", null=True, blank=True, db_index=True)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    seats = models.PositiveSmallIntegerField(default=1)
    participant_name = models.CharField(max_length=160, blank=True)
    participant_is_minor = models.BooleanField(default=False)
    guardian_consent_at = models.DateTimeField(null=True, blank=True)
    price_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, default="RUB")
    amount_confirmed = models.BooleanField(default=False)
    customer_note = models.TextField(blank=True)
    decline_reason = models.CharField(max_length=300, blank=True)
    cancel_reason = models.CharField(max_length=300, blank=True)
    cancelled_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    cancelled_side = models.CharField(max_length=16, choices=Side.choices, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    is_overdue = models.BooleanField(default=False)
    damage_reported = models.BooleanField(default=False)

    class Meta:
        ordering = ["-starts_at"]
        constraints = [
            models.CheckConstraint(condition=_SINGLE_PROVIDER, name="booking_single_provider"),
            models.CheckConstraint(
                condition=(Q(lesson_session__isnull=False, inventory_item__isnull=True)
                           | Q(lesson_session__isnull=True, inventory_item__isnull=False)),
                name="booking_single_target",
            ),
            models.CheckConstraint(condition=Q(ends_at__gt=F("starts_at")), name="booking_ends_after_start"),
            # AT-05 / F07 / ATX-16: у экземпляра нет двух подтверждённых пересекающихся броней.
            ExclusionConstraint(
                name="no_inventory_double_booking",
                expressions=[
                    ("inventory_item", RangeOperators.EQUAL),
                    (TsTzRange("starts_at", "ends_at"), RangeOperators.OVERLAPS),
                ],
                condition=Q(status__in=ACTIVE_BOOKING_STATUSES, inventory_item__isnull=False),
            ),
        ]
        verbose_name = "бронирование"
        verbose_name_plural = "бронирования"

    def __str__(self):
        return f"{self.get_kind_display()} {self.starts_at:%Y-%m-%d %H:%M} ({self.get_status_display()})"


class BookingStatusChange(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="history")
    from_status = models.CharField(max_length=16, blank=True)
    to_status = models.CharField(max_length=16)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    comment = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "смена статуса брони"
        verbose_name_plural = "история статусов броней"
