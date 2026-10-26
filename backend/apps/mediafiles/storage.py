"""Доступ к объектному хранилищу через узкий интерфейс (DATA-04, 9.1).

Бизнес-код (`apps.mediafiles.services`, выгрузки данных) работает только с `get_storage()`:
- `S3MediaStorage` — MinIO/S3 через `apps.common.s3` (внутренний клиент для HEAD/GET/PUT/DELETE,
  публичный клиент для подписи ссылок под origin браузера — nginx проксирует `/<bucket>/` с исходным Host);
- `InMemoryMediaStorage` — для тестов: без сети, объекты хранятся в словаре.

В тестовом окружении (`settings.TESTING`) по умолчанию используется in-memory хранилище.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from urllib.parse import quote

from django.conf import settings


@dataclass(frozen=True)
class ObjectInfo:
    size: int
    content_type: str


class MediaStorage:
    """Контракт хранилища. Ключи — полные пути внутри бакета (`public/...`, `private/...`)."""

    def presigned_put(self, key: str, content_type: str, expires: int, origin: str) -> str:
        raise NotImplementedError

    def presigned_get(self, key: str, expires: int, origin: str, *, filename: str | None = None,
                      attachment: bool = False) -> str:
        raise NotImplementedError

    def head(self, key: str) -> ObjectInfo | None:
        raise NotImplementedError

    def read(self, key: str, length: int | None = None) -> bytes:
        """Содержимое объекта; `length` — только первые N байт (ranged GET)."""
        raise NotImplementedError

    def write(self, key: str, data: bytes, content_type: str) -> None:
        raise NotImplementedError

    def delete(self, key: str) -> None:
        raise NotImplementedError

    def exists(self, key: str) -> bool:
        return self.head(key) is not None


def _content_disposition(filename, attachment):
    kind = "attachment" if attachment else "inline"
    if not filename:
        return kind
    safe = "".join(ch for ch in filename if ch.isprintable() and ch not in '"\\') or "file"
    return f"{kind}; filename*=UTF-8''{quote(safe)}"


class S3MediaStorage(MediaStorage):
    def __init__(self, bucket=None):
        self.bucket = bucket or settings.S3_BUCKET

    @staticmethod
    def _internal():
        from apps.common.s3 import internal_client

        return internal_client()

    @staticmethod
    def _public(origin):
        from apps.common.s3 import public_client

        return public_client(origin)

    def presigned_put(self, key, content_type, expires, origin):
        return self._public(origin).generate_presigned_url(
            "put_object",
            Params={"Bucket": self.bucket, "Key": key, "ContentType": content_type},
            ExpiresIn=expires,
            HttpMethod="PUT",
        )

    def presigned_get(self, key, expires, origin, *, filename=None, attachment=False):
        params = {"Bucket": self.bucket, "Key": key}
        if filename or attachment:
            params["ResponseContentDisposition"] = _content_disposition(filename, attachment)
        return self._public(origin).generate_presigned_url("get_object", Params=params, ExpiresIn=expires)

    def head(self, key):
        from botocore.exceptions import ClientError

        try:
            meta = self._internal().head_object(Bucket=self.bucket, Key=key)
        except ClientError as exc:
            status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            code = exc.response.get("Error", {}).get("Code")
            if status == 404 or code in {"404", "NoSuchKey", "NotFound"}:
                return None
            raise
        return ObjectInfo(size=int(meta.get("ContentLength", 0)), content_type=meta.get("ContentType", ""))

    def read(self, key, length=None):
        from botocore.exceptions import ClientError

        kwargs = {"Bucket": self.bucket, "Key": key}
        if length:
            kwargs["Range"] = f"bytes=0-{length - 1}"
        try:
            body = self._internal().get_object(**kwargs)["Body"]
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in {"NoSuchKey", "404", "NotFound"}:
                raise FileNotFoundError(key) from exc
            raise
        try:
            return body.read()
        finally:
            body.close()

    def write(self, key, data, content_type):
        self._internal().put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)

    def delete(self, key):
        self._internal().delete_object(Bucket=self.bucket, Key=key)


class InMemoryMediaStorage(MediaStorage):
    """Хранилище для тестов: ссылки детерминированные, объекты — в памяти процесса."""

    def __init__(self, bucket=None):
        self.bucket = bucket or settings.S3_BUCKET
        self.objects: dict[str, tuple[bytes, str]] = {}
        self._lock = threading.Lock()

    def clear(self):
        with self._lock:
            self.objects.clear()

    def presigned_put(self, key, content_type, expires, origin):
        return f"{origin}/{self.bucket}/{key}?X-Amz-Method=PUT&X-Amz-Expires={expires}&X-Amz-Signature=memory"

    def presigned_get(self, key, expires, origin, *, filename=None, attachment=False):
        url = f"{origin}/{self.bucket}/{key}?X-Amz-Expires={expires}&X-Amz-Signature=memory"
        if filename or attachment:
            url += "&response-content-disposition=" + quote(_content_disposition(filename, attachment))
        return url

    def head(self, key):
        with self._lock:
            item = self.objects.get(key)
        return ObjectInfo(size=len(item[0]), content_type=item[1]) if item else None

    def read(self, key, length=None):
        with self._lock:
            if key not in self.objects:
                raise FileNotFoundError(key)
            data = self.objects[key][0]
        return data[:length] if length else data

    def write(self, key, data, content_type):
        with self._lock:
            self.objects[key] = (bytes(data), content_type)

    def delete(self, key):
        with self._lock:
            self.objects.pop(key, None)


_storage: MediaStorage | None = None
_storage_lock = threading.Lock()


def get_storage() -> MediaStorage:
    global _storage
    if _storage is None:
        with _storage_lock:
            if _storage is None:
                _storage = InMemoryMediaStorage() if getattr(settings, "TESTING", False) else S3MediaStorage()
    return _storage


def set_storage(storage: MediaStorage | None) -> None:
    """Подмена хранилища (тесты, management-команды). None — вернуть поведение по умолчанию."""
    global _storage
    with _storage_lock:
        _storage = storage
