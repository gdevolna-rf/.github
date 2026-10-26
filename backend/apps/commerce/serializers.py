"""Форматы обращений и броней. Люди — PublicAccountSerializer, медиа — MediaSerializer (+ signed_url для закрытых)."""
from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.accounts.serializers_public import PublicAccountSerializer
from apps.commerce.models import Booking, BookingStatusChange, Inquiry, InquiryMilestone, InquiryStatusChange
from apps.commerce.services import access
from apps.commerce.services import bookings as booking_service
from apps.commerce.services import inquiries as inquiry_service
from apps.commerce.services.snapshots import TARGET_TYPES, context_card, organization_url
from apps.mediafiles.serializers import MediaSerializer

# --- общие карточки ----------------------------------------------------------------------------------------------------


class CommercePartyCardSerializer(serializers.Serializer):
    """Собеседник / исполнитель: аккаунт или организация."""

    type = serializers.ChoiceField(choices=["account", "organization"])
    id = serializers.UUIDField()
    name = serializers.CharField()
    avatar = MediaSerializer(allow_null=True, help_text="Только для type=account")
    logo = MediaSerializer(allow_null=True, help_text="Только для type=organization")
    handle = serializers.CharField(allow_null=True)
    slug = serializers.CharField(allow_null=True)
    kind = serializers.CharField(allow_null=True, help_text="Вид организации: school / workshop / rental")
    url = serializers.CharField(allow_null=True)


class CommerceOrganizationBriefSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    kind = serializers.CharField()
    slug = serializers.CharField()


class InquiryContextCardSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=list(TARGET_TYPES))
    id = serializers.CharField()
    title = serializers.CharField()
    subtitle = serializers.CharField(allow_blank=True)
    image = serializers.CharField(allow_null=True)
    url = serializers.CharField(allow_null=True)


class ChatLastMessageSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    kind = serializers.CharField()
    body = serializers.CharField(allow_blank=True)
    created_at = serializers.DateTimeField()
    sender_name = serializers.CharField(allow_null=True)
    is_mine = serializers.BooleanField()


def account_card(account):
    if account is None:
        return None
    public = PublicAccountSerializer(account).data
    url = None
    instructor = getattr(account, "instructor_profile", None) if _has_instructor(account) else None
    if instructor is not None and instructor.status == "published" and public["handle"]:
        url = f"/instructors/{public['handle']}"
    return {"type": "account", "id": str(account.pk), "name": public["display_name"], "avatar": public["avatar"],
            "logo": None, "handle": public["handle"], "slug": None, "kind": None, "url": url}


def _has_instructor(account):
    try:
        return account.instructor_profile is not None
    except Exception:  # RelatedObjectDoesNotExist
        return False


def organization_card(org):
    if org is None:
        return None
    return {"type": "organization", "id": str(org.pk), "name": org.name, "avatar": None,
            "logo": MediaSerializer(org.logo).data if org.logo_id else None, "handle": None, "slug": org.slug,
            "kind": org.kind, "url": organization_url(org)}


def organization_brief(org):
    if org is None:
        return None
    return {"id": str(org.pk), "name": org.name, "kind": org.kind, "slug": org.slug}


def _user(serializer):
    request = serializer.context.get("request")
    return getattr(request, "user", None)


# --- обращения ---------------------------------------------------------------------------------------------------------


class InquiryCreateSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=Inquiry.Kind.choices)
    target_type = serializers.ChoiceField(choices=list(TARGET_TYPES), required=False)
    target_id = serializers.UUIDField(required=False)
    provider_account_id = serializers.UUIDField(required=False)
    provider_organization_id = serializers.UUIDField(required=False)
    message = serializers.CharField(max_length=4000, help_text="Первое сообщение в чате")
    details = serializers.JSONField(required=False, default=dict,
                                    help_text="repair: {problem*, desired_date, photo_ids[], board}; "
                                              "custom_order: {params{}, desired_date, budget, comment}; "
                                              "остальные виды — плоский объект простых значений")
    subject = serializers.CharField(max_length=200, required=False, allow_blank=True)
    source_channel = serializers.SlugField(max_length=32, required=False, allow_blank=True)

    def validate(self, attrs):
        has_target = bool(attrs.get("target_type")) or bool(attrs.get("target_id"))
        options = [has_target, bool(attrs.get("provider_account_id")), bool(attrs.get("provider_organization_id"))]
        if sum(options) != 1:
            raise serializers.ValidationError(
                "Укажите объект (target_type + target_id) или исполнителя (provider_account_id / provider_organization_id).")
        if has_target and not (attrs.get("target_type") and attrs.get("target_id")):
            raise serializers.ValidationError({"target_id": ["Укажите target_type и target_id вместе."]})
        return attrs


class CommerceReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")


class CommerceRequiredReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=300)


class InquiryCompleteSerializer(serializers.Serializer):
    agreed_amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0, required=False,
                                             allow_null=True)
    amount_confirmed = serializers.BooleanField(required=False, default=False,
                                                help_text="Исполнитель подтверждает фактическую сумму (MET-07)")


class CommerceEmptySerializer(serializers.Serializer):
    pass


class InquiryStatusChangeSerializer(serializers.ModelSerializer):
    from_status_label = serializers.SerializerMethodField()
    to_status_label = serializers.SerializerMethodField()
    actor = PublicAccountSerializer(allow_null=True)

    class Meta:
        model = InquiryStatusChange
        fields = ["from_status", "from_status_label", "to_status", "to_status_label", "actor", "comment", "created_at"]

    def get_from_status_label(self, obj) -> str:
        return Inquiry.Status(obj.from_status).label if obj.from_status else ""

    def get_to_status_label(self, obj) -> str:
        return Inquiry.Status(obj.to_status).label


class InquiryMilestoneSerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = InquiryMilestone
        fields = ["id", "inquiry", "title", "amount", "due_date", "status", "status_label", "position",
                  "completed_at", "confirmed_at", "created_at", "updated_at"]
        read_only_fields = ["id", "inquiry", "status", "status_label", "completed_at", "confirmed_at", "created_at",
                            "updated_at"]
        extra_kwargs = {"amount": {"min_value": 0}, "position": {"required": False}}


class InquiryListSerializer(serializers.ModelSerializer):
    kind_label = serializers.CharField(source="get_kind_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    my_role = serializers.SerializerMethodField()
    counterpart = serializers.SerializerMethodField()
    provider_organization = serializers.SerializerMethodField()
    context = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    conversation_id = serializers.SerializerMethodField()
    actions = serializers.SerializerMethodField()

    class Meta:
        model = Inquiry
        fields = ["id", "kind", "kind_label", "status", "status_label", "subject", "created_at", "updated_at",
                  "my_role", "counterpart", "provider_organization", "context", "last_message", "unread_count",
                  "conversation_id", "agreed_amount", "currency", "amount_confirmed", "actions"]

    def _side(self, obj):
        # Queryset/сервис уже отфильтровали видимость: не клиент — значит сторона исполнителя.
        user = _user(self)
        return access.CUSTOMER if user is not None and obj.customer_id == user.pk else access.PROVIDER

    @extend_schema_field(serializers.ChoiceField(choices=["customer", "provider"]))
    def get_my_role(self, obj):
        return self._side(obj)

    @extend_schema_field(CommercePartyCardSerializer)
    def get_counterpart(self, obj):
        if self._side(obj) == access.PROVIDER:
            return account_card(obj.customer)
        if obj.provider_account_id:
            return account_card(obj.provider_account)
        return organization_card(obj.provider_organization)

    @extend_schema_field(CommerceOrganizationBriefSerializer(allow_null=True))
    def get_provider_organization(self, obj):
        return organization_brief(obj.provider_organization)

    @extend_schema_field(InquiryContextCardSerializer(allow_null=True))
    def get_context(self, obj):
        return context_card(obj.object_snapshot)

    @extend_schema_field(ChatLastMessageSerializer(allow_null=True))
    def get_last_message(self, obj):
        from apps.messaging.services.conversations import last_message_preview

        message = self.context.get("last_messages", {}).get(getattr(obj, "_last_message_id", None))
        return last_message_preview(message, _user(self))

    def get_unread_count(self, obj) -> int:
        value = getattr(obj, "_unread", None)
        if value is not None:
            return value
        conversation = getattr(obj, "conversation", None)
        if conversation is None:
            return 0
        from apps.messaging.services.conversations import unread_count

        return unread_count(conversation, _user(self))

    @extend_schema_field(serializers.UUIDField(allow_null=True))
    def get_conversation_id(self, obj):
        value = getattr(obj, "_conversation_id", None)
        if value is None:
            conversation = getattr(obj, "conversation", None)
            value = conversation.pk if conversation is not None else None
        return str(value) if value else None

    @extend_schema_field(serializers.ListField(child=serializers.ChoiceField(
        choices=["accept", "decline", "complete", "cancel"])))
    def get_actions(self, obj):
        return inquiry_service.available_actions(obj, self._side(obj))


class InquiryDetailSerializer(InquiryListSerializer):
    customer = PublicAccountSerializer(read_only=True)
    provider = serializers.SerializerMethodField()
    snapshot = serializers.JSONField(source="object_snapshot", read_only=True)
    details = serializers.SerializerMethodField()
    history = InquiryStatusChangeSerializer(many=True, read_only=True)
    milestones = InquiryMilestoneSerializer(many=True, read_only=True)
    can_send_messages = serializers.SerializerMethodField()
    send_blocked_reason = serializers.SerializerMethodField()
    bookings = serializers.SerializerMethodField()

    class Meta(InquiryListSerializer.Meta):
        fields = InquiryListSerializer.Meta.fields + [
            "customer", "provider", "message", "details", "snapshot", "source_channel", "history", "milestones",
            "decline_reason", "cancel_reason", "closed_at", "board_model", "board_variant", "inventory_item",
            "instructor_offer", "school_program", "lesson_session", "can_send_messages", "send_blocked_reason",
            "bookings",
        ]

    @extend_schema_field(CommercePartyCardSerializer)
    def get_provider(self, obj):
        if obj.provider_account_id:
            return account_card(obj.provider_account)
        return organization_card(obj.provider_organization)

    @extend_schema_field(serializers.JSONField(help_text="details + photos[] (Media + signed_url) для ремонта"))
    def get_details(self, obj):
        from apps.mediafiles.models import MediaAsset
        from apps.messaging.services.media import signed_media

        details = dict(obj.details or {})
        photo_ids = details.get("photo_ids") or []
        if photo_ids:
            assets = {str(a.pk): a for a in MediaAsset.objects.filter(pk__in=photo_ids)}
            request = self.context.get("request")
            details["photos"] = [signed_media(assets[pid], request) for pid in photo_ids if pid in assets]
        return details

    def _conversation(self, obj):
        try:
            return obj.conversation
        except Exception:
            return None

    def get_can_send_messages(self, obj) -> bool:
        return self.get_send_blocked_reason(obj) is None

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_send_blocked_reason(self, obj):
        from apps.messaging.services.conversations import send_block_reason

        conversation = self._conversation(obj)
        if conversation is None:
            return "conversation_closed"
        reason = send_block_reason(conversation, _user(self))
        return reason[1] if reason else None

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_bookings(self, obj):
        return [{"id": str(b.pk), "kind": b.kind, "status": b.status,
                 "starts_at": serializers.DateTimeField().to_representation(b.starts_at)}
                for b in obj.bookings.all()]


# --- брони -------------------------------------------------------------------------------------------------------------


class BookingCreateSerializer(serializers.Serializer):
    lesson_session_id = serializers.UUIDField(required=False)
    seats = serializers.IntegerField(min_value=1, max_value=100, required=False, default=1)
    participant_name = serializers.CharField(max_length=160, required=False, allow_blank=True, default="")
    participant_is_minor = serializers.BooleanField(required=False, default=False)
    guardian_consent = serializers.BooleanField(required=False, default=False,
                                                help_text="Обязательно true, если participant_is_minor (SCH-11)")
    inventory_item_id = serializers.UUIDField(required=False)
    starts_at = serializers.DateTimeField(required=False)
    ends_at = serializers.DateTimeField(required=False)
    customer_note = serializers.CharField(max_length=2000, required=False, allow_blank=True, default="")
    group_with = serializers.UUIDField(required=False, allow_null=True,
                                       help_text="Другая моя бронь — объединить в группу (F06)")

    def validate(self, attrs):
        lesson, rental = bool(attrs.get("lesson_session_id")), bool(attrs.get("inventory_item_id"))
        if lesson == rental:
            raise serializers.ValidationError("Укажите lesson_session_id (занятие) или inventory_item_id (аренда).")
        if rental:
            missing = {f: ["Обязательное поле."] for f in ("starts_at", "ends_at") if not attrs.get(f)}
            if missing:
                raise serializers.ValidationError(missing)
        return attrs


class BookingCompleteSerializer(serializers.Serializer):
    amount_confirmed = serializers.BooleanField(required=False, allow_null=True, default=None)


class BookingStatusChangeSerializer(serializers.ModelSerializer):
    from_status_label = serializers.SerializerMethodField()
    to_status_label = serializers.SerializerMethodField()
    actor = PublicAccountSerializer(allow_null=True)

    class Meta:
        model = BookingStatusChange
        fields = ["from_status", "from_status_label", "to_status", "to_status_label", "actor", "comment", "created_at"]

    def get_from_status_label(self, obj) -> str:
        return Booking.Status(obj.from_status).label if obj.from_status else ""

    def get_to_status_label(self, obj) -> str:
        return Booking.Status(obj.to_status).label


class BookingRefSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    title = serializers.CharField()


class BookingSpotRefSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    slug = serializers.CharField()


class BookingLessonCardSerializer(serializers.Serializer):
    session_id = serializers.UUIDField()
    title = serializers.CharField()
    status = serializers.CharField()
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    capacity = serializers.IntegerField()
    free_seats = serializers.IntegerField()
    program = BookingRefSerializer(allow_null=True)
    offer = BookingRefSerializer(allow_null=True)
    spot = BookingSpotRefSerializer(allow_null=True)
    instructor = PublicAccountSerializer(allow_null=True)
    url = serializers.CharField()


class BookingRentalCardSerializer(serializers.Serializer):
    item_id = serializers.UUIDField()
    title = serializers.CharField()
    kind = serializers.CharField()
    size = serializers.CharField(allow_blank=True)
    photo = MediaSerializer(allow_null=True)
    pickup_location = serializers.CharField(allow_blank=True)
    rental_price_per_day = serializers.DecimalField(max_digits=10, decimal_places=2, allow_null=True)
    rental_price_per_hour = serializers.DecimalField(max_digits=10, decimal_places=2, allow_null=True)
    url = serializers.CharField()


class BookingSerializer(serializers.ModelSerializer):
    kind_label = serializers.CharField(source="get_kind_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    my_role = serializers.SerializerMethodField()
    customer = PublicAccountSerializer(read_only=True)
    provider = serializers.SerializerMethodField()
    provider_organization = serializers.SerializerMethodField()
    title = serializers.SerializerMethodField()
    lesson = serializers.SerializerMethodField()
    rental = serializers.SerializerMethodField()
    actions = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = ["id", "kind", "kind_label", "status", "status_label", "my_role", "title", "starts_at", "ends_at",
                  "seats", "participant_name", "participant_is_minor", "guardian_consent_at", "price_amount", "currency",
                  "amount_confirmed", "customer_note", "group_key", "is_overdue", "damage_reported", "decline_reason",
                  "cancel_reason", "cancelled_side", "confirmed_at", "completed_at", "created_at", "updated_at",
                  "customer", "provider", "provider_organization", "lesson", "rental", "inquiry", "actions"]

    def _side(self, obj):
        user = _user(self)
        return access.CUSTOMER if user is not None and obj.customer_id == user.pk else access.PROVIDER

    @extend_schema_field(serializers.ChoiceField(choices=["customer", "provider"]))
    def get_my_role(self, obj):
        return self._side(obj)

    @extend_schema_field(CommercePartyCardSerializer)
    def get_provider(self, obj):
        if obj.provider_account_id:
            return account_card(obj.provider_account)
        return organization_card(obj.provider_organization)

    @extend_schema_field(CommerceOrganizationBriefSerializer(allow_null=True))
    def get_provider_organization(self, obj):
        return organization_brief(obj.provider_organization)

    def get_title(self, obj) -> str:
        from apps.commerce.services.booking_transitions import booking_title

        return booking_title(obj)

    @extend_schema_field(BookingLessonCardSerializer(allow_null=True))
    def get_lesson(self, obj):
        session = obj.lesson_session
        if session is None:
            return None
        free = self.context.setdefault("_free", {})
        if session.pk not in free:
            free[session.pk] = booking_service.free_seats(session)
        return {
            "session_id": str(session.pk), "title": session.title, "status": session.status,
            "starts_at": serializers.DateTimeField().to_representation(session.starts_at),
            "ends_at": serializers.DateTimeField().to_representation(session.ends_at),
            "capacity": session.capacity, "free_seats": free[session.pk],
            "program": {"id": str(session.program_id), "title": session.program.title} if session.program_id else None,
            "offer": {"id": str(session.offer_id), "title": session.offer.title} if session.offer_id else None,
            "spot": ({"id": str(session.spot_id), "name": session.spot.name, "slug": session.spot.slug}
                     if session.spot_id else None),
            "instructor": PublicAccountSerializer(session.instructor).data if session.instructor_id else None,
            "url": f"/sessions/{session.pk}",
        }

    @extend_schema_field(BookingRentalCardSerializer(allow_null=True))
    def get_rental(self, obj):
        item = obj.inventory_item
        if item is None:
            return None
        photos = list(item.photos.all())
        return {
            "item_id": str(item.pk), "title": item.title, "kind": item.kind, "size": item.size,
            "photo": MediaSerializer(photos[0].media).data if photos else None,
            "pickup_location": item.pickup_location,
            "rental_price_per_day": item.rental_price_per_day, "rental_price_per_hour": item.rental_price_per_hour,
            "url": f"/rentals/{item.pk}",
        }

    @extend_schema_field(serializers.ListField(child=serializers.ChoiceField(
        choices=["confirm", "decline", "start", "complete", "no_show", "cancel"])))
    def get_actions(self, obj):
        return booking_service.available_actions(obj, self._side(obj), now=self.context.get("now") or timezone.now())


class GroupBookingSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    kind = serializers.CharField()
    status = serializers.CharField()
    title = serializers.CharField()
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()


class BookingDetailSerializer(BookingSerializer):
    history = BookingStatusChangeSerializer(many=True, read_only=True)
    group = serializers.SerializerMethodField()

    class Meta(BookingSerializer.Meta):
        fields = BookingSerializer.Meta.fields + ["history", "group"]

    @extend_schema_field(GroupBookingSerializer(many=True))
    def get_group(self, obj):
        if not obj.group_key:
            return []
        from apps.commerce.services.booking_transitions import booking_title

        user = _user(self)
        others = (Booking.objects.filter(group_key=obj.group_key, customer_id=obj.customer_id).exclude(pk=obj.pk)
                  .select_related("lesson_session", "inventory_item", "provider_organization", "provider_account"))
        visible = [b for b in others if access.booking_side(b, user)]
        return [{"id": str(b.pk), "kind": b.kind, "status": b.status, "title": booking_title(b),
                 "starts_at": serializers.DateTimeField().to_representation(b.starts_at),
                 "ends_at": serializers.DateTimeField().to_representation(b.ends_at)} for b in visible]
