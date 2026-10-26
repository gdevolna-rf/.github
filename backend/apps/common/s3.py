"""Клиенты S3: внутренний (backend → minio) и публичный (подпись ссылок для браузера)."""
from functools import lru_cache

import boto3
from botocore.config import Config
from django.conf import settings


def _client(endpoint):
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        region_name=settings.S3_REGION,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


@lru_cache(maxsize=1)
def internal_client():
    return _client(settings.S3_ENDPOINT_URL)


@lru_cache(maxsize=8)
def public_client(origin):
    """Клиент, подписывающий ссылки для origin браузера (http://host:port).

    nginx проксирует /<bucket>/ на MinIO с исходным Host, поэтому подпись, рассчитанная для
    origin, совпадает с тем, что проверит MinIO.
    """
    return _client(origin)


def request_origin(request):
    if request is None:
        return settings.SITE_URL
    return f"{request.scheme}://{request.get_host()}"
