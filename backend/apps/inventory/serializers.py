"""Сериализаторы аренды и кабинета инвентаря. Публичные карточки не содержат данных клиентов броней."""
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.accounts.serializers_public import PublicAccountSerializer
from apps.boards.serializers import BoardTypeShortSerializer, BoardsRegionSerializer
from apps.boards.services.dimensions import format_dimensions, format_volume
from apps.inventory.models import InventoryItem, InventoryItemPhoto, RentalHandover
from apps.inventory.services.items import MANUAL_STATUSES, MAX_PHOTOS
from apps.mediafiles.serializers import MediaSerializer
from apps.spots.models import Region, Spot

MANUAL_STATUS_CHOICES = [(status.value, status.label) for status in MANUAL_STATUSES]


class RentalSpotSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    slug = serializers.CharField(read_only=True)
    name = serializers.CharField(read_only=True)

    def get_attribute(self, instance):
        """Скрытый модератором или черновой спот в объявлении не показывается."""
        from apps.spots.services.catalog import is_public_spot

        spot = super().get_attribute(instance)
        return spot if is_public_spot(spot) else None


class ItemPhotoSerializer(serializers.ModelSerializer):
    media = MediaSerializer(read_only=True)

    class Meta:
        model = InventoryItemPhoto
        fields = ["id", "position", "media"]
        read_only_fields = fields


class ListingOwnerSerializer(serializers.Serializer):
    """Владелец объявления: аккаунт (handle, avatar) или организация (slug, logo)."""

    type = serializers.ChoiceField(choices=["account", "organization"])
    id = serializers.UUIDField()
    name = serializers.CharField()
    handle = serializers.CharField(allow_null=True)
    slug = serializers.CharField(allow_null=True)
    kind = serializers.CharField(allow_null=True, help_text="Тип организации: school | workshop | rental")
    avatar = MediaSerializer(allow_null=True)


def owner_data(item):
    if item.owner_organization_id:
        org = item.owner_organization
        return {"type": "organization", "id": org.pk, "name": org.name, "handle": None, "slug": org.slug,
                "kind": org.kind, "avatar": MediaSerializer(org.logo).data if org.logo_id else None}
    account = PublicAccountSerializer(item.owner_account).data
    return {"type": "account", "id": account["id"], "name": account["display_name"], "handle": account["handle"],
            "slug": None, "kind": None, "avatar": account["avatar"]}


class VariantInfoSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    sku = serializers.CharField()
    model_id = serializers.UUIDField()
    model_name = serializers.CharField()
    board_type = BoardTypeShortSerializer()
    dimensions_display = serializers.CharField()
    volume_l = serializers.DecimalField(max_digits=5, decimal_places=2, allow_null=True)
    volume_display = serializers.CharField(allow_null=True)
    shaper = serializers.DictField(help_text="{slug, name}")


def variant_data(item):
    variant = item.variant
    if variant is None:
        return None
    model = variant.model
    return {
        "id": str(variant.pk), "sku": variant.sku, "model_id": str(model.pk), "model_name": model.name,
        "board_type": BoardTypeShortSerializer(model.board_type).data,
        "dimensions_display": format_dimensions(variant.length_in, variant.width_in, variant.thickness_in),
        "volume_l": None if variant.volume_l is None else f"{variant.volume_l:.2f}",
        "volume_display": format_volume(variant.volume_l),
        "shaper": {"slug": model.workshop.slug, "name": model.workshop.name},
    }


class RentalCardSerializer(serializers.ModelSerializer):
    kind_label = serializers.CharField(source="get_kind_display", read_only=True)
    condition_label = serializers.CharField(source="get_condition_display", read_only=True)
    region = BoardsRegionSerializer(read_only=True, allow_null=True)
    spot = RentalSpotSerializer(read_only=True, allow_null=True)
    cover = serializers.SerializerMethodField()
    photos_count = serializers.SerializerMethodField()
    owner = serializers.SerializerMethodField()
    variant = serializers.SerializerMethodField()
    is_own = serializers.SerializerMethodField()
    public_url = serializers.SerializerMethodField()

    class Meta:
        model = InventoryItem
        fields = ["id", "title", "kind", "kind_label", "purpose", "size", "condition", "condition_label", "region",
                  "spot", "pickup_location", "available_hours", "rental_price_per_day", "rental_price_per_hour",
                  "min_rental_hours", "deposit_note", "sale_price", "currency", "cover", "photos_count", "owner",
                  "variant", "is_own", "public_url"]
        read_only_fields = fields

    def _photos(self, obj):
        return sorted(obj.photos.all(), key=lambda p: (p.position, p.pk))

    @extend_schema_field(MediaSerializer(allow_null=True))
    def get_cover(self, obj):
        photos = self._photos(obj)
        return MediaSerializer(photos[0].media).data if photos else None

    def get_photos_count(self, obj) -> int:
        return len(self._photos(obj))

    @extend_schema_field(ListingOwnerSerializer)
    def get_owner(self, obj):
        return owner_data(obj)

    @extend_schema_field(VariantInfoSerializer(allow_null=True))
    def get_variant(self, obj):
        return variant_data(obj)

    def get_is_own(self, obj) -> bool:
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False
        if obj.owner_account_id:
            return obj.owner_account_id == user.pk
        return obj.owner_organization_id in self.context.get("my_org_ids", set())

    def get_public_url(self, obj) -> str:
        return f"/rentals/{obj.pk}"


class BookedIntervalSerializer(serializers.Serializer):
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()


class RentalDetailSerializer(RentalCardSerializer):
    photos = serializers.SerializerMethodField()
    booked_intervals = serializers.SerializerMethodField()

    class Meta(RentalCardSerializer.Meta):
        fields = RentalCardSerializer.Meta.fields + ["description", "restrictions", "photos", "booked_intervals",
                                                     "created_at", "updated_at"]
        read_only_fields = fields

    @extend_schema_field(ItemPhotoSerializer(many=True))
    def get_photos(self, obj):
        return ItemPhotoSerializer(self._photos(obj), many=True).data

    @extend_schema_field(BookedIntervalSerializer(many=True))
    def get_booked_intervals(self, obj):
        return BookedIntervalSerializer(self.context.get("booked_intervals", []), many=True).data


class InventoryItemCabinetSerializer(RentalDetailSerializer):
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    organization_id = serializers.UUIDField(source="owner_organization_id", read_only=True, allow_null=True)

    class Meta(RentalDetailSerializer.Meta):
        fields = [f for f in RentalDetailSerializer.Meta.fields if f != "booked_intervals"] + [
            "status", "status_label", "is_published", "serial_number", "organization_id"]
        read_only_fields = fields


class InventoryItemWriteSerializer(serializers.Serializer):
    organization_id = serializers.UUIDField(required=False, allow_null=True,
                                            help_text="Экземпляр организации (школа/прокат/мастерская); иначе личный")
    variant_id = serializers.UUIDField(required=False, allow_null=True,
                                       help_text="Вариант доски вашей мастерской (наличие обновляется, BRD-13)")
    kind = serializers.ChoiceField(choices=InventoryItem.Kind.choices, required=False)
    purpose = serializers.ChoiceField(choices=InventoryItem.Purpose.choices, required=False)
    status = serializers.ChoiceField(choices=MANUAL_STATUS_CHOICES, required=False)
    title = serializers.CharField(max_length=200, required=False, allow_blank=True)
    description = serializers.CharField(max_length=5000, required=False, allow_blank=True)
    size = serializers.CharField(max_length=60, required=False, allow_blank=True)
    condition = serializers.ChoiceField(choices=InventoryItem.Condition.choices, required=False)
    region_id = serializers.IntegerField(required=False, allow_null=True)
    spot_id = serializers.UUIDField(required=False, allow_null=True)
    pickup_location = serializers.CharField(max_length=300, required=False, allow_blank=True)
    available_hours = serializers.CharField(max_length=120, required=False, allow_blank=True)
    rental_price_per_day = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True,
                                                    min_value=0)
    rental_price_per_hour = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True,
                                                     min_value=0)
    sale_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True, min_value=0)
    deposit_note = serializers.CharField(max_length=200, required=False, allow_blank=True)
    currency = serializers.RegexField(r"^[A-Z]{3}$", required=False)
    min_rental_hours = serializers.IntegerField(required=False, min_value=1, max_value=24 * 30)
    restrictions = serializers.CharField(max_length=2000, required=False, allow_blank=True)
    serial_number = serializers.CharField(max_length=80, required=False, allow_blank=True)
    is_published = serializers.BooleanField(required=False)
    photo_ids = serializers.ListField(child=serializers.UUIDField(), required=False, max_length=MAX_PHOTOS,
                                      help_text="Только при создании; далее — me/inventory/{id}/photos")

    def validate(self, attrs):
        if "region_id" in attrs:
            region_id = attrs.pop("region_id")
            attrs["region"] = Region.objects.filter(pk=region_id).first() if region_id is not None else None
            if region_id is not None and attrs["region"] is None:
                raise serializers.ValidationError({"region_id": ["Регион не найден."]})
        if "spot_id" in attrs:
            spot_id = attrs.pop("spot_id")
            attrs["spot"] = Spot.objects.filter(pk=spot_id).first() if spot_id is not None else None
            if spot_id is not None and attrs["spot"] is None:
                raise serializers.ValidationError({"spot_id": ["Спот не найден."]})
        return attrs


class InventoryStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=MANUAL_STATUS_CHOICES)


class InventoryPhotoAddSerializer(serializers.Serializer):
    media_ids = serializers.ListField(child=serializers.UUIDField(), min_length=1, max_length=MAX_PHOTOS)


class InventoryPhotoOrderSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.IntegerField(), min_length=1, max_length=MAX_PHOTOS)


class InventoryPhotosSerializer(serializers.Serializer):
    photos = ItemPhotoSerializer(many=True)


class InventoryAvailabilityBookingSerializer(serializers.Serializer):
    booking_id = serializers.UUIDField()
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    status = serializers.CharField()


class InventoryAvailabilityItemSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    title = serializers.CharField()
    kind = serializers.CharField()
    status = serializers.CharField()
    size = serializers.CharField()
    is_published = serializers.BooleanField()
    is_booked_now = serializers.BooleanField()
    is_free_in_range = serializers.BooleanField()
    booked = InventoryAvailabilityBookingSerializer(many=True)


class InventoryAvailabilitySummarySerializer(serializers.Serializer):
    total = serializers.IntegerField(help_text="Экземпляры для аренды (кроме списанных/проданных)")
    free_now = serializers.IntegerField(help_text="«Свободных бордов» сейчас")
    booked_now = serializers.IntegerField(help_text="«Забронировано» сейчас (подтверждено или выдано)")
    maintenance = serializers.IntegerField()
    free_in_range = serializers.IntegerField()
    booked_in_range = serializers.IntegerField()


class InventoryAvailabilitySerializer(serializers.Serializer):
    # «from» — зарезервированное слово Python, поэтому поле объявляется через fields
    to = serializers.DateTimeField()
    summary = InventoryAvailabilitySummarySerializer()
    items = InventoryAvailabilityItemSerializer(many=True)

    def get_fields(self):
        fields = super().get_fields()
        fields["from"] = serializers.DateTimeField()
        return fields


class HandoverWriteSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=RentalHandover.Kind.choices)
    condition = serializers.ChoiceField(choices=InventoryItem.Condition.choices)
    notes = serializers.CharField(max_length=2000, required=False, allow_blank=True)
    damage_reported = serializers.BooleanField(required=False, default=False)
    damage_description = serializers.CharField(max_length=2000, required=False, allow_blank=True)
    photo_ids = serializers.ListField(child=serializers.UUIDField(), required=False, max_length=10)


class HandoverSerializer(serializers.ModelSerializer):
    kind_label = serializers.CharField(source="get_kind_display", read_only=True)
    condition_label = serializers.CharField(source="get_condition_display", read_only=True)
    photos = MediaSerializer(many=True, read_only=True)
    recorded_by = PublicAccountSerializer(read_only=True)
    booking_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = RentalHandover
        fields = ["id", "booking_id", "kind", "kind_label", "condition", "condition_label", "notes", "damage_reported",
                  "damage_description", "photos", "recorded_by", "created_at"]
        read_only_fields = fields
