"""Посевные изображения: загрузка в MinIO (вне транзакции БД) и строки MediaAsset (внутри неё).

Файлы лежат в apps/demo/seed_assets/ и публикуются под public/seed/<key>; рядом — WebP-миниатюра <key>.thumb.webp
(не больше 640 px по большей стороне). Повторный запуск идемпотентен по storage_key: объект с тем же sha256 в S3
не перезаливается, строка MediaAsset переиспользуется.
"""
import hashlib
import io
from dataclasses import dataclass
from pathlib import Path

from botocore.exceptions import ClientError
from django.conf import settings
from django.utils import timezone
from PIL import Image

from apps.common import s3
from apps.mediafiles.models import MediaAsset

ASSET_ROOT = Path(__file__).resolve().parent / "seed_assets"
KEY_PREFIX = "public/seed/"
THUMB_SUFFIX = ".thumb.webp"
THUMB_MAX_PX = 640
CACHE_CONTROL = "public, max-age=86400"
CONTENT_TYPES = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
EXTENSIONS = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".webp": "WEBP"}
_MISSING_CODES = {"404", "NoSuchKey", "NotFound"}


@dataclass(frozen=True)
class AssetSpec:
    """Один публичный файл: key — путь под public/seed/, source — файл в seed_assets/."""

    key: str
    source: str
    purpose: str
    alt: str = ""

    @property
    def storage_key(self):
        return KEY_PREFIX + self.key

    @property
    def thumbnail_key(self):
        return self.storage_key + THUMB_SUFFIX


@dataclass(frozen=True)
class PreparedImage:
    body: bytes
    sha256: str
    content_type: str
    width: int
    height: int
    thumb: bytes
    thumb_sha256: str


def prepare_image(source):
    path = ASSET_ROOT / source
    body = path.read_bytes()
    with Image.open(io.BytesIO(body)) as im:
        content_type = CONTENT_TYPES.get(im.format)
        if content_type is None:
            raise ValueError(f"{source}: неподдерживаемый формат {im.format}")
        if EXTENSIONS.get(path.suffix.lower()) != im.format:
            raise ValueError(f"{source}: расширение не совпадает с форматом файла ({im.format})")
        width, height = im.size
        thumb_im = im.copy()
    thumb_im.thumbnail((THUMB_MAX_PX, THUMB_MAX_PX))
    if thumb_im.mode not in ("RGB", "RGBA"):
        thumb_im = thumb_im.convert("RGBA" if "transparency" in thumb_im.info or "A" in thumb_im.getbands() else "RGB")
    out = io.BytesIO()
    thumb_im.save(out, format="WEBP", quality=82, method=4)
    thumb = out.getvalue()
    return PreparedImage(
        body=body, sha256=hashlib.sha256(body).hexdigest(), content_type=content_type, width=width, height=height,
        thumb=thumb, thumb_sha256=hashlib.sha256(thumb).hexdigest(),
    )


class AssetUploader:
    """Заливает файлы в бакет; объект с совпадающим sha256 (метаданные) пропускается."""

    def __init__(self, client=None):
        self.client = client or s3.internal_client()
        self.bucket = settings.S3_BUCKET
        self.uploaded = 0
        self.reused = 0
        self._cache = {}

    def _same_object_exists(self, key, sha256):
        try:
            head = self.client.head_object(Bucket=self.bucket, Key=key)
        except ClientError as exc:
            if str(exc.response.get("Error", {}).get("Code")) in _MISSING_CODES:
                return False
            raise
        return (head.get("Metadata") or {}).get("sha256") == sha256

    def _put(self, key, body, content_type, sha256):
        if self._same_object_exists(key, sha256):
            self.reused += 1
            return
        self.client.put_object(
            Bucket=self.bucket, Key=key, Body=body, ContentType=content_type, CacheControl=CACHE_CONTROL,
            Metadata={"sha256": sha256},
        )
        self.uploaded += 1

    def upload(self, specs):
        """Возвращает {storage_key: PreparedImage} для всех спецификаций."""
        prepared = {}
        for spec in specs:
            image = self._cache.get(spec.source)
            if image is None:
                image = self._cache[spec.source] = prepare_image(spec.source)
            self._put(spec.storage_key, image.body, image.content_type, image.sha256)
            self._put(spec.thumbnail_key, image.thumb, "image/webp", image.thumb_sha256)
            prepared[spec.storage_key] = image
        return prepared


def save_media_assets(specs, prepared):
    """Создаёт/обновляет MediaAsset (status=ready, public, is_demo). Вызывать внутри transaction.atomic()."""
    now = timezone.now()
    assets = {}
    for spec in specs:
        image = prepared[spec.storage_key]
        asset, _ = MediaAsset.objects.update_or_create(
            storage_key=spec.storage_key,
            defaults={
                "kind": MediaAsset.Kind.IMAGE,
                "purpose": spec.purpose,
                "visibility": MediaAsset.Visibility.PUBLIC,
                "status": MediaAsset.Status.READY,
                "original_filename": Path(spec.source).name,
                "content_type": image.content_type,
                "size_bytes": len(image.body),
                "width": image.width,
                "height": image.height,
                "thumbnail_key": spec.thumbnail_key,
                "checksum_sha256": image.sha256,
                "alt_text": spec.alt[:300],
                "rejection_reason": "",
                "upload_expires_at": None,
                "processed_at": now,
                "is_demo": True,
            },
        )
        assets[spec.key] = asset
    return assets
