from rest_framework import serializers

from apps.accounts.serializers_public import PublicAccountSerializer
from apps.club.models import ClubEvent, EventRegistration
from apps.community.serializers import CatalogRegionSerializer, CatalogSpotSerializer
from apps.mediafiles.serializers import MediaSerializer

# ---------------------------------------------------------------- ответы (описание формы для drf-spectacular)


class ClubOrganizationRefSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    slug = serializers.CharField()
    name = serializers.CharField()
    kind = serializers.CharField()
    url = serializers.CharField()


class ClubEventCardSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    slug = serializers.CharField()
    title = serializers.CharField()
    kind = serializers.ChoiceField(choices=ClubEvent.Kind.choices)
    kind_label = serializers.CharField()
    status = serializers.ChoiceField(choices=ClubEvent.Status.choices)
    status_label = serializers.CharField()
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    timezone = serializers.CharField(help_text="Часовой пояс региона события")
    spot = CatalogSpotSerializer(allow_null=True)
    region = CatalogRegionSerializer(allow_null=True)
    location_note = serializers.CharField(allow_blank=True)
    capacity = serializers.IntegerField(allow_null=True, help_text="null — без лимита")
    registrations_count = serializers.IntegerField()
    waitlist_count = serializers.IntegerField()
    free_places = serializers.IntegerField(allow_null=True, help_text="null — без лимита")
    is_full = serializers.BooleanField()
    registration_open = serializers.BooleanField(help_text="Можно зарегистрироваться сейчас")
    cover = MediaSerializer(allow_null=True)
    organizer = PublicAccountSerializer()
    organizer_organization = ClubOrganizationRefSerializer(allow_null=True)
    url = serializers.CharField()


class ClubRegistrationSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    status = serializers.ChoiceField(choices=EventRegistration.Status.choices)
    status_label = serializers.CharField()
    created_at = serializers.DateTimeField()
    promoted_at = serializers.DateTimeField(allow_null=True)
    waitlist_position = serializers.IntegerField(allow_null=True)


class ClubEventDetailSerializer(ClubEventCardSerializer):
    description = serializers.CharField(allow_blank=True)
    my_registration = ClubRegistrationSerializer(allow_null=True)


class ClubRegistrationResultSerializer(ClubRegistrationSerializer):
    event = ClubEventCardSerializer()


class ClubAnnouncementPublicSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    title = serializers.CharField()
    body = serializers.CharField()
    is_pinned = serializers.BooleanField()
    published_at = serializers.DateTimeField(allow_null=True)


class ClubHighlightSerializer(serializers.Serializer):
    emoji = serializers.CharField()
    title = serializers.CharField()
    text = serializers.CharField()


class ClubAboutSerializer(serializers.Serializer):
    kicker = serializers.CharField()
    title = serializers.CharField()
    text = serializers.CharField()
    invite = serializers.DictField()
    highlights_title = serializers.CharField()
    highlights = ClubHighlightSerializer(many=True)
    roadmap = serializers.ListField(child=serializers.DictField())
    banner = serializers.DictField()


class ClubStatsSerializer(serializers.Serializer):
    members = serializers.IntegerField(help_text="Участники с включённым GG Surfer")
    upcoming_events = serializers.IntegerField()


class ClubOverviewSerializer(serializers.Serializer):
    about = ClubAboutSerializer()
    stats = ClubStatsSerializer()
    announcements = ClubAnnouncementPublicSerializer(many=True)
    upcoming_events = ClubEventCardSerializer(many=True)


class ClubManagedEventSerializer(ClubEventDetailSerializer):
    registration_open_flag = serializers.BooleanField(help_text="Флаг организатора (без учёта статуса и времени)")
    reminder_sent_at = serializers.DateTimeField(allow_null=True)
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class ClubManagedRegistrationSerializer(ClubRegistrationSerializer):
    account = PublicAccountSerializer()
    cancelled_at = serializers.DateTimeField(allow_null=True)
    reminder_sent_at = serializers.DateTimeField(allow_null=True)


class ClubManagedAnnouncementSerializer(ClubAnnouncementPublicSerializer):
    is_published = serializers.BooleanField()
    author = PublicAccountSerializer(allow_null=True)
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


# ---------------------------------------------------------------- вход


class ClubEventWriteSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200)
    kind = serializers.ChoiceField(choices=ClubEvent.Kind.choices, required=False)
    status = serializers.ChoiceField(
        choices=[(s, label) for s, label in ClubEvent.Status.choices if s != ClubEvent.Status.COMPLETED],
        required=False, help_text="draft → published → cancelled; отмена уведомляет участников")
    description = serializers.CharField(max_length=20000, required=False, allow_blank=True)
    spot_id = serializers.UUIDField(required=False, allow_null=True)
    region_id = serializers.IntegerField(required=False, allow_null=True)
    location_note = serializers.CharField(max_length=300, required=False, allow_blank=True)
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    capacity = serializers.IntegerField(min_value=1, max_value=10000, required=False, allow_null=True)
    registration_open = serializers.BooleanField(required=False)
    organizer_organization_id = serializers.UUIDField(required=False, allow_null=True)
    cover_id = serializers.UUIDField(required=False, allow_null=True, help_text="MediaAsset purpose=event_cover")
    cancel_reason = serializers.CharField(max_length=300, required=False, allow_blank=True, write_only=True)

    def validate(self, attrs):
        starts, ends = attrs.get("starts_at"), attrs.get("ends_at")
        if starts and ends and ends <= starts:
            raise serializers.ValidationError({"ends_at": ["Окончание должно быть позже начала."]})
        return attrs


class ClubAnnouncementWriteSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200)
    body = serializers.CharField(max_length=20000)
    is_pinned = serializers.BooleanField(required=False)
    is_published = serializers.BooleanField(required=False, help_text="true — опубликовать сейчас")
    published_at = serializers.DateTimeField(required=False, allow_null=True,
                                             help_text="Отложенная публикация (видно с этого момента)")
