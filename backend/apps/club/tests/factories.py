import datetime as dt

import factory
from django.utils import timezone

from apps.accounts.models import StaffRole
from apps.club.models import ClubAnnouncement, ClubEvent, EventRegistration
from tests.factories import AccountFactory


def make_organizer(account=None):
    account = account or AccountFactory()
    StaffRole.objects.get_or_create(account=account, role=StaffRole.Role.ORGANIZER, revoked_at=None)
    return account


class ClubEventFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ClubEvent

    slug = factory.Sequence(lambda n: f"event-{n}")
    title = factory.Sequence(lambda n: f"Совместное катание {n}")
    status = ClubEvent.Status.PUBLISHED
    starts_at = factory.LazyFunction(lambda: timezone.now() + dt.timedelta(days=3))
    ends_at = factory.LazyAttribute(lambda o: o.starts_at + dt.timedelta(hours=3))
    organizer = factory.SubFactory(AccountFactory)


class EventRegistrationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = EventRegistration

    event = factory.SubFactory(ClubEventFactory)
    account = factory.SubFactory(AccountFactory)


class ClubAnnouncementFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ClubAnnouncement

    title = factory.Sequence(lambda n: f"Анонс {n}")
    body = "Текст анонса"
    published_at = factory.LazyFunction(timezone.now)
