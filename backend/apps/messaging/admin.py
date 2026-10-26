"""Django Admin: диалоги, сообщения (скрытие по жалобам, MSG-13), уведомления, настройки, блокировки."""
from django.contrib import admin

from apps.messaging.models import (
    AccountBlock,
    Conversation,
    ConversationParticipant,
    Message,
    MessageAttachment,
    Notification,
    NotificationPreference,
    PushDevice,
)
from apps.trust.services.audit import record


class ParticipantInline(admin.TabularInline):
    model = ConversationParticipant
    extra = 0
    fields = ["account", "role", "organization", "last_read_at", "joined_at", "left_at", "is_muted"]
    readonly_fields = ["joined_at", "last_read_at"]
    raw_id_fields = ["account", "organization"]


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    can_delete = False
    fields = ["created_at", "sender", "kind", "body", "is_hidden"]
    readonly_fields = ["created_at", "sender", "kind", "body"]
    ordering = ["-created_at"]
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ["__str__", "kind", "inquiry", "is_locked", "last_message_at", "created_at"]
    list_filter = ["kind", "is_locked"]
    search_fields = ["subject", "participants__account__email"]
    raw_id_fields = ["inquiry"]
    readonly_fields = ["id", "direct_key", "last_message_at", "created_at", "updated_at"]
    inlines = [ParticipantInline, MessageInline]

    def save_model(self, request, obj, form, change):
        if change and "is_locked" in form.changed_data:
            record(request.user, "conversation.locked" if obj.is_locked else "conversation.unlocked", obj,
                   before={"is_locked": not obj.is_locked}, after={"is_locked": obj.is_locked}, request=request)
        super().save_model(request, obj, form, change)


class AttachmentInline(admin.TabularInline):
    model = MessageAttachment
    extra = 0
    raw_id_fields = ["media"]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ["__str__", "conversation", "sender", "kind", "is_hidden", "created_at"]
    list_filter = ["kind", "is_hidden", "created_at"]
    search_fields = ["body", "sender__email"]
    raw_id_fields = ["conversation", "sender"]
    readonly_fields = ["id", "conversation", "sender", "kind", "body", "client_id", "created_at", "updated_at",
                       "edited_at"]
    inlines = [AttachmentInline]
    actions = ["hide_messages", "unhide_messages"]

    @admin.action(description="Скрыть выбранные сообщения")
    def hide_messages(self, request, queryset):
        for message in queryset.filter(is_hidden=False):
            message.is_hidden = True
            message.save(update_fields=["is_hidden", "updated_at"])
            record(request.user, "message.hidden", message, before={"is_hidden": False}, after={"is_hidden": True},
                   request=request)

    @admin.action(description="Вернуть выбранные сообщения")
    def unhide_messages(self, request, queryset):
        for message in queryset.filter(is_hidden=True):
            message.is_hidden = False
            message.save(update_fields=["is_hidden", "updated_at"])
            record(request.user, "message.unhidden", message, before={"is_hidden": True}, after={"is_hidden": False},
                   request=request)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["title", "recipient", "kind", "created_at", "read_at", "email_sent_at"]
    list_filter = ["kind", "created_at"]
    search_fields = ["title", "body", "recipient__email", "event_id"]
    raw_id_fields = ["recipient", "actor"]
    readonly_fields = ["id", "event_id", "created_at"]


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ["account", "kind", "in_app", "email", "push"]
    list_filter = ["kind", "in_app", "email", "push"]
    search_fields = ["account__email"]
    raw_id_fields = ["account"]


@admin.register(PushDevice)
class PushDeviceAdmin(admin.ModelAdmin):
    list_display = ["account", "platform", "is_active", "created_at"]
    list_filter = ["platform", "is_active"]
    search_fields = ["account__email", "token"]
    raw_id_fields = ["account"]


@admin.register(AccountBlock)
class AccountBlockAdmin(admin.ModelAdmin):
    list_display = ["blocker", "blocked", "created_at"]
    search_fields = ["blocker__email", "blocked__email"]
    raw_id_fields = ["blocker", "blocked"]
