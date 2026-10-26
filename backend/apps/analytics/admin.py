from django.contrib import admin

from apps.analytics.models import AnalyticsEvent


@admin.register(AnalyticsEvent)
class AnalyticsEventAdmin(admin.ModelAdmin):
    """События пишутся один раз и не редактируются (раздел 10, MET-08)."""

    list_display = ["name", "subject_type", "subject_id", "owner_account", "owner_organization", "occurred_at",
                    "rule_version"]
    list_filter = ["name", "subject_type", "rule_version"]
    search_fields = ["subject_id", "event_id", "dedup_key", "anonymous_id"]
    date_hierarchy = "occurred_at"
    raw_id_fields = ["actor", "owner_account", "owner_organization"]
    readonly_fields = [f.name for f in AnalyticsEvent._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
