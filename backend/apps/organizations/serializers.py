"""Сериализаторы организаций. Публичная карточка не содержит телефон/email организации и персональные данные людей."""
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.accounts.serializers import AccountRegionSerializer, ProfileInstructorLinkSerializer
from apps.accounts.serializers_public import PublicAccountSerializer
from apps.mediafiles.serializers import MediaSerializer
from apps.organizations.models import Membership, Organization, OrganizationInvite


class OrganizationSpotSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    slug = serializers.CharField()
    name = serializers.CharField()
    region = AccountRegionSerializer(allow_null=True)

    def to_representation(self, spot):
        region = spot.region
        return {"id": str(spot.pk), "slug": spot.slug, "name": spot.name,
                "region": {"id": region.pk, "slug": region.slug, "name": region.name} if region else None}


class OrganizationCardSerializer(serializers.ModelSerializer):
    """Элемент каталога GET /organizations."""

    region = AccountRegionSerializer(allow_null=True)
    logo = MediaSerializer(allow_null=True)
    cover = MediaSerializer(allow_null=True)

    class Meta:
        model = Organization
        fields = ["id", "slug", "kind", "name", "short_description", "region", "city", "logo", "cover",
                  "rating_avg", "rating_count", "price_from", "currency", "formats", "languages",
                  "verification_status", "published_at", "is_demo"]


class OrganizationTeamMemberSerializer(serializers.Serializer):
    account = PublicAccountSerializer()
    role = serializers.ChoiceField(choices=Membership.Role.choices)
    title = serializers.CharField()
    instructor_profile = ProfileInstructorLinkSerializer(allow_null=True, help_text="Опубликованная карточка инструктора")


class OrganizationProgramSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    title = serializers.CharField()
    description = serializers.CharField()
    level = serializers.CharField()
    age_category = serializers.CharField()
    format = serializers.CharField()
    duration_min = serializers.IntegerField()
    sessions_count = serializers.IntegerField()
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    currency = serializers.CharField()
    max_group_size = serializers.IntegerField()
    equipment_included = serializers.BooleanField()


class OrganizationSessionSpotSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    slug = serializers.CharField()
    name = serializers.CharField()

    def get_attribute(self, instance):
        """Скрытый модератором или черновой спот в расписании школы не показывается."""
        from apps.spots.services.catalog import is_public_spot

        spot = super().get_attribute(instance)
        return spot if is_public_spot(spot) else None


class OrganizationSessionSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    title = serializers.CharField()
    program_id = serializers.UUIDField(allow_null=True)
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    capacity = serializers.IntegerField()
    free_seats = serializers.IntegerField()
    price = serializers.DecimalField(max_digits=10, decimal_places=2, allow_null=True)
    currency = serializers.CharField()
    status = serializers.CharField()
    spot = OrganizationSessionSpotSerializer(allow_null=True)
    instructor = PublicAccountSerializer(allow_null=True)


class OrganizationPublicSerializer(OrganizationCardSerializer):
    """GET /organizations/{slug}: карточка + галерея, споты, команда; для школы — программы и ближайшие занятия."""

    gallery = serializers.SerializerMethodField()
    spots = serializers.SerializerMethodField()
    team = serializers.SerializerMethodField()
    programs = serializers.SerializerMethodField()
    upcoming_sessions = serializers.SerializerMethodField()
    viewer_role = serializers.SerializerMethodField()

    class Meta(OrganizationCardSerializer.Meta):
        fields = OrganizationCardSerializer.Meta.fields + [
            "description", "address", "website", "social_links", "gallery", "spots", "team", "programs",
            "upcoming_sessions", "viewer_role",
        ]

    @extend_schema_field(MediaSerializer(many=True))
    def get_gallery(self, org):
        return MediaSerializer(org.gallery.filter(status="ready"), many=True).data

    @extend_schema_field(OrganizationSpotSerializer(many=True))
    def get_spots(self, org):
        from apps.spots.models import Spot

        spots = org.spots.filter(status=Spot.Status.PUBLISHED).select_related("region")
        return [OrganizationSpotSerializer().to_representation(spot) for spot in spots]

    @extend_schema_field(OrganizationTeamMemberSerializer(many=True))
    def get_team(self, org):
        from apps.organizations.services.organizations import team

        return OrganizationTeamMemberSerializer(team(org), many=True).data

    @extend_schema_field(OrganizationProgramSerializer(many=True))
    def get_programs(self, org):
        if org.kind != Organization.Kind.SCHOOL:
            return []
        from apps.organizations.services.organizations import active_programs

        return OrganizationProgramSerializer(active_programs(org), many=True).data

    @extend_schema_field(OrganizationSessionSerializer(many=True))
    def get_upcoming_sessions(self, org):
        if org.kind != Organization.Kind.SCHOOL:
            return []
        from apps.organizations.services.organizations import upcoming_sessions

        return OrganizationSessionSerializer(upcoming_sessions(org), many=True).data

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_viewer_role(self, org):
        from apps.organizations.services.access import member_role

        request = self.context.get("request")
        return member_role(request.user, org) if request else None


class OrganizationManageSerializer(serializers.ModelSerializer):
    """GET/PATCH /organizations/{id}/manage — закрытая карточка для owner/manager."""

    region = AccountRegionSerializer(allow_null=True)
    logo = MediaSerializer(allow_null=True)
    cover = MediaSerializer(allow_null=True)
    gallery = MediaSerializer(many=True)
    spots = serializers.SerializerMethodField()
    owner = PublicAccountSerializer()
    my_role = serializers.SerializerMethodField()
    members_count = serializers.SerializerMethodField()
    pending_invites_count = serializers.SerializerMethodField()
    missing_fields = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = ["id", "slug", "kind", "name", "status", "verification_status", "moderation_note",
                  "short_description", "description", "region", "city", "address", "spots", "logo", "cover",
                  "gallery", "phone", "email", "website", "social_links", "formats", "languages", "price_from",
                  "currency", "rating_avg", "rating_count", "published_at", "owner", "my_role", "members_count",
                  "pending_invites_count", "missing_fields", "created_at", "updated_at"]

    @extend_schema_field(OrganizationSpotSerializer(many=True))
    def get_spots(self, org):
        return [OrganizationSpotSerializer().to_representation(spot) for spot in org.spots.select_related("region")]

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_my_role(self, org):
        from apps.organizations.services.access import member_role

        request = self.context.get("request")
        return member_role(request.user, org) if request else None

    def get_members_count(self, org) -> int:
        return org.memberships.filter(status=Membership.Status.ACTIVE).count()

    def get_pending_invites_count(self, org) -> int:
        return org.invites.filter(status=OrganizationInvite.Status.PENDING).count()

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_missing_fields(self, org):
        from apps.organizations.services.organizations import missing_fields

        return missing_fields(org)


class OrganizationWriteSerializer(serializers.Serializer):
    """Тело POST /organizations (kind, name обязательны) и PATCH /organizations/{id}/manage."""

    kind = serializers.ChoiceField(choices=Organization.Kind.choices)
    name = serializers.CharField(max_length=160)
    short_description = serializers.CharField(max_length=300, required=False, allow_blank=True)
    description = serializers.CharField(max_length=10000, required=False, allow_blank=True)
    region_id = serializers.IntegerField(required=False, allow_null=True)
    city = serializers.CharField(max_length=120, required=False, allow_blank=True)
    address = serializers.CharField(max_length=300, required=False, allow_blank=True)
    spot_ids = serializers.ListField(child=serializers.UUIDField(), required=False, max_length=50)
    logo_id = serializers.UUIDField(required=False, allow_null=True)
    cover_id = serializers.UUIDField(required=False, allow_null=True)
    gallery_ids = serializers.ListField(child=serializers.UUIDField(), required=False, max_length=30)
    phone = serializers.RegexField(r"^[0-9+()\-\s]{0,32}$", max_length=32, required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    website = serializers.URLField(required=False, allow_blank=True, max_length=200)
    social_links = serializers.DictField(child=serializers.URLField(max_length=300), required=False)
    formats = serializers.ListField(child=serializers.CharField(max_length=32), required=False, max_length=10)
    languages = serializers.ListField(child=serializers.CharField(max_length=8), required=False, max_length=10)
    price_from = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True,
                                          min_value=0)
    currency = serializers.RegexField(r"^[A-Z]{3}$", required=False)

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Укажите название.")
        return value

    def validate_social_links(self, value):
        if len(value) > 10:
            raise serializers.ValidationError("Не больше 10 ссылок.")
        return value


class OrganizationPatchSerializer(OrganizationWriteSerializer):
    kind = None  # тип организации после создания не меняется


class MyOrganizationMembershipSerializer(serializers.ModelSerializer):
    """GET /me/organizations."""

    organization = OrganizationCardSerializer()
    membership_id = serializers.UUIDField(source="id")

    class Meta:
        model = Membership
        fields = ["membership_id", "role", "status", "title", "joined_at", "organization"]


class OrganizationMembershipSerializer(serializers.ModelSerializer):
    account = PublicAccountSerializer()
    invited_by = PublicAccountSerializer(allow_null=True)
    revoked_by = PublicAccountSerializer(allow_null=True)

    class Meta:
        model = Membership
        fields = ["id", "account", "role", "status", "title", "joined_at", "invited_by", "revoked_at", "revoked_by"]


class OrganizationMembershipUpdateSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=Membership.Role.choices, required=False)
    title = serializers.CharField(max_length=120, required=False, allow_blank=True)


class OrganizationInviteCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=Membership.Role.choices)
    message = serializers.CharField(max_length=2000, required=False, allow_blank=True, default="")


class OrganizationInviteSerializer(serializers.ModelSerializer):
    """Приглашение со стороны организации (токен не раскрывается)."""

    invited_by = PublicAccountSerializer()
    has_account = serializers.SerializerMethodField()

    class Meta:
        model = OrganizationInvite
        fields = ["id", "email", "role", "status", "message", "invited_by", "has_account", "expires_at",
                  "responded_at", "created_at"]

    def get_has_account(self, invite) -> bool:
        return invite.account_id is not None


class InviteOrganizationBriefSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    slug = serializers.CharField()
    name = serializers.CharField()
    kind = serializers.CharField()
    status = serializers.CharField()
    logo = MediaSerializer(allow_null=True)


class MyOrganizationInviteSerializer(serializers.ModelSerializer):
    """Приглашение со стороны адресата: с токеном для accept/decline."""

    organization = InviteOrganizationBriefSerializer()
    invited_by = PublicAccountSerializer()

    class Meta:
        model = OrganizationInvite
        fields = ["id", "token", "organization", "role", "status", "message", "invited_by", "expires_at",
                  "created_at"]


class OrganizationTransferOwnershipSerializer(serializers.Serializer):
    account_id = serializers.UUIDField()
