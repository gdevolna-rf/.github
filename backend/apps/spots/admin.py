from django.contrib import admin

from apps.spots.models import Region, Spot, SpotChangeRequest, SpotForecast, SpotPhoto, SpotSourceRecord
from apps.trust.services.audit import record


def _jsonable(value):
    if value is None or isinstance(value, (str, int, float, bool, list, dict)):
        return value
    return str(value)


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "timezone", "center_lat", "center_lng", "sort_order"]
    list_editable = ["sort_order"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ["name"]}


class SpotPhotoInline(admin.TabularInline):
    model = SpotPhoto
    extra = 0
    raw_id_fields = ["media", "author"]
    fields = ["media", "position", "caption", "author"]


class SpotSourceRecordInline(admin.TabularInline):
    model = SpotSourceRecord
    extra = 0
    raw_id_fields = ["created_by"]
    fields = ["source", "url", "note", "confirmed_at", "created_by"]


@admin.register(Spot)
class SpotAdmin(admin.ModelAdmin):
    list_display = ["name", "region", "status", "difficulty", "location_precision", "is_sensitive", "rating_avg",
                    "rating_count", "last_confirmed_at", "is_demo"]
    list_filter = ["status", "region", "difficulty", "bottom_type", "break_type", "location_precision", "is_sensitive",
                   "is_demo"]
    search_fields = ["name", "slug", "short_description"]
    prepopulated_fields = {"slug": ["name"]}
    raw_id_fields = ["cover", "created_by"]
    readonly_fields = ["rating_avg", "rating_count", "created_at", "updated_at"]
    inlines = [SpotPhotoInline, SpotSourceRecordInline]
    fieldsets = [
        (None, {"fields": ["name", "slug", "region", "status", "is_demo", "created_by"]}),
        ("Геоположение (SPT-12)", {"fields": ["lat", "lng", "location_precision", "is_sensitive"]}),
        ("Описание", {"fields": ["short_description", "description", "difficulty", "bottom_type", "break_type",
                                 "wave_character", "wave_power"]}),
        ("Типичные условия (SPT-04)", {"fields": ["season", "best_months", "best_wind_directions",
                                                  "best_swell_directions", "best_tide", "typical_conditions",
                                                  "water_temp_note"]}),
        ("Безопасность и доступ (SPT-05/06)", {"fields": ["hazards", "hazard_notes", "entry_exit", "access",
                                                          "infrastructure"]}),
        ("Ограничения (GEO-06)", {"fields": ["seasonal_warning", "closed_until"]}),
        ("Медиа", {"fields": ["cover", "webcam_url", "webcam_is_premium"]}),
        ("Достоверность (SPT-11)", {"fields": ["data_source", "last_confirmed_at"]}),
        ("Рейтинг (только published-отзывы)", {"fields": ["rating_avg", "rating_count"]}),
        ("Служебное", {"fields": ["created_at", "updated_at"]}),
    ]

    def save_model(self, request, obj, form, change):
        """Правка карточки администратором тоже попадает в журнал аудита (7.4)."""
        fields = [f for f in form.changed_data if f in {fl.name for fl in Spot._meta.fields}]
        before = {}
        if change and fields:
            old = Spot.objects.filter(pk=obj.pk).first()
            before = {f: _jsonable(getattr(old, f)) for f in fields} if old else {}
        super().save_model(request, obj, form, change)
        if fields or not change:
            record(request.user, "spot.admin_updated" if change else "spot.admin_created", obj, before=before or None,
                   after={f: _jsonable(getattr(obj, f)) for f in fields}, request=request)


@admin.register(SpotForecast)
class SpotForecastAdmin(admin.ModelAdmin):
    list_display = ["spot", "provider", "issued_at", "valid_from", "valid_to", "wave_height_m", "wind_speed_ms"]
    list_filter = ["provider"]
    raw_id_fields = ["spot"]
    date_hierarchy = "valid_from"


@admin.register(SpotChangeRequest)
class SpotChangeRequestAdmin(admin.ModelAdmin):
    """Решения по правкам принимаются через API модерации (аудит + уведомление); здесь — просмотр."""

    list_display = ["spot", "author", "status", "created_at", "decided_at", "reverted_at"]
    list_filter = ["status"]
    search_fields = ["spot__name", "author__email"]
    raw_id_fields = ["spot", "author", "moderator", "reverted_by"]
    readonly_fields = ["spot", "author", "status", "changes", "comment", "source", "evidence", "moderator",
                       "moderator_comment", "decided_at", "reverted_at", "reverted_by", "created_at", "updated_at"]

    def has_add_permission(self, request):
        return False
