"""Django Admin: обращения и брони. Статусы меняются только через API (машины состояний 7.2/7.3), здесь — просмотр."""
from django.contrib import admin

from apps.commerce.models import Booking, BookingStatusChange, Inquiry, InquiryMilestone, InquiryStatusChange


class ReadOnlyInline(admin.TabularInline):
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class InquiryStatusChangeInline(ReadOnlyInline):
    model = InquiryStatusChange
    fields = ["created_at", "from_status", "to_status", "actor", "comment"]
    readonly_fields = fields


class InquiryMilestoneInline(ReadOnlyInline):
    model = InquiryMilestone
    fields = ["position", "title", "amount", "due_date", "status", "completed_at", "confirmed_at"]
    readonly_fields = fields


@admin.register(Inquiry)
class InquiryAdmin(admin.ModelAdmin):
    list_display = ["subject", "kind", "status", "customer", "provider_account", "provider_organization",
                    "agreed_amount", "amount_confirmed", "created_at"]
    list_filter = ["kind", "status", "amount_confirmed", "source_channel", "created_at"]
    search_fields = ["subject", "message", "customer__email", "provider_account__email", "provider_organization__name"]
    date_hierarchy = "created_at"
    list_select_related = ["customer", "provider_account", "provider_organization"]
    raw_id_fields = ["customer", "provider_account", "provider_organization", "board_model", "board_variant",
                     "inventory_item", "instructor_offer", "school_program", "lesson_session"]
    readonly_fields = ["id", "kind", "status", "customer", "provider_account", "provider_organization",
                       "object_snapshot", "details", "source_channel", "closed_at", "created_at", "updated_at"]
    inlines = [InquiryStatusChangeInline, InquiryMilestoneInline]


class BookingStatusChangeInline(ReadOnlyInline):
    model = BookingStatusChange
    fields = ["created_at", "from_status", "to_status", "actor", "comment"]
    readonly_fields = fields


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ["__str__", "kind", "status", "customer", "provider_account", "provider_organization", "starts_at",
                    "ends_at", "seats", "price_amount", "is_overdue"]
    list_filter = ["kind", "status", "is_overdue", "participant_is_minor", "cancelled_side", "starts_at"]
    search_fields = ["customer__email", "participant_name", "provider_organization__name", "inventory_item__title",
                     "lesson_session__title"]
    date_hierarchy = "starts_at"
    list_select_related = ["customer", "provider_account", "provider_organization"]
    raw_id_fields = ["customer", "provider_account", "provider_organization", "lesson_session", "inventory_item",
                     "inquiry", "cancelled_by"]
    readonly_fields = ["id", "kind", "status", "customer", "provider_account", "provider_organization",
                       "lesson_session", "inventory_item", "starts_at", "ends_at", "price_amount",
                       "guardian_consent_at", "confirmed_at", "completed_at", "cancelled_by", "cancelled_side",
                       "created_at", "updated_at"]
    inlines = [BookingStatusChangeInline]
