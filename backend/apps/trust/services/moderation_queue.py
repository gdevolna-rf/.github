"""Открытие кейсов единой очереди модерации (TRUST-04). Решения по кейсам — в apps.trust (moderation API)."""
import datetime as dt

from django.conf import settings
from django.utils import timezone

from apps.trust.models import ModerationCase


def open_case(kind, summary, *, spot_change_request=None, review=None, certificate=None, complaint=None,
              organization=None):
    """Создаёт открытый кейс (или возвращает уже открытый по тому же объекту)."""
    target = dict(spot_change_request=spot_change_request, review=review, certificate=certificate,
                  complaint=complaint, organization=organization)
    lookup = {k: v for k, v in target.items() if v is not None}
    if not lookup:
        raise ValueError("open_case: нужен объект модерации")
    existing = ModerationCase.objects.filter(kind=kind, status__in=[ModerationCase.Status.OPEN, ModerationCase.Status.IN_REVIEW], **lookup).first()
    if existing:
        return existing
    return ModerationCase.objects.create(
        kind=kind, summary=summary[:300], due_at=timezone.now() + dt.timedelta(hours=settings.MODERATION_SLA_HOURS),
        **target,
    )


def close_cases(resolution, moderator, note="", **target):
    """Закрывает открытые кейсы по объекту (вызывается из сервисов решений)."""
    lookup = {k: v for k, v in target.items() if v is not None}
    if not lookup:
        raise ValueError("close_cases: нужен объект модерации")
    return ModerationCase.objects.filter(
        status__in=[ModerationCase.Status.OPEN, ModerationCase.Status.IN_REVIEW], **lookup
    ).update(status=ModerationCase.Status.RESOLVED, resolution=resolution, resolution_note=note,
             resolved_by=moderator, resolved_at=timezone.now())
