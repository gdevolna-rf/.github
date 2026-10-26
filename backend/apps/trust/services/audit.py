"""Запись в неизменяемый журнал аудита. Вызывать внутри той же транзакции, что и само изменение."""
from apps.common.middleware import current_request_id
from apps.trust.models import AuditEvent


def _ip(request):
    if request is None:
        return None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    return (forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")) or None


def record(actor, action, obj=None, *, object_type=None, object_id=None, before=None, after=None,
           organization=None, metadata=None, request=None):
    """record(user, "spot.change_approved", spot, before={...}, after={...})."""
    if obj is not None:
        object_type = object_type or obj._meta.label_lower
        object_id = object_id or str(obj.pk)
    return AuditEvent.objects.create(
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        action=action,
        object_type=object_type or "",
        object_id=str(object_id or ""),
        organization=organization,
        before=before,
        after=after,
        metadata=metadata or {},
        ip=_ip(request),
        request_id=current_request_id(),
    )
