"""Сериализаторы learning. Публичные — без закрытых полей (ACC-14); люди — PublicAccountSerializer, медиа — MediaSerializer."""
import re

from django.db.models import Count
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.accounts.models import Account, UserProfile
from apps.accounts.serializers_public import PublicAccountSerializer
from apps.boards.models import BoardType
from apps.commerce.models import Booking
from apps.learning.models import (
    InstructorCertificate,
    InstructorMedia,
    InstructorOffer,
    InstructorProfile,
    LessonSession,
    SchoolProgram,
    StudentNote,
    WaitlistEntry,
)
from apps.learning.services import common
from apps.mediafiles.serializers import MediaSerializer
from apps.spots.models import Region, Spot

LEVEL_CHOICES = UserProfile.Level.choices
FORMAT_CHOICES = [("individual", "Индивидуально"), ("pair", "Вдвоём"), ("group", "Группа"), ("kids", "Детские занятия")]
LANGUAGE_RE = r"^[a-z]{2,3}$"
CURRENCY_RE = r"^[A-Z]{3}$"
MAX_FUN_FACTS = 5
SLUG_RE = re.compile(r"[-a-zA-Z0-9_]{1,80}")


# --- краткие представления -------------------------------------------------------------------------------------

class LearningRegionSerializer(serializers.Serializer):
    slug = serializers.CharField(read_only=True)
    name = serializers.CharField(read_only=True)


class LearningSpotSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    slug = serializers.CharField(read_only=True)
    name = serializers.CharField(read_only=True)
    region = serializers.SerializerMethodField()

    def get_attribute(self, instance):
        """Скрытый модератором или черновой спот не показывается в карточках занятий и предложений."""
        from apps.spots.services.catalog import is_public_spot

        spot = super().get_attribute(instance)
        return spot if is_public_spot(spot) else None

    @extend_schema_field(LearningRegionSerializer(allow_null=True))
    def get_region(self, spot):
        return LearningRegionSerializer(spot.region).data if spot.region_id else None


class LearningOrganizationSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    slug = serializers.CharField(read_only=True)
    name = serializers.CharField(read_only=True)
    kind = serializers.CharField(read_only=True)


class LessonProgramBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchoolProgram
        fields = ["id", "title", "level", "age_category", "format", "duration_min", "sessions_count"]
        read_only_fields = fields


class LessonOfferBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = InstructorOffer
        fields = ["id", "title", "format", "level", "duration_min"]
        read_only_fields = fields


class LessonSessionBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = LessonSession
        fields = ["id", "title", "starts_at", "ends_at", "status"]
        read_only_fields = fields


class InstructorAccountSerializer(PublicAccountSerializer):
    """Инструктор занятия: публичный аккаунт + есть ли опубликованная карточка (/instructors/{handle})."""

    has_public_profile = serializers.SerializerMethodField()

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_handle(self, account):
        return super().get_handle(account)

    @extend_schema_field(OpenApiTypes.STR)
    def get_display_name(self, account):
        return super().get_display_name(account)

    @extend_schema_field(MediaSerializer(allow_null=True))
    def get_avatar(self, account):
        return super().get_avatar(account)

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_is_deleted(self, account):
        return super().get_is_deleted(account)

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_has_public_profile(self, account):
        profile = getattr(account, "instructor_profile", None)
        return bool(profile and profile.status == InstructorProfile.Status.PUBLISHED and not account.anonymized_at)


# --- поля ввода ------------------------------------------------------------------------------------------------

class RegionSlugsField(serializers.ListField):
    child = serializers.SlugField()

    def to_internal_value(self, data):
        slugs = list(dict.fromkeys(super().to_internal_value(data)))
        regions = list(Region.objects.filter(slug__in=slugs))
        unknown = set(slugs) - {r.slug for r in regions}
        if unknown:
            raise serializers.ValidationError(f"Неизвестные регионы: {', '.join(sorted(unknown))}.")
        return regions


class SpotSlugsField(serializers.ListField):
    child = serializers.SlugField()

    def to_internal_value(self, data):
        slugs = list(dict.fromkeys(super().to_internal_value(data)))
        spots = list(Spot.objects.filter(slug__in=slugs, status=Spot.Status.PUBLISHED))
        unknown = set(slugs) - {s.slug for s in spots}
        if unknown:
            raise serializers.ValidationError(f"Неизвестные споты: {', '.join(sorted(unknown))}.")
        return spots


@extend_schema_field(OpenApiTypes.STR)
class SpotSlugField(serializers.Field):
    """slug опубликованного спота → объект Spot."""

    default_error_messages = {"invalid": "Укажите slug спота.", "not_found": "Спот не найден."}

    def to_internal_value(self, data):
        if not isinstance(data, str) or not SLUG_RE.fullmatch(data):
            self.fail("invalid")
        spot = Spot.objects.filter(slug=data, status=Spot.Status.PUBLISHED).select_related("region").first()
        if spot is None:
            self.fail("not_found")
        return spot

    def to_representation(self, value):
        return value.slug


def validate_year(value):
    if value is not None and not 1940 <= value <= timezone.localdate().year:
        raise serializers.ValidationError("Укажите год от 1940 до текущего.")
    return value


# --- профиль инструктора ---------------------------------------------------------------------------------------

class _ProfilePeopleMixin(serializers.Serializer):
    handle = serializers.SerializerMethodField()
    display_name = serializers.SerializerMethodField()
    first_name = serializers.SerializerMethodField()
    last_name = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()

    def _p(self, obj):
        return getattr(obj.account, "profile", None)

    @extend_schema_field(OpenApiTypes.STR)
    def get_handle(self, obj):
        p = self._p(obj)
        return p.handle if p else None

    @extend_schema_field(OpenApiTypes.STR)
    def get_display_name(self, obj):
        p = self._p(obj)
        return p.display_name if p else "Инструктор"

    @extend_schema_field(OpenApiTypes.STR)
    def get_first_name(self, obj):
        p = self._p(obj)
        return p.first_name if p else ""

    @extend_schema_field(OpenApiTypes.STR)
    def get_last_name(self, obj):
        p = self._p(obj)
        return p.last_name if p else ""

    @extend_schema_field(MediaSerializer(allow_null=True))
    def get_avatar(self, obj):
        p = self._p(obj)
        return MediaSerializer(p.avatar).data if p and p.avatar_id else None


class InstructorCardSerializer(_ProfilePeopleMixin, serializers.ModelSerializer):
    """Карточка каталога (INS-01, INS-03): бейдж «проверен» — только после модерации (BR-07, ATX-05)."""

    regions = LearningRegionSerializer(many=True, read_only=True)
    spots = LearningSpotSerializer(many=True, read_only=True)
    price_from = serializers.SerializerMethodField()
    certificate_status = serializers.SerializerMethodField()
    schools = serializers.SerializerMethodField()

    class Meta:
        model = InstructorProfile
        fields = ["id", "handle", "display_name", "first_name", "last_name", "avatar", "headline", "regions", "spots",
                  "surfing_since", "teaching_since", "riding_level", "formats", "student_levels", "board_types",
                  "languages", "price_from", "currency", "certificate_status", "rating_avg", "rating_count",
                  "schools", "is_demo"]
        read_only_fields = fields

    @extend_schema_field(serializers.DecimalField(max_digits=10, decimal_places=2, allow_null=True))
    def get_price_from(self, obj):
        value = getattr(obj, "effective_price", None)
        if value is None and not hasattr(obj, "effective_price"):
            prices = [o.price for o in obj.offers.all() if o.is_active]
            candidates = [p for p in [obj.price_from, min(prices) if prices else None] if p is not None]
            value = min(candidates) if candidates else None
        return f"{value:.2f}" if value is not None else None

    @extend_schema_field(serializers.ChoiceField(choices=["none", "uploaded", "verified"]))
    def get_certificate_status(self, obj):
        return obj.certificate_status

    @extend_schema_field(LearningOrganizationSerializer(many=True))
    def get_schools(self, obj):
        memberships = getattr(obj.account, "public_school_memberships", None)
        if memberships is None:
            from apps.organizations.models import Membership, Organization

            memberships = Membership.objects.filter(
                account=obj.account, status=Membership.Status.ACTIVE, organization__kind=Organization.Kind.SCHOOL,
                organization__status=Organization.Status.PUBLISHED,
            ).select_related("organization")
        seen, result = set(), []
        for m in memberships:
            if m.organization_id not in seen:
                seen.add(m.organization_id)
                result.append(LearningOrganizationSerializer(m.organization).data)
        return result


class InstructorMediaSerializer(serializers.ModelSerializer):
    media = MediaSerializer(read_only=True)

    class Meta:
        model = InstructorMedia
        fields = ["id", "position", "media"]
        read_only_fields = fields


class OfferPublicSerializer(serializers.ModelSerializer):
    spot = LearningSpotSerializer(read_only=True, allow_null=True)

    class Meta:
        model = InstructorOffer
        fields = ["id", "title", "description", "format", "level", "duration_min", "price", "currency", "capacity",
                  "spot", "equipment_included", "equipment_note", "rules"]
        read_only_fields = fields


class CertificatePublicSerializer(serializers.ModelSerializer):
    is_expired = serializers.SerializerMethodField()
    scan_available = serializers.SerializerMethodField()

    class Meta:
        model = InstructorCertificate
        fields = ["id", "title", "issuer", "status", "issued_on", "valid_until", "is_expired", "scan_available"]
        read_only_fields = fields

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_is_expired(self, cert):
        return bool(cert.valid_until and cert.valid_until < timezone.localdate())

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_scan_available(self, cert):
        return (cert.status == InstructorCertificate.Status.VERIFIED and cert.allow_public_scan
                and not self.get_is_expired(cert))


class SessionPublicSerializer(serializers.ModelSerializer):
    """Публичная карточка занятия: время в ISO с часовым поясом, свободные места (SCH-05, ATX-14)."""

    kind = serializers.SerializerMethodField()
    timezone = serializers.SerializerMethodField()
    seats_taken = serializers.SerializerMethodField()
    free_seats = serializers.SerializerMethodField()
    is_full = serializers.SerializerMethodField()
    program = LessonProgramBriefSerializer(read_only=True, allow_null=True)
    offer = LessonOfferBriefSerializer(read_only=True, allow_null=True)
    organization = LearningOrganizationSerializer(read_only=True, allow_null=True)
    instructor = InstructorAccountSerializer(read_only=True, allow_null=True)
    spot = LearningSpotSerializer(read_only=True, allow_null=True)

    class Meta:
        model = LessonSession
        fields = ["id", "kind", "title", "status", "starts_at", "ends_at", "timezone", "capacity", "seats_taken",
                  "free_seats", "is_full", "price", "currency", "program", "offer", "organization", "instructor",
                  "spot", "reschedule_reason", "cancel_reason"]
        read_only_fields = fields

    @extend_schema_field(serializers.ChoiceField(choices=["school", "private"]))
    def get_kind(self, obj):
        return "school" if obj.organization_id else "private"

    @extend_schema_field(OpenApiTypes.STR)
    def get_timezone(self, obj):
        return common.tz_name_for(obj)

    @extend_schema_field(OpenApiTypes.INT)
    def get_seats_taken(self, obj):
        return common.seats_taken(obj)

    @extend_schema_field(OpenApiTypes.INT)
    def get_free_seats(self, obj):
        return common.free_seats(obj)

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_is_full(self, obj):
        return common.free_seats(obj) <= 0


class WaitlistStatusSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    status = serializers.CharField(read_only=True)
    position = serializers.IntegerField(read_only=True, allow_null=True)
    created_at = serializers.DateTimeField(read_only=True)


class SessionDetailSerializer(SessionPublicSerializer):
    my_waitlist = serializers.SerializerMethodField()
    waitlist_count = serializers.SerializerMethodField()

    class Meta(SessionPublicSerializer.Meta):
        fields = SessionPublicSerializer.Meta.fields + ["my_waitlist", "waitlist_count"]
        read_only_fields = fields

    @extend_schema_field(WaitlistStatusSerializer(allow_null=True))
    def get_my_waitlist(self, obj):
        from apps.learning.services.waitlist import current_entry, position_of

        request = self.context.get("request")
        entry = current_entry(obj, getattr(request, "user", None))
        if entry is None:
            return None
        return {"id": entry.pk, "status": entry.status, "position": position_of(entry), "created_at": entry.created_at}

    @extend_schema_field(OpenApiTypes.INT)
    def get_waitlist_count(self, obj):
        return obj.waitlist.filter(status=WaitlistEntry.Status.WAITING).count()


class InstructorSlotSerializer(SessionPublicSerializer):
    """Свободное окно в профиле инструктора."""


class InstructorDetailSerializer(InstructorCardSerializer):
    media = serializers.SerializerMethodField()
    offers = serializers.SerializerMethodField()
    upcoming_slots = serializers.SerializerMethodField()
    certificates = serializers.SerializerMethodField()

    class Meta(InstructorCardSerializer.Meta):
        fields = InstructorCardSerializer.Meta.fields + [
            "about", "fun_facts", "contact_note", "media", "offers", "upcoming_slots", "certificates", "published_at"]
        read_only_fields = fields

    @extend_schema_field(InstructorMediaSerializer(many=True))
    def get_media(self, obj):
        items = obj.media_items.select_related("media").filter(media__status="ready")
        return InstructorMediaSerializer(items, many=True).data

    @extend_schema_field(OfferPublicSerializer(many=True))
    def get_offers(self, obj):
        offers = obj.offers.filter(is_active=True).select_related("spot__region").order_by("price", "title")
        return OfferPublicSerializer(offers, many=True).data

    @extend_schema_field(InstructorSlotSerializer(many=True))
    def get_upcoming_slots(self, obj):
        from apps.learning.services.catalog import upcoming_free_slots

        return InstructorSlotSerializer(upcoming_free_slots(obj), many=True, context=self.context).data

    @extend_schema_field(CertificatePublicSerializer(many=True))
    def get_certificates(self, obj):
        certs = obj.certificates.filter(status__in=[InstructorCertificate.Status.UPLOADED,
                                                    InstructorCertificate.Status.VERIFIED]).order_by("-created_at")
        return CertificatePublicSerializer(certs, many=True).data


class InstructorPublishCheckSerializer(serializers.Serializer):
    can_publish = serializers.BooleanField()
    missing = serializers.DictField(child=serializers.CharField())


class InstructorOwnSerializer(InstructorCardSerializer):
    """Своя карточка в кабинете: сырой price_from, статус публикации, чек-лист обязательных полей (ACC-15)."""

    price_from = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True, allow_null=True)
    effective_price_from = serializers.SerializerMethodField()
    media = serializers.SerializerMethodField()
    publish_check = serializers.SerializerMethodField()

    class Meta(InstructorCardSerializer.Meta):
        fields = InstructorCardSerializer.Meta.fields + [
            "effective_price_from", "about", "fun_facts", "contact_note", "allow_overlap", "status", "published_at",
            "media", "publish_check", "created_at", "updated_at"]
        read_only_fields = fields

    @extend_schema_field(serializers.DecimalField(max_digits=10, decimal_places=2, allow_null=True))
    def get_effective_price_from(self, obj):
        return InstructorCardSerializer.get_price_from(self, obj)

    @extend_schema_field(InstructorMediaSerializer(many=True))
    def get_media(self, obj):
        items = obj.media_items.select_related("media").order_by("position", "id")
        return InstructorMediaSerializer(items, many=True).data

    @extend_schema_field(InstructorPublishCheckSerializer)
    def get_publish_check(self, obj):
        from apps.learning.services.instructors import publish_requirements

        missing = publish_requirements(obj)
        if not obj.account.is_email_verified:
            missing["email"] = "Подтвердите email."
        return {"can_publish": not missing, "missing": missing}


class InstructorProfileWriteSerializer(serializers.Serializer):
    headline = serializers.CharField(max_length=200, required=False, allow_blank=True)
    about = serializers.CharField(max_length=4000, required=False, allow_blank=True)
    fun_facts = serializers.ListField(child=serializers.CharField(max_length=200, allow_blank=True),
                                      max_length=MAX_FUN_FACTS, required=False)
    region_slugs = RegionSlugsField(required=False, max_length=20)
    spot_slugs = SpotSlugsField(required=False, max_length=50)
    surfing_since = serializers.IntegerField(required=False, allow_null=True, validators=[validate_year])
    teaching_since = serializers.IntegerField(required=False, allow_null=True, validators=[validate_year])
    riding_level = serializers.ChoiceField(choices=LEVEL_CHOICES, required=False, allow_blank=True)
    formats = serializers.ListField(child=serializers.ChoiceField(choices=FORMAT_CHOICES), required=False, max_length=10)
    student_levels = serializers.ListField(child=serializers.ChoiceField(choices=LEVEL_CHOICES), required=False,
                                           max_length=10)
    board_types = serializers.ListField(child=serializers.SlugField(max_length=40), required=False, max_length=20)
    languages = serializers.ListField(child=serializers.RegexField(LANGUAGE_RE), required=False, max_length=10)
    price_from = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0, required=False, allow_null=True)
    currency = serializers.RegexField(CURRENCY_RE, required=False)
    contact_note = serializers.CharField(max_length=300, required=False, allow_blank=True)
    allow_overlap = serializers.BooleanField(required=False)

    def validate_board_types(self, value):
        value = list(dict.fromkeys(value))
        known = set(BoardType.objects.filter(workshop__isnull=True, code__in=value).values_list("code", flat=True))
        unknown = [v for v in value if v not in known]
        if unknown:
            raise serializers.ValidationError(f"Неизвестные типы досок: {', '.join(unknown)}.")
        return value

    def validate_fun_facts(self, value):
        return [v.strip() for v in value if v.strip()]

    def validate(self, attrs):
        surfing, teaching = attrs.get("surfing_since"), attrs.get("teaching_since")
        if surfing and teaching and teaching < surfing:
            raise serializers.ValidationError({"teaching_since": ["Преподавание не может начаться раньше катания."]})
        for key in ("formats", "student_levels", "languages"):
            if key in attrs:
                attrs[key] = list(dict.fromkeys(attrs[key]))
        if "region_slugs" in attrs:
            attrs["regions"] = attrs.pop("region_slugs")
        if "spot_slugs" in attrs:
            attrs["spots"] = attrs.pop("spot_slugs")
        return attrs


# --- медиа -----------------------------------------------------------------------------------------------------

class InstructorMediaAddSerializer(serializers.Serializer):
    media_id = serializers.UUIDField()


class InstructorMediaReorderSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.IntegerField(min_value=1), allow_empty=False, max_length=100)


class InstructorMediaMoveSerializer(serializers.Serializer):
    position = serializers.IntegerField(min_value=1)


# --- сертификаты -----------------------------------------------------------------------------------------------

class CertificateOwnSerializer(CertificatePublicSerializer):
    document = MediaSerializer(read_only=True)

    class Meta(CertificatePublicSerializer.Meta):
        fields = CertificatePublicSerializer.Meta.fields + [
            "allow_public_scan", "moderator_comment", "decided_at", "document", "created_at", "updated_at"]
        read_only_fields = fields


class CertificateUploadSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200)
    issuer = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")
    issued_on = serializers.DateField(required=False, allow_null=True)
    valid_until = serializers.DateField(required=False, allow_null=True)
    document_id = serializers.UUIDField()
    allow_public_scan = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        issued, valid = attrs.get("issued_on"), attrs.get("valid_until")
        if issued and issued > timezone.localdate():
            raise serializers.ValidationError({"issued_on": ["Дата выдачи не может быть в будущем."]})
        if issued and valid and valid < issued:
            raise serializers.ValidationError({"valid_until": ["Срок действия раньше даты выдачи."]})
        return attrs


class CertificateUpdateSerializer(serializers.Serializer):
    allow_public_scan = serializers.BooleanField()


class CertificateScanUrlSerializer(serializers.Serializer):
    url = serializers.URLField()
    expires_in = serializers.IntegerField()
    content_type = serializers.CharField()


# --- предложения -----------------------------------------------------------------------------------------------

class OfferSerializer(serializers.ModelSerializer):
    spot = LearningSpotSerializer(read_only=True, allow_null=True)
    spot_slug = SpotSlugField(write_only=True, required=False, allow_null=True)
    level = serializers.ChoiceField(choices=LEVEL_CHOICES, required=False, allow_blank=True)
    duration_min = serializers.IntegerField(min_value=15, max_value=1440, required=False)
    capacity = serializers.IntegerField(min_value=1, max_value=100, required=False)
    price = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0)
    currency = serializers.RegexField(CURRENCY_RE, required=False)
    upcoming_sessions = serializers.SerializerMethodField()

    class Meta:
        model = InstructorOffer
        fields = ["id", "title", "description", "format", "level", "duration_min", "price", "currency", "capacity",
                  "spot", "spot_slug", "equipment_included", "equipment_note", "rules", "is_active",
                  "upcoming_sessions", "created_at", "updated_at"]
        read_only_fields = ["id", "spot", "upcoming_sessions", "created_at", "updated_at"]

    @extend_schema_field(OpenApiTypes.INT)
    def get_upcoming_sessions(self, obj):
        return obj.sessions.filter(status=LessonSession.Status.SCHEDULED, starts_at__gt=timezone.now()).count()

    def validate(self, attrs):
        if "spot_slug" in attrs:
            attrs["spot"] = attrs.pop("spot_slug")
        fmt = attrs.get("format", getattr(self.instance, "format", InstructorOffer.Format.INDIVIDUAL))
        capacity = attrs.get("capacity", getattr(self.instance, "capacity", 1))
        if fmt == InstructorOffer.Format.INDIVIDUAL and capacity > 2:
            raise serializers.ValidationError({"capacity": ["Индивидуальное занятие — не больше 2 учеников."]})
        return attrs


# --- программы школы -------------------------------------------------------------------------------------------

class ProgramSerializer(serializers.ModelSerializer):
    level = serializers.ChoiceField(choices=LEVEL_CHOICES, required=False, allow_blank=True)
    duration_min = serializers.IntegerField(min_value=15, max_value=1440, required=False)
    sessions_count = serializers.IntegerField(min_value=1, max_value=100, required=False)
    max_group_size = serializers.IntegerField(min_value=1, max_value=500, required=False)
    price = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0)
    currency = serializers.RegexField(CURRENCY_RE, required=False)
    upcoming_sessions = serializers.SerializerMethodField()

    class Meta:
        model = SchoolProgram
        fields = ["id", "title", "description", "level", "age_category", "format", "duration_min", "sessions_count",
                  "price", "currency", "max_group_size", "equipment_included", "is_active", "upcoming_sessions",
                  "created_at", "updated_at"]
        read_only_fields = ["id", "upcoming_sessions", "created_at", "updated_at"]

    @extend_schema_field(OpenApiTypes.INT)
    def get_upcoming_sessions(self, obj):
        return obj.sessions.filter(status=LessonSession.Status.SCHEDULED, starts_at__gt=timezone.now()).count()


# --- занятия: управление ---------------------------------------------------------------------------------------

class SessionBookingsSummarySerializer(serializers.Serializer):
    requested = serializers.IntegerField()
    confirmed = serializers.IntegerField()
    in_progress = serializers.IntegerField()
    completed = serializers.IntegerField()
    no_show = serializers.IntegerField()
    cancelled = serializers.IntegerField()
    declined = serializers.IntegerField()


class SessionManageSerializer(SessionPublicSerializer):
    bookings_summary = serializers.SerializerMethodField()
    waitlist_count = serializers.SerializerMethodField()

    class Meta(SessionPublicSerializer.Meta):
        fields = SessionPublicSerializer.Meta.fields + [
            "notes", "allow_overlap", "bookings_summary", "waitlist_count", "cancelled_at", "completed_at",
            "created_at", "updated_at"]
        read_only_fields = fields

    @extend_schema_field(SessionBookingsSummarySerializer)
    def get_bookings_summary(self, obj):
        counts = {s: 0 for s in Booking.Status.values}
        cached = getattr(obj, "summary_bookings", None)
        if cached is not None:
            for b in cached:
                counts[b.status] += 1
            return counts
        for row in obj.bookings.order_by().values("status").annotate(n=Count("id")):
            counts[row["status"]] = row["n"]
        return counts

    @extend_schema_field(OpenApiTypes.INT)
    def get_waitlist_count(self, obj):
        cached = getattr(obj, "waiting_entries", None)
        if cached is not None:
            return len(cached)
        return obj.waitlist.filter(status=WaitlistEntry.Status.WAITING).count()


class _SessionTimesMixin(serializers.Serializer):
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField(required=False, allow_null=True)

    def validate(self, attrs):
        start, end = attrs.get("starts_at"), attrs.get("ends_at")
        if start and end and end <= start:
            raise serializers.ValidationError({"ends_at": ["Окончание должно быть позже начала."]})
        if "spot_slug" in attrs:
            attrs["spot"] = attrs.pop("spot_slug")
        return attrs


class SchoolSessionCreateSerializer(_SessionTimesMixin):
    program_id = serializers.UUIDField(required=False, allow_null=True)
    title = serializers.CharField(max_length=200, required=False, allow_blank=True)
    instructor_id = serializers.UUIDField(required=False, allow_null=True)
    spot_slug = SpotSlugField(required=False, allow_null=True)
    capacity = serializers.IntegerField(min_value=1, max_value=500, required=False)
    price = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0, required=False, allow_null=True)
    currency = serializers.RegexField(CURRENCY_RE, required=False)
    notes = serializers.CharField(max_length=2000, required=False, allow_blank=True)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        program_id = attrs.pop("program_id", None)
        if program_id:
            org = self.context["organization"]
            program = SchoolProgram.objects.filter(pk=program_id, organization=org).first()
            if program is None:
                raise serializers.ValidationError({"program_id": ["Программа не найдена в этой школе."]})
            attrs["program"] = program
        return attrs


class SessionUpdateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200, required=False)
    program_id = serializers.UUIDField(required=False, allow_null=True)
    instructor_id = serializers.UUIDField(required=False, allow_null=True)
    spot_slug = SpotSlugField(required=False, allow_null=True)
    starts_at = serializers.DateTimeField(required=False)
    ends_at = serializers.DateTimeField(required=False)
    reschedule_reason = serializers.CharField(max_length=300, required=False, allow_blank=True)
    capacity = serializers.IntegerField(min_value=1, max_value=500, required=False)
    price = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0, required=False, allow_null=True)
    currency = serializers.RegexField(CURRENCY_RE, required=False)
    notes = serializers.CharField(max_length=2000, required=False, allow_blank=True)

    def validate(self, attrs):
        if "spot_slug" in attrs:
            attrs["spot"] = attrs.pop("spot_slug")
        if "program_id" in attrs:
            program_id = attrs.pop("program_id")
            session = self.context["session"]
            program = None
            if program_id:
                program = SchoolProgram.objects.filter(pk=program_id, organization_id=session.organization_id).first()
                if program is None:
                    raise serializers.ValidationError({"program_id": ["Программа не найдена в этой школе."]})
            attrs["program"] = program
        return attrs


class PrivateSessionCreateSerializer(_SessionTimesMixin):
    offer_id = serializers.UUIDField()
    title = serializers.CharField(max_length=200, required=False, allow_blank=True)
    spot_slug = SpotSlugField(required=False, allow_null=True)
    notes = serializers.CharField(max_length=2000, required=False, allow_blank=True)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        offer = InstructorOffer.objects.filter(pk=attrs.pop("offer_id"), instructor=self.context["profile"]).first()
        if offer is None:
            raise serializers.ValidationError({"offer_id": ["Предложение не найдено."]})
        attrs["offer"] = offer
        return attrs


class PrivateSessionUpdateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200, required=False)
    spot_slug = SpotSlugField(required=False, allow_null=True)
    starts_at = serializers.DateTimeField(required=False)
    ends_at = serializers.DateTimeField(required=False)
    reschedule_reason = serializers.CharField(max_length=300, required=False, allow_blank=True)
    notes = serializers.CharField(max_length=2000, required=False, allow_blank=True)

    def validate(self, attrs):
        if "spot_slug" in attrs:
            attrs["spot"] = attrs.pop("spot_slug")
        return attrs


class SessionAssignSerializer(serializers.Serializer):
    instructor_id = serializers.UUIDField(allow_null=True)


class SessionRescheduleSerializer(serializers.Serializer):
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField(required=False)
    reason = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")


class SessionCancelSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=300, min_length=2)


class SessionCompleteSerializer(serializers.Serializer):
    no_show_booking_ids = serializers.ListField(child=serializers.UUIDField(), required=False, default=list,
                                                max_length=500)


class SessionCompleteResultSerializer(serializers.Serializer):
    session = SessionManageSerializer()
    completed_booking_ids = serializers.ListField(child=serializers.UUIDField())
    no_show_booking_ids = serializers.ListField(child=serializers.UUIDField())


# --- расписание инструктора (INS-07, AT-06) --------------------------------------------------------------------

class SessionParticipantSerializer(serializers.Serializer):
    booking_id = serializers.UUIDField(source="pk")
    status = serializers.CharField()
    seats = serializers.IntegerField()
    name = serializers.SerializerMethodField()
    participant_is_minor = serializers.BooleanField()
    customer = PublicAccountSerializer()

    @extend_schema_field(OpenApiTypes.STR)
    def get_name(self, booking):
        if booking.participant_name:
            return booking.participant_name
        profile = getattr(booking.customer, "profile", None)
        return profile.display_name if profile and not booking.customer.anonymized_at else "Ученик"


class ScheduleItemSerializer(SessionPublicSerializer):
    participants = serializers.SerializerMethodField()
    requested_count = serializers.SerializerMethodField()
    can_manage = serializers.SerializerMethodField()

    class Meta(SessionPublicSerializer.Meta):
        fields = SessionPublicSerializer.Meta.fields + ["participants", "requested_count", "can_manage", "notes"]
        read_only_fields = fields

    def _bookings(self, obj):
        cached = getattr(obj, "schedule_bookings", None)
        if cached is None:
            cached = list(obj.bookings.exclude(status__in=[Booking.Status.DECLINED, Booking.Status.CANCELLED])
                          .select_related("customer__profile__avatar"))
        return cached

    @extend_schema_field(SessionParticipantSerializer(many=True))
    def get_participants(self, obj):
        rows = [b for b in self._bookings(obj) if b.status in common.SEAT_STATUSES]
        return SessionParticipantSerializer(rows, many=True).data

    @extend_schema_field(OpenApiTypes.INT)
    def get_requested_count(self, obj):
        return sum(1 for b in self._bookings(obj) if b.status == Booking.Status.REQUESTED)

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_can_manage(self, obj):
        managed = self.context.get("managed_org_ids")
        user = getattr(self.context.get("request"), "user", None)
        if managed is None or user is None:
            from apps.learning.services.access import can_manage_session

            return can_manage_session(user, obj)
        if obj.organization_id:
            return obj.organization_id in managed
        return bool(obj.offer_id and obj.offer.instructor.account_id == user.pk)


# --- лист ожидания ---------------------------------------------------------------------------------------------

class WaitlistEntrySerializer(serializers.ModelSerializer):
    session_id = serializers.UUIDField(read_only=True)
    position = serializers.SerializerMethodField()

    class Meta:
        model = WaitlistEntry
        fields = ["id", "session_id", "status", "position", "created_at"]
        read_only_fields = fields

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_position(self, obj):
        from apps.learning.services.waitlist import position_of

        return position_of(obj)


# --- ученики и заметки (SCH-10) --------------------------------------------------------------------------------

class StudentNoteSerializer(serializers.ModelSerializer):
    student = PublicAccountSerializer(read_only=True)
    author = PublicAccountSerializer(read_only=True)
    organization = LearningOrganizationSerializer(read_only=True, allow_null=True)
    session = LessonSessionBriefSerializer(read_only=True, allow_null=True)
    can_edit = serializers.SerializerMethodField()

    class Meta:
        model = StudentNote
        fields = ["id", "student", "author", "organization", "session", "level", "comment", "visible_to_student",
                  "can_edit", "created_at", "updated_at"]
        read_only_fields = fields

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_can_edit(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        return bool(user and user.is_authenticated and obj.author_id == user.pk)


class StudentNoteCreateSerializer(serializers.Serializer):
    student_id = serializers.UUIDField()
    organization_id = serializers.UUIDField(required=False, allow_null=True)
    session_id = serializers.UUIDField(required=False, allow_null=True)
    level = serializers.ChoiceField(choices=LEVEL_CHOICES, required=False, allow_blank=True, default="")
    comment = serializers.CharField(max_length=4000)
    visible_to_student = serializers.BooleanField(required=False, default=True)

    def validate(self, attrs):
        from apps.organizations.models import Organization

        student = Account.objects.filter(pk=attrs.pop("student_id"), is_active=True).first()
        if student is None:
            raise serializers.ValidationError({"student_id": ["Ученик не найден."]})
        attrs["student"] = student
        org_id = attrs.pop("organization_id", None)
        attrs["organization"] = None
        if org_id:
            attrs["organization"] = Organization.objects.filter(pk=org_id).first()
            if attrs["organization"] is None:
                raise serializers.ValidationError({"organization_id": ["Организация не найдена."]})
        session_id = attrs.pop("session_id", None)
        attrs["session"] = None
        if session_id:
            attrs["session"] = LessonSession.objects.filter(pk=session_id).select_related("organization").first()
            if attrs["session"] is None:
                raise serializers.ValidationError({"session_id": ["Занятие не найдено."]})
        return attrs


class StudentNoteUpdateSerializer(serializers.Serializer):
    level = serializers.ChoiceField(choices=LEVEL_CHOICES, required=False, allow_blank=True)
    comment = serializers.CharField(max_length=4000, required=False)
    visible_to_student = serializers.BooleanField(required=False)


class StudentRowSerializer(serializers.Serializer):
    student = PublicAccountSerializer()
    bookings_count = serializers.IntegerField()
    completed_count = serializers.IntegerField()
    no_show_count = serializers.IntegerField()
    attendance_pct = serializers.FloatField(allow_null=True)
    is_repeat = serializers.BooleanField()
    first_session_at = serializers.DateTimeField(allow_null=True)
    last_session_at = serializers.DateTimeField(allow_null=True)
    next_session_at = serializers.DateTimeField(allow_null=True)
    last_session = LessonSessionBriefSerializer(allow_null=True)


class MyStudentRowSerializer(StudentRowSerializer):
    notes = StudentNoteSerializer(many=True)


class SchoolStudentRowSerializer(StudentRowSerializer):
    notes_count = serializers.SerializerMethodField()

    @extend_schema_field(OpenApiTypes.INT)
    def get_notes_count(self, row):
        return len(row.get("notes", []))


class StudentsSummarySerializer(serializers.Serializer):
    unique_students = serializers.IntegerField(help_text="Ученики с ≥1 завершённым занятием")
    repeat_students = serializers.IntegerField(help_text="Ученики с ≥2 завершёнными занятиями")
    repeat_students_pct = serializers.FloatField(allow_null=True)
    students_with_bookings = serializers.IntegerField()

