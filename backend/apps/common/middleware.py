import contextvars
import logging
import uuid

_request_id = contextvars.ContextVar("request_id", default="-")


def current_request_id():
    return _request_id.get()


class RequestIdMiddleware:
    """Сквозной X-Request-ID: берётся от nginx или генерируется; попадает в логи и ответ."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        token = _request_id.set(rid)
        request.request_id = rid
        try:
            response = self.get_response(request)
        finally:
            _request_id.reset(token)
        response["X-Request-ID"] = rid
        return response


class RequestIdLogFilter(logging.Filter):
    def filter(self, record):
        record.request_id = current_request_id()
        return True
