"""Сериализаторы каталога досок и кабинета шейпера.

Деньги и размеры — строки-десятичные ("65000.00", "70.00" дюймов) + готовые строки для показа (5'10" × 20 1/2").
Медиа — MediaSerializer, люди — PublicAccountSerializer (без закрытых полей, ACC-14).
"""
import datetime as dt

from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.accounts.serializers_public import PublicAccountSerializer
from apps.boards.models import BoardMedia, BoardModel, BoardType, BoardVariant, Material, WorkshopProfile
from apps.boards.services.availability import best_availability, sale_items_available
from apps.boards.services.dimensions import (format_dimensions, format_inches, format_length, format_volume,
                                             parse_inches)
from apps.boards.services.sku import SHAPER_CODE_RE, normalize_suffix
from apps.boards.services.types import SILHOUETTES
from apps.mediafiles.serializers import MediaSerializer
from apps.organizations.models import Organization
from apps.spots.models import Region

AVAILABILITY_LABELS = dict(BoardVariant.Availability.choices)
FIN_LABELS = dict(BoardVariant.FinSystem.choices)


# ---------------------------------------------------------------- справочники

class BoardsRegionSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    slug = serializers.CharField(read_only=True)
    name = serializers.CharField(read_only=True)


class BoardTypeSerializer(serializers.ModelSerializer):
    is_custom = serializers.SerializerMethodField()

    class Meta:
        model = BoardType
        fields = ["id", "code", "name", "silhouette", "sku_code", "sort_order", "is_custom"]
        read_only_fields = fields

    def get_is_custom(self, obj) -> bool:
        return obj.workshop_id is not None


class BoardTypeShortSerializer(serializers.ModelSerializer):
    class Meta:
        model = BoardType
        fields = ["id", "code", "name", "silhouette"]
        read_only_fields = fields


class BoardTypeWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=40, min_length=2)
    silhouette = serializers.ChoiceField(choices=SILHOUETTES, required=False)
    sort_order = serializers.IntegerField(min_value=0, max_value=1000, required=False)


class MaterialSerializer(serializers.ModelSerializer):
    is_custom = serializers.SerializerMethodField()

    class Meta:
        model = Material
        fields = ["id", "name", "is_custom"]
        read_only_fields = fields

    def get_is_custom(self, obj) -> bool:
        return obj.workshop_id is not None


class MaterialWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=50, min_length=2)


# ---------------------------------------------------------------- медиа

class BoardMediaSerializer(serializers.ModelSerializer):
    variant_id = serializers.UUIDField(read_only=True, allow_null=True)
    media = MediaSerializer(read_only=True)

    class Meta:
        model = BoardMedia
        fields = ["id", "position", "is_cover", "variant_id", "media"]
        read_only_fields = fields


def _model_media(model):
    items = getattr(model, "prefetched_media", None)
    if items is None:
        items = list(model.media_items.select_related("media").order_by("position", "id"))
    return items


def _gallery(model, variant_id=None):
    items = [m for m in _model_media(model) if m.variant_id == variant_id]
    return sorted(items, key=lambda m: (not m.is_cover, m.position, m.id))


def _active_variants(model):
    variants = getattr(model, "prefetched_variants", None)
    if variants is None:
        variants = list(model.variants.filter(is_active=True).select_related("material").order_by("length_in", "width_in"))
    return [v for v in variants if v.is_active]


def model_cover(model):
    gallery = _gallery(model)
    if gallery:
        return gallery[0].media
    active_ids = {v.pk for v in _active_variants(model)}
    for item in sorted(_model_media(model), key=lambda m: (not m.is_cover, m.position, m.id)):
        if item.variant_id in active_ids:
            return item.media
    return None


# ---------------------------------------------------------------- шейпер (мастерская)

def _profile(org):
    try:
        return org.workshop
    except WorkshopProfile.DoesNotExist:
        return None


class ShaperMiniSerializer(serializers.Serializer):
    """Мастерская в карточке доски: {slug, name, logo, region, does_repair, rating}."""

    id = serializers.UUIDField(read_only=True)
    slug = serializers.CharField(read_only=True)
    name = serializers.CharField(read_only=True)
    logo = MediaSerializer(read_only=True, allow_null=True)
    region = BoardsRegionSerializer(read_only=True, allow_null=True)
    city = serializers.CharField(read_only=True)
    does_repair = serializers.SerializerMethodField()
    rating_avg = serializers.DecimalField(max_digits=3, decimal_places=2, read_only=True)
    rating_count = serializers.IntegerField(read_only=True)
    public_url = serializers.SerializerMethodField()

    def get_does_repair(self, obj) -> bool:
        profile = _profile(obj)
        return bool(profile and profile.does_repair)

    def get_public_url(self, obj) -> str:
        return f"/shapers/{obj.slug}"


# ---------------------------------------------------------------- варианты

class VariantDisplayMixin(serializers.Serializer):
    length_display = serializers.SerializerMethodField()
    width_display = serializers.SerializerMethodField()
    thickness_display = serializers.SerializerMethodField()
    dimensions_display = serializers.SerializerMethodField()
    volume_display = serializers.SerializerMethodField()
    fin_system_label = serializers.SerializerMethodField()
    availability_label = serializers.SerializerMethodField()

    def get_length_display(self, obj) -> str:
        return format_length(obj.length_in)

    def get_width_display(self, obj) -> str:
        return format_inches(obj.width_in)

    def get_thickness_display(self, obj) -> str | None:
        return format_inches(obj.thickness_in)

    def get_dimensions_display(self, obj) -> str:
        return format_dimensions(obj.length_in, obj.width_in, obj.thickness_in)

    def get_volume_display(self, obj) -> str | None:
        return format_volume(obj.volume_l)

    def get_fin_system_label(self, obj) -> str:
        return FIN_LABELS.get(obj.fin_system, obj.fin_system)

    def get_availability_label(self, obj) -> str:
        return AVAILABILITY_LABELS.get(obj.availability, obj.availability)


class VariantShortSerializer(VariantDisplayMixin, serializers.ModelSerializer):
    class Meta:
        model = BoardVariant
        fields = ["id", "sku", "length_in", "width_in", "thickness_in", "volume_l", "length_display", "width_display",
                  "thickness_display", "dimensions_display", "volume_display", "fin_system", "fin_system_label",
                  "price", "currency", "availability", "availability_label"]
        read_only_fields = fields


class VariantPublicSerializer(VariantDisplayMixin, serializers.ModelSerializer):
    material = MaterialSerializer(read_only=True, allow_null=True)
    items_available_for_sale = serializers.SerializerMethodField()
    photos = serializers.SerializerMethodField()

    class Meta:
        model = BoardVariant
        fields = ["id", "sku", "version", "length_in", "width_in", "thickness_in", "volume_l", "length_display",
                  "width_display", "thickness_display", "dimensions_display", "volume_display", "material",
                  "construction", "fin_system", "fin_system_label", "fin_setup", "price", "currency",
                  "made_to_order_days", "availability", "availability_label", "items_available_for_sale", "photos"]
        read_only_fields = fields

    def get_items_available_for_sale(self, obj) -> int:
        value = getattr(obj, "items_available_for_sale", None)
        return value if value is not None else sale_items_available(obj).count()

    @extend_schema_field(BoardMediaSerializer(many=True))
    def get_photos(self, obj):
        model = self.context.get("model_obj")
        items = _gallery(model, obj.pk) if model is not None else list(
            obj.media_items.select_related("media").order_by("-is_cover", "position", "id"))
        return BoardMediaSerializer(items, many=True).data


class VariantCabinetSerializer(VariantPublicSerializer):
    previous_version_id = serializers.UUIDField(read_only=True, allow_null=True)
    has_orders = serializers.SerializerMethodField()

    class Meta(VariantPublicSerializer.Meta):
        fields = VariantPublicSerializer.Meta.fields + [
            "model_id", "sku_suffix", "is_active", "previous_version_id", "has_orders", "created_at", "updated_at"]
        read_only_fields = fields

    def get_has_orders(self, obj) -> bool:
        """Есть заказы/брони/продажи: изменение размеров или конструкции создаст новую версию (F10)."""
        from apps.boards.services.history import variant_has_history

        known = self.context.get("history_ids")
        return obj.pk in known if known is not None else variant_has_history(obj)


class VariantTableSerializer(VariantCabinetSerializer):
    """Строка табличного редактора (BRD-12) с данными модели."""

    model = serializers.SerializerMethodField()

    class Meta(VariantCabinetSerializer.Meta):
        fields = [f for f in VariantCabinetSerializer.Meta.fields if f != "photos"] + ["model"]
        read_only_fields = fields

    @extend_schema_field({"type": "object", "properties": {
        "id": {"type": "string", "format": "uuid"}, "name": {"type": "string"}, "status": {"type": "string"},
        "board_type": {"type": "object"}}})
    def get_model(self, obj):
        return {"id": str(obj.model_id), "name": obj.model.name, "status": obj.model.status,
                "board_type": BoardTypeShortSerializer(obj.model.board_type).data}


class VariantWriteSerializer(serializers.Serializer):
    """Вход варианта. Размеры — числом в дюймах (*_in) или строкой («5'10\"», «20 1/2», «52 см»)."""

    length_in = serializers.DecimalField(max_digits=5, decimal_places=2, required=False)
    length = serializers.CharField(required=False, write_only=True, max_length=40)
    width_in = serializers.DecimalField(max_digits=5, decimal_places=2, required=False)
    width = serializers.CharField(required=False, write_only=True, max_length=40)
    thickness_in = serializers.DecimalField(max_digits=4, decimal_places=2, required=False, allow_null=True)
    thickness = serializers.CharField(required=False, write_only=True, max_length=40, allow_blank=True)
    volume_l = serializers.DecimalField(max_digits=5, decimal_places=2, required=False, allow_null=True,
                                        min_value=1, max_value=300)
    material_id = serializers.IntegerField(required=False, allow_null=True)
    construction = serializers.CharField(required=False, allow_blank=True, max_length=80)
    fin_system = serializers.ChoiceField(choices=BoardVariant.FinSystem.choices, required=False)
    fin_setup = serializers.CharField(required=False, allow_blank=True, max_length=40)
    price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True, min_value=0)
    currency = serializers.RegexField(r"^[A-Z]{3}$", required=False)
    made_to_order_days = serializers.IntegerField(required=False, allow_null=True, min_value=0, max_value=365)
    sku_suffix = serializers.CharField(required=False, allow_blank=True, max_length=12)
    is_active = serializers.BooleanField(required=False)
    in_stock_quantity = serializers.IntegerField(required=False, min_value=0, max_value=100, write_only=True,
                                                 help_text="Число свободных экземпляров мастерской на продажу")

    LIMITS = {"length_in": (24, 240, "Длина — от 2' до 20'."), "width_in": (8, 40, "Ширина — от 8\" до 40\"."),
              "thickness_in": (1, 8, "Толщина — от 1\" до 8\".")}

    def validate_sku_suffix(self, value):
        try:
            return normalize_suffix(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from exc

    def validate(self, attrs):
        errors = {}
        for text_field, field in (("length", "length_in"), ("width", "width_in"), ("thickness", "thickness_in")):
            if text_field in attrs:
                raw = attrs.pop(text_field)
                if raw in ("", None) and field == "thickness_in":
                    attrs[field] = None
                    continue
                try:
                    attrs[field] = parse_inches(raw, feet_allowed=field == "length_in")
                except ValueError as exc:
                    errors[text_field] = [str(exc)]
        for field, (low, high, message) in self.LIMITS.items():
            value = attrs.get(field)
            if value is not None and not (low <= value <= high):
                errors[field] = [message]
        if not self.partial:
            for field in ("length_in", "width_in"):
                if attrs.get(field) is None and field not in errors:
                    errors[field] = ["Обязательное поле."]
        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class VariantBulkRowSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True, min_value=0)
    currency = serializers.RegexField(r"^[A-Z]{3}$", required=False)
    made_to_order_days = serializers.IntegerField(required=False, allow_null=True, min_value=0, max_value=365)
    is_active = serializers.BooleanField(required=False)
    in_stock_quantity = serializers.IntegerField(required=False, min_value=0, max_value=100)


class VariantBulkSerializer(serializers.Serializer):
    items = VariantBulkRowSerializer(many=True, allow_empty=False, max_length=500)


class VariantBulkResultSerializer(serializers.Serializer):
    updated = serializers.IntegerField()
    items = VariantTableSerializer(many=True)


class VariantResultSerializer(VariantCabinetSerializer):
    """Ответ на правку варианта: versioned=true — создана новая версия (новый id), старая деактивирована."""

    versioned = serializers.SerializerMethodField()

    class Meta(VariantCabinetSerializer.Meta):
        fields = VariantCabinetSerializer.Meta.fields + ["versioned"]
        read_only_fields = fields

    def get_versioned(self, obj) -> bool:
        return bool(self.context.get("versioned"))


# ---------------------------------------------------------------- модели (карточки)

class BoardTileSerializer(serializers.ModelSerializer):
    """Компактная карточка модели (карусель в карточке шейпера, профиль мастерской)."""

    board_type = BoardTypeShortSerializer(read_only=True)
    cover = serializers.SerializerMethodField()
    photos_count = serializers.SerializerMethodField()
    has_video = serializers.SerializerMethodField()
    price_from = serializers.SerializerMethodField()
    currency = serializers.SerializerMethodField()
    length_min_in = serializers.SerializerMethodField()
    length_max_in = serializers.SerializerMethodField()
    length_range_display = serializers.SerializerMethodField()
    volume_min_l = serializers.SerializerMethodField()
    volume_max_l = serializers.SerializerMethodField()
    volume_range_display = serializers.SerializerMethodField()
    availability = serializers.SerializerMethodField()
    availability_label = serializers.SerializerMethodField()
    variants_count = serializers.SerializerMethodField()
    primary_variant = serializers.SerializerMethodField()
    public_url = serializers.SerializerMethodField()

    class Meta:
        model = BoardModel
        fields = ["id", "name", "slug", "board_type", "cover", "photos_count", "has_video", "price_from", "currency",
                  "length_min_in", "length_max_in", "length_range_display", "volume_min_l", "volume_max_l",
                  "volume_range_display", "availability", "availability_label", "variants_count", "primary_variant",
                  "public_url"]
        read_only_fields = fields

    def _variants(self, obj):
        return _active_variants(obj)

    def _agg(self, obj, name, func, attr):
        if hasattr(obj, name):
            return getattr(obj, name)
        values = [getattr(v, attr) for v in self._variants(obj) if getattr(v, attr) is not None]
        return func(values) if values else None

    @extend_schema_field(MediaSerializer(allow_null=True))
    def get_cover(self, obj):
        cover = model_cover(obj)
        return MediaSerializer(cover).data if cover else None

    def get_photos_count(self, obj) -> int:
        if hasattr(obj, "photos_count"):
            return obj.photos_count
        active = {v.pk for v in self._variants(obj)}
        return len([m for m in _model_media(obj) if m.variant_id is None or m.variant_id in active])

    def get_has_video(self, obj) -> bool:
        return obj.video_id is not None

    @extend_schema_field(OpenApiTypes.DECIMAL)
    def get_price_from(self, obj):
        value = self._agg(obj, "price_from", min, "price")
        return None if value is None else f"{value:.2f}"

    def get_currency(self, obj) -> str:
        variants = self._variants(obj)
        return variants[0].currency if variants else "RUB"

    @extend_schema_field(OpenApiTypes.DECIMAL)
    def get_length_min_in(self, obj):
        value = self._agg(obj, "length_min_in", min, "length_in")
        return None if value is None else f"{value:.2f}"

    @extend_schema_field(OpenApiTypes.DECIMAL)
    def get_length_max_in(self, obj):
        value = self._agg(obj, "length_max_in", max, "length_in")
        return None if value is None else f"{value:.2f}"

    def get_length_range_display(self, obj) -> str | None:
        low, high = self._agg(obj, "length_min_in", min, "length_in"), self._agg(obj, "length_max_in", max, "length_in")
        if low is None:
            return None
        return format_length(low) if low == high else f"{format_length(low)} – {format_length(high)}"

    @extend_schema_field(OpenApiTypes.DECIMAL)
    def get_volume_min_l(self, obj):
        value = self._agg(obj, "volume_min_l", min, "volume_l")
        return None if value is None else f"{value:.2f}"

    @extend_schema_field(OpenApiTypes.DECIMAL)
    def get_volume_max_l(self, obj):
        value = self._agg(obj, "volume_max_l", max, "volume_l")
        return None if value is None else f"{value:.2f}"

    def get_volume_range_display(self, obj) -> str | None:
        low, high = self._agg(obj, "volume_min_l", min, "volume_l"), self._agg(obj, "volume_max_l", max, "volume_l")
        if low is None:
            return None
        if low == high:
            return format_volume(low)
        return f"{format_volume(low)[:-2]}–{format_volume(high)}"

    def get_availability(self, obj) -> str:
        if hasattr(obj, "has_in_stock"):
            if obj.has_in_stock:
                return BoardVariant.Availability.IN_STOCK
            if obj.has_made_to_order:
                return BoardVariant.Availability.MADE_TO_ORDER
            return BoardVariant.Availability.OUT_OF_STOCK
        return best_availability([v.availability for v in self._variants(obj)])

    def get_availability_label(self, obj) -> str:
        return AVAILABILITY_LABELS[self.get_availability(obj)]

    def get_variants_count(self, obj) -> int:
        return obj.variants_count if hasattr(obj, "variants_count") else len(self._variants(obj))

    @extend_schema_field(VariantShortSerializer(allow_null=True))
    def get_primary_variant(self, obj):
        variants = self._variants(obj)
        return VariantShortSerializer(variants[0]).data if variants else None

    def get_public_url(self, obj) -> str:
        return f"/boards/{obj.pk}"


class BoardCardSerializer(BoardTileSerializer):
    """Карточка «Все доски» (SHP-07): модель + мастерская + is_own (скрыть «Заказать» на своих досках, SHP-11)."""

    shaper = ShaperMiniSerializer(source="workshop", read_only=True)
    is_own = serializers.SerializerMethodField()

    class Meta(BoardTileSerializer.Meta):
        fields = BoardTileSerializer.Meta.fields + ["shaper", "is_own", "published_at"]
        read_only_fields = fields

    def get_is_own(self, obj) -> bool:
        return obj.workshop_id in self.context.get("my_workshop_ids", set())


class ShaperDetailMiniSerializer(ShaperMiniSerializer):
    short_description = serializers.CharField(read_only=True)
    specialization = serializers.SerializerMethodField()
    lead_time = serializers.SerializerMethodField()
    services = serializers.SerializerMethodField()

    def get_specialization(self, obj) -> str:
        profile = _profile(obj)
        return profile.specialization if profile else ""

    def get_lead_time(self, obj) -> str:
        profile = _profile(obj)
        return profile.lead_time if profile else ""

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_services(self, obj):
        profile = _profile(obj)
        return list(profile.services) if profile else []


class BoardDetailSerializer(BoardCardSerializer):
    """GET boards/{id}: модель + активные варианты + фото (обложка первой, ≤10) + отдельное видео + мастерская."""

    shaper = ShaperDetailMiniSerializer(source="workshop", read_only=True)
    photos = serializers.SerializerMethodField()
    video = MediaSerializer(read_only=True, allow_null=True)
    variants = serializers.SerializerMethodField()

    class Meta(BoardCardSerializer.Meta):
        fields = BoardCardSerializer.Meta.fields + ["description", "tags", "photos", "video", "variants", "updated_at"]
        read_only_fields = fields

    @extend_schema_field(BoardMediaSerializer(many=True))
    def get_photos(self, obj):
        return BoardMediaSerializer(_gallery(obj)[: BoardMedia.MAX_PHOTOS], many=True).data

    @extend_schema_field(VariantPublicSerializer(many=True))
    def get_variants(self, obj):
        return VariantPublicSerializer(self._variants(obj), many=True, context={**self.context, "model_obj": obj}).data


# ---------------------------------------------------------------- модели (кабинет)

class BoardModelCabinetSerializer(BoardTileSerializer):
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    is_public = serializers.SerializerMethodField()

    class Meta(BoardTileSerializer.Meta):
        fields = BoardTileSerializer.Meta.fields + ["status", "status_label", "is_public", "serial", "published_at",
                                                    "created_at", "updated_at"]
        read_only_fields = fields

    def get_is_public(self, obj) -> bool:
        return obj.status == BoardModel.Status.PUBLISHED and obj.workshop.status == Organization.Status.PUBLISHED


class BoardModelCabinetDetailSerializer(BoardModelCabinetSerializer):
    workshop = serializers.SerializerMethodField()
    photos = serializers.SerializerMethodField()
    video = MediaSerializer(read_only=True, allow_null=True)
    variants = serializers.SerializerMethodField()
    publish_requirements = serializers.SerializerMethodField()

    class Meta(BoardModelCabinetSerializer.Meta):
        fields = BoardModelCabinetSerializer.Meta.fields + ["workshop", "description", "tags", "photos", "video",
                                                            "variants", "publish_requirements"]
        read_only_fields = fields

    @extend_schema_field({"type": "object", "properties": {"id": {"type": "string", "format": "uuid"},
                                                           "slug": {"type": "string"}, "name": {"type": "string"}}})
    def get_workshop(self, obj):
        return {"id": str(obj.workshop_id), "slug": obj.workshop.slug, "name": obj.workshop.name}

    @extend_schema_field(BoardMediaSerializer(many=True))
    def get_photos(self, obj):
        return BoardMediaSerializer(_gallery(obj), many=True).data

    @extend_schema_field(VariantCabinetSerializer(many=True))
    def get_variants(self, obj):
        from apps.boards.services.history import variants_with_history

        variants = list(obj.variants.select_related("material").annotate(
            items_available_for_sale=_items_count()).order_by("-is_active", "length_in", "width_in", "-version"))
        context = {**self.context, "model_obj": obj, "history_ids": variants_with_history([v.pk for v in variants])}
        return VariantCabinetSerializer(variants, many=True, context=context).data

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_publish_requirements(self, obj):
        from apps.boards.services.board_models import publish_requirements

        request = self.context.get("request")
        return publish_requirements(obj, request.user if request else None)


def _items_count():
    from apps.boards.services.catalog import items_for_sale_count

    return items_for_sale_count()


class BoardModelWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100, min_length=1)
    slug = serializers.SlugField(max_length=76, required=False)
    board_type_id = serializers.IntegerField()
    description = serializers.CharField(required=False, allow_blank=True, max_length=5000)
    tags = serializers.ListField(child=serializers.CharField(max_length=40), required=False, max_length=12)
    variants = VariantWriteSerializer(many=True, required=False, max_length=30,
                                      help_text="Только при создании: варианты создаются в той же транзакции")


class DeletionResultSerializer(serializers.Serializer):
    result = serializers.ChoiceField(choices=["deleted", "archived", "deactivated", "retired"])


class BoardMediaAddSerializer(serializers.Serializer):
    media_ids = serializers.ListField(child=serializers.UUIDField(), min_length=1, max_length=BoardMedia.MAX_PHOTOS)
    variant_id = serializers.UUIDField(required=False, allow_null=True)


class BoardMediaOrderSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.IntegerField(), min_length=1, max_length=BoardMedia.MAX_PHOTOS)
    variant_id = serializers.UUIDField(required=False, allow_null=True)


class BoardVideoSetSerializer(serializers.Serializer):
    media_id = serializers.UUIDField()


class BoardGallerySerializer(serializers.Serializer):
    variant_id = serializers.UUIDField(allow_null=True)
    photos = BoardMediaSerializer(many=True)


class BoardModelMediaSerializer(serializers.Serializer):
    photos = BoardMediaSerializer(many=True)
    variants = BoardGallerySerializer(many=True)
    video = MediaSerializer(allow_null=True)


# ---------------------------------------------------------------- мастерская: публичный профиль

class ShaperCardSerializer(serializers.ModelSerializer):
    """Карточка «По шейперам» (SHP-08/09): знакомство, услуги, сроки, регион, рейтинг и до 8 моделей."""

    logo = MediaSerializer(read_only=True, allow_null=True)
    region = BoardsRegionSerializer(read_only=True, allow_null=True)
    owner = PublicAccountSerializer(read_only=True)
    specialization = serializers.CharField(source="workshop.specialization", read_only=True)
    services = serializers.ListField(source="workshop.services", child=serializers.CharField(), read_only=True)
    lead_time = serializers.CharField(source="workshop.lead_time", read_only=True)
    does_repair = serializers.BooleanField(source="workshop.does_repair", read_only=True)
    repair_note = serializers.CharField(source="workshop.repair_note", read_only=True)
    experience_since = serializers.IntegerField(source="workshop.experience_since", read_only=True, allow_null=True)
    experience_years = serializers.SerializerMethodField()
    promo_video = MediaSerializer(source="workshop.promo_video", read_only=True, allow_null=True)
    models_count = serializers.SerializerMethodField()
    models = serializers.SerializerMethodField()
    is_own = serializers.SerializerMethodField()
    public_url = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = ["id", "slug", "name", "logo", "region", "city", "short_description", "owner", "specialization",
                  "services", "lead_time", "does_repair", "repair_note", "experience_since", "experience_years",
                  "promo_video", "rating_avg", "rating_count", "models_count", "models", "is_own", "public_url"]
        read_only_fields = fields

    def get_experience_years(self, obj) -> int | None:
        since = obj.workshop.experience_since
        return max(timezone.localdate().year - since, 0) if since else None

    def get_models_count(self, obj) -> int:
        return getattr(obj, "models_count", 0)

    @extend_schema_field(BoardTileSerializer(many=True))
    def get_models(self, obj):
        models = self.context.get("models_by_workshop", {}).get(obj.pk, [])
        return BoardTileSerializer(models, many=True, context=self.context).data

    def get_is_own(self, obj) -> bool:
        return obj.pk in self.context.get("my_workshop_ids", set())

    def get_public_url(self, obj) -> str:
        return f"/shapers/{obj.slug}"


class ShaperDetailSerializer(ShaperCardSerializer):
    """GET shapers/{slug}: профиль мастерской (промо-видео SHP-03, ремонт SHP-04, свои типы и материалы)."""

    cover = MediaSerializer(read_only=True, allow_null=True)
    gallery = MediaSerializer(many=True, read_only=True)
    board_types = serializers.SerializerMethodField()
    materials = serializers.SerializerMethodField()

    class Meta(ShaperCardSerializer.Meta):
        fields = ShaperCardSerializer.Meta.fields + ["description", "cover", "gallery", "address", "website",
                                                     "social_links", "board_types", "materials", "published_at"]
        read_only_fields = fields

    @extend_schema_field(BoardTypeSerializer(many=True))
    def get_board_types(self, obj):
        return BoardTypeSerializer(obj.custom_board_types.all(), many=True).data

    @extend_schema_field(MaterialSerializer(many=True))
    def get_materials(self, obj):
        return MaterialSerializer(obj.custom_materials.all(), many=True).data


# ---------------------------------------------------------------- мастерская: кабинет

class WorkshopCabinetSerializer(serializers.ModelSerializer):
    """GET/PUT me/workshop. created=true — мастерская только что создана (кнопка «Зарегистрироваться как шейпер»
    сменяется на «Сохранить изменения», SHP-01)."""

    status_label = serializers.CharField(source="get_status_display", read_only=True)
    region = BoardsRegionSerializer(read_only=True, allow_null=True)
    logo = MediaSerializer(read_only=True, allow_null=True)
    cover = MediaSerializer(read_only=True, allow_null=True)
    shaper_code = serializers.CharField(source="workshop.shaper_code", read_only=True)
    specialization = serializers.CharField(source="workshop.specialization", read_only=True)
    services = serializers.ListField(source="workshop.services", child=serializers.CharField(), read_only=True)
    lead_time = serializers.CharField(source="workshop.lead_time", read_only=True)
    does_repair = serializers.BooleanField(source="workshop.does_repair", read_only=True)
    repair_note = serializers.CharField(source="workshop.repair_note", read_only=True)
    experience_since = serializers.IntegerField(source="workshop.experience_since", read_only=True, allow_null=True)
    promo_video = MediaSerializer(source="workshop.promo_video", read_only=True, allow_null=True)
    my_role = serializers.SerializerMethodField()
    can_manage = serializers.SerializerMethodField()
    is_public = serializers.SerializerMethodField()
    public_url = serializers.SerializerMethodField()
    models_count = serializers.SerializerMethodField()
    publish_requirements = serializers.SerializerMethodField()
    created = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = ["id", "slug", "name", "status", "status_label", "verification_status", "short_description",
                  "description", "region", "city", "address", "phone", "email", "website", "social_links", "logo",
                  "cover", "shaper_code", "specialization", "services", "lead_time", "does_repair", "repair_note",
                  "experience_since", "promo_video", "rating_avg", "rating_count", "published_at", "my_role",
                  "can_manage", "is_public", "public_url", "models_count", "publish_requirements", "created"]
        read_only_fields = fields

    def _role(self, obj):
        from apps.organizations.services.access import member_role

        request = self.context.get("request")
        return member_role(request.user, obj) if request else None

    def get_my_role(self, obj) -> str | None:
        return self._role(obj)

    def get_can_manage(self, obj) -> bool:
        from apps.organizations.services.access import MANAGE_ROLES

        return self._role(obj) in MANAGE_ROLES

    def get_is_public(self, obj) -> bool:
        return obj.status == Organization.Status.PUBLISHED

    def get_public_url(self, obj) -> str:
        return f"/shapers/{obj.slug}"

    def get_models_count(self, obj) -> int:
        return obj.board_models.exclude(status=BoardModel.Status.ARCHIVED).count()

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_publish_requirements(self, obj):
        from apps.boards.services.workshops import publish_requirements

        request = self.context.get("request")
        return publish_requirements(obj, request.user if request else None)

    def get_created(self, obj) -> bool:
        return bool(self.context.get("created", False))


class WorkshopWriteSerializer(serializers.Serializer):
    """PUT me/workshop — создание (обязательно name) или частичное обновление."""

    name = serializers.CharField(max_length=90, required=False)
    short_description = serializers.CharField(max_length=300, required=False, allow_blank=True)
    description = serializers.CharField(max_length=5000, required=False, allow_blank=True)
    region_id = serializers.IntegerField(required=False, allow_null=True)
    city = serializers.CharField(max_length=120, required=False, allow_blank=True)
    address = serializers.CharField(max_length=300, required=False, allow_blank=True)
    phone = serializers.CharField(max_length=32, required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    website = serializers.URLField(required=False, allow_blank=True)
    social_links = serializers.DictField(child=serializers.CharField(max_length=300, allow_blank=True), required=False)
    logo_id = serializers.UUIDField(required=False, allow_null=True)
    cover_id = serializers.UUIDField(required=False, allow_null=True)
    shaper_code = serializers.CharField(max_length=6, min_length=2, required=False)
    specialization = serializers.CharField(max_length=300, required=False, allow_blank=True)
    services = serializers.ListField(child=serializers.CharField(max_length=80, allow_blank=True), required=False,
                                     max_length=20)
    lead_time = serializers.CharField(max_length=120, required=False, allow_blank=True)
    does_repair = serializers.BooleanField(required=False)
    repair_note = serializers.CharField(max_length=300, required=False, allow_blank=True)
    promo_video_id = serializers.UUIDField(required=False, allow_null=True)
    experience_since = serializers.IntegerField(required=False, allow_null=True, min_value=1950)

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Укажите название мастерской.")
        return value

    def validate_shaper_code(self, value):
        value = value.strip().upper()
        if not SHAPER_CODE_RE.match(value):
            raise serializers.ValidationError("2–6 заглавных латинских букв или цифр.")
        return value

    def validate_experience_since(self, value):
        if value is not None and value > dt.date.today().year:
            raise serializers.ValidationError("Год не может быть в будущем.")
        return value

    def validate(self, attrs):
        if "region_id" in attrs:
            region_id = attrs.pop("region_id")
            region = Region.objects.filter(pk=region_id).first() if region_id is not None else None
            if region_id is not None and region is None:
                raise serializers.ValidationError({"region_id": ["Регион не найден."]})
            attrs["region"] = region
        if "services" in attrs:
            attrs["services"] = [s.strip() for s in attrs["services"] if s.strip()]
        return attrs
