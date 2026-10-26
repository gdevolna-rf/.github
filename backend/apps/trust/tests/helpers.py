"""Вспомогательные фабрики для тестов trust (заказы, диалоги, сертификаты)."""
import datetime as dt
import uuid

from django.utils import timezone

from apps.commerce.models import Booking, Inquiry
from apps.learning.models import InstructorCertificate
from apps.mediafiles.models import MediaAsset
from apps.messaging.models import Conversation, ConversationParticipant, Message
from tests.factories import InventoryItemFactory, LessonSessionFactory, MediaAssetFactory


def completed_lesson_booking(customer, *, organization=None, instructor_account=None, provider_account=None):
    if organization is not None:
        session = LessonSessionFactory(program__organization=organization, organization=organization,
                                       instructor=instructor_account)
        provider = {"provider_organization": organization}
    else:
        session = LessonSessionFactory(instructor=instructor_account)
        provider = {"provider_account": provider_account or instructor_account}
    start = timezone.now() - dt.timedelta(days=3)
    return Booking.objects.create(kind=Booking.Kind.LESSON, customer=customer, lesson_session=session,
                                  starts_at=start, ends_at=start + dt.timedelta(hours=2),
                                  status=Booking.Status.COMPLETED, **provider)


def completed_rental_booking(customer, item=None):
    item = item or InventoryItemFactory()
    start = timezone.now() - dt.timedelta(days=5)
    provider = ({"provider_account": item.owner_account} if item.owner_account_id
                else {"provider_organization": item.owner_organization})
    return Booking.objects.create(kind=Booking.Kind.RENTAL, customer=customer, inventory_item=item, starts_at=start,
                                  ends_at=start + dt.timedelta(days=1), status=Booking.Status.COMPLETED, **provider)


def inquiry(customer, status=Inquiry.Status.COMPLETED, **provider):
    return Inquiry.objects.create(kind=Inquiry.Kind.GENERAL, customer=customer, subject="Ремонт доски",
                                  status=status, **provider)


def certificate(instructor, status=InstructorCertificate.Status.UPLOADED):
    doc = MediaAssetFactory(owner=instructor.account, kind=MediaAsset.Kind.DOCUMENT,
                            purpose=MediaAsset.Purpose.CERTIFICATE, visibility=MediaAsset.Visibility.PRIVATE,
                            storage_key=f"private/certificates/{uuid.uuid4().hex}.pdf", content_type="application/pdf")
    return InstructorCertificate.objects.create(instructor=instructor, title="ISA Level 1", issuer="ISA",
                                                document=doc, status=status)


def conversation_message(sender, other, body="Привет"):
    conv = Conversation.objects.create(kind=Conversation.Kind.DIRECT)
    ConversationParticipant.objects.create(conversation=conv, account=sender, role=ConversationParticipant.Role.PEER)
    ConversationParticipant.objects.create(conversation=conv, account=other, role=ConversationParticipant.Role.PEER)
    return Message.objects.create(conversation=conv, sender=sender, body=body)
