"""Сериализаторы trust: отзывы (публичные и свои), жалобы, очередь модерации, журнал, ограничения."""
from django.utils import timezone
from drf_spectacular.utils import PolymorphicProxySerializer, extend_schema_field
from rest_framework import serializers

from apps.accounts.serializers_public import PublicAccountSerializer
from apps.mediafiles.serializers import MediaSerializer
from apps.spots.models import SpotChangeRequest
from apps.spots.serializer_fields import LabeledChoiceField
from apps.spots.serializers import ProposalChangeWithCurrentSerializer, changes_list
from apps.trust.models import AccountRestriction, AuditEvent, Complaint, ModerationCase, Review
from apps.trust.services.complaints import APPEALABLE_ACTIONS
from apps.trust.services.media_access import moderator_url
from apps.trust.services.restrictions import is_restriction_active
from apps.trust.services.reviews import target_name, target_public_link


def _ready_public(media_items):
    return [m for m in media_items if m.status == m.Status.READY and m.is_public]


# --- входные данные --------------------------------------------------------------------------------

class ReviewSubmitSerializer(serializers.Serializer):
    target_type = serializers.ChoiceField(choices=Review.Target.choices)
    target_id = serializers.UUIDField()
    rating = serializers.IntegerField(min_value=1, max_value=5)
    text = serializers.CharField(max_length=3000, trim_whitespace=True)
    photo_ids = serializers.ListField(child=serializers.UUIDField(), required=False, allow_null=True, default=None,
                                      max_length=6, help_text="Не передано — фото без изменений; [] — убрать все")


class ComplaintCreateSerializer(serializers.Serializer):
    target_type = serializers.ChoiceField(choices=Complaint.Target.choices)
    target_id = serializers.UUIDField()
    reason = serializers.ChoiceField(choices=Complaint.Reason.choices)
    text = serializers.CharField(max_length=2000, required=False, allow_blank=True, default="")


class AppealSerializer(serializers.Serializer):
    text = serializers.CharField(max_length=2000)


class ProposalApproveSerializer(serializers.Serializer):
    comment = serializers.CharField(max_length=2000, required=False, allow_blank=True, default="")
    add_evidence_to_gallery = serializers.BooleanField(required=False, default=False)


class CommentRequiredSerializer(serializers.Serializer):
    comment = serializers.CharField(max_length=2000)


class ProposalRevertSerializer(serializers.Serializer):
    comment = serializers.CharField(max_length=2000, required=False, allow_blank=True, default="")
    force = serializers.BooleanField(required=False, default=False,
                                     help_text="Откатить, даже если поля менялись после одобрения")


class NoteOptionalSerializer(serializers.Serializer):
    note = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")


class NoteRequiredSerializer(serializers.Serializer):
    note = serializers.CharField(max_length=300)


class ComplaintResolveSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=Complaint.Action.choices)
    note = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")
    expires_at = serializers.DateTimeField(required=False, allow_null=True, default=None,
                                           help_text="Только для action=suspended; пусто — бессрочно")


class AppealDecisionSerializer(serializers.Serializer):
    grant = serializers.BooleanField(help_text="true — апелляция удовлетворена, мера снимается")
    note = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")


class RestrictSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=AccountRestriction.Kind.choices)
    reason = serializers.CharField(max_length=300)
    expires_at = serializers.DateTimeField(required=False, allow_null=True, default=None)


# --- отзывы ---------------------------------------------------------------------------------------

class ReviewTargetSerializer(serializers.Serializer):
    type = serializers.CharField()
    id = serializers.UUIDField()
    name = serializers.CharField()
    link = serializers.CharField()


def review_target(review):
    target_id = {"spot": review.spot_id, "instructor": review.instructor_id, "organization": review.organization_id}[
        review.target_type]
    return {"type": review.target_type, "id": target_id, "name": target_name(review), "link": target_public_link(review)}


class PublicReviewSerializer(serializers.ModelSerializer):
    """Опубликованный отзыв: автор с аватаром, контекст услуги, дата (SPT-03, TRUST-01/02)."""

    author = PublicAccountSerializer(read_only=True)
    photos = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = ["id", "target_type", "rating", "text", "author", "context_label", "photos", "published_at",
                  "created_at", "updated_at"]

    @extend_schema_field(MediaSerializer(many=True))
    def get_photos(self, obj):
        return MediaSerializer(_ready_public(obj.photos.all()), many=True).data


class MyReviewSerializer(serializers.ModelSerializer):
    status = LabeledChoiceField(Review.Status.choices)
    target = serializers.SerializerMethodField()
    photos = MediaSerializer(many=True, read_only=True)
    pending_photos = MediaSerializer(many=True, read_only=True)

    class Meta:
        model = Review
        fields = ["id", "target_type", "target", "rating", "text", "status", "context_label", "photos",
                  "has_pending_revision", "pending_rating", "pending_text", "pending_photos", "moderation_note",
                  "moderated_at", "published_at", "created_at", "updated_at"]

    @extend_schema_field(ReviewTargetSerializer)
    def get_target(self, obj):
        return review_target(obj)


# --- жалобы ---------------------------------------------------------------------------------------

class _ComplaintBase(serializers.ModelSerializer):
    target_type = LabeledChoiceField(Complaint.Target.choices)
    reason = LabeledChoiceField(Complaint.Reason.choices)
    status = LabeledChoiceField(Complaint.Status.choices)
    action_taken = LabeledChoiceField(Complaint.Action.choices)


class MyComplaintSerializer(_ComplaintBase):
    """Жалоба глазами автора жалобы: статус и принятая мера (заметки модератора не раскрываются)."""

    class Meta:
        model = Complaint
        fields = ["id", "target_type", "target_id", "reason", "text", "status", "action_taken", "created_at",
                  "updated_at"]


class ComplaintAgainstMeSerializer(_ComplaintBase):
    """Жалоба на мой материал после решения — без текста и личности автора жалобы; можно обжаловать."""

    can_appeal = serializers.SerializerMethodField()

    class Meta:
        model = Complaint
        fields = ["id", "target_type", "target_id", "reason", "status", "action_taken", "appeal_text", "appealed_at",
                  "can_appeal", "updated_at"]

    @extend_schema_field(serializers.BooleanField())
    def get_can_appeal(self, obj):
        return obj.status == Complaint.Status.RESOLVED and obj.action_taken in APPEALABLE_ACTIONS and obj.appealed_at is None


# --- модерация: медиа, журнал, ограничения ---------------------------------------------------------

class ModeratorMediaSerializer(MediaSerializer):
    """Медиа для модератора: + signed_url — короткоживущая ссылка и на закрытые файлы."""

    signed_url = serializers.SerializerMethodField()

    class Meta(MediaSerializer.Meta):
        fields = MediaSerializer.Meta.fields + ["signed_url"]
        read_only_fields = fields

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_signed_url(self, obj):
        return moderator_url(self.context.get("request"), obj)


class AuditEventSerializer(serializers.ModelSerializer):
    actor = PublicAccountSerializer(read_only=True, allow_null=True)

    class Meta:
        model = AuditEvent
        fields = ["id", "actor", "action", "object_type", "object_id", "organization", "before", "after", "metadata",
                  "ip", "request_id", "created_at"]


class RestrictionSerializer(serializers.ModelSerializer):
    account = PublicAccountSerializer(read_only=True)
    kind = LabeledChoiceField(AccountRestriction.Kind.choices)
    created_by = PublicAccountSerializer(read_only=True, allow_null=True)
    is_active = serializers.SerializerMethodField()

    class Meta:
        model = AccountRestriction
        fields = ["id", "account", "kind", "reason", "created_by", "expires_at", "lifted_at", "is_active", "created_at"]

    @extend_schema_field(serializers.BooleanField())
    def get_is_active(self, obj):
        return is_restriction_active(obj)


class ModeratorComplaintShortSerializer(_ComplaintBase):
    reporter = PublicAccountSerializer(read_only=True)

    class Meta:
        model = Complaint
        fields = ["id", "target_type", "target_id", "reason", "text", "status", "action_taken", "reporter",
                  "appealed_at", "created_at"]


# --- модерация: очередь -----------------------------------------------------------------------------

def case_target_id(case):
    for field in ("spot_change_request_id", "review_id", "certificate_id", "complaint_id", "organization_id"):
        value = getattr(case, field)
        if value:
            return value
    return None


class CaseListSerializer(serializers.ModelSerializer):
    kind = LabeledChoiceField(ModerationCase.Kind.choices)
    status = LabeledChoiceField(ModerationCase.Status.choices)
    target_id = serializers.SerializerMethodField()
    is_overdue = serializers.SerializerMethodField()
    assigned_to = PublicAccountSerializer(read_only=True, allow_null=True)
    resolved_by = PublicAccountSerializer(read_only=True, allow_null=True)

    class Meta:
        model = ModerationCase
        fields = ["id", "kind", "status", "summary", "target_id", "due_at", "is_overdue", "assigned_to", "resolution",
                  "resolution_note", "resolved_by", "resolved_at", "created_at", "updated_at"]

    @extend_schema_field(serializers.UUIDField(allow_null=True))
    def get_target_id(self, obj):
        return case_target_id(obj)

    @extend_schema_field(serializers.BooleanField())
    def get_is_overdue(self, obj):
        return obj.status != ModerationCase.Status.RESOLVED and bool(obj.due_at and obj.due_at < timezone.now())


class ShortSpotSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    slug = serializers.CharField()
    name = serializers.CharField()
    region = serializers.CharField(source="region.name")


class SpotChangeCaseTargetSerializer(serializers.ModelSerializer):
    type = serializers.SerializerMethodField()
    status = LabeledChoiceField(SpotChangeRequest.Status.choices)
    spot = ShortSpotSerializer(read_only=True)
    author = PublicAccountSerializer(read_only=True)
    moderator = PublicAccountSerializer(read_only=True, allow_null=True)
    diff = serializers.SerializerMethodField()
    evidence = serializers.SerializerMethodField()

    class Meta:
        model = SpotChangeRequest
        fields = ["type", "id", "status", "spot", "author", "comment", "source", "diff", "evidence", "moderator",
                  "moderator_comment", "decided_at", "reverted_at", "created_at", "updated_at"]

    @extend_schema_field(serializers.CharField())
    def get_type(self, obj):
        return "spot_change"

    @extend_schema_field(ProposalChangeWithCurrentSerializer(many=True))
    def get_diff(self, obj):
        return changes_list(obj.changes, spot=obj.spot)

    @extend_schema_field(ModeratorMediaSerializer(many=True))
    def get_evidence(self, obj):
        return ModeratorMediaSerializer(obj.evidence.all(), many=True, context=self.context).data


class ReviewCaseTargetSerializer(serializers.ModelSerializer):
    type = serializers.SerializerMethodField()
    status = LabeledChoiceField(Review.Status.choices)
    target = serializers.SerializerMethodField()
    author = PublicAccountSerializer(read_only=True)
    photos = serializers.SerializerMethodField()
    pending_photos = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = ["type", "id", "status", "target_type", "target", "rating", "text", "has_pending_revision",
                  "pending_rating", "pending_text", "photos", "pending_photos", "author", "context_label", "booking",
                  "inquiry", "moderation_note", "published_at", "created_at", "updated_at"]

    @extend_schema_field(serializers.CharField())
    def get_type(self, obj):
        return "review"

    @extend_schema_field(ReviewTargetSerializer)
    def get_target(self, obj):
        return review_target(obj)

    @extend_schema_field(ModeratorMediaSerializer(many=True))
    def get_photos(self, obj):
        return ModeratorMediaSerializer(obj.photos.all(), many=True, context=self.context).data

    @extend_schema_field(ModeratorMediaSerializer(many=True))
    def get_pending_photos(self, obj):
        return ModeratorMediaSerializer(obj.pending_photos.all(), many=True, context=self.context).data


class CertificateCaseTargetSerializer(serializers.Serializer):
    type = serializers.SerializerMethodField()
    id = serializers.UUIDField()
    status = LabeledChoiceField([("uploaded", "Загружен, на проверке"), ("verified", "Проверен"),
                                 ("rejected", "Отклонён"), ("revoked", "Отозван")])
    title = serializers.CharField()
    issuer = serializers.CharField()
    issued_on = serializers.DateField(allow_null=True)
    valid_until = serializers.DateField(allow_null=True)
    allow_public_scan = serializers.BooleanField()
    instructor = serializers.SerializerMethodField()
    document = serializers.SerializerMethodField()
    moderator_comment = serializers.CharField()
    decided_at = serializers.DateTimeField(allow_null=True)
    created_at = serializers.DateTimeField()

    @extend_schema_field(serializers.CharField())
    def get_type(self, obj):
        return "certificate"

    @extend_schema_field(serializers.DictField())
    def get_instructor(self, obj):
        profile = obj.instructor
        return {"id": str(profile.pk), "headline": profile.headline, "status": profile.status,
                "account": PublicAccountSerializer(profile.account).data}

    @extend_schema_field(ModeratorMediaSerializer)
    def get_document(self, obj):
        return ModeratorMediaSerializer(obj.document, context=self.context).data


class ComplaintCaseTargetSerializer(_ComplaintBase):
    type = serializers.SerializerMethodField()
    reporter = PublicAccountSerializer(read_only=True)
    target_owner = PublicAccountSerializer(read_only=True, allow_null=True)
    target_snapshot = serializers.SerializerMethodField()
    owner_history = serializers.SerializerMethodField()

    class Meta:
        model = Complaint
        fields = ["type", "id", "status", "reason", "text", "reporter", "target_type", "target_id", "target_owner",
                  "target_snapshot", "owner_history", "action_taken", "appeal_text", "appealed_at", "created_at",
                  "updated_at"]

    @extend_schema_field(serializers.CharField())
    def get_type(self, obj):
        return "complaint"

    @extend_schema_field(serializers.DictField())
    def get_target_snapshot(self, obj):
        return complaint_target_snapshot(obj, self.context.get("request"))

    @extend_schema_field(serializers.DictField())
    def get_owner_history(self, obj):
        if obj.target_owner_id is None:
            return None
        complaints = Complaint.objects.filter(target_owner_id=obj.target_owner_id)
        restrictions = AccountRestriction.objects.filter(account_id=obj.target_owner_id)
        return {
            "complaints_total": complaints.count(),
            "complaints_upheld": complaints.filter(status=Complaint.Status.RESOLVED)
            .exclude(action_taken=Complaint.Action.NONE).count(),
            "active_restrictions": sum(1 for r in restrictions if is_restriction_active(r)),
        }


class OrganizationCaseTargetSerializer(serializers.Serializer):
    type = serializers.SerializerMethodField()
    id = serializers.UUIDField()
    kind = LabeledChoiceField([("school", "Сёрф-школа"), ("workshop", "Мастерская шейпера"), ("rental", "Прокат")])
    name = serializers.CharField()
    slug = serializers.CharField()
    status = serializers.CharField()
    verification_status = serializers.CharField()
    short_description = serializers.CharField()
    description = serializers.CharField()
    region = serializers.CharField(source="region.name", allow_null=True, default=None)
    city = serializers.CharField()
    address = serializers.CharField()
    phone = serializers.CharField()
    email = serializers.CharField()
    website = serializers.CharField()
    social_links = serializers.JSONField()
    formats = serializers.ListField(child=serializers.CharField())
    languages = serializers.ListField(child=serializers.CharField())
    price_from = serializers.DecimalField(max_digits=10, decimal_places=2, allow_null=True)
    currency = serializers.CharField()
    logo = MediaSerializer(allow_null=True)
    cover = MediaSerializer(allow_null=True)
    gallery = serializers.SerializerMethodField()
    owner = PublicAccountSerializer()
    spots = serializers.SerializerMethodField()
    moderation_note = serializers.CharField()
    created_at = serializers.DateTimeField()

    @extend_schema_field(serializers.CharField())
    def get_type(self, obj):
        return "organization"

    @extend_schema_field(MediaSerializer(many=True))
    def get_gallery(self, obj):
        return MediaSerializer(obj.gallery.all(), many=True).data

    @extend_schema_field(ShortSpotSerializer(many=True))
    def get_spots(self, obj):
        return ShortSpotSerializer(obj.spots.select_related("region"), many=True).data


CASE_TARGET_SCHEMA = PolymorphicProxySerializer(
    component_name="ModerationCaseTarget",
    serializers=[SpotChangeCaseTargetSerializer, ReviewCaseTargetSerializer, CertificateCaseTargetSerializer,
                 ComplaintCaseTargetSerializer, OrganizationCaseTargetSerializer],
    resource_type_field_name=None,
)


def complaint_target_snapshot(complaint, request):
    """Снимок цели жалобы для модератора (в любом статусе)."""
    from apps.trust.services.complaints import T, target_object

    obj = target_object(complaint)
    if obj is None:
        return {"exists": False}
    tt = complaint.target_type
    data = {"exists": True}
    if tt == T.SPOT:
        data.update(name=obj.name, slug=obj.slug, status=obj.status, region=obj.region.name, link=f"/spots/{obj.slug}")
    elif tt == T.ACCOUNT:
        profile = getattr(obj, "profile", None)
        data.update(account=PublicAccountSerializer(obj).data, bio=profile.bio if profile else "",
                    is_active=obj.is_active)
    elif tt == T.REVIEW:
        data.update(rating=obj.rating, text=obj.text, status=obj.status, author=PublicAccountSerializer(obj.author).data,
                    target=review_target(obj))
    elif tt == T.MESSAGE:
        attachments = [a.media for a in obj.attachments.select_related("media")]
        data.update(body=obj.body, is_hidden=obj.is_hidden, conversation_id=str(obj.conversation_id),
                    created_at=obj.created_at.isoformat(),
                    sender=PublicAccountSerializer(obj.sender).data if obj.sender else None,
                    attachments=ModeratorMediaSerializer(attachments, many=True, context={"request": request}).data)
    elif tt == T.BOARD_MODEL:
        data.update(name=obj.name, status=obj.status, description=obj.description, link=f"/boards/{obj.pk}",
                    workshop={"id": str(obj.workshop_id), "name": obj.workshop.name, "slug": obj.workshop.slug})
    elif tt == T.INVENTORY_ITEM:
        owner = obj.owner_account if obj.owner_account_id else None
        data.update(title=obj.title, description=obj.description, is_published=obj.is_published, status=obj.status,
                    link=f"/rentals/{obj.pk}", owner=PublicAccountSerializer(owner).data if owner else None,
                    organization={"id": str(obj.owner_organization_id), "name": obj.owner_organization.name}
                    if obj.owner_organization_id else None)
    elif tt == T.ORGANIZATION:
        data.update(name=obj.name, slug=obj.slug, kind=obj.kind, status=obj.status)
    elif tt == T.MEDIA:
        data.update(media=ModeratorMediaSerializer(obj, context={"request": request}).data)
    elif tt == T.CLUB_EVENT:
        data.update(title=obj.title, slug=obj.slug, status=obj.status, starts_at=obj.starts_at.isoformat(),
                    link=f"/club/events/{obj.slug}")
    return data


class CaseDetailSerializer(CaseListSerializer):
    target = serializers.SerializerMethodField()
    history = serializers.SerializerMethodField()
    available_actions = serializers.SerializerMethodField()

    class Meta(CaseListSerializer.Meta):
        fields = CaseListSerializer.Meta.fields + ["target", "history", "available_actions"]

    @extend_schema_field(CASE_TARGET_SCHEMA)
    def get_target(self, obj):
        ctx = self.context
        if obj.spot_change_request_id:
            return SpotChangeCaseTargetSerializer(obj.spot_change_request, context=ctx).data
        if obj.review_id:
            return ReviewCaseTargetSerializer(obj.review, context=ctx).data
        if obj.certificate_id:
            return CertificateCaseTargetSerializer(obj.certificate, context=ctx).data
        if obj.complaint_id:
            return ComplaintCaseTargetSerializer(obj.complaint, context=ctx).data
        if obj.organization_id:
            return OrganizationCaseTargetSerializer(obj.organization, context=ctx).data
        return None

    @extend_schema_field(AuditEventSerializer(many=True))
    def get_history(self, obj):
        from apps.trust.services.case_queries import case_history

        return AuditEventSerializer(case_history(obj), many=True).data

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_available_actions(self, obj):
        from apps.trust.services.case_queries import available_actions

        return available_actions(obj)
