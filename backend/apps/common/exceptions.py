"""Единый формат ошибок API (раздел 9): {"error": {"code", "message", "fields"}}."""
import logging

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler

from .middleware import current_request_id

logger = logging.getLogger(__name__)


class DomainError(exceptions.APIException):
    """Нарушение бизнес-правила. Сервисы бросают его с машинным кодом."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "domain_error"
    default_detail = "Операция недопустима."

    def __init__(self, code, message, status_code=None, fields=None):
        super().__init__(detail=message, code=code)
        self.code = code
        self.message = message
        self.fields = fields or {}
        if status_code:
            self.status_code = status_code


class Forbidden(DomainError):
    def __init__(self, message="Недостаточно прав.", code="forbidden"):
        super().__init__(code, message, status.HTTP_403_FORBIDDEN)


class Conflict(DomainError):
    def __init__(self, message, code="conflict", fields=None):
        super().__init__(code, message, status.HTTP_409_CONFLICT, fields)


class NotFound(DomainError):
    def __init__(self, message="Не найдено.", code="not_found"):
        super().__init__(code, message, status.HTTP_404_NOT_FOUND)


_DEFAULT_MESSAGES = {
    400: "Проверьте введённые данные.",
    401: "Требуется вход в аккаунт.",
    403: "Недостаточно прав.",
    404: "Не найдено.",
    405: "Метод не поддерживается.",
    409: "Конфликт данных.",
    429: "Слишком много запросов, попробуйте позже.",
}


def _flatten(detail):
    if isinstance(detail, dict):
        return {k: _flatten(v) for k, v in detail.items()}
    if isinstance(detail, list):
        out = []
        for item in detail:
            flat = _flatten(item)
            out.extend(flat if isinstance(flat, list) else [flat])
        return out
    return str(detail)


def api_exception_handler(exc, context):
    if isinstance(exc, DjangoValidationError):
        exc = exceptions.ValidationError(exc.message_dict if hasattr(exc, "error_dict") else exc.messages)
    elif isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, DjangoPermissionDenied):
        exc = exceptions.PermissionDenied()

    response = exception_handler(exc, context)
    if response is None:
        logger.exception("unhandled API error", exc_info=exc)
        return Response(
            {"error": {"code": "server_error", "message": "Внутренняя ошибка сервера.", "fields": {},
                       "request_id": current_request_id()}},
            status=500,
        )

    code = getattr(exc, "default_code", "error")
    fields = {}
    message = _DEFAULT_MESSAGES.get(response.status_code, "Ошибка.")
    if isinstance(exc, DomainError):
        code, message, fields = exc.code, exc.message, exc.fields
    elif isinstance(exc, exceptions.ValidationError):
        code = "validation_error"
        detail = _flatten(exc.detail)
        if isinstance(detail, dict):
            non_field = detail.pop("non_field_errors", None)
            fields = {k: (v if isinstance(v, list) else [v]) for k, v in detail.items()}
            if non_field:
                message = non_field[0]
        elif isinstance(detail, list) and detail:
            message = detail[0]
    elif isinstance(exc, exceptions.APIException):
        code = exc.get_codes() if isinstance(exc.get_codes(), str) else code
        if isinstance(exc.detail, str) and response.status_code not in (401, 403):
            message = str(exc.detail)
        elif response.status_code == 403 and isinstance(exc.detail, str) and exc.detail != exceptions.PermissionDenied.default_detail:
            message = str(exc.detail)

    response.data = {"error": {"code": code, "message": message, "fields": fields, "request_id": current_request_id()}}
    return response
