"""Idempotency-Key для критических POST (раздел 9.1): повтор запроса не создаёт дубль."""
import hashlib
import json

from django.db import IntegrityError, connection, transaction
from rest_framework.response import Response
from rest_framework.utils.encoders import JSONEncoder

from .exceptions import Conflict
from .models import IdempotencyRecord

HEADER = "Idempotency-Key"


def _hash(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, cls=JSONEncoder).encode()).hexdigest()


def run_idempotent(request, endpoint, handler):
    """Выполнить handler() -> Response однократно для пары (аккаунт, endpoint, ключ)."""
    key = request.headers.get(HEADER)
    if not key or not request.user.is_authenticated:
        return handler()
    if len(key) > 128:
        raise Conflict("Слишком длинный Idempotency-Key.", code="idempotency_key_invalid")
    request_hash = _hash(request.data)

    def replay(record):
        if record.request_hash != request_hash:
            raise Conflict("Idempotency-Key уже использован с другими данными.", code="idempotency_mismatch")
        response = Response(record.response_body, status=record.response_status)
        response["Idempotent-Replay"] = "true"
        return response

    # Параллельные повторы с одним ключом выполняются последовательно: второй дождётся коммита первого
    # и получит сохранённый ответ (advisory-lock действует до конца транзакции).
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", [f"idem:{request.user.pk}:{endpoint}:{key}"])
        existing = IdempotencyRecord.objects.filter(account=request.user, endpoint=endpoint, key=key).first()
        if existing:
            return replay(existing)

        response = handler()
        if 200 <= response.status_code < 300:
            try:
                with transaction.atomic():
                    IdempotencyRecord.objects.create(
                        key=key,
                        account=request.user,
                        endpoint=endpoint,
                        request_hash=request_hash,
                        response_status=response.status_code,
                        # Тот же кодировщик, что у JSONRenderer: повтор отдаёт те же значения (даты, Decimal, UUID).
                        response_body=json.loads(json.dumps(response.data, cls=JSONEncoder)),
                    )
            except IntegrityError:
                return replay(IdempotencyRecord.objects.get(account=request.user, endpoint=endpoint, key=key))
        return response


class IdempotentCreateMixin:
    """Для ViewSet/CreateAPIView: оборачивает create() в run_idempotent."""

    idempotency_endpoint = None

    def create(self, request, *args, **kwargs):
        endpoint = self.idempotency_endpoint or request.path
        return run_idempotent(request, endpoint, lambda: super(IdempotentCreateMixin, self).create(request, *args, **kwargs))
