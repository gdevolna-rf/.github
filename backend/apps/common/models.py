import uuid

from django.db import models


class UUIDModel(models.Model):
    """Базовая модель с неизменяемым UUID-идентификатором."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class TimeStampedModel(UUIDModel):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class IdempotencyRecord(models.Model):
    """Сохранённый ответ на критический POST с заголовком Idempotency-Key (раздел 9.1)."""

    key = models.CharField(max_length=128)
    account = models.ForeignKey("accounts.Account", on_delete=models.CASCADE, related_name="+")
    endpoint = models.CharField(max_length=200)
    request_hash = models.CharField(max_length=64)
    response_status = models.PositiveSmallIntegerField()
    response_body = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["account", "endpoint", "key"], name="uniq_idempotency_key"),
        ]
