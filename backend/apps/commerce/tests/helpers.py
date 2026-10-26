"""Помощники тестов commerce/messaging: типовые обращения и брони через API и сервисы."""
import datetime as dt
from decimal import Decimal

from django.utils import timezone

from apps.commerce.models import Booking, Inquiry
from apps.commerce.services.inquiries import create_inquiry
from apps.mediafiles.models import MediaAsset
from apps.organizations.models import Membership
from tests.factories import (
    AccountFactory,
    BoardModelFactory,
    BoardVariantFactory,
    InventoryItemFactory,
    LessonSessionFactory,
    MediaAssetFactory,
    WorkshopFactory,
    add_member,
)


def results(response):
    data = response.json()
    return data["results"] if isinstance(data, dict) and "results" in data else data


def board_inquiry(customer=None, workshop=None, message="Здравствуйте! Есть ли доска в наличии?", **kwargs):
    """Обращение к модели доски мастерской через сервис. Возвращает (inquiry, customer, workshop)."""
    customer = customer or AccountFactory()
    workshop = workshop or WorkshopFactory()
    model = kwargs.pop("model", None) or BoardModelFactory(workshop=workshop)
    BoardVariantFactory(model=model)
    inquiry = create_inquiry(customer, kind=kwargs.pop("kind", Inquiry.Kind.BOARD_PURCHASE), message=message,
                             target_type="board_model", target_id=model.pk, **kwargs)
    return inquiry, customer, workshop


def post_inquiry(client, **payload):
    payload.setdefault("message", "Здравствуйте!")
    return client.post("/api/v1/inquiries", payload, format="json")


def attachment(owner, purpose=MediaAsset.Purpose.MESSAGE_ATTACHMENT, status=MediaAsset.Status.READY,
               visibility=MediaAsset.Visibility.PRIVATE, kind=MediaAsset.Kind.IMAGE):
    return MediaAssetFactory(owner=owner, purpose=purpose, status=status, visibility=visibility, kind=kind,
                             storage_key=f"private/test/{owner.pk}/{timezone.now().timestamp()}-{purpose}.jpg")


def add_manager(org, account=None):
    account = account or AccountFactory()
    add_member(org, account, role=Membership.Role.MANAGER)
    return account


def revoke(org, account):
    Membership.objects.filter(organization=org, account=account, status=Membership.Status.ACTIVE).update(
        status=Membership.Status.REVOKED, revoked_at=timezone.now())


def rental_item(owner=None, **kwargs):
    kwargs.setdefault("rental_price_per_day", Decimal("2500"))
    if owner is not None:
        kwargs["owner_account"] = owner
    return InventoryItemFactory(**kwargs)


def rental_window(hours_from_now=48, duration_hours=4):
    start = timezone.now().replace(minute=0, second=0, microsecond=0) + dt.timedelta(hours=hours_from_now)
    return start, start + dt.timedelta(hours=duration_hours)


def requested_rental(item, customer=None, start=None, end=None):
    if start is None:
        start, end = rental_window()
    return Booking.objects.create(kind=Booking.Kind.RENTAL, customer=customer or AccountFactory(), inventory_item=item,
                                  provider_account=item.owner_account, provider_organization=item.owner_organization,
                                  starts_at=start, ends_at=end, price_amount=Decimal("2500"))


def lesson_session(**kwargs):
    return LessonSessionFactory(**kwargs)


def requested_lesson(session, customer=None, seats=1, status=Booking.Status.REQUESTED):
    return Booking.objects.create(kind=Booking.Kind.LESSON, customer=customer or AccountFactory(),
                                  lesson_session=session, provider_organization=session.organization,
                                  provider_account=None if session.organization_id else session.offer.instructor.account,
                                  starts_at=session.starts_at, ends_at=session.ends_at, seats=seats, status=status)
