"""Загрузка медиа: presigned PUT → complete → Celery-проверка (DATA-04, 9.1, ATX-24)."""
import datetime as dt
import io
import re

import pytest
from django.conf import settings
from django.utils import timezone
from PIL import Image

from apps.mediafiles.models import MediaAsset
from apps.mediafiles.storage import get_storage
from apps.mediafiles.tests.utils import (
    MOV_BYTES,
    MP4_BYTES,
    PDF_BYTES,
    WEBM_BYTES,
    browser_put,
    exif_with_orientation,
    make_image,
    request_upload,
    upload_ready,
)
from tests.factories import OrganizationFactory

pytestmark = pytest.mark.django_db


def test_guest_cannot_request_upload(api_client):
    response = request_upload(api_client)
    assert response.status_code == 401


def test_upload_request_returns_one_time_presigned_put_for_browser_origin(auth_client):
    response = request_upload(auth_client, filename="../../etc/Моё фото.jpg", size=12345)
    assert response.status_code == 201
    body = response.json()
    asset = MediaAsset.objects.get(pk=body["id"])
    assert asset.status == MediaAsset.Status.PENDING
    assert asset.owner == auth_client.account
    assert asset.visibility == MediaAsset.Visibility.PUBLIC
    assert re.fullmatch(r"public/avatar/\d{4}/\d{2}/[0-9a-f]{32}\.jpg", asset.storage_key)
    assert asset.original_filename == "Моё фото.jpg"
    assert body["method"] == "PUT"
    assert body["upload_url"].startswith(f"http://testserver/{settings.S3_BUCKET}/{asset.storage_key}")
    assert body["headers"] == {"Content-Type": "image/jpeg", "If-None-Match": "*"}
    assert body["media"]["status"] == "pending" and body["media"]["url"] is None
    expires = dt.datetime.fromisoformat(body["expires_at"])
    assert 14 * 60 < (expires - timezone.now()).total_seconds() <= 15 * 60


@pytest.mark.parametrize("purpose", ["certificate", "message_attachment", "spot_evidence", "repair_photo",
                                     "handover_photo"])
def test_private_purposes_are_stored_under_private_prefix(auth_client, purpose):
    kind = "document" if purpose == "certificate" else "image"
    response = request_upload(auth_client, kind=kind, purpose=purpose)
    assert response.status_code == 201
    asset = MediaAsset.objects.get(pk=response.json()["id"])
    assert asset.visibility == MediaAsset.Visibility.PRIVATE
    assert asset.storage_key.startswith(f"private/{purpose}/")


@pytest.mark.parametrize("payload,code", [
    ({"content_type": "image/gif"}, "media_type_not_allowed"),
    ({"content_type": "text/html"}, "media_type_not_allowed"),
    ({"size": 15 * 1024 * 1024 + 1}, "media_too_large"),
    ({"kind": "video", "content_type": "video/mp4"}, "media_kind_not_allowed"),  # аватар — только изображение
    ({"purpose": "data_export", "kind": "document", "content_type": "application/pdf"}, "media_purpose_invalid"),
])
def test_upload_request_validation(auth_client, payload, code):
    response = request_upload(auth_client, **payload)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == code


def test_video_100mb_is_accepted_for_board_video(auth_client):
    """ATX-24: видео 100+ МБ проходит ограничения (загрузка напрямую в хранилище)."""
    response = request_upload(auth_client, kind="video", purpose="board_video", content_type="video/mp4",
                              size=120 * 1024 * 1024, filename="ride.mp4")
    assert response.status_code == 201
    assert MediaAsset.objects.get(pk=response.json()["id"]).storage_key.endswith(".mp4")


def test_zero_size_rejected(auth_client):
    response = request_upload(auth_client, size=0)
    assert response.status_code == 400


def test_upload_for_foreign_organization_is_not_found(auth_client):
    org = OrganizationFactory()
    response = request_upload(auth_client, purpose="org_logo", organization_id=str(org.pk))
    assert response.status_code == 404


def test_upload_for_own_organization_links_asset(make_client):
    org = OrganizationFactory()
    client = make_client(org.owner)
    response = request_upload(client, purpose="org_gallery", organization_id=str(org.pk))
    assert response.status_code == 201
    assert MediaAsset.objects.get(pk=response.json()["id"]).organization == org


def test_too_many_pending_uploads_is_throttled(auth_client):
    for _ in range(50):
        assert request_upload(auth_client).status_code == 201
    response = request_upload(auth_client)
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "media_too_many_pending"


def test_complete_before_put_is_rejected(auth_client):
    asset_id = request_upload(auth_client).json()["id"]
    response = auth_client.post(f"/api/v1/media/{asset_id}/complete")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "upload_not_found"
    assert MediaAsset.objects.get(pk=asset_id).status == MediaAsset.Status.PENDING


def test_complete_after_expiry_without_upload(auth_client):
    asset_id = request_upload(auth_client).json()["id"]
    MediaAsset.objects.filter(pk=asset_id).update(upload_expires_at=timezone.now() - dt.timedelta(minutes=1))
    response = auth_client.post(f"/api/v1/media/{asset_id}/complete")
    assert response.json()["error"]["code"] == "upload_expired"


def test_foreign_user_cannot_complete(auth_client, make_client):
    data = make_image()
    asset_id = request_upload(auth_client, size=len(data)).json()["id"]
    browser_put(MediaAsset.objects.get(pk=asset_id), data, "image/jpeg")
    response = make_client().post(f"/api/v1/media/{asset_id}/complete")
    assert response.status_code == 404


def test_full_flow_image_ready_with_thumbnail_and_exif_stripped(auth_client, run_on_commit):
    original = make_image(size=(1600, 1200), exif=exif_with_orientation(6))
    asset = upload_ready(auth_client, run_on_commit, original)
    assert asset.status == MediaAsset.Status.READY
    # Ориентация из EXIF применена, затем EXIF удалён (геометка/модель камеры не утекают).
    assert (asset.width, asset.height) == (1200, 1600)
    stored = get_storage().read(asset.storage_key)
    cleaned = Image.open(io.BytesIO(stored))
    exif = cleaned.getexif()
    assert 0x010F not in exif and 0x0131 not in exif and 0x0112 not in exif
    assert asset.size_bytes == len(stored)
    assert len(asset.checksum_sha256) == 64
    assert asset.thumbnail_key == f"{asset.storage_key}.thumb.webp"
    thumb = Image.open(io.BytesIO(get_storage().read(asset.thumbnail_key)))
    assert thumb.format == "WEBP" and max(thumb.size) == 640
    assert get_storage().head(asset.thumbnail_key).content_type == "image/webp"
    assert asset.url == f"/{settings.S3_BUCKET}/{asset.storage_key}"
    assert asset.thumbnail_url == f"/{settings.S3_BUCKET}/{asset.thumbnail_key}"


def test_complete_is_idempotent(auth_client, run_on_commit):
    asset = upload_ready(auth_client, run_on_commit)
    response = auth_client.post(f"/api/v1/media/{asset.pk}/complete")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


@pytest.mark.parametrize("fmt,content_type", [("PNG", "image/png"), ("WEBP", "image/webp")])
def test_png_and_webp_are_processed(auth_client, run_on_commit, fmt, content_type):
    asset = upload_ready(auth_client, run_on_commit, make_image(fmt, size=(300, 200)), content_type=content_type,
                         filename=f"x.{fmt.lower()}")
    assert asset.status == MediaAsset.Status.READY
    assert (asset.width, asset.height) == (300, 200)
    assert asset.thumbnail_key


def test_fake_image_with_wrong_magic_bytes_is_rejected_and_removed(auth_client, run_on_commit):
    data = b"<html><script>alert(1)</script></html>" + b" " * 200
    asset = upload_ready(auth_client, run_on_commit, data)
    assert asset.status == MediaAsset.Status.REJECTED
    assert "не соответствует" in asset.rejection_reason
    assert get_storage().head(asset.storage_key) is None


def test_png_declared_as_jpeg_is_rejected(auth_client, run_on_commit):
    asset = upload_ready(auth_client, run_on_commit, make_image("PNG"), content_type="image/jpeg")
    assert asset.status == MediaAsset.Status.REJECTED


def test_truncated_jpeg_is_rejected(auth_client, run_on_commit):
    data = make_image(size=(400, 400))[:300]
    asset = upload_ready(auth_client, run_on_commit, data)
    assert asset.status == MediaAsset.Status.REJECTED
    assert get_storage().head(asset.storage_key) is None


def test_actual_size_over_limit_is_rejected_on_complete(auth_client, settings):
    settings.MEDIA_LIMITS = {**settings.MEDIA_LIMITS, "image": {**settings.MEDIA_LIMITS["image"], "max_bytes": 1000}}
    asset_id = request_upload(auth_client, size=900).json()["id"]
    asset = MediaAsset.objects.get(pk=asset_id)
    browser_put(asset, make_image(size=(500, 500)), "image/jpeg")  # реальный файл больше лимита
    response = auth_client.post(f"/api/v1/media/{asset_id}/complete")
    assert response.status_code == 400
    asset.refresh_from_db()
    assert asset.status == MediaAsset.Status.REJECTED
    assert get_storage().head(asset.storage_key) is None


def test_stored_content_type_mismatch_is_rejected_on_complete(auth_client):
    data = make_image()
    asset_id = request_upload(auth_client, size=len(data)).json()["id"]
    browser_put(MediaAsset.objects.get(pk=asset_id), data, "text/html")
    response = auth_client.post(f"/api/v1/media/{asset_id}/complete")
    assert response.status_code == 400
    assert MediaAsset.objects.get(pk=asset_id).status == MediaAsset.Status.REJECTED


@pytest.mark.parametrize("data,content_type,filename", [
    (MP4_BYTES, "video/mp4", "a.mp4"),
    (MOV_BYTES, "video/quicktime", "a.mov"),
    (MOV_BYTES, "video/mp4", "a.mp4"),  # одно семейство ISO BMFF
    (WEBM_BYTES, "video/webm", "a.webm"),
])
def test_videos_are_checked_by_signature(auth_client, run_on_commit, data, content_type, filename):
    asset = upload_ready(auth_client, run_on_commit, data, kind="video", purpose="board_video",
                         content_type=content_type, filename=filename)
    assert asset.status == MediaAsset.Status.READY
    assert asset.thumbnail_key == ""


def test_video_with_image_bytes_is_rejected(auth_client, run_on_commit):
    asset = upload_ready(auth_client, run_on_commit, make_image(), kind="video", purpose="board_video",
                         content_type="video/mp4", filename="a.mp4")
    assert asset.status == MediaAsset.Status.REJECTED


def test_pdf_document_is_ready_and_private_for_certificate(auth_client, run_on_commit):
    asset = upload_ready(auth_client, run_on_commit, PDF_BYTES, kind="document", purpose="certificate",
                         content_type="application/pdf", filename="cert.pdf")
    assert asset.status == MediaAsset.Status.READY
    assert asset.visibility == MediaAsset.Visibility.PRIVATE
    assert asset.url is None and asset.thumbnail_url is None
    assert len(asset.checksum_sha256) == 64


def test_pdf_declared_but_not_pdf_is_rejected(auth_client, run_on_commit):
    asset = upload_ready(auth_client, run_on_commit, b"MZ\x90\x00" + b"\x00" * 100, kind="document",
                         purpose="certificate", content_type="application/pdf", filename="cert.pdf")
    assert asset.status == MediaAsset.Status.REJECTED


def test_certificate_scan_image_gets_private_thumbnail(auth_client, run_on_commit):
    asset = upload_ready(auth_client, run_on_commit, make_image(size=(900, 700)), kind="document",
                         purpose="certificate", content_type="image/jpeg", filename="scan.jpg")
    assert asset.status == MediaAsset.Status.READY
    assert asset.thumbnail_key.startswith("private/certificate/")


def test_detail_shows_rejection_reason_to_owner(auth_client, run_on_commit):
    asset = upload_ready(auth_client, run_on_commit, b"not an image at all" * 10)
    response = auth_client.get(f"/api/v1/media/{asset.pk}")
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"
    assert response.json()["rejection_reason"]


def test_animated_webp_is_resaved_with_all_frames(auth_client, run_on_commit):
    frames = [Image.new("RGB", (120, 80), color) for color in ("red", "green", "blue")]
    buf = io.BytesIO()
    exif = exif_with_orientation(1)
    frames[0].save(buf, "WEBP", save_all=True, append_images=frames[1:], duration=100, exif=exif.tobytes())
    asset = upload_ready(auth_client, run_on_commit, buf.getvalue(), content_type="image/webp", filename="a.webp")
    assert asset.status == MediaAsset.Status.READY
    stored = Image.open(io.BytesIO(get_storage().read(asset.storage_key)))
    assert getattr(stored, "n_frames", 1) == 3
    assert 0x010F not in stored.getexif()
