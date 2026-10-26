"""Общие фабрики тестовых данных. Доменные тесты могут добавлять свои фабрики рядом."""
import datetime as dt
import uuid
from decimal import Decimal

import factory
from django.utils import timezone

from apps.accounts.models import Account, Specialty, StaffRole, UserProfile, UserSpecialty
from apps.boards.models import BoardModel, BoardType, BoardVariant, WorkshopProfile
from apps.inventory.models import InventoryItem
from apps.learning.models import InstructorOffer, InstructorProfile, LessonSession, SchoolProgram
from apps.mediafiles.models import MediaAsset
from apps.organizations.models import Membership, Organization
from apps.spots.models import Region, Spot


class AccountFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Account
        skip_postgeneration_save = True

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    email_verified_at = factory.LazyFunction(timezone.now)
    password = factory.PostGenerationMethodCall("set_password", "Passw0rd!x")

    @factory.post_generation
    def profile(self, create, extracted, **kwargs):
        if not create:
            return
        self.save()
        UserProfile.objects.get_or_create(
            account=self,
            defaults={"handle": f"u-{uuid.uuid4().hex[:10]}", "first_name": kwargs.get("first_name", "Тест"),
                      "last_name": kwargs.get("last_name", "Пользователь")},
        )
        UserSpecialty.objects.get_or_create(account=self, specialty_id=Specialty.SURFER, defaults={"is_primary": True})


def add_specialty(account, code):
    obj, _ = UserSpecialty.objects.update_or_create(
        account=account, specialty_id=code, defaults={"status": UserSpecialty.Status.ACTIVE, "disabled_at": None}
    )
    return obj


def make_moderator(account, role=StaffRole.Role.MODERATOR):
    StaffRole.objects.get_or_create(account=account, role=role, revoked_at=None)
    return account


class RegionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Region
        django_get_or_create = ("slug",)

    slug = factory.Sequence(lambda n: f"region-{n}")
    name = factory.Sequence(lambda n: f"Регион {n}")
    timezone = "Asia/Kamchatka"


class SpotFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Spot

    slug = factory.Sequence(lambda n: f"spot-{n}")
    name = factory.Sequence(lambda n: f"Спот {n}")
    region = factory.SubFactory(RegionFactory)
    lat = Decimal("52.950000")
    lng = Decimal("158.700000")
    best_wind_directions = ["N", "NW"]
    best_swell_directions = ["S", "SE"]


class MediaAssetFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = MediaAsset

    owner = factory.SubFactory(AccountFactory)
    kind = MediaAsset.Kind.IMAGE
    purpose = MediaAsset.Purpose.BOARD_PHOTO
    status = MediaAsset.Status.READY
    storage_key = factory.Sequence(lambda n: f"public/test/{n}.jpg")
    content_type = "image/jpeg"
    size_bytes = 1024


class OrganizationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Organization
        skip_postgeneration_save = True

    kind = Organization.Kind.SCHOOL
    name = factory.Sequence(lambda n: f"Организация {n}")
    slug = factory.Sequence(lambda n: f"org-{n}")
    owner = factory.SubFactory(AccountFactory)
    status = Organization.Status.PUBLISHED

    @factory.post_generation
    def owner_membership(self, create, extracted, **kwargs):
        if create:
            Membership.objects.get_or_create(
                organization=self, account=self.owner, status=Membership.Status.ACTIVE,
                defaults={"role": Membership.Role.OWNER},
            )


def add_member(org, account, role=Membership.Role.INSTRUCTOR):
    return Membership.objects.create(organization=org, account=account, role=role)


class WorkshopFactory(OrganizationFactory):
    kind = Organization.Kind.WORKSHOP

    @factory.post_generation
    def workshop_profile(self, create, extracted, **kwargs):
        if create:
            WorkshopProfile.objects.get_or_create(organization=self, defaults={"shaper_code": f"S{uuid.uuid4().hex[:4].upper()}"})
            add_specialty(self.owner, Specialty.SHAPER)


class BoardModelFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = BoardModel

    workshop = factory.SubFactory(WorkshopFactory)
    name = factory.Sequence(lambda n: f"Модель {n}")
    slug = factory.Sequence(lambda n: f"model-{n}")
    board_type = factory.LazyFunction(lambda: BoardType.objects.get(workshop=None, code="shortboard"))
    status = BoardModel.Status.PUBLISHED


class BoardVariantFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = BoardVariant

    model = factory.SubFactory(BoardModelFactory)
    sku = factory.Sequence(lambda n: f"SKU-{n:05d}")
    length_in = Decimal("70")
    width_in = Decimal("20.5")
    thickness_in = Decimal("2.6")
    volume_l = Decimal("38.5")
    price = Decimal("65000")


class InventoryItemFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = InventoryItem

    owner_account = factory.SubFactory(AccountFactory)
    kind = InventoryItem.Kind.BOARD
    purpose = InventoryItem.Purpose.RENTAL
    title = factory.Sequence(lambda n: f"Доска в аренду {n}")
    rental_price_per_day = Decimal("2500")


class InstructorProfileFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = InstructorProfile
        skip_postgeneration_save = True

    account = factory.SubFactory(AccountFactory)
    status = InstructorProfile.Status.PUBLISHED
    headline = "Инструктор по сёрфингу"

    @factory.post_generation
    def specialty(self, create, extracted, **kwargs):
        if create:
            add_specialty(self.account, Specialty.INSTRUCTOR)


class InstructorOfferFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = InstructorOffer

    instructor = factory.SubFactory(InstructorProfileFactory)
    title = "Индивидуальное занятие"
    price = Decimal("4000")


class SchoolProgramFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SchoolProgram

    organization = factory.SubFactory(OrganizationFactory)
    title = "Группа для начинающих"
    price = Decimal("3500")
    max_group_size = 6


def future(hours=24, duration=2):
    start = timezone.now().replace(minute=0, second=0, microsecond=0) + dt.timedelta(hours=hours)
    return start, start + dt.timedelta(hours=duration)


class LessonSessionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = LessonSession

    program = factory.SubFactory(SchoolProgramFactory)
    organization = factory.SelfAttribute("program.organization")
    title = "Занятие"
    starts_at = factory.LazyFunction(lambda: future()[0])
    ends_at = factory.LazyAttribute(lambda o: o.starts_at + dt.timedelta(hours=2))
    capacity = 6
