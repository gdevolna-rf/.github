from django.contrib import admin, messages

from apps.club.models import ClubAnnouncement, ClubEvent, EventRegistration
from apps.club.services.manage import cancel_event_by_admin
from apps.common.text import unique_slug


class EventRegistrationInline(admin.TabularInline):
    model = EventRegistration
    extra = 0
    raw_id_fields = ("account",)
    fields = ("account", "status", "created_at", "promoted_at", "cancelled_at", "reminder_sent_at")
    readonly_fields = ("created_at", "promoted_at", "cancelled_at", "reminder_sent_at")
    show_change_link = True


@admin.register(ClubEvent)
class ClubEventAdmin(admin.ModelAdmin):
    list_display = ("title", "kind", "status", "starts_at", "region", "capacity", "organizer", "is_demo")
    list_filter = ("status", "kind", "region", "is_demo")
    search_fields = ("title", "slug", "description", "location_note", "organizer__email")
    raw_id_fields = ("organizer", "organizer_organization", "spot", "cover")
    readonly_fields = ("reminder_sent_at", "created_at", "updated_at")
    date_hierarchy = "starts_at"
    inlines = [EventRegistrationInline]
    actions = ["cancel_events"]

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if "slug" in form.base_fields:
            form.base_fields["slug"].required = False
            form.base_fields["slug"].help_text = "Пусто — сгенерируется из названия латиницей."
        return form

    def save_model(self, request, obj, form, change):
        if not obj.slug:
            obj.slug = unique_slug(ClubEvent, obj.title, max_length=80)
        super().save_model(request, obj, form, change)

    @admin.action(description="Отменить события и уведомить участников")
    def cancel_events(self, request, queryset):
        cancelled = sum(1 for event in queryset if cancel_event_by_admin(event, request.user, request))
        self.message_user(request, f"Отменено событий: {cancelled}", messages.SUCCESS)


@admin.register(EventRegistration)
class EventRegistrationAdmin(admin.ModelAdmin):
    list_display = ("event", "account", "status", "created_at", "promoted_at", "reminder_sent_at")
    list_filter = ("status",)
    search_fields = ("event__title", "account__email")
    raw_id_fields = ("event", "account")
    readonly_fields = ("created_at", "updated_at", "promoted_at", "cancelled_at", "reminder_sent_at")


@admin.register(ClubAnnouncement)
class ClubAnnouncementAdmin(admin.ModelAdmin):
    list_display = ("title", "is_pinned", "published_at", "author", "created_at")
    list_filter = ("is_pinned",)
    search_fields = ("title", "body")
    raw_id_fields = ("author",)
    readonly_fields = ("created_at", "updated_at")

    def save_model(self, request, obj, form, change):
        if not obj.author_id:
            obj.author = request.user
        super().save_model(request, obj, form, change)
