"""Форматы диалогов, сообщений, уведомлений, настроек и блокировок."""
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.accounts.serializers_public import PublicAccountSerializer
from apps.commerce.serializers import (
    InquiryContextCardSerializer,
    ChatLastMessageSerializer,
    CommerceOrganizationBriefSerializer,
    CommercePartyCardSerializer,
    account_card,
    organization_brief,
    organization_card,
)
from apps.commerce.services import access as commerce_access
from apps.commerce.services import inquiries as inquiry_service
from apps.commerce.services.snapshots import context_card
from apps.mediafiles.serializers import MediaSerializer
from apps.messaging.models import Conversation, ConversationParticipant, Notification
from apps.messaging.services import conversations as chat


def _user(serializer):
    request = serializer.context.get("request")
    return getattr(request, "user", None)


# --- сообщения ---------------------------------------------------------------------------------------------------------


class ChatSignedMediaSerializer(MediaSerializer):
    signed_url = serializers.CharField(allow_null=True, read_only=True,
                                       help_text="Короткоживущая ссылка (≈2 мин) для участников; null, пока файл не проверен")
    signed_thumbnail_url = serializers.CharField(allow_null=True, read_only=True)

    class Meta(MediaSerializer.Meta):
        fields = MediaSerializer.Meta.fields + ["signed_url", "signed_thumbnail_url"]
        read_only_fields = fields


class ChatMessageSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    conversation_id = serializers.UUIDField()
    kind = serializers.ChoiceField(choices=["text", "system"])
    body = serializers.CharField(allow_blank=True)
    sender = PublicAccountSerializer(allow_null=True)
    is_mine = serializers.BooleanField()
    is_hidden = serializers.BooleanField(help_text="Скрыто модератором: body и attachments пустые")
    client_id = serializers.CharField(allow_blank=True, help_text="Только для своих сообщений")
    created_at = serializers.DateTimeField()
    edited_at = serializers.DateTimeField(allow_null=True)
    attachments = ChatSignedMediaSerializer(many=True)

    def to_representation(self, instance):
        user = _user(self)
        return chat.message_payload(instance, self.context.get("request"), getattr(user, "pk", None))


class ChatMessageCreateSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=chat.MAX_BODY, required=False, allow_blank=True, default="",
                                 trim_whitespace=False)
    attachment_ids = serializers.ListField(child=serializers.UUIDField(), required=False, default=list,
                                           max_length=chat.MAX_ATTACHMENTS,
                                           help_text="MediaAsset purpose=message_attachment, изображения, ≤10")
    client_id = serializers.CharField(max_length=64, required=False, allow_blank=True, default="",
                                      help_text="Идентификатор клиента для дедупликации повторной отправки")


class ChatMessagePageSerializer(serializers.Serializer):
    results = ChatMessageSerializer(many=True)
    has_more = serializers.BooleanField(help_text="Есть более ранние сообщения (для before)")
    has_newer = serializers.BooleanField(help_text="Есть более новые сообщения (для after)")
    next_before = serializers.UUIDField(allow_null=True, help_text="Передайте в before для следующей страницы")


class ConversationReadRequestSerializer(serializers.Serializer):
    message_id = serializers.UUIDField(required=False, allow_null=True)


class MeCountersSerializer(serializers.Serializer):
    unread_messages = serializers.IntegerField()
    unread_notifications = serializers.IntegerField()
    new_inquiries = serializers.IntegerField()
    pending_bookings = serializers.IntegerField()


class ConversationReadResultSerializer(serializers.Serializer):
    conversation_id = serializers.UUIDField()
    last_read_at = serializers.DateTimeField(allow_null=True)
    unread_count = serializers.IntegerField()
    counters = MeCountersSerializer()


# --- диалоги -----------------------------------------------------------------------------------------------------------


class ConversationInquirySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    kind = serializers.CharField()
    kind_label = serializers.CharField()
    status = serializers.CharField()
    status_label = serializers.CharField()
    subject = serializers.CharField()
    my_role = serializers.ChoiceField(choices=["customer", "provider"])
    actions = serializers.ListField(child=serializers.CharField())
    provider_organization = CommerceOrganizationBriefSerializer(allow_null=True)


class ConversationParticipantSerializer(serializers.Serializer):
    account = PublicAccountSerializer()
    role = serializers.ChoiceField(choices=ConversationParticipant.Role.choices)
    organization = CommerceOrganizationBriefSerializer(allow_null=True)
    last_read_at = serializers.DateTimeField(allow_null=True)


class ConversationListSerializer(serializers.ModelSerializer):
    inquiry_id = serializers.UUIDField(read_only=True, allow_null=True)
    inquiry_status = serializers.SerializerMethodField()
    counterpart = serializers.SerializerMethodField()
    context = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = ["id", "kind", "subject", "inquiry_id", "inquiry_status", "counterpart", "context", "last_message",
                  "unread_count", "is_locked", "last_message_at", "created_at"]

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_inquiry_status(self, obj):
        return obj.inquiry.status if obj.inquiry_id else None

    @extend_schema_field(CommercePartyCardSerializer(allow_null=True))
    def get_counterpart(self, obj):
        user = _user(self)
        if obj.kind == Conversation.Kind.INQUIRY and obj.inquiry_id:
            inquiry = obj.inquiry
            if inquiry.customer_id != user.pk:
                return account_card(inquiry.customer)
            if inquiry.provider_account_id:
                return account_card(inquiry.provider_account)
            return organization_card(inquiry.provider_organization)
        others = [p.account for p in obj.participants.all() if p.account_id != user.pk]
        return account_card(others[0]) if others else None

    @extend_schema_field(InquiryContextCardSerializer(allow_null=True))
    def get_context(self, obj):
        return context_card(obj.inquiry.object_snapshot) if obj.inquiry_id else None

    @extend_schema_field(ChatLastMessageSerializer(allow_null=True))
    def get_last_message(self, obj):
        message = self.context.get("last_messages", {}).get(getattr(obj, "_last_message_id", None))
        return chat.last_message_preview(message, _user(self))

    def get_unread_count(self, obj) -> int:
        value = getattr(obj, "_unread", None)
        return value if value is not None else chat.unread_count(obj, _user(self))


class ConversationDetailSerializer(ConversationListSerializer):
    inquiry = serializers.SerializerMethodField()
    participants = serializers.SerializerMethodField()
    my_last_read_at = serializers.SerializerMethodField()
    can_send = serializers.SerializerMethodField()
    send_blocked_reason = serializers.SerializerMethodField()

    class Meta(ConversationListSerializer.Meta):
        fields = ConversationListSerializer.Meta.fields + [
            "inquiry", "participants", "my_last_read_at", "can_send", "send_blocked_reason"]

    @extend_schema_field(ConversationInquirySerializer(allow_null=True))
    def get_inquiry(self, obj):
        if not obj.inquiry_id:
            return None
        inquiry = obj.inquiry
        side = commerce_access.inquiry_side(inquiry, _user(self))
        return {
            "id": str(inquiry.pk), "kind": inquiry.kind, "kind_label": inquiry.get_kind_display(),
            "status": inquiry.status, "status_label": inquiry.get_status_display(), "subject": inquiry.subject,
            "my_role": side, "actions": inquiry_service.available_actions(inquiry, side),
            "provider_organization": organization_brief(inquiry.provider_organization),
        }

    @extend_schema_field(ConversationParticipantSerializer(many=True))
    def get_participants(self, obj):
        from apps.accounts.models import Account

        audience = chat.audience_ids(obj)
        rows = {p.account_id: p for p in obj.participants.select_related("organization")}
        accounts = Account.objects.filter(pk__in=audience).select_related("profile__avatar")
        result = []
        inquiry = obj.inquiry if obj.inquiry_id else None
        for account in accounts:
            row = rows.get(account.pk)
            if row is not None:
                role, org = row.role, row.organization
            elif inquiry is not None and inquiry.customer_id == account.pk:
                role, org = ConversationParticipant.Role.CUSTOMER, None
            elif inquiry is not None and inquiry.provider_account_id == account.pk:
                role, org = ConversationParticipant.Role.PROVIDER, None
            elif inquiry is not None:
                role, org = ConversationParticipant.Role.MEMBER, inquiry.provider_organization
            else:
                role, org = ConversationParticipant.Role.PEER, None
            result.append({
                "account": PublicAccountSerializer(account).data, "role": role,
                "organization": organization_brief(org),
                "last_read_at": chat.iso(row.last_read_at) if row is not None else None,
            })
        order = {ConversationParticipant.Role.CUSTOMER: 0, ConversationParticipant.Role.PROVIDER: 1}
        result.sort(key=lambda r: (order.get(r["role"], 2), r["account"]["display_name"]))
        return result

    @extend_schema_field(serializers.DateTimeField(allow_null=True))
    def get_my_last_read_at(self, obj):
        row = obj.participants.filter(account=_user(self)).first()
        return chat.iso(row.last_read_at) if row else None

    def get_can_send(self, obj) -> bool:
        return self.get_send_blocked_reason(obj) is None

    @extend_schema_field(serializers.ChoiceField(
        choices=["conversation_closed", "messaging_restricted", "blocked"], allow_null=True))
    def get_send_blocked_reason(self, obj):
        cache = self.context.setdefault("_send_reason", {})
        if obj.pk not in cache:
            reason = chat.send_block_reason(obj, _user(self))
            cache[obj.pk] = reason[1] if reason else None
        return cache[obj.pk]


class DirectConversationCreateSerializer(serializers.Serializer):
    account_id = serializers.UUIDField()


# --- уведомления -------------------------------------------------------------------------------------------------------


class UserNotificationSerializer(serializers.ModelSerializer):
    kind_label = serializers.CharField(source="get_kind_display", read_only=True)
    actor = PublicAccountSerializer(allow_null=True, read_only=True)
    is_read = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = ["id", "kind", "kind_label", "title", "body", "link", "payload", "actor", "created_at", "read_at",
                  "is_read"]
        read_only_fields = fields

    def get_is_read(self, obj) -> bool:
        return obj.read_at is not None


class NotificationsReadAllSerializer(serializers.Serializer):
    updated = serializers.IntegerField()


class NotificationPreferenceItemSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=Notification.Kind.choices)
    label = serializers.CharField(read_only=True)
    in_app = serializers.BooleanField(required=False)
    email = serializers.BooleanField(required=False)
    push = serializers.BooleanField(required=False)
    is_default = serializers.BooleanField(read_only=True, help_text="Пользователь не менял настройку")


class NotificationPreferencesSerializer(serializers.Serializer):
    preferences = NotificationPreferenceItemSerializer(many=True)


# --- блокировки --------------------------------------------------------------------------------------------------------


class AccountBlockSerializer(serializers.Serializer):
    account = PublicAccountSerializer(source="blocked")
    created_at = serializers.DateTimeField()


class AccountBlockCreateSerializer(serializers.Serializer):
    account_id = serializers.UUIDField()
