"""Тестовые помощники медиа: реальные байты изображений/видео/PDF и загрузка «как из браузера»."""
import io

from PIL import Image

from apps.mediafiles.models import MediaAsset
from apps.mediafiles.storage import get_storage

PDF_BYTES = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
MP4_BYTES = b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2" + b"\x00" * 64
MOV_BYTES = b"\x00\x00\x00\x14ftypqt  \x00\x00\x00\x00qt  " + b"\x00" * 64
WEBM_BYTES = b"\x1a\x45\xdf\xa3\x9f\x42\x86\x81\x01" + b"\x00" * 64


def make_image(fmt="JPEG", size=(800, 600), color="red", exif=None):
    image = Image.new("RGB", size, color)
    buf = io.BytesIO()
    kwargs = {}
    if exif is not None:
        kwargs["exif"] = exif.tobytes()
    image.save(buf, fmt, **kwargs)
    return buf.getvalue()


def exif_with_orientation(orientation=6, make="TestCam"):
    exif = Image.Exif()
    exif[0x0112] = orientation  # Orientation
    exif[0x010F] = make  # Make
    exif[0x0131] = "SecretSoftware"  # Software
    return exif


def browser_put(asset_or_key, data, content_type):
    """Имитирует PUT по presigned-ссылке: объект появляется в хранилище."""
    key = asset_or_key.storage_key if isinstance(asset_or_key, MediaAsset) else asset_or_key
    get_storage().write(key, data, content_type)


def request_upload(client, *, kind="image", purpose="avatar", content_type="image/jpeg", size=1000,
                   filename="photo.jpg", **extra):
    payload = {"kind": kind, "purpose": purpose, "content_type": content_type, "size": size, "filename": filename}
    payload.update(extra)
    return client.post("/api/v1/media/uploads", payload, format="json")


def upload_ready(client, run_on_commit, data=None, *, kind="image", purpose="avatar", content_type="image/jpeg",
                 filename="photo.jpg", **extra):
    """Полный цикл: uploads → PUT → complete → обработка. Возвращает MediaAsset."""
    data = data if data is not None else make_image()
    response = request_upload(client, kind=kind, purpose=purpose, content_type=content_type, size=len(data),
                              filename=filename, **extra)
    assert response.status_code == 201, response.json()
    asset = MediaAsset.objects.get(pk=response.json()["id"])
    browser_put(asset, data, content_type)
    complete = run_on_commit(client.post, f"/api/v1/media/{asset.pk}/complete")
    assert complete.status_code == 200, complete.json()
    asset.refresh_from_db()
    return asset
