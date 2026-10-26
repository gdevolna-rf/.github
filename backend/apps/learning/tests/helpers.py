"""Тестовые помощники learning/analytics (общие фабрики — tests/factories.py)."""
import datetime as dt
import uuid
from decimal import Decimal

from django.utils import timezone

from apps.accounts.models import Specialty
from apps.commerce.models import Booking
from apps.learning.models import InstructorCertificate, InstructorProfile, LessonSession
from apps.mediafiles.models import MediaAsset
from apps.organizations.models import Membership
from tests.factories import (
    AccountFactory,
    InstructorOfferFactory,
    InstructorProfileFactory,
    LessonSessionFactory,
    MediaAssetFactory,
    OrganizationFactory,
    RegionFactory,
    SchoolProgramFactory,
    SpotFactory,
    add_member,
    add_specialty,
    future,
)

S = Booking.Status


def instructor_account(**kwargs):
    account = AccountFactory(**kwargs)
    add_specialty(account, Specialty.INSTRUCTOR)
    return account


def published_instructor(account=None, *, region=None, spots=(), price_from=Decimal("3500"), **fields):
    """Опубликованная карточка, удовлетворяющая ACC-15."""
    account = account or instructor_account()
    defaults = dict(status=InstructorProfile.Status.PUBLISHED, headline="Инструктор по сёрфингу",
                    formats=["individual"], price_from=price_from, published_at=timezone.now())
    defaults.update(fields)
    profile = InstructorProfileFactory(account=account, **defaults)
    profile.regions.add(region or RegionFactory())
    for spot in spots:
        profile.spots.add(spot)
    return profile


def school(owner=None, **kwargs):
    if owner is not None:
        kwargs["owner"] = owner
    return OrganizationFactory(**kwargs)


def school_instructor(org, account=None, role=Membership.Role.INSTRUCTOR):
    account = account or instructor_account()
    add_member(org, account, role)
    return account


def school_session(org=None, *, instructor=None, start=None, hours=24, duration=2, capacity=6, **kwargs):
    program = kwargs.pop("program", None) or SchoolProgramFactory(organization=org or OrganizationFactory())
    start = start or future(hours=hours, duration=duration)[0]
    return LessonSessionFactory(program=program, organization=program.organization, instructor=instructor,
                                starts_at=start, ends_at=start + dt.timedelta(hours=duration), capacity=capacity,
                                **kwargs)


def private_session(profile, *, start=None, hours=24, duration=2, offer=None, capacity=None, **kwargs):
    offer = offer or InstructorOfferFactory(instructor=profile, capacity=capacity or 1)
    start = start or future(hours=hours, duration=duration)[0]
    return LessonSession.objects.create(
        offer=offer, instructor=profile.account, title=offer.title, starts_at=start,
        ends_at=start + dt.timedelta(hours=duration), capacity=capacity or offer.capacity, price=offer.price, **kwargs)


def past_start(hours_ago=3):
    return timezone.now().replace(microsecond=0) - dt.timedelta(hours=hours_ago)


def booking(session, customer=None, status=S.CONFIRMED, seats=1, **kwargs):
    customer = customer or AccountFactory()
    provider = ({"provider_organization": session.organization} if session.organization_id
                else {"provider_account": session.offer.instructor.account})
    now = timezone.now()
    defaults = dict(
        kind=Booking.Kind.LESSON, lesson_session=session, customer=customer, starts_at=session.starts_at,
        ends_at=session.ends_at, seats=seats, status=status,
        confirmed_at=now if status in (S.CONFIRMED, S.IN_PROGRESS, S.COMPLETED, S.NO_SHOW) else None,
        completed_at=now if status == S.COMPLETED else None, **provider,
    )
    defaults.update(kwargs)
    return Booking.objects.create(**defaults)


def certificate(profile, status=InstructorCertificate.Status.UPLOADED, **kwargs):
    document = MediaAssetFactory(owner=profile.account, kind=MediaAsset.Kind.DOCUMENT,
                                 purpose=MediaAsset.Purpose.CERTIFICATE, visibility=MediaAsset.Visibility.PRIVATE,
                                 content_type="application/pdf",
                                 storage_key=f"private/certificates/{uuid.uuid4().hex}.pdf")
    return InstructorCertificate.objects.create(instructor=profile, title=kwargs.pop("title", "ISA Level 1"),
                                                document=document, status=status, **kwargs)


def gallery_media(owner, kind=MediaAsset.Kind.IMAGE, purpose=MediaAsset.Purpose.PROFILE_GALLERY, **kwargs):
    return MediaAssetFactory(owner=owner, kind=kind, purpose=purpose, **kwargs)


def private_document(owner, **kwargs):
    return MediaAssetFactory(owner=owner, kind=MediaAsset.Kind.DOCUMENT, purpose=MediaAsset.Purpose.CERTIFICATE,
                             visibility=MediaAsset.Visibility.PRIVATE, content_type="application/pdf",
                             storage_key=f"private/certificates/{uuid.uuid4().hex}.pdf", **kwargs)


__all__ = ["AccountFactory", "SpotFactory", "RegionFactory", "OrganizationFactory", "SchoolProgramFactory",
           "InstructorOfferFactory", "future", "add_member"]
