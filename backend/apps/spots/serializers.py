"""Сериализаторы спотов: публичный каталог (BR-01), карточка (SPT-02…12), прогноз (GEO-04), правки (SPT-07/08)."""
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.accounts.serializers_public import PublicAccountSerializer
from apps.mediafiles.serializers import MediaSerializer
from apps.spots.choices import (
    FIELD_LABELS,
    HAZARDS,
    compass_item,
    display_value,
    field_kind,
    infrastructure_item,
    month_item,
)
from apps.spots.models import Region, Spot, SpotChangeRequest, SpotForecast, SpotPhoto, SpotSourceRecord
from apps.spots.serializer_fields import (
    ChoiceValueSerializer,
    CompassPointSerializer,
    LabeledChoiceField,
    MonthSerializer,
    choice_dict,
)
from apps.spots.services.catalog import effective_precision, is_closed, public_coordinates, public_cover


class RegionSerializer(serializers.ModelSerializer):
    center_lat = serializers.FloatField(read_only=True, allow_null=True)
    center_lng = serializers.FloatField(read_only=True, allow_null=True)
    spots_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Region
        fields = ["id", "slug", "name", "timezone", "center_lat", "center_lng", "map_zoom", "spots_count"]


class RegionShortSerializer(serializers.ModelSerializer):
    class Meta:
        model = Region
        fields = ["id", "slug", "name"]


class InfrastructureItemSerializer(serializers.Serializer):
    type = serializers.CharField()
    type_label = serializers.CharField()
    name = serializers.CharField(allow_blank=True)
    distance_m = serializers.IntegerField(allow_null=True)


class SpotPhotoSerializer(serializers.ModelSerializer):
    media = MediaSerializer(read_only=True)
    author = PublicAccountSerializer(read_only=True, allow_null=True)

    class Meta:
        model = SpotPhoto
        fields = ["id", "media", "caption", "position", "author", "created_at"]


class SpotSourceRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = SpotSourceRecord
        fields = ["id", "source", "url", "note", "confirmed_at"]


class _SpotBaseSerializer(serializers.ModelSerializer):
    """Общие поля карточки каталога и детальной страницы. Координаты — только через public_coordinates."""

    region = RegionShortSerializer(read_only=True)
    status = LabeledChoiceField(Spot.Status.choices)
    lat = serializers.SerializerMethodField()
    lng = serializers.SerializerMethodField()
    precise = serializers.SerializerMethodField()
    location_precision = serializers.SerializerMethodField()
    difficulty = LabeledChoiceField(Spot.Difficulty.choices)
    bottom_type = LabeledChoiceField(Spot.Bottom.choices)
    break_type = LabeledChoiceField(Spot.Break.choices)
    best_wind_directions = serializers.SerializerMethodField()
    best_swell_directions = serializers.SerializerMethodField()
    hazards = serializers.SerializerMethodField()
    is_closed = serializers.SerializerMethodField()
    cover = serializers.SerializerMethodField()
    has_webcam = serializers.SerializerMethodField()

    def _coords(self, obj):
        if not hasattr(obj, "_public_coords"):
            obj._public_coords = public_coordinates(obj)
        return obj._public_coords

    @extend_schema_field(serializers.FloatField())
    def get_lat(self, obj):
        return self._coords(obj)["lat"]

    @extend_schema_field(serializers.FloatField())
    def get_lng(self, obj):
        return self._coords(obj)["lng"]

    @extend_schema_field(serializers.BooleanField())
    def get_precise(self, obj):
        return self._coords(obj)["precise"]

    @extend_schema_field(ChoiceValueSerializer())
    def get_location_precision(self, obj):
        return choice_dict(effective_precision(obj), Spot.Precision.choices)

    @extend_schema_field(CompassPointSerializer(many=True))
    def get_best_wind_directions(self, obj):
        return [compass_item(code) for code in obj.best_wind_directions]

    @extend_schema_field(CompassPointSerializer(many=True))
    def get_best_swell_directions(self, obj):
        return [compass_item(code) for code in obj.best_swell_directions]

    @extend_schema_field(ChoiceValueSerializer(many=True))
    def get_hazards(self, obj):
        return [{"code": code, "label": HAZARDS.get(code, code)} for code in obj.hazards]

    @extend_schema_field(serializers.BooleanField())
    def get_is_closed(self, obj):
        return is_closed(obj)

    @extend_schema_field(MediaSerializer(allow_null=True))
    def get_cover(self, obj):
        cover = public_cover(obj)
        return MediaSerializer(cover).data if cover else None

    @extend_schema_field(serializers.BooleanField())
    def get_has_webcam(self, obj):
        return bool(obj.webcam_url)


class SpotListSerializer(_SpotBaseSerializer):
    class Meta:
        model = Spot
        fields = [
            "id", "slug", "name", "region", "status", "lat", "lng", "precise", "location_precision",
            "short_description", "difficulty", "bottom_type", "break_type", "season",
            "best_wind_directions", "best_swell_directions", "hazards", "seasonal_warning", "closed_until", "is_closed",
            "cover", "rating_avg", "rating_count", "has_webcam",
        ]


class MapMarkerSerializer(serializers.Serializer):
    """Форма элемента GET spots/map (отдаётся из кеша)."""

    id = serializers.UUIDField()
    slug = serializers.CharField()
    name = serializers.CharField()
    region_slug = serializers.CharField()
    region_name = serializers.CharField()
    lat = serializers.FloatField()
    lng = serializers.FloatField()
    precise = serializers.BooleanField()
    difficulty = serializers.CharField()
    difficulty_label = serializers.CharField()
    status = serializers.CharField()
    is_closed = serializers.BooleanField()
    rating_avg = serializers.DecimalField(max_digits=3, decimal_places=2)
    rating_count = serializers.IntegerField()
    thumbnail_url = serializers.CharField(allow_null=True)


class SpotOrganizationCardSerializer(serializers.Serializer):
    """Короткая карточка опубликованной организации на странице спота."""

    id = serializers.UUIDField()
    slug = serializers.CharField()
    name = serializers.CharField()
    kind = LabeledChoiceField([("school", "Сёрф-школа"), ("workshop", "Мастерская шейпера"), ("rental", "Прокат")])
    short_description = serializers.CharField()
    city = serializers.CharField()
    logo = MediaSerializer(allow_null=True)
    rating_avg = serializers.DecimalField(max_digits=3, decimal_places=2)
    rating_count = serializers.IntegerField()
    is_verified = serializers.SerializerMethodField()

    @extend_schema_field(serializers.BooleanField())
    def get_is_verified(self, obj):
        return obj.verification_status == "verified"


class SpotInstructorCardSerializer(serializers.Serializer):
    """Короткая карточка опубликованного инструктора на странице спота."""

    id = serializers.UUIDField()
    account = PublicAccountSerializer()
    headline = serializers.CharField()
    rating_avg = serializers.DecimalField(max_digits=3, decimal_places=2)
    rating_count = serializers.IntegerField()
    price_from = serializers.DecimalField(max_digits=10, decimal_places=2, allow_null=True)
    currency = serializers.CharField()
    certificate_verified = serializers.SerializerMethodField()

    @extend_schema_field(serializers.BooleanField())
    def get_certificate_verified(self, obj):
        return any(c.status == "verified" for c in obj.certificates.all())


class ProposalChangeSerializer(serializers.Serializer):
    field = serializers.CharField()
    label = serializers.CharField()
    kind = serializers.CharField()
    old = serializers.JSONField(allow_null=True)
    new = serializers.JSONField(allow_null=True)
    old_display = serializers.CharField()
    new_display = serializers.CharField()


class ProposalChangeWithCurrentSerializer(ProposalChangeSerializer):
    current = serializers.JSONField(allow_null=True)
    current_display = serializers.CharField()
    changed_since_submission = serializers.BooleanField()


def changes_list(changes, spot=None):
    """{field: {old, new}} → список для «было → стало»; со spot — ещё текущее значение (для модератора)."""
    from apps.spots.services.proposals import current_value

    items = []
    for field, value in (changes or {}).items():
        item = {
            "field": field, "label": FIELD_LABELS.get(field, field), "kind": field_kind(field),
            "old": value.get("old"), "new": value.get("new"),
            "old_display": display_value(field, value.get("old")), "new_display": display_value(field, value.get("new")),
        }
        if spot is not None:
            current = current_value(spot, field)
            item.update(current=current, current_display=display_value(field, current),
                        changed_since_submission=current != value.get("old"))
        items.append(item)
    return items


class ProposalSpotSerializer(serializers.ModelSerializer):
    class Meta:
        model = Spot
        fields = ["id", "slug", "name"]


class ProposalSerializer(serializers.ModelSerializer):
    """Предложение правки для автора: статус, «было → стало», комментарий модератора (7.4)."""

    spot = ProposalSpotSerializer(read_only=True)
    status = LabeledChoiceField(SpotChangeRequest.Status.choices)
    changes = serializers.SerializerMethodField()
    evidence = MediaSerializer(many=True, read_only=True)
    can_edit = serializers.SerializerMethodField()
    can_withdraw = serializers.SerializerMethodField()
    is_reverted = serializers.SerializerMethodField()

    class Meta:
        model = SpotChangeRequest
        fields = ["id", "spot", "status", "changes", "comment", "source", "evidence", "moderator_comment",
                  "decided_at", "is_reverted", "reverted_at", "can_edit", "can_withdraw", "created_at", "updated_at"]

    @extend_schema_field(ProposalChangeSerializer(many=True))
    def get_changes(self, obj):
        return changes_list(obj.changes)

    @extend_schema_field(serializers.BooleanField())
    def get_can_edit(self, obj):
        return obj.status == SpotChangeRequest.Status.NEEDS_INFO

    @extend_schema_field(serializers.BooleanField())
    def get_can_withdraw(self, obj):
        return obj.status in (SpotChangeRequest.Status.SUBMITTED, SpotChangeRequest.Status.NEEDS_INFO)

    @extend_schema_field(serializers.BooleanField())
    def get_is_reverted(self, obj):
        return obj.reverted_at is not None


class PendingProposalShortSerializer(serializers.ModelSerializer):
    status = LabeledChoiceField(SpotChangeRequest.Status.choices)
    changed_fields = serializers.SerializerMethodField()

    class Meta:
        model = SpotChangeRequest
        fields = ["id", "status", "changed_fields", "moderator_comment", "created_at"]

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_changed_fields(self, obj):
        return list(obj.changes)


class MyReviewShortSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    rating = serializers.IntegerField()
    text = serializers.CharField()
    status = LabeledChoiceField([("pending", "На модерации"), ("published", "Опубликован"),
                                 ("rejected", "Отклонён"), ("hidden", "Скрыт модератором")])
    has_pending_revision = serializers.BooleanField()
    pending_rating = serializers.IntegerField(allow_null=True)
    pending_text = serializers.CharField()
    moderation_note = serializers.CharField()
    published_at = serializers.DateTimeField(allow_null=True)
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class SpotDetailSerializer(_SpotBaseSerializer):
    best_months = serializers.SerializerMethodField()
    infrastructure = serializers.SerializerMethodField()
    photos = serializers.SerializerMethodField()
    sources = SpotSourceRecordSerializer(many=True, read_only=True)
    webcam_url = serializers.SerializerMethodField()
    organizations = serializers.SerializerMethodField()
    instructors = serializers.SerializerMethodField()
    my_review = serializers.SerializerMethodField()
    my_pending_proposals = serializers.SerializerMethodField()

    class Meta:
        model = Spot
        fields = [
            "id", "slug", "name", "region", "status", "lat", "lng", "precise", "location_precision",
            "short_description", "description",
            "difficulty", "bottom_type", "break_type", "wave_character", "wave_power",
            "season", "best_months", "best_wind_directions", "best_swell_directions", "best_tide",
            "typical_conditions", "water_temp_note",
            "hazards", "hazard_notes", "entry_exit", "access", "infrastructure",
            "seasonal_warning", "closed_until", "is_closed",
            "cover", "photos", "has_webcam", "webcam_url", "webcam_is_premium",
            "data_source", "last_confirmed_at", "sources",
            "rating_avg", "rating_count",
            "organizations", "instructors", "my_review", "my_pending_proposals",
            "created_at", "updated_at",
        ]

    def _user(self):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        return user if user is not None and user.is_authenticated else None

    @extend_schema_field(MonthSerializer(many=True))
    def get_best_months(self, obj):
        return [month_item(m) for m in obj.best_months]

    @extend_schema_field(InfrastructureItemSerializer(many=True))
    def get_infrastructure(self, obj):
        return [infrastructure_item(item) for item in (obj.infrastructure or [])]

    @extend_schema_field(SpotPhotoSerializer(many=True))
    def get_photos(self, obj):
        photos = [p for p in obj.photos.all() if p.media.status == p.media.Status.READY and p.media.is_public]
        return SpotPhotoSerializer(photos, many=True).data

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_webcam_url(self, obj):
        """Premium-трансляции (GEO-03) не раскрываются до появления платного доступа."""
        return obj.webcam_url if obj.webcam_url and not obj.webcam_is_premium else None

    @extend_schema_field(SpotOrganizationCardSerializer(many=True))
    def get_organizations(self, obj):
        orgs = [o for o in obj.organizations.all() if o.status == "published"]
        return SpotOrganizationCardSerializer(orgs, many=True).data

    @extend_schema_field(SpotInstructorCardSerializer(many=True))
    def get_instructors(self, obj):
        instructors = [i for i in obj.instructors.all() if i.status == "published"]
        return SpotInstructorCardSerializer(instructors, many=True).data

    @extend_schema_field(MyReviewShortSerializer(allow_null=True))
    def get_my_review(self, obj):
        user = self._user()
        if user is None:
            return None
        review = obj.reviews.filter(author=user).first()
        return MyReviewShortSerializer(review).data if review else None

    @extend_schema_field(PendingProposalShortSerializer(many=True))
    def get_my_pending_proposals(self, obj):
        user = self._user()
        if user is None:
            return []
        qs = obj.change_requests.filter(
            author=user, status__in=[SpotChangeRequest.Status.SUBMITTED, SpotChangeRequest.Status.NEEDS_INFO]
        ).order_by("-created_at")
        return PendingProposalShortSerializer(qs, many=True).data


class ForecastItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = SpotForecast
        fields = ["valid_from", "valid_to", "wave_height_m", "wave_period_s", "wave_direction", "wind_speed_ms",
                  "wind_direction", "water_temp_c", "tide_note"]


class ForecastResponseSerializer(serializers.Serializer):
    provider = serializers.CharField(allow_null=True)
    provider_title = serializers.CharField(allow_null=True)
    issued_at = serializers.DateTimeField(allow_null=True)
    items = ForecastItemSerializer(many=True)
    message = serializers.CharField(allow_blank=True)


class ProposalCreateSerializer(serializers.Serializer):
    changes = serializers.DictField(child=serializers.JSONField(allow_null=True), allow_empty=False,
                                    help_text="{поле: новое значение}; только EDITABLE_SPOT_FIELDS")
    comment = serializers.CharField(max_length=2000, required=False, allow_blank=True, default="")
    source = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")
    evidence_ids = serializers.ListField(child=serializers.UUIDField(), required=False, default=list, max_length=10)


class ProposalUpdateSerializer(serializers.Serializer):
    changes = serializers.DictField(child=serializers.JSONField(allow_null=True), required=False, allow_empty=False)
    comment = serializers.CharField(max_length=2000, required=False, allow_blank=True)
    source = serializers.CharField(max_length=300, required=False, allow_blank=True)
    evidence_ids = serializers.ListField(child=serializers.UUIDField(), required=False, max_length=10)


class DictionariesSerializer(serializers.Serializer):
    class EditableFieldSerializer(serializers.Serializer):
        field = serializers.CharField()
        label = serializers.CharField()
        kind = serializers.ChoiceField(choices=["text", "choice", "compass", "months", "hazards", "infrastructure"])
        max_length = serializers.IntegerField(allow_null=True)

    difficulty = ChoiceValueSerializer(many=True)
    bottom_type = ChoiceValueSerializer(many=True)
    break_type = ChoiceValueSerializer(many=True)
    location_precision = ChoiceValueSerializer(many=True)
    compass_points = CompassPointSerializer(many=True)
    months = MonthSerializer(many=True)
    hazards = ChoiceValueSerializer(many=True)
    infrastructure_types = ChoiceValueSerializer(many=True)
    editable_fields = EditableFieldSerializer(many=True)
