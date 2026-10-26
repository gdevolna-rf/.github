"""Сериализаторы accounts. Закрытые поля профиля (email, phone, birth_date, private_contacts) — только в /me (ACC-14)."""
import datetime as dt

from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.accounts.models import (
    AccountDeletionRequest,
    ConsentRecord,
    DataExportRequest,
    Specialty,
    StaffRole,
    UserProfile,
    UserSpecialty,
)
from apps.accounts.serializers_public import PublicAccountSerializer
from apps.mediafiles.serializers import MediaSerializer


# --- общие краткие представления ---------------------------------------------------------------------------

class AccountRegionSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    slug = serializers.CharField()
    name = serializers.CharField()


class AccountSpotSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    slug = serializers.CharField()
    name = serializers.CharField()


class SpecialtySerializer(serializers.ModelSerializer):
    class Meta:
        model = Specialty
        fields = ["code", "name", "description"]


class UserSpecialtySerializer(serializers.ModelSerializer):
    code = serializers.CharField(source="specialty_id")
    name = serializers.CharField(source="specialty.name")

    class Meta:
        model = UserSpecialty
        fields = ["code", "name", "status", "is_primary", "activated_at", "disabled_at"]


# --- /me ----------------------------------------------------------------------------------------------------

class MeProfileSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(read_only=True)
    avatar = MediaSerializer(allow_null=True)
    region = AccountRegionSerializer(allow_null=True)
    favorite_spot_ids = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = [
            "handle", "first_name", "last_name", "display_name", "avatar", "region", "city", "bio", "fun_facts",
            "surfing_since", "riding_level", "preferred_board_types", "favorite_spot_ids", "interests", "languages",
            "phone", "birth_date", "private_contacts", "gg_surfer_enabled", "gg_contact_policy", "gg_show_region",
            "gg_show_age", "birthday_greetings_consent", "show_birthday",
        ]

    @extend_schema_field(serializers.ListField(child=serializers.UUIDField()))
    def get_favorite_spot_ids(self, profile):
        return [str(pk) for pk in profile.favorite_spots.values_list("pk", flat=True)]


class MeOrganizationSerializer(serializers.Serializer):
    id = serializers.UUIDField(source="organization.id")
    slug = serializers.CharField(source="organization.slug")
    name = serializers.CharField(source="organization.name")
    kind = serializers.CharField(source="organization.kind")
    status = serializers.CharField(source="organization.status", help_text="Статус организации")
    role = serializers.CharField()
    membership_id = serializers.UUIDField(source="id")


class MeInstructorProfileSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    status = serializers.CharField()


class TwoFactorStateSerializer(serializers.Serializer):
    enabled = serializers.BooleanField()
    verified = serializers.BooleanField(help_text="Текущая сессия подтверждена TOTP-кодом")
    required = serializers.BooleanField(help_text="Обязательна для служебных ролей")


class MeDeletionSerializer(serializers.Serializer):
    requested_at = serializers.DateTimeField()
    scheduled_for = serializers.DateTimeField()


class MeSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    email = serializers.EmailField()
    email_verified = serializers.SerializerMethodField()
    date_joined = serializers.DateTimeField()
    profile = serializers.SerializerMethodField()
    specialties = serializers.SerializerMethodField()
    available_specialties = serializers.SerializerMethodField()
    staff_roles = serializers.SerializerMethodField()
    organizations = serializers.SerializerMethodField()
    instructor_profile = serializers.SerializerMethodField()
    two_factor = serializers.SerializerMethodField()
    deletion = serializers.SerializerMethodField()

    def get_email_verified(self, account) -> bool:
        return account.is_email_verified

    @extend_schema_field(MeProfileSerializer)
    def get_profile(self, account):
        profile = UserProfile.objects.select_related("avatar", "region").filter(account=account).first()
        return MeProfileSerializer(profile).data if profile else None

    @extend_schema_field(UserSpecialtySerializer(many=True))
    def get_specialties(self, account):
        qs = account.specialties.select_related("specialty").order_by("specialty__sort_order")
        return UserSpecialtySerializer(qs, many=True).data

    @extend_schema_field(SpecialtySerializer(many=True))
    def get_available_specialties(self, account):
        return SpecialtySerializer(Specialty.objects.all(), many=True).data

    @extend_schema_field(serializers.ListField(child=serializers.ChoiceField(choices=StaffRole.Role.choices)))
    def get_staff_roles(self, account):
        from apps.accounts.services.roles import active_roles

        return sorted(active_roles(account))

    @extend_schema_field(MeOrganizationSerializer(many=True))
    def get_organizations(self, account):
        from apps.organizations.models import Membership

        qs = Membership.objects.filter(account=account, status=Membership.Status.ACTIVE).select_related(
            "organization").order_by("joined_at")
        return MeOrganizationSerializer(qs, many=True).data

    @extend_schema_field(MeInstructorProfileSerializer(allow_null=True))
    def get_instructor_profile(self, account):
        from apps.learning.models import InstructorProfile

        profile = InstructorProfile.objects.filter(account=account).only("id", "status").first()
        return {"id": str(profile.id), "status": profile.status} if profile else None

    @extend_schema_field(TwoFactorStateSerializer)
    def get_two_factor(self, account):
        from apps.accounts.services.two_factor import state

        return state(account, self.context.get("request"))

    @extend_schema_field(MeDeletionSerializer(allow_null=True))
    def get_deletion(self, account):
        if not account.deletion_requested_at:
            return None
        deletion = account.deletion_requests.filter(status=AccountDeletionRequest.Status.REQUESTED).first()
        if deletion is None:
            return None
        return {"requested_at": deletion.created_at, "scheduled_for": deletion.scheduled_for}


class RegisterResponseSerializer(MeSerializer):
    next_step = serializers.CharField(allow_null=True, help_text="create_school — предложить создать школу")


# --- auth ---------------------------------------------------------------------------------------------------

class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(write_only=True, max_length=128, trim_whitespace=False)
    first_name = serializers.CharField(max_length=80)
    last_name = serializers.CharField(max_length=80, allow_blank=True, required=False, default="")
    primary_type = serializers.ChoiceField(choices=["surfer", "instructor", "shaper", "school", "rental"])
    extra_specialties = serializers.ListField(
        child=serializers.ChoiceField(choices=["instructor", "shaper", "rental", "school"]),
        required=False, default=list, max_length=4,
    )
    accept_terms = serializers.BooleanField()
    accept_privacy = serializers.BooleanField()


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(trim_whitespace=False, max_length=128)


class CsrfSerializer(serializers.Serializer):
    csrf_token = serializers.CharField()


class EmailTokenSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=512)


class EmailVerifiedSerializer(serializers.Serializer):
    email = serializers.EmailField()
    email_verified = serializers.BooleanField()


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class AccountsDetailSerializer(serializers.Serializer):
    detail = serializers.CharField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField(max_length=100)
    token = serializers.CharField(max_length=100)
    new_password = serializers.CharField(max_length=128, trim_whitespace=False)


class PasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField(max_length=128, trim_whitespace=False)
    new_password = serializers.CharField(max_length=128, trim_whitespace=False)


class TwoFactorCodeSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=12)


class TwoFactorSetupSerializer(serializers.Serializer):
    secret = serializers.CharField()
    otpauth_uri = serializers.CharField()


# --- PATCH /me ----------------------------------------------------------------------------------------------

def _string_list(max_items, max_len):
    return serializers.ListField(child=serializers.CharField(max_length=max_len, allow_blank=False),
                                 max_length=max_items, required=False)


class ProfileUpdateSerializer(serializers.Serializer):
    """Поля профиля для PATCH /me. Принимаются как на верхнем уровне, так и во вложенном объекте `profile`."""

    handle = serializers.CharField(max_length=60, required=False)
    first_name = serializers.CharField(max_length=80, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=80, required=False, allow_blank=True)
    avatar_id = serializers.UUIDField(required=False, allow_null=True)
    region_id = serializers.IntegerField(required=False, allow_null=True)
    city = serializers.CharField(max_length=120, required=False, allow_blank=True)
    bio = serializers.CharField(max_length=3000, required=False, allow_blank=True)
    fun_facts = _string_list(10, 200)
    surfing_since = serializers.IntegerField(required=False, allow_null=True, min_value=1950)
    riding_level = serializers.ChoiceField(choices=UserProfile.Level.choices, required=False, allow_blank=True)
    preferred_board_types = _string_list(12, 40)
    favorite_spot_ids = serializers.ListField(child=serializers.UUIDField(), required=False, max_length=50)
    interests = _string_list(20, 60)
    languages = _string_list(10, 8)
    phone = serializers.RegexField(r"^[0-9+()\-\s]{0,32}$", max_length=32, required=False, allow_blank=True,
                                   error_messages={"invalid": "Телефон: цифры, пробелы, +, -, скобки."})
    birth_date = serializers.DateField(required=False, allow_null=True)
    private_contacts = serializers.CharField(max_length=2000, required=False, allow_blank=True)
    gg_surfer_enabled = serializers.BooleanField(required=False)
    gg_contact_policy = serializers.ChoiceField(choices=UserProfile.ContactPolicy.choices, required=False)
    gg_show_region = serializers.BooleanField(required=False)
    gg_show_age = serializers.BooleanField(required=False)
    birthday_greetings_consent = serializers.BooleanField(required=False)
    show_birthday = serializers.BooleanField(required=False)

    def to_internal_value(self, data):
        if hasattr(data, "get") and isinstance(data.get("profile"), dict):
            merged = {k: v for k, v in data.items() if k != "profile"}
            merged.update(data["profile"])
            data = merged
        return super().to_internal_value(data)

    def validate_surfing_since(self, value):
        if value is not None and value > timezone.localdate().year:
            raise serializers.ValidationError("Год не может быть в будущем.")
        return value

    def validate_birth_date(self, value):
        if value is None:
            return value
        today = timezone.localdate()
        if value > today:
            raise serializers.ValidationError("Дата рождения не может быть в будущем.")
        if value < dt.date(today.year - 120, 1, 1):
            raise serializers.ValidationError("Проверьте дату рождения.")
        return value

    def validate_languages(self, value):
        return [v.strip().lower() for v in value]


# --- направления --------------------------------------------------------------------------------------------

class SpecialtyWarningSerializer(serializers.Serializer):
    code = serializers.CharField()
    message = serializers.CharField()
    count = serializers.IntegerField(allow_null=True)


class UnpublishedItemSerializer(serializers.Serializer):
    type = serializers.CharField()
    id = serializers.UUIDField()


class SpecialtyActivateResponseSerializer(serializers.Serializer):
    specialty = UserSpecialtySerializer()
    next_step = serializers.CharField(allow_null=True, help_text="instructor_profile | create_workshop | null")


class SpecialtyDeactivateResponseSerializer(serializers.Serializer):
    specialty = UserSpecialtySerializer()
    warnings = SpecialtyWarningSerializer(many=True)
    unpublished = UnpublishedItemSerializer(many=True)


# --- согласия, выгрузка, удаление ---------------------------------------------------------------------------

class ConsentRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConsentRecord
        fields = ["id", "kind", "granted", "created_at"]


class ConsentCreateSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=ConsentRecord.Kind.choices)
    granted = serializers.BooleanField()


class ConsentsResponseSerializer(serializers.Serializer):
    current = serializers.DictField(child=serializers.BooleanField(),
                                    help_text="Последнее решение по каждому виду согласия")
    history = ConsentRecordSerializer(many=True)


class DataExportSerializer(serializers.ModelSerializer):
    file = MediaSerializer(allow_null=True)

    class Meta:
        model = DataExportRequest
        fields = ["id", "status", "file", "created_at", "completed_at"]


class DeletionRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccountDeletionRequest
        fields = ["id", "status", "reason", "scheduled_for", "created_at", "completed_at"]


class DeletionCreateSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=2000, required=False, allow_blank=True, default="")


class DeletionStateSerializer(serializers.Serializer):
    pending = serializers.BooleanField()
    request = DeletionRequestSerializer(allow_null=True)
    grace_days = serializers.IntegerField()


# --- публичный профиль --------------------------------------------------------------------------------------

class ProfileInstructorLinkSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    handle = serializers.CharField()


class ProfileOrganizationLinkSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    slug = serializers.CharField()
    name = serializers.CharField()
    kind = serializers.CharField()
    role = serializers.CharField()


class ProfileGGSerializer(serializers.Serializer):
    bio = serializers.CharField()
    fun_facts = serializers.ListField(child=serializers.CharField())
    surfing_since = serializers.IntegerField(allow_null=True)
    riding_level = serializers.CharField()
    preferred_board_types = serializers.ListField(child=serializers.CharField())
    favorite_spots = AccountSpotSerializer(many=True)
    interests = serializers.ListField(child=serializers.CharField())
    languages = serializers.ListField(child=serializers.CharField())
    region = AccountRegionSerializer(allow_null=True, help_text="null, если пользователь скрыл регион")
    city = serializers.CharField()
    age = serializers.IntegerField(allow_null=True, help_text="Возраст (не дата рождения), если разрешён показ")
    contact_policy = serializers.CharField()


class UserPublicProfileSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    handle = serializers.CharField()
    display_name = serializers.CharField()
    avatar = MediaSerializer(allow_null=True)
    member_since = serializers.DateTimeField()
    specialties = serializers.ListField(child=serializers.CharField())
    instructor_profile = ProfileInstructorLinkSerializer(allow_null=True)
    organizations = ProfileOrganizationLinkSerializer(many=True)
    gg_surfer = serializers.BooleanField()
    gg = ProfileGGSerializer(allow_null=True, help_text="Поля сообщества — только при согласии GG Surfer")


class ProfileRedirectSerializer(serializers.Serializer):
    redirect = serializers.CharField(help_text="Актуальный handle")


# --- служебные роли -----------------------------------------------------------------------------------------

class StaffRoleSerializer(serializers.ModelSerializer):
    account = PublicAccountSerializer()
    account_email = serializers.EmailField(source="account.email")
    granted_by = PublicAccountSerializer(allow_null=True)
    two_factor_enabled = serializers.BooleanField(source="account.totp_enabled")

    class Meta:
        model = StaffRole
        fields = ["id", "account", "account_email", "role", "granted_by", "granted_at", "revoked_at",
                  "two_factor_enabled"]


class StaffRoleGrantSerializer(serializers.Serializer):
    account_email = serializers.EmailField()
    role = serializers.ChoiceField(choices=StaffRole.Role.choices)


class StaffRoleRevokeSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=False)
    account_email = serializers.EmailField(required=False)
    role = serializers.ChoiceField(choices=StaffRole.Role.choices, required=False)

    def validate(self, attrs):
        if not attrs.get("id") and not (attrs.get("account_email") and attrs.get("role")):
            raise serializers.ValidationError("Укажите id роли или пару account_email + role.")
        return attrs
