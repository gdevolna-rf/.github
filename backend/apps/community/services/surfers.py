"""Каталог GG Surfer (COM-02/03, BR-12, ACC-06, CLB-04).

В каталог попадают только аккаунты с отдельным согласием gg_surfer_enabled, активные, не анонимизированные и без
ограничения профиля модератором. Карточка раскрывает только добровольно публичные поля: регион — при gg_show_region,
возраст (число лет, не дата) — при gg_show_age, никогда email/телефон/дату рождения/город/закрытые контакты (ACC-14).
"""
import uuid

from django.db.models import Prefetch, Q
from django.utils import timezone

from apps.accounts.models import HandleRedirect, UserProfile
from apps.common.exceptions import NotFound
from apps.messaging.models import AccountBlock
from apps.search.services.catalog import active_restriction_exists, excerpt, public_media, region_data, spot_ref
from apps.spots.models import Region, Spot
from apps.trust.models import AccountRestriction


def _authenticated(viewer):
    return bool(viewer is not None and getattr(viewer, "is_authenticated", False))


def blocked_account_ids(viewer):
    """Аккаунты, с которыми у зрителя есть блокировка в любую сторону (COM-07)."""
    if not _authenticated(viewer):
        return set()
    rows = AccountBlock.objects.filter(Q(blocker=viewer) | Q(blocked=viewer)).values_list("blocker_id", "blocked_id")
    return {other for pair in rows for other in pair if other != viewer.pk}


def gg_profiles():
    """Все участники GG Surfer, видимые публично (без учёта конкретного зрителя)."""
    return (UserProfile.objects
            .filter(gg_surfer_enabled=True, account__is_active=True, account__anonymized_at__isnull=True)
            .filter(~active_restriction_exists(AccountRestriction.Kind.SUSPENDED))
            .select_related("account", "avatar", "region"))


def gg_profiles_for(viewer):
    """Каталог для конкретного зрителя: без участников, с которыми есть блокировка."""
    qs = gg_profiles().prefetch_related(Prefetch(
        "favorite_spots", queryset=Spot.objects.filter(status=Spot.Status.PUBLISHED).order_by("name"),
        to_attr="public_favorite_spots"))
    blocked = blocked_account_ids(viewer)
    if blocked:
        qs = qs.exclude(account_id__in=blocked)
    return qs


def is_gg_member(account):
    """Зритель сам участник GG Surfer (для записей дневника с видимостью «community»)."""
    if not _authenticated(account) or account.anonymized_at:
        return False
    profile = getattr(account, "profile", None)
    return bool(profile and profile.gg_surfer_enabled)


def lookup_region(value):
    value = (value or "").strip()
    if not value:
        return None
    if value.isdigit():
        return Region.objects.filter(pk=int(value)).first() or Region.objects.filter(slug=value).first()
    return Region.objects.filter(slug=value).first()


def lookup_public_spot(value):
    """Опубликованный спот по UUID или slug."""
    value = str(value or "").strip()
    if not value:
        return None
    qs = Spot.objects.filter(status=Spot.Status.PUBLISHED)
    try:
        return qs.filter(pk=uuid.UUID(value)).first()
    except ValueError:
        return qs.filter(slug=value).first()


def filter_profiles(qs, params):
    """Фильтры каталога: region, spot, level, interest, board_type, q. Никогда не фильтрует по скрытым полям."""
    region = params.get("region")
    if region:
        obj = lookup_region(region)
        # Регион участвует в фильтре только у тех, кто разрешил его показывать.
        qs = qs.filter(region=obj, gg_show_region=True) if obj else qs.none()
    spot = params.get("spot")
    if spot:
        obj = lookup_public_spot(spot)
        qs = qs.filter(favorite_spots=obj) if obj else qs.none()
    level = params.get("level")
    if level:
        qs = qs.filter(riding_level=level)
    interest = (params.get("interest") or "").strip()
    if interest:
        qs = qs.filter(interests__icontains=interest)
    board_type = (params.get("board_type") or "").strip()
    if board_type:
        qs = qs.filter(preferred_board_types__icontains=board_type)
    q = (params.get("q") or "").strip()
    if q:
        for term in q.split()[:6]:
            qs = qs.filter(
                Q(first_name__icontains=term) | Q(last_name__icontains=term) | Q(handle__icontains=term)
                | Q(bio__icontains=term) | Q(interests__icontains=term)
                | Q(gg_show_region=True, region__name__icontains=term)
            )
    return qs.distinct()


def age_of(birth_date, today=None):
    today = today or timezone.localdate()
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))


def can_message(profile, viewer, blocked_ids=None):
    """Политика контакта GG Surfer: «все участники», нет блокировки в любую сторону, не я сам."""
    if not _authenticated(viewer) or viewer.pk == profile.account_id:
        return False
    if profile.gg_contact_policy != UserProfile.ContactPolicy.EVERYONE:
        return False
    if blocked_ids is None:
        blocked_ids = blocked_account_ids(viewer)
    return profile.account_id not in blocked_ids


def _favorite_spots(profile):
    spots = getattr(profile, "public_favorite_spots", None)
    if spots is None:
        spots = list(profile.favorite_spots.filter(status=Spot.Status.PUBLISHED).order_by("name"))
    return [spot_ref(s) for s in spots]


def surfer_card(profile, viewer=None, blocked_ids=None, today=None):
    today = today or timezone.localdate()
    show_age = profile.gg_show_age and profile.birth_date is not None
    return {
        "id": str(profile.account_id),
        "handle": profile.handle,
        "display_name": profile.display_name,
        "avatar": public_media(profile.avatar) if profile.avatar_id else None,
        "region": region_data(profile.region) if profile.gg_show_region else None,
        "age": age_of(profile.birth_date, today) if show_age else None,
        "riding_level": profile.riding_level or None,
        "riding_level_label": profile.get_riding_level_display() if profile.riding_level else None,
        "surfing_since": profile.surfing_since,
        "experience_years": max(today.year - profile.surfing_since, 0) if profile.surfing_since else None,
        "preferred_board_types": list(profile.preferred_board_types),
        "favorite_spots": _favorite_spots(profile),
        "interests": list(profile.interests),
        "bio_excerpt": excerpt(profile.bio, 200),
        "fun_facts": list(profile.fun_facts),
        "accepts_messages": profile.gg_contact_policy == UserProfile.ContactPolicy.EVERYONE,
        "can_message": can_message(profile, viewer, blocked_ids),
        "is_me": _authenticated(viewer) and viewer.pk == profile.account_id,
        "url": f"/surfers/{profile.handle}",
    }


def get_surfer(handle, viewer):
    """Профиль участника или {"redirect": новый handle} для старого адреса; иначе NotFound."""
    profile = gg_profiles_for(viewer).filter(handle=handle).first()
    if profile is not None:
        return profile, None
    redirect = HandleRedirect.objects.filter(old_handle=handle).select_related("account__profile").first()
    if redirect is not None:
        new_profile = gg_profiles_for(viewer).filter(account_id=redirect.account_id).first()
        if new_profile is not None:
            return None, new_profile.handle
    raise NotFound("Участник не найден или скрыл анкету.", code="surfer_not_found")


def surfer_detail(profile, viewer, diary_stats):
    from apps.learning.models import InstructorProfile

    data = surfer_card(profile, viewer)
    instructor = InstructorProfile.objects.filter(account_id=profile.account_id,
                                                  status=InstructorProfile.Status.PUBLISHED).exists()
    data.update({
        "bio": profile.bio,
        "languages": list(profile.languages),
        "member_since": profile.account.date_joined.year,
        "instructor_url": f"/instructors/{profile.handle}" if instructor else None,
        "diary": diary_stats,
    })
    return data


def members_count():
    return gg_profiles().count()

