"""Публичный профиль по handle (5.1, ACC-14, BR-12): только публичные поля; поля сообщества — по согласию GG."""
from django.utils import timezone

from apps.accounts.models import HandleRedirect, UserProfile
from apps.accounts.services.specialties import active_codes
from apps.common.exceptions import NotFound


def _age(birth_date):
    if not birth_date:
        return None
    today = timezone.localdate()
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))


def _region(region):
    return {"id": region.pk, "slug": region.slug, "name": region.name} if region else None


def resolve(handle):
    """Возвращает ("profile", profile) или ("redirect", new_handle). Удалённые/неактивные аккаунты → 404."""
    handle = (handle or "").strip().lower()
    profile = UserProfile.objects.select_related("account", "avatar", "region").filter(handle=handle).first()
    if profile is not None:
        if not profile.account.is_active or profile.account.anonymized_at:
            raise NotFound("Профиль не найден.")
        return "profile", profile
    redirect = HandleRedirect.objects.select_related("account__profile").filter(old_handle=handle).first()
    if redirect is not None and redirect.account.is_active and not redirect.account.anonymized_at:
        return "redirect", redirect.account.profile.handle
    raise NotFound("Профиль не найден.")


def build(profile):
    from apps.learning.models import InstructorProfile
    from apps.mediafiles.serializers import MediaSerializer
    from apps.organizations.models import Membership, Organization
    from apps.spots.models import Spot

    account = profile.account
    instructor = InstructorProfile.objects.filter(account=account, status=InstructorProfile.Status.PUBLISHED).first()
    memberships = Membership.objects.filter(
        account=account, status=Membership.Status.ACTIVE, organization__status=Organization.Status.PUBLISHED
    ).select_related("organization").order_by("joined_at")
    avatar = profile.avatar if profile.avatar_id and profile.avatar.status == "ready" else None
    data = {
        "id": account.pk,
        "handle": profile.handle,
        "display_name": profile.display_name,
        "avatar": MediaSerializer(avatar).data if avatar else None,
        "member_since": account.date_joined,
        "specialties": active_codes(account),
        "instructor_profile": {"id": instructor.pk, "handle": profile.handle} if instructor else None,
        "organizations": [
            {"id": m.organization.pk, "slug": m.organization.slug, "name": m.organization.name,
             "kind": m.organization.kind, "role": m.role}
            for m in memberships
        ],
        "gg_surfer": profile.gg_surfer_enabled,
        "gg": None,
    }
    if profile.gg_surfer_enabled:
        spots = profile.favorite_spots.filter(status=Spot.Status.PUBLISHED).values("id", "slug", "name")
        data["gg"] = {
            "bio": profile.bio,
            "fun_facts": profile.fun_facts,
            "surfing_since": profile.surfing_since,
            "riding_level": profile.riding_level,
            "preferred_board_types": profile.preferred_board_types,
            "favorite_spots": list(spots),
            "interests": profile.interests,
            "languages": profile.languages,
            "region": _region(profile.region) if profile.gg_show_region else None,
            "city": profile.city if profile.gg_show_region else "",
            "age": _age(profile.birth_date) if profile.gg_show_age else None,
            "contact_policy": profile.gg_contact_policy,
        }
    return data
