"""Доступ к медиа: публичные файлы — всем, закрытые — только по правам; угаданный id → 404 (ATX-23, INS-04)."""
import uuid

import pytest

from apps.commerce.models import Booking, Inquiry
from apps.inventory.models import RentalHandover
from apps.learning.models import InstructorCertificate
from apps.mediafiles.models import MediaAsset
from apps.messaging.models import Conversation, ConversationParticipant, Message, MessageAttachment
from apps.organizations.models import Membership
from tests.factories import (
    AccountFactory,
    InstructorProfileFactory,
    InventoryItemFactory,
    MediaAssetFactory,
    OrganizationFactory,
    add_member,
    future,
    make_moderator,
)

pytestmark = pytest.mark.django_db


def private_asset(owner, purpose=MediaAsset.Purpose.MESSAGE_ATTACHMENT, **kwargs):
    return MediaAssetFactory(owner=owner, purpose=purpose, visibility=MediaAsset.Visibility.PRIVATE,
                             storage_key=f"private/{purpose}/2026/10/{uuid.uuid4().hex}.jpg", **kwargs)


def url_of(client, asset, **params):
    return client.get(f"/api/v1/media/{asset.pk}/url", params)


def test_public_ready_media_is_visible_to_guest(api_client):
    asset = MediaAssetFactory()
    response = api_client.get(f"/api/v1/media/{asset.pk}")
    assert response.status_code == 200
    assert response.json()["url"] == asset.url
    link = url_of(api_client, asset).json()
    assert link == {"url": asset.url, "expires_at": None}


def test_pending_media_visible_only_to_owner(make_client, api_client):
    asset = MediaAssetFactory(status=MediaAsset.Status.PENDING)
    assert make_client(asset.owner).get(f"/api/v1/media/{asset.pk}").status_code == 200
    assert api_client.get(f"/api/v1/media/{asset.pk}").status_code == 404
    assert make_client().get(f"/api/v1/media/{asset.pk}").status_code == 404


def test_url_for_not_ready_media_is_conflict_for_owner(make_client):
    asset = MediaAssetFactory(status=MediaAsset.Status.PROCESSING)
    response = url_of(make_client(asset.owner), asset)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "media_not_ready"


def test_guessed_id_returns_404(auth_client, api_client):
    assert auth_client.get(f"/api/v1/media/{uuid.uuid4()}/url").status_code == 404
    assert api_client.get(f"/api/v1/media/{uuid.uuid4()}").status_code == 404


def test_private_media_owner_gets_short_presigned_url(make_client):
    asset = private_asset(AccountFactory())
    response = url_of(make_client(asset.owner), asset)
    assert response.status_code == 200
    body = response.json()
    assert asset.storage_key in body["url"] and "X-Amz-Signature" in body["url"]
    assert "X-Amz-Expires=120" in body["url"]
    assert body["expires_at"] is not None
    # В описании файла закрытая ссылка не раскрывается.
    assert make_client(asset.owner).get(f"/api/v1/media/{asset.pk}").json()["url"] is None


def test_private_media_hidden_from_stranger_and_guest(make_client, api_client):
    """ATX-23: чужие документы недоступны по угаданному URL."""
    asset = private_asset(AccountFactory(), purpose=MediaAsset.Purpose.CERTIFICATE)
    assert url_of(make_client(), asset).status_code == 404
    assert url_of(api_client, asset).status_code == 404
    assert make_client().get(f"/api/v1/media/{asset.pk}").status_code == 404


def test_moderator_needs_2fa_for_private_media(make_client):
    asset = private_asset(AccountFactory(), purpose=MediaAsset.Purpose.CERTIFICATE)
    moderator = make_moderator(AccountFactory())
    assert url_of(make_client(moderator), asset).status_code == 404
    assert url_of(make_client(moderator, two_factor=True), asset).status_code == 200


def _conversation_with_attachment(customer, provider_account=None, provider_org=None):
    inquiry = Inquiry.objects.create(kind=Inquiry.Kind.GENERAL, customer=customer, provider_account=provider_account,
                                     provider_organization=provider_org, subject="Вопрос")
    conversation = Conversation.objects.create(inquiry=inquiry)
    ConversationParticipant.objects.create(conversation=conversation, account=customer,
                                           role=ConversationParticipant.Role.CUSTOMER)
    asset = private_asset(customer)
    message = Message.objects.create(conversation=conversation, sender=customer, body="Фото")
    MessageAttachment.objects.create(message=message, media=asset)
    return conversation, asset


def test_message_attachment_visible_to_conversation_participants_only(make_client):
    customer, provider = AccountFactory(), AccountFactory()
    conversation, asset = _conversation_with_attachment(customer, provider_account=provider)
    ConversationParticipant.objects.create(conversation=conversation, account=provider,
                                           role=ConversationParticipant.Role.PROVIDER)
    assert url_of(make_client(provider), asset).status_code == 200
    assert url_of(make_client(), asset).status_code == 404


def test_message_attachment_visible_to_provider_org_managers_but_not_after_revocation(make_client):
    customer = AccountFactory()
    org = OrganizationFactory()
    manager = AccountFactory()
    membership = add_member(org, manager, Membership.Role.MANAGER)
    conversation, asset = _conversation_with_attachment(customer, provider_org=org)
    ConversationParticipant.objects.create(conversation=conversation, account=manager, organization=org,
                                           role=ConversationParticipant.Role.MEMBER)
    instructor = AccountFactory()
    add_member(org, instructor, Membership.Role.INSTRUCTOR)
    assert url_of(make_client(org.owner), asset).status_code == 200  # менеджмент организации-исполнителя
    assert url_of(make_client(manager), asset).status_code == 200
    assert url_of(make_client(instructor), asset).status_code == 404  # не участник диалога и не менеджер
    membership.status = Membership.Status.REVOKED
    membership.save()
    assert url_of(make_client(manager), asset).status_code == 404  # отзыв доступа действует сразу


def test_certificate_scan_public_only_when_verified_and_allowed(api_client):
    instructor = InstructorProfileFactory()
    asset = private_asset(instructor.account, purpose=MediaAsset.Purpose.CERTIFICATE)
    certificate = InstructorCertificate.objects.create(instructor=instructor, title="ISA", document=asset)
    assert url_of(api_client, asset).status_code == 404  # загружен, но не проверен (ATX-05)
    certificate.status = InstructorCertificate.Status.VERIFIED
    certificate.save()
    assert url_of(api_client, asset).status_code == 404  # проверен, но показ не разрешён
    certificate.allow_public_scan = True
    certificate.save()
    assert url_of(api_client, asset).status_code == 200


def test_handover_photo_visible_to_booking_parties(make_client):
    item = InventoryItemFactory()
    customer = AccountFactory()
    start, end = future(48, 4)
    booking = Booking.objects.create(kind=Booking.Kind.RENTAL, customer=customer, provider_account=item.owner_account,
                                     inventory_item=item, starts_at=start, ends_at=end, status="in_progress")
    asset = private_asset(item.owner_account, purpose=MediaAsset.Purpose.HANDOVER_PHOTO)
    handover = RentalHandover.objects.create(booking=booking, kind=RentalHandover.Kind.ISSUE, condition="good",
                                             recorded_by=item.owner_account)
    handover.photos.add(asset)
    assert url_of(make_client(customer), asset).status_code == 200
    assert url_of(make_client(), asset).status_code == 404


def test_data_export_is_downloaded_as_attachment(make_client):
    asset = private_asset(AccountFactory(), purpose=MediaAsset.Purpose.DATA_EXPORT, kind=MediaAsset.Kind.DOCUMENT,
                          content_type="application/json", original_filename="gdevolna-data.json")
    body = url_of(make_client(asset.owner), asset).json()
    assert "response-content-disposition=attachment" in body["url"]


def test_thumbnail_variant_for_private_image(make_client):
    asset = private_asset(AccountFactory(), thumbnail_key="private/x.jpg.thumb.webp")
    body = url_of(make_client(asset.owner), asset, variant="thumbnail").json()
    assert "private/x.jpg.thumb.webp" in body["url"]


def test_thumbnail_variant_missing_is_400(make_client):
    asset = private_asset(AccountFactory())
    response = url_of(make_client(asset.owner), asset, variant="thumbnail")
    assert response.status_code == 400


def test_deleted_media_is_not_found_even_for_owner(make_client):
    asset = MediaAssetFactory(status=MediaAsset.Status.DELETED)
    assert make_client(asset.owner).get(f"/api/v1/media/{asset.pk}").status_code == 404


def test_presigned_url_uses_request_host(make_client):
    asset = private_asset(AccountFactory())
    response = make_client(asset.owner).get(f"/api/v1/media/{asset.pk}/url", HTTP_HOST="localhost:8080")
    assert response.json()["url"].startswith("http://localhost:8080/gdevolna-media/private/")

