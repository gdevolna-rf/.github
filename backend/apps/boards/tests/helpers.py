"""Помощники тестов boards/inventory поверх общих фабрик (tests/factories.py)."""
import datetime as dt
from decimal import Decimal

from django.utils import timezone

from apps.accounts.models import Specialty
from apps.boards.models import BoardMedia, BoardModel, BoardType, BoardVariant
from apps.commerce.models import Booking, Inquiry
from apps.mediafiles.models import MediaAsset
from apps.organizations.models import Organization
from tests.factories import (AccountFactory, BoardModelFactory, BoardVariantFactory, MediaAssetFactory,
                             RegionFactory, WorkshopFactory, add_specialty)


def shaper_account(**kwargs):
    account = AccountFactory(**kwargs)
    add_specialty(account, Specialty.SHAPER)
    return account


def workshop_for(owner=None, **kwargs):
    owner = owner or shaper_account()
    kwargs.setdefault("region", RegionFactory())
    return WorkshopFactory(owner=owner, **kwargs)


def std_type(code="shortboard"):
    return BoardType.objects.get(workshop=None, code=code)


def photo(owner, purpose=MediaAsset.Purpose.BOARD_PHOTO, kind=MediaAsset.Kind.IMAGE, **kwargs):
    return MediaAssetFactory(owner=owner, purpose=purpose, kind=kind, **kwargs)


def video(owner, purpose=MediaAsset.Purpose.BOARD_VIDEO):
    return MediaAssetFactory(owner=owner, purpose=purpose, kind=MediaAsset.Kind.VIDEO, content_type="video/mp4")


def published_model(workshop, *, name="Pacific Fish", board_type=None, variants=None, with_cover=True, **kwargs):
    """Опубликованная модель с вариантами и обложкой."""
    model = BoardModelFactory(workshop=workshop, name=name, board_type=board_type or std_type(),
                              status=BoardModel.Status.PUBLISHED, published_at=timezone.now(), **kwargs)
    for spec in variants or [{}]:
        BoardVariantFactory(model=model, **spec)
    if with_cover:
        BoardMedia.objects.create(model=model, media=photo(workshop.owner), position=0, is_cover=True)
    return model


def variant(model, **kwargs):
    return BoardVariantFactory(model=model, **kwargs)


def inquiry_for(variant_obj, customer=None):
    model = variant_obj.model
    return Inquiry.objects.create(
        kind=Inquiry.Kind.BOARD_PURCHASE, customer=customer or AccountFactory(),
        provider_organization=model.workshop, board_model=model, board_variant=variant_obj,
        subject=f"Покупка {model.name}", object_snapshot={"sku": variant_obj.sku, "length_in": str(variant_obj.length_in)},
    )


def rental_booking(item, *, status=Booking.Status.CONFIRMED, customer=None, start=None, hours=4):
    start = start or (timezone.now().replace(microsecond=0) + dt.timedelta(days=1))
    provider = {"provider_account": item.owner_account} if item.owner_account_id else {
        "provider_organization": item.owner_organization}
    return Booking.objects.create(
        kind=Booking.Kind.RENTAL, status=status, customer=customer or AccountFactory(), inventory_item=item,
        starts_at=start, ends_at=start + dt.timedelta(hours=hours), price_amount=Decimal("2500"), **provider,
    )


def unpublish(org):
    Organization.objects.filter(pk=org.pk).update(status=Organization.Status.DRAFT)


def variants_of(model):
    return BoardVariant.objects.filter(model=model)
