"""Публичный каталог досок и шейперов (SHP-07/08/09, NAV-02, ATX-02): только опубликованные модели
опубликованных мастерских, без требований к специальности посетителя."""
from collections import defaultdict
from decimal import Decimal, InvalidOperation

from django.db.models import (Count, Exists, F, IntegerField, Max, Min, OuterRef, Prefetch, Q, Subquery, Value)
from django.db.models.functions import Coalesce

from apps.boards.models import BoardMedia, BoardModel, BoardType, BoardVariant, Material
from apps.boards.services.availability import SALE_PURPOSES
from apps.boards.services.dimensions import parse_inches
from apps.common.exceptions import DomainError
from apps.inventory.models import InventoryItem
from apps.organizations.models import Organization

MODEL_CARD_LIMIT_PER_SHAPER = 8


def public_workshops():
    return Organization.objects.filter(kind=Organization.Kind.WORKSHOP, status=Organization.Status.PUBLISHED,
                                       workshop__isnull=False)


def _active_variants():
    return BoardVariant.objects.filter(is_active=True)


def items_for_sale_count():
    return Count("items", filter=Q(items__purpose__in=SALE_PURPOSES, items__status=InventoryItem.Status.AVAILABLE,
                                   items__is_published=True))


def variant_prefetch(active_only=True, to_attr="prefetched_variants"):
    qs = BoardVariant.objects.select_related("material").annotate(items_available_for_sale=items_for_sale_count())
    if active_only:
        qs = qs.filter(is_active=True)
    return Prefetch("variants", queryset=qs.order_by("length_in", "width_in", "sku"), to_attr=to_attr)


def media_prefetch():
    return Prefetch("media_items", queryset=BoardMedia.objects.select_related("media").order_by("position", "id"),
                    to_attr="prefetched_media")


def annotate_cards(qs):
    """Агрегаты карточки по активным вариантам: цена «от», диапазоны размеров, наличие, число фото."""
    active = Q(variants__is_active=True)
    photos = (BoardMedia.objects.filter(model=OuterRef("pk"))
              .filter(Q(variant__isnull=True) | Q(variant__is_active=True))
              .order_by().values("model").annotate(n=Count("pk")).values("n"))
    return qs.annotate(
        price_from=Min("variants__price", filter=active),
        length_min_in=Min("variants__length_in", filter=active),
        length_max_in=Max("variants__length_in", filter=active),
        volume_min_l=Min("variants__volume_l", filter=active),
        volume_max_l=Max("variants__volume_l", filter=active),
        variants_count=Count("variants", filter=active, distinct=True),
        photos_count=Coalesce(Subquery(photos, output_field=IntegerField()), Value(0)),
        has_in_stock=Exists(_active_variants().filter(model=OuterRef("pk"),
                                                       availability=BoardVariant.Availability.IN_STOCK)),
        has_made_to_order=Exists(_active_variants().filter(model=OuterRef("pk"),
                                                           availability=BoardVariant.Availability.MADE_TO_ORDER)),
    )


def card_queryset(qs):
    return annotate_cards(qs).select_related(
        "board_type", "workshop", "workshop__workshop", "workshop__logo", "workshop__region", "video",
    ).prefetch_related(variant_prefetch(), media_prefetch())


def public_models():
    return BoardModel.objects.filter(
        status=BoardModel.Status.PUBLISHED, workshop__in=public_workshops(),
    ).filter(Exists(_active_variants().filter(model=OuterRef("pk"))))


def _decimal(params, name):
    value = params.get(name)
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value).replace(",", "."))
    except InvalidOperation as exc:
        raise DomainError("validation_error", "Некорректный фильтр.", fields={name: ["Ожидается число."]}) from exc


def _inches(params, name):
    value = params.get(name)
    if value in (None, ""):
        return None
    try:
        return parse_inches(value)
    except ValueError as exc:
        raise DomainError("validation_error", "Некорректный фильтр размера.", fields={name: [str(exc)]}) from exc


def _bool(params, name):
    value = params.get(name)
    if value in (None, ""):
        return None
    return str(value).lower() in ("1", "true", "yes", "on")


def _region_q(value, field):
    if str(value).isdigit():
        return Q(**{f"{field}_id": int(value)})
    return Q(**{f"{field}__slug": value})


def filter_models(qs, params):
    """Фильтры «Все доски». Условия по вариантам применяются к одному и тому же активному варианту."""
    types = [t.strip() for t in (params.get("type") or "").split(",") if t.strip()]
    if types:
        qs = qs.filter(board_type__code__in=types)
    if params.get("region"):
        qs = qs.filter(_region_q(params["region"], "workshop__region"))
    if params.get("shaper"):
        qs = qs.filter(workshop__slug=params["shaper"])
    repair = _bool(params, "repair")
    if repair is not None:
        qs = qs.filter(workshop__workshop__does_repair=repair)

    variant_q = Q()
    length_min, length_max = _inches(params, "length_min"), _inches(params, "length_max")
    volume_min, volume_max = _decimal(params, "volume_min"), _decimal(params, "volume_max")
    price_max = _decimal(params, "price_max")
    if length_min is not None:
        variant_q &= Q(length_in__gte=length_min)
    if length_max is not None:
        variant_q &= Q(length_in__lte=length_max)
    if volume_min is not None:
        variant_q &= Q(volume_l__gte=volume_min)
    if volume_max is not None:
        variant_q &= Q(volume_l__lte=volume_max)
    if price_max is not None:
        variant_q &= Q(price__lte=price_max)
    availability = [a.strip() for a in (params.get("availability") or "").split(",") if a.strip()]
    if availability:
        valid = set(BoardVariant.Availability.values)
        if not set(availability) <= valid:
            raise DomainError("validation_error", "Некорректный фильтр наличия.",
                              fields={"availability": [f"Допустимо: {', '.join(sorted(valid))}."]})
        variant_q &= Q(availability__in=availability)
    material = params.get("material")
    if material:
        variant_q &= Q(material_id=int(material)) if str(material).isdigit() else Q(material__name__iexact=material)
    if variant_q:
        qs = qs.filter(Exists(_active_variants().filter(variant_q, model=OuterRef("pk"))))

    q = (params.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(workshop__name__icontains=q) | Q(board_type__name__icontains=q)
                       | Q(workshop__region__name__icontains=q) | Q(description__icontains=q)
                       | Exists(BoardVariant.objects.filter(model=OuterRef("pk"), is_active=True, sku__iexact=q)))
    return qs


MODEL_ORDERING = {
    "new": ["-published_at", "-created_at"],
    "price": [F("price_from").asc(nulls_last=True), "name"],
    "-price": [F("price_from").desc(nulls_last=True), "name"],
    "name": ["name"],
}


def order_models(qs, params):
    return qs.order_by(*MODEL_ORDERING.get(params.get("ordering") or "new", MODEL_ORDERING["new"]))


def filter_shapers(qs, params):
    if params.get("region"):
        qs = qs.filter(_region_q(params["region"], "region"))
    repair = _bool(params, "repair")
    if repair is not None:
        qs = qs.filter(workshop__does_repair=repair)
    types = [t.strip() for t in (params.get("type") or "").split(",") if t.strip()]
    if types:
        qs = qs.filter(Exists(public_models().filter(workshop=OuterRef("pk"), board_type__code__in=types)))
    q = (params.get("q") or "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q) | Q(short_description__icontains=q) | Q(description__icontains=q)
            | Q(city__icontains=q) | Q(region__name__icontains=q) | Q(workshop__specialization__icontains=q)
            | Q(owner__profile__first_name__icontains=q) | Q(owner__profile__last_name__icontains=q)
            | Exists(public_models().filter(workshop=OuterRef("pk")).filter(
                Q(name__icontains=q) | Q(board_type__name__icontains=q)))
        )
    return qs


def shaper_queryset(qs):
    models_count = (public_models().filter(workshop=OuterRef("pk")).order_by().values("workshop")
                    .annotate(n=Count("pk")).values("n"))
    return qs.annotate(
        models_count=Coalesce(Subquery(models_count, output_field=IntegerField()), Value(0)),
    ).select_related("workshop", "workshop__promo_video", "logo", "cover", "region", "owner", "owner__profile",
                     "owner__profile__avatar")


SHAPER_ORDERING = {
    "rating": ["-rating_avg", "-rating_count", "name"],
    "name": ["name"],
    "new": ["-published_at", "name"],
    "models": ["-models_count", "name"],
}


def order_shapers(qs, params):
    return qs.order_by(*SHAPER_ORDERING.get(params.get("ordering") or "rating", SHAPER_ORDERING["rating"]))


def models_by_workshop(workshop_ids, limit=MODEL_CARD_LIMIT_PER_SHAPER):
    """Несколько моделей в карточке шейпера (SHP-09) — одним запросом на страницу."""
    grouped = defaultdict(list)
    qs = card_queryset(public_models().filter(workshop_id__in=workshop_ids)).order_by("-published_at", "-created_at")
    for model in qs:
        if len(grouped[model.workshop_id]) < limit:
            grouped[model.workshop_id].append(model)
    return grouped


def public_board_types():
    """Стандартные типы + пользовательские типы, использованные в опубликованных моделях (для фильтра каталога)."""
    used = public_models().values("board_type_id")
    return BoardType.objects.filter(Q(workshop__isnull=True) | Q(pk__in=used)).order_by("sort_order", "name")


def public_materials():
    used = BoardVariant.objects.filter(is_active=True, model__in=public_models()).values("material_id")
    return Material.objects.filter(Q(workshop__isnull=True) | Q(pk__in=used)).order_by("name")
