"""Публичные каталоги и типовые карточки объектов (NAV-04, MSG-11, ARCHITECTURE §9).

Единая точка правды «что считается опубликованным» для поиска, избранного и помощника подбора: в выдачу
попадают только опубликованные объекты, аккаунты без анонимизации и блокировки, медиа — только готовые публичные.
Карточка: {title, subtitle, image (MediaSerializer | None), url (маршрут фронтенда), extra {...}}.
"""
from decimal import Decimal

from django.db.models import Prefetch

from apps.boards.models import BoardMedia, BoardModel, BoardVariant
from apps.inventory.models import InventoryItem, InventoryItemPhoto
from apps.learning.models import InstructorCertificate
from apps.mediafiles.models import MediaAsset
from apps.mediafiles.serializers import MediaSerializer
from apps.organizations.models import Organization
from apps.spots.models import Spot, SpotPhoto

# Маршруты фронтенда (ARCHITECTURE §9).
ORGANIZATION_ROUTES = {
    Organization.Kind.SCHOOL: "/schools/{slug}",
    Organization.Kind.WORKSHOP: "/shapers/{slug}",
    # У проката-организации нет собственной страницы в §9 — ведём в каталог аренды с фильтром по владельцу.
    Organization.Kind.RENTAL: "/rentals?organization={slug}",
}
AVAILABILITY_ORDER = [
    BoardVariant.Availability.IN_STOCK,
    BoardVariant.Availability.MADE_TO_ORDER,
    BoardVariant.Availability.OUT_OF_STOCK,
]
HIDDEN_ITEM_STATUSES = [InventoryItem.Status.SOLD, InventoryItem.Status.RETIRED]


# ---------------------------------------------------------------- форматирование

def public_media(asset):
    """Только готовые публичные файлы; иначе None (фронтенд покажет заглушку)."""
    if asset is None or asset.status != MediaAsset.Status.READY or asset.visibility != MediaAsset.Visibility.PUBLIC:
        return None
    return MediaSerializer(asset).data


def money(value):
    if value is None:
        return None
    return f"{Decimal(value):.2f}"


def decimal_str(value, places=2):
    if value is None:
        return None
    return f"{Decimal(value):.{places}f}"


def region_data(region):
    if region is None:
        return None
    return {"id": region.id, "slug": region.slug, "name": region.name}


def spot_ref(spot):
    if spot is None:
        return None
    return {"id": str(spot.pk), "slug": spot.slug, "name": spot.name, "url": f"/spots/{spot.slug}"}


def excerpt(text, limit=200):
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(",.;:—- ")
    return f"{cut}…"


def length_label(length_in):
    """70 → 5′10″ (длина доски в футах и дюймах)."""
    if length_in is None:
        return None
    total = Decimal(length_in)
    feet = int(total // 12)
    inches = total - feet * 12
    inches_str = f"{inches:.1f}".rstrip("0").rstrip(".")
    return f"{feet}′{inches_str}″"


# ---------------------------------------------------------------- публичные querysets

def active_restriction_exists(kind, account_ref="account_id"):
    from apps.trust.services.restrictions import restriction_exists

    return restriction_exists(kind, account_ref)


def public_spots():
    return (Spot.objects.filter(status=Spot.Status.PUBLISHED)
            .select_related("region", "cover")
            .prefetch_related(Prefetch("photos", queryset=SpotPhoto.objects.select_related("media"))))


def public_instructors():
    """Те же правила, что у каталога /instructors (learning.catalog.public_profiles): без ограниченных и удаляемых."""
    from apps.learning.services.catalog import public_profiles

    return (public_profiles()
            .select_related("account__profile__avatar")
            .prefetch_related("regions", Prefetch(
                "certificates",
                queryset=InstructorCertificate.objects.filter(status=InstructorCertificate.Status.VERIFIED),
                to_attr="verified_certificates")))


def public_organizations(kind=None):
    qs = Organization.objects.filter(status=Organization.Status.PUBLISHED).select_related("region", "logo", "cover")
    if kind:
        qs = qs.filter(kind=kind)
    return qs


def public_board_models():
    return (BoardModel.objects
            .filter(status=BoardModel.Status.PUBLISHED, workshop__status=Organization.Status.PUBLISHED)
            .select_related("workshop", "board_type")
            .prefetch_related(
                Prefetch("media_items", queryset=BoardMedia.objects.select_related("media")),
                Prefetch("variants", queryset=BoardVariant.objects.filter(is_active=True), to_attr="active_variants"),
            ))


def public_inventory_items():
    from apps.inventory.services.rentals import visible_owner_q

    return (InventoryItem.objects.filter(is_published=True).exclude(status__in=HIDDEN_ITEM_STATUSES)
            .filter(visible_owner_q())
            .select_related("region", "spot", "owner_organization", "owner_account__profile")
            .prefetch_related(Prefetch("photos", queryset=InventoryItemPhoto.objects.select_related("media"))))


# ---------------------------------------------------------------- изображения

def spot_image(spot):
    image = public_media(spot.cover) if spot.cover_id else None
    if image:
        return image
    for photo in spot.photos.all():
        image = public_media(photo.media)
        if image:
            return image
    return None


def board_model_image(model):
    items = sorted(model.media_items.all(), key=lambda m: (not m.is_cover, m.variant_id is not None, m.position, m.id))
    for item in items:
        if item.media.kind != MediaAsset.Kind.IMAGE:
            continue
        image = public_media(item.media)
        if image:
            return image
    return None


def inventory_item_image(item):
    for photo in item.photos.all():
        image = public_media(photo.media)
        if image:
            return image
    return None


def organization_image(org):
    return public_media(org.logo) or public_media(org.cover)


def instructor_image(instructor):
    profile = getattr(instructor.account, "profile", None)
    return public_media(profile.avatar) if profile and profile.avatar_id else None


# ---------------------------------------------------------------- карточки

def instructor_handle(instructor):
    profile = getattr(instructor.account, "profile", None)
    return profile.handle if profile else None


def instructor_name(instructor):
    profile = getattr(instructor.account, "profile", None)
    return profile.display_name if profile else "Инструктор"


def _verified(instructor):
    certs = getattr(instructor, "verified_certificates", None)
    if certs is None:
        return instructor.certificates.filter(status=InstructorCertificate.Status.VERIFIED).exists()
    return bool(certs)


def spot_card(spot):
    return {
        "title": spot.name,
        "subtitle": " · ".join(filter(None, [spot.region.name, spot.get_difficulty_display()])),
        "image": spot_image(spot),
        "url": f"/spots/{spot.slug}",
        "extra": {
            "slug": spot.slug,
            "region": region_data(spot.region),
            "difficulty": spot.difficulty,
            "difficulty_label": spot.get_difficulty_display(),
            "break_type": spot.break_type,
            "rating_avg": decimal_str(spot.rating_avg),
            "rating_count": spot.rating_count,
        },
    }


def instructor_card(instructor):
    regions = [r.name for r in instructor.regions.all()]
    handle = instructor_handle(instructor)
    return {
        "title": instructor_name(instructor),
        "subtitle": instructor.headline or ", ".join(regions),
        "image": instructor_image(instructor),
        "url": f"/instructors/{handle}",
        "extra": {
            "handle": handle,
            "account_id": str(instructor.account_id),
            "regions": regions,
            "student_levels": list(instructor.student_levels),
            "board_types": list(instructor.board_types),
            "rating_avg": decimal_str(instructor.rating_avg),
            "rating_count": instructor.rating_count,
            "price_from": money(instructor.price_from),
            "currency": instructor.currency,
            "certificate_verified": _verified(instructor),
        },
    }


def organization_url(org):
    return ORGANIZATION_ROUTES.get(org.kind, "/schools/{slug}").format(slug=org.slug, id=org.pk)


def organization_card(org):
    place = org.region.name if org.region_id else org.city
    return {
        "title": org.name,
        "subtitle": " · ".join(filter(None, [org.get_kind_display(), place])),
        "image": organization_image(org),
        "url": organization_url(org),
        "extra": {
            "slug": org.slug,
            "kind": org.kind,
            "kind_label": org.get_kind_display(),
            "region": region_data(org.region),
            "city": org.city,
            "rating_avg": decimal_str(org.rating_avg),
            "rating_count": org.rating_count,
            "price_from": money(org.price_from),
            "currency": org.currency,
            "verified": org.verification_status == Organization.Verification.VERIFIED,
        },
    }


def _active_variants(model):
    variants = getattr(model, "active_variants", None)
    if variants is None:
        variants = list(model.variants.filter(is_active=True))
    return variants


def board_model_card(model):
    variants = _active_variants(model)
    prices = [v.price for v in variants if v.price is not None]
    volumes = [v.volume_l for v in variants if v.volume_l is not None]
    availability = None
    for value in AVAILABILITY_ORDER:
        if any(v.availability == value for v in variants):
            availability = value
            break
    return {
        "title": model.name,
        "subtitle": f"{model.workshop.name} · {model.board_type.name}",
        "image": board_model_image(model),
        "url": f"/boards/{model.pk}",
        "extra": {
            "board_type": {"code": model.board_type.code, "name": model.board_type.name},
            "shaper": {"name": model.workshop.name, "slug": model.workshop.slug,
                       "url": f"/shapers/{model.workshop.slug}"},
            "price_from": money(min(prices)) if prices else None,
            "currency": variants[0].currency if variants else "RUB",
            "volume_min": decimal_str(min(volumes)) if volumes else None,
            "volume_max": decimal_str(max(volumes)) if volumes else None,
            "variants_count": len(variants),
            "availability": availability,
            "availability_label": BoardVariant.Availability(availability).label if availability else None,
        },
    }


def inventory_owner_name(item):
    if item.owner_organization_id:
        return item.owner_organization.name
    profile = getattr(item.owner_account, "profile", None) if item.owner_account_id else None
    return profile.display_name if profile else None


def inventory_item_card(item):
    return {
        "title": item.title,
        "subtitle": " · ".join(filter(None, [item.get_kind_display(), item.size,
                                             item.region.name if item.region_id else ""])),
        "image": inventory_item_image(item),
        "url": f"/rentals/{item.pk}",
        "extra": {
            "kind": item.kind,
            "kind_label": item.get_kind_display(),
            "purpose": item.purpose,
            "size": item.size,
            "condition": item.condition,
            "condition_label": item.get_condition_display(),
            "region": region_data(item.region),
            "spot": spot_ref(item.spot) if item.spot_id and item.spot.status == Spot.Status.PUBLISHED else None,
            "price_per_day": money(item.rental_price_per_day),
            "price_per_hour": money(item.rental_price_per_hour),
            "sale_price": money(item.sale_price),
            "currency": item.currency,
            "owner_name": inventory_owner_name(item),
        },
    }
