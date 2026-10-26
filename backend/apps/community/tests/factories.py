import datetime as dt

import factory
from django.utils import timezone

from apps.community.models import SurfSession
from tests.factories import AccountFactory


def gg_account(**profile_fields):
    """Аккаунт с включённым GG Surfer и заданными полями профиля."""
    account = AccountFactory()
    profile = account.profile
    profile.gg_surfer_enabled = True
    for field, value in profile_fields.items():
        if field == "favorite_spots":
            continue
        setattr(profile, field, value)
    profile.save()
    if "favorite_spots" in profile_fields:
        profile.favorite_spots.set(profile_fields["favorite_spots"])
    return account


class SurfSessionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SurfSession

    account = factory.SubFactory(AccountFactory)
    spot_name = "Халактырский пляж"
    date = factory.LazyFunction(lambda: timezone.localdate() - dt.timedelta(days=3))
    visibility = SurfSession.Visibility.PUBLIC
