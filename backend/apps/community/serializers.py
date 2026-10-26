import datetime as dt

from django.utils import timezone
from rest_framework import serializers

from apps.accounts.models import UserProfile
from apps.community.models import SurfSession
from apps.mediafiles.serializers import MediaSerializer
from apps.spots.models import Spot

# ---------------------------------------------------------------- схемы ответов (форма описана для drf-spectacular)


class CatalogRegionSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    slug = serializers.CharField()
    name = serializers.CharField()


class CatalogSpotSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    slug = serializers.CharField()
    name = serializers.CharField()
    url = serializers.CharField()


class SurferCardSerializer(serializers.Serializer):
    id = serializers.UUIDField(help_text="id аккаунта (для POST direct-conversations)")
    handle = serializers.CharField()
    display_name = serializers.CharField()
    avatar = MediaSerializer(allow_null=True)
    region = CatalogRegionSerializer(allow_null=True, help_text="Только если участник разрешил показ региона")
    age = serializers.IntegerField(allow_null=True, help_text="Число лет, только при gg_show_age; дата не отдаётся")
    riding_level = serializers.CharField(allow_null=True)
    riding_level_label = serializers.CharField(allow_null=True)
    surfing_since = serializers.IntegerField(allow_null=True)
    experience_years = serializers.IntegerField(allow_null=True)
    preferred_board_types = serializers.ListField(child=serializers.CharField())
    favorite_spots = CatalogSpotSerializer(many=True)
    interests = serializers.ListField(child=serializers.CharField())
    bio_excerpt = serializers.CharField(allow_blank=True)
    fun_facts = serializers.ListField(child=serializers.CharField())
    accepts_messages = serializers.BooleanField(help_text="gg_contact_policy = everyone")
    can_message = serializers.BooleanField(help_text="Можно написать сейчас: политика, нет блокировок, не я")
    is_me = serializers.BooleanField()
    url = serializers.CharField()


class TopSpotSerializer(serializers.Serializer):
    spot = CatalogSpotSerializer(allow_null=True)
    name = serializers.CharField()
    days = serializers.IntegerField()


class DiaryStatsSerializer(serializers.Serializer):
    ride_days = serializers.IntegerField(help_text="Уникальные даты катания")
    sessions = serializers.IntegerField()
    spots_visited = serializers.IntegerField()
    this_year_days = serializers.IntegerField()
    longest_streak_days = serializers.IntegerField()
    current_streak_days = serializers.IntegerField()
    last_ride_date = serializers.DateField(allow_null=True)
    top_spots = TopSpotSerializer(many=True)


class SurferDetailSerializer(SurferCardSerializer):
    bio = serializers.CharField(allow_blank=True)
    languages = serializers.ListField(child=serializers.CharField())
    member_since = serializers.IntegerField(help_text="Год регистрации")
    instructor_url = serializers.CharField(allow_null=True)
    diary = DiaryStatsSerializer(help_text="Статистика только по записям, видимым текущему зрителю (COM-08)")


class DiarySpotSerializer(CatalogSpotSerializer):
    region = CatalogRegionSerializer(allow_null=True)
    is_published = serializers.BooleanField(required=False, help_text="Только в собственном дневнике")


class DiaryEntrySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    date = serializers.DateField()
    spot = DiarySpotSerializer(allow_null=True)
    spot_name = serializers.CharField(allow_blank=True)
    place_name = serializers.CharField(allow_blank=True)
    duration_min = serializers.IntegerField(allow_null=True)
    board_note = serializers.CharField(allow_blank=True)
    conditions = serializers.CharField(allow_blank=True)
    wave_height_m = serializers.DecimalField(max_digits=4, decimal_places=1, allow_null=True)
    mood_rating = serializers.IntegerField(allow_null=True)
    notes = serializers.CharField(allow_blank=True)
    visibility = serializers.ChoiceField(choices=SurfSession.Visibility.choices)
    visibility_label = serializers.CharField()
    photos = MediaSerializer(many=True)
    created_at = serializers.DateTimeField(required=False)
    updated_at = serializers.DateTimeField(required=False)


# ---------------------------------------------------------------- вход


class DiaryEntryWriteSerializer(serializers.Serializer):
    spot_id = serializers.UUIDField(required=False, allow_null=True, help_text="Опубликованный спот каталога")
    spot_name = serializers.CharField(max_length=160, required=False, allow_blank=True,
                                      help_text="Свободное название места, если спота нет в каталоге")
    date = serializers.DateField()
    duration_min = serializers.IntegerField(min_value=1, max_value=24 * 60, required=False, allow_null=True)
    board_note = serializers.CharField(max_length=160, required=False, allow_blank=True)
    conditions = serializers.CharField(max_length=200, required=False, allow_blank=True)
    wave_height_m = serializers.DecimalField(max_digits=4, decimal_places=1, min_value=0, max_value=30,
                                             required=False, allow_null=True)
    mood_rating = serializers.IntegerField(min_value=1, max_value=5, required=False, allow_null=True)
    notes = serializers.CharField(max_length=5000, required=False, allow_blank=True)
    visibility = serializers.ChoiceField(choices=SurfSession.Visibility.choices, required=False)
    photo_ids = serializers.ListField(child=serializers.UUIDField(), required=False, max_length=10,
                                      help_text="MediaAsset purpose=diary_photo; при правке заменяет набор фото")

    def validate_date(self, value):
        # Допуск +1 день: на Камчатке «сегодня» может наступить раньше, чем в Москве.
        if value > timezone.localdate() + dt.timedelta(days=1):
            raise serializers.ValidationError("Дата катания не может быть в будущем.")
        if value < dt.date(1950, 1, 1):
            raise serializers.ValidationError("Слишком ранняя дата.")
        return value

    def validate_spot_id(self, value):
        if value is None:
            return None
        spot = Spot.objects.filter(pk=value, status=Spot.Status.PUBLISHED).first()
        if spot is None:
            raise serializers.ValidationError("Спот не найден в каталоге.")
        return spot

    def validate(self, attrs):
        if "spot_id" in attrs:
            attrs["spot"] = attrs.pop("spot_id")
        if not self.partial and not attrs.get("spot") and not (attrs.get("spot_name") or "").strip():
            raise serializers.ValidationError({"spot_id": ["Выберите спот или впишите название места."]})
        if "spot_name" in attrs:
            attrs["spot_name"] = attrs["spot_name"].strip()
        return attrs


LEVEL_CHOICES = UserProfile.Level.choices
