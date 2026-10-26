"""Удаление своих файлов и периодическая очистка (ARCHITECTURE §5: mediafiles.cleanup_expired_uploads)."""
import datetime as dt
import uuid

import pytest
from django.utils import timezone

from apps.commerce.models import Inquiry
from apps.mediafiles.models import MediaAsset
from apps.mediafiles.storage import get_storage
from apps.mediafiles.tasks import cleanup_expired_uploads, process_media
from apps.mediafiles.tests.utils import browser_put, make_image, request_upload, upload_ready
from apps.messaging.models import Conversation, Message, MessageAttachment
from tests.factories import AccountFactory, MediaAssetFactory

pytestmark = pytest.mark.django_db


def test_owner_deletes_media_and_objects_are_removed(auth_client, run_on_commit):
    asset = upload_ready(auth_client, run_on_commit)
    assert get_storage().head(asset.thumbnail_key) is not None
    response = run_on_commit(auth_client.delete, f"/api/v1/media/{asset.pk}")
    assert response.status_code == 204
    asset.refresh_from_db()
    assert asset.status == MediaAsset.Status.DELETED
    assert get_storage().head(asset.storage_key) is None
    assert get_storage().head(asset.thumbnail_key) is None


def test_deleting_avatar_unlinks_it_from_profile(auth_client, run_on_commit):
    asset = upload_ready(auth_client, run_on_commit)
    profile = auth_client.account.profile
    profile.avatar = asset
    profile.save()
    run_on_commit(auth_client.delete, f"/api/v1/media/{asset.pk}")
    profile.refresh_from_db()
    assert profile.avatar is None


def test_foreign_user_cannot_delete(make_client):
    asset = MediaAssetFactory()
    assert make_client().delete(f"/api/v1/media/{asset.pk}").status_code == 404
    asset.refresh_from_db()
    assert asset.status == MediaAsset.Status.READY


def test_guest_cannot_delete(api_client):
    asset = MediaAssetFactory()
    assert api_client.delete(f"/api/v1/media/{asset.pk}").status_code == 401


def test_sent_message_attachment_cannot_be_deleted(make_client):
    customer, provider = AccountFactory(), AccountFactory()
    inquiry = Inquiry.objects.create(kind="general", customer=customer, provider_account=provider, subject="?")
    conversation = Conversation.objects.create(inquiry=inquiry)
    asset = MediaAssetFactory(owner=customer, purpose="message_attachment", visibility="private",
                              storage_key=f"private/message_attachment/{uuid.uuid4().hex}.jpg")
    message = Message.objects.create(conversation=conversation, sender=customer, body="x")
    MessageAttachment.objects.create(message=message, media=asset)
    response = make_client(customer).delete(f"/api/v1/media/{asset.pk}")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "media_in_use"


def test_cleanup_removes_expired_pending_uploads_only(auth_client, run_on_commit):
    stale_id = request_upload(auth_client).json()["id"]
    fresh_id = request_upload(auth_client).json()["id"]
    stale = MediaAsset.objects.get(pk=stale_id)
    browser_put(stale, make_image(), "image/jpeg")  # загружен, но complete так и не вызван
    MediaAsset.objects.filter(pk=stale_id).update(upload_expires_at=timezone.now() - dt.timedelta(hours=1))
    ready = upload_ready(auth_client, run_on_commit)
    result = cleanup_expired_uploads()
    assert result["removed"] == 1
    assert not MediaAsset.objects.filter(pk=stale_id).exists()
    assert get_storage().head(stale.storage_key) is None
    assert MediaAsset.objects.filter(pk=fresh_id, status="pending").exists()
    assert MediaAsset.objects.get(pk=ready.pk).status == "ready"


def test_cleanup_requeues_stuck_processing(auth_client, run_on_commit):
    data = make_image()
    asset_id = request_upload(auth_client, size=len(data)).json()["id"]
    asset = MediaAsset.objects.get(pk=asset_id)
    browser_put(asset, data, "image/jpeg")
    auth_client.post(f"/api/v1/media/{asset_id}/complete")  # задача не выполнилась (on_commit не сработал)
    MediaAsset.objects.filter(pk=asset_id).update(updated_at=timezone.now() - dt.timedelta(hours=2))
    result = run_on_commit(cleanup_expired_uploads)
    assert result["requeued"] == 1
    assert MediaAsset.objects.get(pk=asset_id).status == "ready"


def test_process_media_task_is_noop_for_non_processing(auth_client):
    asset = MediaAssetFactory(status=MediaAsset.Status.READY)
    assert process_media(str(asset.pk)) == MediaAsset.Status.READY
    assert process_media(str(uuid.uuid4())) is None


def test_deleted_during_processing_stays_deleted(auth_client):
    data = make_image()
    asset_id = request_upload(auth_client, size=len(data)).json()["id"]
    asset = MediaAsset.objects.get(pk=asset_id)
    browser_put(asset, data, "image/jpeg")
    auth_client.post(f"/api/v1/media/{asset_id}/complete")
    MediaAsset.objects.filter(pk=asset_id).update(status=MediaAsset.Status.DELETED)
    assert process_media(asset_id) == MediaAsset.Status.DELETED
