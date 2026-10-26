from django.contrib import admin

from apps.community.models import BirthdayGreeting, SurfSession


@admin.register(SurfSession)
class SurfSessionAdmin(admin.ModelAdmin):
    list_display = ("date", "account", "spot", "spot_name", "visibility", "duration_min", "created_at")
    list_filter = ("visibility", "date")
    search_fields = ("account__email", "account__profile__handle", "spot__name", "spot_name", "notes")
    date_hierarchy = "date"
    list_select_related = ("account", "spot")
    readonly_fields = ("created_at", "updated_at")
    raw_id_fields = ("account", "spot", "photos")


@admin.register(BirthdayGreeting)
class BirthdayGreetingAdmin(admin.ModelAdmin):
    """Журнал отправленных поздравлений: только год, дата рождения здесь не показывается (ATX-34)."""

    list_display = ("account", "year", "sent_at")
    list_filter = ("year",)
    search_fields = ("account__email",)
    raw_id_fields = ("account",)
    readonly_fields = ("account", "year", "sent_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
