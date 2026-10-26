"""Communications: диалоги, read-курсоры участников, сообщения, вложения, уведомления (8.6, 25)."""
import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.common.models import TimeStampedModel


class Conversation(TimeStampedModel):
    class Kind(models.TextChoices):
        INQUIRY = "inquiry", "По обращению"
        DIRECT = "direct", "Личная переписка GG Surfer"
        SUPPORT = "support", "Поддержка"

    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.INQUIRY)
    inquiry = models.OneToOneField("commerce.Inquiry", null=True, blank=True, on_delete=models.CASCADE, related_name="conversation")
    subject = models.CharField(max_length=200, blank=True)
    last_message_at = models.DateTimeField(null=True, blank=True, db_index=True)
    is_locked = models.BooleanField("закрыт модератором", default=False)
    # Упорядоченная пара аккаунтов для личной переписки: одна беседа на пару (гонка решается уникальностью).
    direct_key = models.CharField(max_length=80, null=True, blank=True, unique=True, editable=False)

    class Meta:
        verbose_name = "диалог"
        verbose_name_plural = "диалоги"

    def __str__(self):
        return self.subject or f"{self.get_kind_display()} {self.pk}"


class ConversationParticipant(models.Model):
    """Read-состояние хранится по участнику (BR-10, MSG-06): непрочитанность — не статус обращения."""

    class Role(models.TextChoices):
        CUSTOMER = "customer", "Клиент"
        PROVIDER = "provider", "Исполнитель"
        MEMBER = "member", "Сотрудник организации"
        PEER = "peer", "Собеседник"
        STAFF = "staff", "Поддержка"

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="participants")
    account = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="conversation_memberships")
    role = models.CharField(max_length=16, choices=Role.choices)
    organization = models.ForeignKey("organizations.Organization", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    last_read_at = models.DateTimeField(null=True, blank=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)
    is_muted = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["conversation", "account"], name="uniq_conversation_participant")]
        verbose_name = "участник диалога"
        verbose_name_plural = "участники диалогов"


class Message(TimeStampedModel):
    class Kind(models.TextChoices):
        TEXT = "text", "Сообщение"
        SYSTEM = "system", "Системное"

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.TEXT)
    body = models.TextField(blank=True)
    client_id = models.CharField(max_length=64, blank=True)
    edited_at = models.DateTimeField(null=True, blank=True)
    is_hidden = models.BooleanField("скрыто модератором", default=False)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["conversation", "created_at"])]
        constraints = [
            models.UniqueConstraint(
                fields=["conversation", "sender", "client_id"], condition=~Q(client_id=""), name="uniq_message_client_id"
            )
        ]
        verbose_name = "сообщение"
        verbose_name_plural = "сообщения"

    def __str__(self):
        text = " ".join((self.body or "").split())
        return (text[:60] + "…") if len(text) > 60 else (text or f"{self.get_kind_display()} {self.pk}")


class MessageAttachment(models.Model):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="attachments")
    media = models.ForeignKey("mediafiles.MediaAsset", on_delete=models.PROTECT, related_name="+")
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]


class Notification(models.Model):
    class Kind(models.TextChoices):
        MESSAGE_NEW = "message_new", "Новое сообщение"
        INQUIRY_NEW = "inquiry_new", "Новое обращение"
        INQUIRY_STATUS = "inquiry_status", "Статус обращения"
        BOOKING_NEW = "booking_new", "Новая бронь"
        BOOKING_STATUS = "booking_status", "Статус брони"
        LESSON_ASSIGNED = "lesson_assigned", "Назначено занятие"
        MODERATION_DECISION = "moderation_decision", "Решение модератора"
        REVIEW_PUBLISHED = "review_published", "Отзыв опубликован"
        CERTIFICATE_DECISION = "certificate_decision", "Проверка сертификата"
        INVITE = "invite", "Приглашение в организацию"
        MEMBERSHIP = "membership", "Изменение доступа"
        EVENT_REMINDER = "event_reminder", "Напоминание о событии"
        EVENT_STATUS = "event_status", "Изменение события клуба"
        PRODUCT_AVAILABLE = "product_available", "Товар в продаже"
        LESSON_REMINDER = "lesson_reminder", "Напоминание о занятии"
        BIRTHDAY = "birthday", "Поздравление"
        COMPLAINT = "complaint", "Жалоба"
        SYSTEM = "system", "Системное"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    kind = models.CharField(max_length=32, choices=Kind.choices)
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    link = models.CharField(max_length=300, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    event_id = models.CharField("уникальный ключ события", max_length=200, unique=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)
    email_sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["recipient", "read_at"])]
        verbose_name = "уведомление"
        verbose_name_plural = "уведомления"


class NotificationPreference(models.Model):
    """Индивидуальные настройки каналов (MSG-12)."""

    account = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notification_preferences")
    kind = models.CharField(max_length=32, choices=Notification.Kind.choices)
    in_app = models.BooleanField(default=True)
    email = models.BooleanField(default=False)
    push = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["account", "kind"], name="uniq_notification_pref")]


class PushDevice(TimeStampedModel):
    """Точка расширения для APNs/FCM (MSG-12, M2)."""

    account = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="push_devices")
    platform = models.CharField(max_length=16)
    token = models.CharField(max_length=300, unique=True)
    is_active = models.BooleanField(default=True)


class AccountBlock(models.Model):
    """Блокировка собеседника (COM-07, MSG-13)."""

    blocker = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="blocks")
    blocked = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="blocked_by")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["blocker", "blocked"], name="uniq_account_block"),
            models.CheckConstraint(condition=~Q(blocker=models.F("blocked")), name="block_not_self"),
        ]
        verbose_name = "блокировка"
        verbose_name_plural = "блокировки"
