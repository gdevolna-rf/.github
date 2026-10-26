"""Редактирование собственного профиля (ACC-07/08, UX-10): фото меняется только здесь."""
from django.db import transaction

from apps.accounts.models import ConsentRecord, UserProfile
from apps.accounts.services import consents, handles
from apps.common.exceptions import DomainError

SIMPLE_FIELDS = (
    "first_name", "last_name", "city", "bio", "fun_facts", "surfing_since", "riding_level", "preferred_board_types",
    "interests", "languages", "phone", "birth_date", "private_contacts", "gg_contact_policy", "gg_show_region",
    "gg_show_age", "show_birthday",
)
CONSENT_FLAGS = {
    "gg_surfer_enabled": ConsentRecord.Kind.GG_SURFER,
    "birthday_greetings_consent": ConsentRecord.Kind.BIRTHDAY,
}


def update_profile(account, data, request=None):
    """data — validated_data ProfileUpdateSerializer. Возвращает обновлённый профиль."""
    from apps.mediafiles.models import MediaAsset
    from apps.mediafiles.services import claim_media
    from apps.spots.models import Region, Spot
    from apps.trust.services.audit import record

    with transaction.atomic():
        profile = UserProfile.objects.select_for_update().get(account=account)
        changed = []
        before_handle = profile.handle

        if "handle" in data and handles.normalize(data["handle"]) != profile.handle:
            handles.change_handle(profile, data["handle"])
            record(account, "profile.handle_changed", profile, before={"handle": before_handle},
                   after={"handle": profile.handle}, request=request)

        for field in SIMPLE_FIELDS:
            if field in data and getattr(profile, field) != data[field]:
                setattr(profile, field, data[field])
                changed.append(field)

        if "avatar_id" in data:
            avatar_id = data["avatar_id"]
            if avatar_id is None:
                if profile.avatar_id:
                    profile.avatar = None
                    changed.append("avatar")
            elif avatar_id != profile.avatar_id:
                profile.avatar = claim_media(avatar_id, account, purposes=[MediaAsset.Purpose.AVATAR],
                                             kinds=[MediaAsset.Kind.IMAGE])
                changed.append("avatar")

        if "region_id" in data:
            region_id = data["region_id"]
            region = None
            if region_id is not None:
                region = Region.objects.filter(pk=region_id).first()
                if region is None:
                    raise DomainError("region_invalid", "Регион не найден.", fields={"region_id": ["Регион не найден."]})
            if profile.region_id != (region.pk if region else None):
                profile.region = region
                changed.append("region")

        for flag, kind in CONSENT_FLAGS.items():
            if flag in data and bool(data[flag]) != getattr(profile, flag):
                setattr(profile, flag, bool(data[flag]))
                changed.append(flag)
                consents.record_consent(account, kind, bool(data[flag]), request)

        if changed:
            profile.save()

        if "favorite_spot_ids" in data:
            ids = list(dict.fromkeys(data["favorite_spot_ids"]))
            spots = list(Spot.objects.filter(pk__in=ids, status=Spot.Status.PUBLISHED))
            if len(spots) != len(ids):
                raise DomainError("spot_invalid", "Некоторые споты не найдены.",
                                  fields={"favorite_spot_ids": ["Спот не найден или не опубликован."]})
            profile.favorite_spots.set(spots)
    return profile
