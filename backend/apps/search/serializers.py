import datetime as dt

from django.utils import timezone
from rest_framework import serializers

from apps.community.serializers import CatalogRegionSerializer
from apps.mediafiles.serializers import MediaSerializer
from apps.search.services.assistant import LEVELS, WAVES

# ---------------------------------------------------------------- поиск


class SearchResultSerializer(serializers.Serializer):
    type = serializers.CharField()
    id = serializers.CharField()
    title = serializers.CharField()
    subtitle = serializers.CharField(allow_blank=True)
    image = MediaSerializer(allow_null=True)
    url = serializers.CharField(help_text="Маршрут фронтенда (ARCHITECTURE §9)")


class SearchGroupSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=["spots", "instructors", "schools", "shapers", "boards", "equipment",
                                            "surfers"])
    label = serializers.CharField()
    total = serializers.IntegerField()
    results = SearchResultSerializer(many=True)
    more_url = serializers.CharField(help_text="Каталог раздела с тем же запросом")


class SearchResponseSerializer(serializers.Serializer):
    query = serializers.CharField()
    groups = SearchGroupSerializer(many=True)


# ---------------------------------------------------------------- помощник


class BoardSizeInputSerializer(serializers.Serializer):
    weight_kg = serializers.DecimalField(max_digits=5, decimal_places=1, min_value=25, max_value=200)
    level = serializers.ChoiceField(choices=list(LEVELS.items()))
    wave = serializers.ChoiceField(choices=list(WAVES.items()))


class VolumeRangeSerializer(serializers.Serializer):
    min = serializers.DecimalField(max_digits=6, decimal_places=1)
    max = serializers.DecimalField(max_digits=6, decimal_places=1)


class AssistantBoardTypeSerializer(serializers.Serializer):
    code = serializers.CharField()
    name = serializers.CharField()


class MatchingBoardSerializer(serializers.Serializer):
    variant_id = serializers.UUIDField()
    model_id = serializers.UUIDField()
    sku = serializers.CharField()
    title = serializers.CharField()
    subtitle = serializers.CharField()
    board_type = AssistantBoardTypeSerializer()
    length_in = serializers.DecimalField(max_digits=5, decimal_places=2)
    length_label = serializers.CharField()
    width_in = serializers.DecimalField(max_digits=5, decimal_places=2)
    thickness_in = serializers.DecimalField(max_digits=4, decimal_places=2, allow_null=True)
    volume_l = serializers.DecimalField(max_digits=5, decimal_places=2)
    price = serializers.DecimalField(max_digits=10, decimal_places=2, allow_null=True)
    currency = serializers.CharField()
    availability = serializers.CharField()
    availability_label = serializers.CharField()
    type_match = serializers.BooleanField(help_text="Тип доски входит в рекомендованные")
    image = MediaSerializer(allow_null=True)
    url = serializers.CharField()
    source = serializers.CharField()


class BoardSizeFormulaSerializer(serializers.Serializer):
    guild_factor = VolumeRangeSerializer()
    wave_factor = serializers.DecimalField(max_digits=4, decimal_places=2)
    rule_version = serializers.IntegerField()


class BoardSizeResponseSerializer(serializers.Serializer):
    input = serializers.DictField()
    volume_l = VolumeRangeSerializer()
    formula = BoardSizeFormulaSerializer()
    board_types = AssistantBoardTypeSerializer(many=True)
    explanation = serializers.CharField()
    warnings = serializers.ListField(child=serializers.CharField())
    matching_boards = MatchingBoardSerializer(many=True)
    disclaimer = serializers.CharField()


class RecommendInputSerializer(serializers.Serializer):
    region = serializers.CharField(max_length=60, help_text="slug или id региона")
    level = serializers.ChoiceField(choices=list(LEVELS.items()))
    date = serializers.DateField(required=False, allow_null=True)

    def validate_date(self, value):
        if value is None:
            return None
        today = timezone.localdate()
        if value < today - dt.timedelta(days=1) or value > today + dt.timedelta(days=366):
            raise serializers.ValidationError("Выберите дату в пределах ближайшего года.")
        return value


class AssistantForecastSerializer(serializers.Serializer):
    provider = serializers.CharField()
    issued_at = serializers.DateTimeField()
    valid_from = serializers.DateTimeField()
    valid_to = serializers.DateTimeField()
    wave_height_m = serializers.CharField(allow_null=True)
    wave_period_s = serializers.CharField(allow_null=True)
    wave_direction = serializers.CharField(allow_blank=True)
    wind_speed_ms = serializers.CharField(allow_null=True)
    wind_direction = serializers.CharField(allow_blank=True)
    water_temp_c = serializers.CharField(allow_null=True)
    source = serializers.CharField()


class RecommendedItemSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=["spot", "instructor", "rental"])
    id = serializers.UUIDField()
    title = serializers.CharField()
    subtitle = serializers.CharField(allow_blank=True)
    image = MediaSerializer(allow_null=True)
    url = serializers.CharField()
    source = serializers.CharField(help_text="«Каталог ГДеволна, данные обновлены ДД.ММ.ГГГГ»")


class RecommendedSpotSerializer(RecommendedItemSerializer):
    slug = serializers.CharField()
    difficulty = serializers.CharField()
    difficulty_label = serializers.CharField()
    typical_conditions = serializers.CharField(allow_blank=True)
    season = serializers.CharField(allow_blank=True)
    season_match = serializers.BooleanField(allow_null=True)
    hazards = serializers.ListField(child=serializers.CharField())
    hazard_notes = serializers.CharField(allow_blank=True)
    seasonal_warning = serializers.CharField(allow_blank=True)
    rating_avg = serializers.CharField()
    rating_count = serializers.IntegerField()
    forecast = AssistantForecastSerializer(allow_null=True)


class RecommendedInstructorSerializer(RecommendedItemSerializer):
    handle = serializers.CharField()
    rating_avg = serializers.CharField()
    rating_count = serializers.IntegerField()
    price_from = serializers.CharField(allow_null=True)
    currency = serializers.CharField()
    certificate_verified = serializers.BooleanField()


class RecommendedRentalSerializer(RecommendedItemSerializer):
    kind = serializers.CharField()
    kind_label = serializers.CharField()
    price_per_day = serializers.CharField(allow_null=True)
    price_per_hour = serializers.CharField(allow_null=True)
    currency = serializers.CharField()
    owner_name = serializers.CharField(allow_null=True)
    free_on_date = serializers.BooleanField(allow_null=True)


class RecommendResponseSerializer(serializers.Serializer):
    region = CatalogRegionSerializer()
    level = serializers.CharField()
    level_label = serializers.CharField()
    date = serializers.DateField()
    spots = RecommendedSpotSerializer(many=True)
    instructors = RecommendedInstructorSerializer(many=True)
    rentals = RecommendedRentalSerializer(many=True)
    notes = serializers.ListField(child=serializers.CharField())
    disclaimer = serializers.CharField()
    rule_version = serializers.IntegerField()
    generated_at = serializers.DateTimeField()
