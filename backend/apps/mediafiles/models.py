"""Объектная модель медиа (DATA-04): бинарные данные в S3, в БД — ключ, тип, статус, ACL."""
from django.conf import settings
from django.db import models

from apps.common.models import TimeStampedModel


class MediaAsset(TimeStampedModel):
    class Kind(models.TextChoices):
        IMAGE = "image", "Изображение"
        VIDEO = "video", "Видео"
        DOCUMENT = "document", "Документ"

    class Purpose(models.TextChoices):
        AVATAR = "avatar", "Фото профиля"
        ORG_LOGO = "org_logo", "Логотип организации"
        ORG_COVER = "org_cover", "Обложка организации"
        ORG_GALLERY = "org_gallery", "Галерея организации"
        SPOT_PHOTO = "spot_photo", "Фото спота"
        SPOT_EVIDENCE = "spot_evidence", "Фото-доказательство правки"
        BOARD_PHOTO = "board_photo", "Фото доски"
        BOARD_VIDEO = "board_video", "Видео доски"
        PROMO_VIDEO = "promo_video", "Промо-видео"
        PROFILE_GALLERY = "profile_gallery", "Фото/видео инструктора"
        ITEM_PHOTO = "item_photo", "Фото инвентаря"
        CERTIFICATE = "certificate", "Сертификат"
        MESSAGE_ATTACHMENT = "message_attachment", "Вложение в чат"
        REPAIR_PHOTO = "repair_photo", "Фото повреждения"
        HANDOVER_PHOTO = "handover_photo", "Фото выдачи/возврата"
        REVIEW_PHOTO = "review_photo", "Фото к отзыву"
        DIARY_PHOTO = "diary_photo", "Фото дневника"
        EVENT_COVER = "event_cover", "Обложка события"
        PRODUCT_PHOTO = "product_photo", "Фото товара"
        DATA_EXPORT = "data_export", "Выгрузка данных"

    class Visibility(models.TextChoices):
        PUBLIC = "public", "Публичный"
        PRIVATE = "private", "Закрытый"

    class Status(models.TextChoices):
        PENDING = "pending", "Ожидает загрузки"
        PROCESSING = "processing", "Обрабатывается"
        READY = "ready", "Готово"
        REJECTED = "rejected", "Отклонено"
        DELETED = "deleted", "Удалено"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="media_assets")
    organization = models.ForeignKey("organizations.Organization", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    kind = models.CharField(max_length=16, choices=Kind.choices)
    purpose = models.CharField(max_length=32, choices=Purpose.choices)
    visibility = models.CharField(max_length=16, choices=Visibility.choices, default=Visibility.PUBLIC)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    storage_key = models.CharField(max_length=512, unique=True)
    original_filename = models.CharField(max_length=255, blank=True)
    content_type = models.CharField(max_length=100)
    size_bytes = models.BigIntegerField(default=0)
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    duration_seconds = models.FloatField(null=True, blank=True)
    thumbnail_key = models.CharField(max_length=512, blank=True)
    poster_key = models.CharField(max_length=512, blank=True)
    checksum_sha256 = models.CharField(max_length=64, blank=True)
    alt_text = models.CharField(max_length=300, blank=True)
    rejection_reason = models.CharField(max_length=300, blank=True)
    upload_expires_at = models.DateTimeField(null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    is_demo = models.BooleanField(default=False)

    class Meta:
        indexes = [models.Index(fields=["owner", "purpose"])]
        verbose_name = "медиафайл"
        verbose_name_plural = "медиафайлы"

    def __str__(self):
        return f"{self.purpose}:{self.storage_key}"

    def _public_path(self, key):
        return f"/{settings.S3_BUCKET}/{key}" if key else None

    @property
    def is_public(self):
        return self.visibility == self.Visibility.PUBLIC

    @property
    def url(self):
        """Путь для публичного файла (через nginx → MinIO). Для закрытых — None, нужен presigned URL."""
        if self.is_public and self.status == self.Status.READY:
            return self._public_path(self.storage_key)
        return None

    @property
    def thumbnail_url(self):
        if self.is_public and self.status == self.Status.READY:
            return self._public_path(self.thumbnail_key or self.storage_key)
        return None

    @property
    def poster_url(self):
        if self.is_public and self.status == self.Status.READY and self.poster_key:
            return self._public_path(self.poster_key)
        return None
