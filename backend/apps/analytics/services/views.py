"""Квалифицированные просмотры публичных карточек (раздел 10, MET-08): субъект → владелец → track_view."""
import hashlib
import hmac
import uuid
from dataclasses import dataclass, field

from django.conf import settings

from apps.analytics.services import is_bot, track_view
from apps.common.exceptions import NotFound

COOKIE_NAME = "gv_aid"
COOKIE_MAX_AGE = 60 * 60 * 24 * 365

SUBJECT_EVENTS = {
    "instructor": "profile_viewed",
    "surfer": "profile_viewed",
    "board_model": "board_viewed",
    "board_variant": "board_viewed",
    "spot": "spot_viewed",
    "organization": "organization_viewed",
    "inventory_item": "item_viewed",
}


@dataclass
class Subject:
    event: str
    subject_type: str
    subject_id: str
    owner_account: object = None
    owner_organization: object = None
    context: dict = field(default_factory=dict)


def _as_uuid(value):
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return None


def _by_id_or_slug(qs, value, slug_field):
    pk = _as_uuid(value)
    obj = qs.filter(pk=pk).first() if pk else None
    if obj is None and slug_field:
        obj = qs.filter(**{slug_field: str(value)}).first()
    return obj


def _instructor(value):
    from apps.learning.services.catalog import public_profiles

    profile = _by_id_or_slug(public_profiles().select_related("account"), value, "account__profile__handle")
    if profile:
        return Subject("profile_viewed", "instructor", str(profile.pk), owner_account=profile.account)
    return None


def _surfer(value):
    from apps.accounts.models import UserProfile

    qs = UserProfile.objects.filter(gg_surfer_enabled=True, account__is_active=True,
                                    account__anonymized_at__isnull=True).select_related("account")
    pk = _as_uuid(value)
    profile = (qs.filter(account_id=pk).first() if pk else None) or qs.filter(handle=str(value)).first()
    if profile:
        return Subject("profile_viewed", "surfer", str(profile.account_id), owner_account=profile.account)
    return None


def _board_context(model, variant=None):
    return {"model_id": str(model.pk), "variant_id": str(variant.pk) if variant else None,
            "board_type": model.board_type.code, "board_type_name": model.board_type.name}


def _board_model(value):
    from apps.boards.models import BoardModel
    from apps.organizations.models import Organization

    pk = _as_uuid(value)
    model = (BoardModel.objects.filter(pk=pk, status=BoardModel.Status.PUBLISHED,
                                       workshop__status=Organization.Status.PUBLISHED)
             .select_related("board_type", "workshop").first()) if pk else None
    if model:
        return Subject("board_viewed", "board_model", str(model.pk), owner_organization=model.workshop,
                       context=_board_context(model))
    return None


def _board_variant(value):
    from apps.boards.models import BoardModel, BoardVariant
    from apps.organizations.models import Organization

    pk = _as_uuid(value)
    variant = (BoardVariant.objects.filter(pk=pk, is_active=True, model__status=BoardModel.Status.PUBLISHED,
                                           model__workshop__status=Organization.Status.PUBLISHED)
               .select_related("model__board_type", "model__workshop").first()) if pk else None
    if variant:
        return Subject("board_viewed", "board_variant", str(variant.pk), owner_organization=variant.model.workshop,
                       context=_board_context(variant.model, variant))
    return None


def _spot(value):
    from apps.spots.models import Spot

    spot = _by_id_or_slug(Spot.objects.filter(status=Spot.Status.PUBLISHED), value, "slug")
    if spot:
        return Subject("spot_viewed", "spot", str(spot.pk), context={"region": spot.region_id})
    return None


def _organization(value):
    from apps.organizations.models import Organization

    org = _by_id_or_slug(Organization.objects.filter(status=Organization.Status.PUBLISHED), value, "slug")
    if org:
        return Subject("organization_viewed", "organization", str(org.pk), owner_organization=org,
                       context={"kind": org.kind})
    return None


def _inventory_item(value):
    from apps.inventory.models import InventoryItem

    pk = _as_uuid(value)
    item = (InventoryItem.objects.filter(pk=pk, is_published=True)
            .exclude(status__in=[InventoryItem.Status.RETIRED, InventoryItem.Status.SOLD])
            .select_related("owner_account", "owner_organization").first()) if pk else None
    if item:
        return Subject("item_viewed", "inventory_item", str(item.pk), owner_account=item.owner_account,
                       owner_organization=item.owner_organization, context={"kind": item.kind, "purpose": item.purpose})
    return None


RESOLVERS = {
    "instructor": _instructor,
    "surfer": _surfer,
    "board_model": _board_model,
    "board_variant": _board_variant,
    "spot": _spot,
    "organization": _organization,
    "inventory_item": _inventory_item,
}


def resolve_subject(subject_type, subject_id):
    subject = RESOLVERS[subject_type](subject_id)
    if subject is None:
        raise NotFound("Объект не найден или не опубликован.", code="subject_not_found")
    return subject


def _client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    return (forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")) or ""


def anonymous_viewer_id(request):
    """(id, is_new). Без cookie — стабильный псевдоним из HMAC(IP + User-Agent): повторные запросы клиента без
    cookie не накручивают просмотры, а сам IP не хранится."""
    existing = request.COOKIES.get(COOKIE_NAME, "")
    if existing and len(existing) <= 64:
        return existing, False
    raw = f"{_client_ip(request)}|{request.META.get('HTTP_USER_AGENT', '')}".encode()
    digest = hmac.new(settings.SECRET_KEY.encode(), raw, hashlib.sha256).hexdigest()[:32]
    return f"h{digest}", True


def record_view(request, subject_type, subject_id):
    """Возвращает (subject, event | None, anonymous_id, is_new_cookie). Неизвестный/неопубликованный объект → 404."""
    subject = resolve_subject(subject_type, subject_id)
    aid, is_new = anonymous_viewer_id(request)
    if is_bot(request):
        return subject, None, aid, is_new
    event = track_view(subject.event, request, subject_type=subject.subject_type, subject_id=subject.subject_id,
                       owner_account=subject.owner_account, owner_organization=subject.owner_organization,
                       context=subject.context, anon_id=aid)
    return subject, event, aid, is_new
