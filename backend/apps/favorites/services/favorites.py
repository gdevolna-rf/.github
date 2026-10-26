"""Избранное (8.6, MSG-11, ATX-11): только реальные опубликованные объекты, идемпотентно, без IDOR."""
import uuid

from django.db import IntegrityError, transaction
from django.db.models import Prefetch, Q

from apps.boards.models import BoardMedia, BoardVariant
from apps.common.exceptions import DomainError, NotFound
from apps.favorites.models import TARGET_FIELDS, Favorite
from apps.inventory.models import InventoryItemPhoto
from apps.learning.models import InstructorCertificate
from apps.organizations.models import Organization
from apps.search.services import catalog
from apps.spots.models import SpotPhoto

TARGET_TYPES = list(TARGET_FIELDS)

PUBLIC_QUERYSETS = {
    Favorite.Target.SPOT: catalog.public_spots,
    Favorite.Target.INSTRUCTOR: catalog.public_instructors,
    Favorite.Target.ORGANIZATION: catalog.public_organizations,
    Favorite.Target.BOARD_MODEL: catalog.public_board_models,
    Favorite.Target.INVENTORY_ITEM: catalog.public_inventory_items,
}

CARD_BUILDERS = {
    Favorite.Target.SPOT: catalog.spot_card,
    Favorite.Target.INSTRUCTOR: catalog.instructor_card,
    Favorite.Target.ORGANIZATION: catalog.organization_card,
    Favorite.Target.BOARD_MODEL: catalog.board_model_card,
    Favorite.Target.INVENTORY_ITEM: catalog.inventory_item_card,
}

# ?type= для вкладок «Избранного»: типы целей + удобные подтипы организаций.
TYPE_FILTERS = {
    "spot": Q(target_type=Favorite.Target.SPOT),
    "instructor": Q(target_type=Favorite.Target.INSTRUCTOR),
    "organization": Q(target_type=Favorite.Target.ORGANIZATION),
    "school": Q(target_type=Favorite.Target.ORGANIZATION, organization__kind=Organization.Kind.SCHOOL),
    "shaper": Q(target_type=Favorite.Target.ORGANIZATION, organization__kind=Organization.Kind.WORKSHOP),
    "rental": Q(target_type=Favorite.Target.ORGANIZATION, organization__kind=Organization.Kind.RENTAL),
    "board_model": Q(target_type=Favorite.Target.BOARD_MODEL),
    "inventory_item": Q(target_type=Favorite.Target.INVENTORY_ITEM),
}


def _require_type(target_type):
    if target_type not in PUBLIC_QUERYSETS:
        raise DomainError("favorite_type_invalid", "Неизвестный тип объекта для избранного.",
                          fields={"target_type": [f"Допустимые значения: {', '.join(TARGET_TYPES)}."]})


def _parse_uuid(value):
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        return None


def resolve_public_target(target_type, target_id):
    """Опубликованный объект или NotFound. Для инструктора принимается id профиля или id аккаунта."""
    _require_type(target_type)
    pk = _parse_uuid(target_id)
    qs = PUBLIC_QUERYSETS[target_type]()
    target = qs.filter(pk=pk).first() if pk else None
    if target is None and pk and target_type == Favorite.Target.INSTRUCTOR:
        target = qs.filter(account_id=pk).first()
    if target is None:
        raise NotFound("Объект не найден или ещё не опубликован.", code="favorite_target_not_found")
    return target


def add_favorite(account, target_type, target_id):
    """Идемпотентно: повтор возвращает существующую запись. → (favorite, created)."""
    target = resolve_public_target(target_type, target_id)
    field = TARGET_FIELDS[target_type]
    existing = Favorite.objects.filter(account=account, **{field: target}).first()
    if existing:
        return existing, False
    try:
        with transaction.atomic():
            return Favorite.objects.create(account=account, target_type=target_type, **{field: target}), True
    except IntegrityError:  # параллельный повтор того же запроса
        return Favorite.objects.get(account=account, **{field: target}), False


def remove_favorite(account, target_type, target_id):
    """Идемпотентно удаляет запись из своего избранного. Возвращает число удалённых строк."""
    _require_type(target_type)
    pk = _parse_uuid(target_id)
    if pk is None:
        return 0
    field = TARGET_FIELDS[target_type]
    lookup = Q(**{f"{field}_id": pk})
    if target_type == Favorite.Target.INSTRUCTOR:
        lookup |= Q(instructor__account_id=pk)
    deleted, _ = Favorite.objects.filter(account=account, target_type=target_type).filter(lookup).delete()
    return deleted


def visible_q():
    """Запись видна, пока её цель опубликована (скрытые модератором объекты не раскрываются)."""
    return (
        Q(target_type=Favorite.Target.SPOT, spot__in=catalog.public_spots().values("pk"))
        | Q(target_type=Favorite.Target.INSTRUCTOR, instructor__in=catalog.public_instructors().values("pk"))
        | Q(target_type=Favorite.Target.ORGANIZATION, organization__in=catalog.public_organizations().values("pk"))
        | Q(target_type=Favorite.Target.BOARD_MODEL, board_model__in=catalog.public_board_models().values("pk"))
        | Q(target_type=Favorite.Target.INVENTORY_ITEM,
            inventory_item__in=catalog.public_inventory_items().values("pk"))
    )


TYPE_ALIASES = {
    "spots": "spot", "instructors": "instructor", "organizations": "organization", "schools": "school",
    "shapers": "shaper", "workshop": "shaper", "workshops": "shaper", "rentals": "rental", "boards": "board_model",
    "board": "board_model", "equipment": "inventory_item", "inventory": "inventory_item",
}


def parse_type_filter(value):
    if not value:
        return None
    key = value.strip().lower()
    key = TYPE_ALIASES.get(key, key)
    if key not in TYPE_FILTERS:
        raise DomainError("favorite_type_invalid", "Неизвестный тип избранного.",
                          fields={"type": [f"Допустимые значения: {', '.join(TYPE_FILTERS)}."]})
    return TYPE_FILTERS[key]


def favorites_for(account, type_filter=None):
    qs = Favorite.objects.filter(account=account).filter(visible_q())
    if type_filter is not None:
        qs = qs.filter(type_filter)
    return (qs.select_related(
        "spot__region", "spot__cover",
        "instructor__account__profile__avatar",
        "organization__region", "organization__logo", "organization__cover",
        "board_model__workshop", "board_model__board_type",
        "inventory_item__region", "inventory_item__spot", "inventory_item__owner_organization",
        "inventory_item__owner_account__profile",
    ).prefetch_related(
        Prefetch("spot__photos", queryset=SpotPhoto.objects.select_related("media")),
        "instructor__regions",
        Prefetch("instructor__certificates",
                 queryset=InstructorCertificate.objects.filter(status=InstructorCertificate.Status.VERIFIED),
                 to_attr="verified_certificates"),
        Prefetch("board_model__media_items", queryset=BoardMedia.objects.select_related("media")),
        Prefetch("board_model__variants", queryset=BoardVariant.objects.filter(is_active=True),
                 to_attr="active_variants"),
        Prefetch("inventory_item__photos", queryset=InventoryItemPhoto.objects.select_related("media")),
    ).order_by("-created_at", "-id"))


def favorite_data(favorite):
    return {
        "target_type": favorite.target_type,
        "target_id": str(favorite.target_id),
        "created_at": favorite.created_at,
        "card": CARD_BUILDERS[favorite.target_type](favorite.target),
    }


def favorite_ids(account):
    """{spot: [...], instructor: [...], ...} — для состояния «сердечек» в каталогах."""
    result = {target: [] for target in TARGET_TYPES}
    rows = (Favorite.objects.filter(account=account).filter(visible_q())
            .order_by("-created_at", "-id")
            .values_list("target_type", *[f"{f}_id" for f in TARGET_FIELDS.values()]))
    for target_type, *ids in rows:
        value = next((v for v in ids if v is not None), None)
        if value is not None:
            result[target_type].append(str(value))
    return result
