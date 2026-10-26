from django.contrib import admin

from apps.boards.models import BoardMedia, BoardModel, BoardType, BoardVariant, Material, WorkshopProfile


@admin.register(WorkshopProfile)
class WorkshopProfileAdmin(admin.ModelAdmin):
    list_display = ["organization", "shaper_code", "does_repair", "lead_time", "experience_since"]
    list_filter = ["does_repair"]
    search_fields = ["organization__name", "organization__slug", "shaper_code", "specialization"]
    raw_id_fields = ["organization", "promo_video"]


@admin.register(BoardType)
class BoardTypeAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "sku_code", "silhouette", "workshop", "sort_order"]
    list_filter = [("workshop", admin.EmptyFieldListFilter), "silhouette"]
    search_fields = ["name", "code", "workshop__name"]
    raw_id_fields = ["workshop"]


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ["name", "workshop"]
    list_filter = [("workshop", admin.EmptyFieldListFilter)]
    search_fields = ["name", "workshop__name"]
    raw_id_fields = ["workshop"]


# Артикул, версии и наличие поддерживают сервисы (apps.boards.services.variants / availability), поэтому в админке
# размеры и конструкция только для чтения, а варианты не создаются вручную.
VARIANT_SPEC_FIELDS = ["sku", "sku_suffix", "version", "previous_version", "length_in", "width_in", "thickness_in",
                       "volume_l", "material", "construction", "fin_system", "availability"]


class BoardVariantInline(admin.TabularInline):
    model = BoardVariant
    fk_name = "model"
    extra = 0
    fields = ["sku", "version", "is_active", "length_in", "width_in", "thickness_in", "volume_l", "material", "price",
              "currency", "made_to_order_days", "availability"]
    readonly_fields = [f for f in fields if f in VARIANT_SPEC_FIELDS]
    show_change_link = True
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


class BoardMediaInline(admin.TabularInline):
    model = BoardMedia
    extra = 0
    fields = ["media", "variant", "position", "is_cover"]
    raw_id_fields = ["media", "variant"]


@admin.register(BoardModel)
class BoardModelAdmin(admin.ModelAdmin):
    list_display = ["name", "workshop", "board_type", "status", "serial", "published_at", "is_demo", "created_at"]
    list_filter = ["status", "is_demo", "board_type"]
    search_fields = ["name", "slug", "workshop__name", "variants__sku"]
    raw_id_fields = ["workshop", "video"]
    readonly_fields = ["id", "serial", "created_at", "updated_at"]
    inlines = [BoardVariantInline, BoardMediaInline]
    actions = ["hide_models"]

    def save_formset(self, request, form, formset, change):
        from apps.boards.services.availability import refresh_variant_availability

        super().save_formset(request, form, formset, change)
        if formset.model is BoardVariant:
            for variant in formset.queryset:
                refresh_variant_availability(variant)

    @admin.action(description="Скрыть выбранные модели (модерация)")
    def hide_models(self, request, queryset):
        from apps.trust.services.audit import record

        for model in queryset:
            before = model.status
            model.status = BoardModel.Status.HIDDEN
            model.save(update_fields=["status", "updated_at"])
            record(request.user, "board_model.hidden", model, before={"status": before},
                   after={"status": model.status}, organization=model.workshop, request=request)


@admin.register(BoardVariant)
class BoardVariantAdmin(admin.ModelAdmin):
    list_display = ["sku", "model", "version", "is_active", "length_in", "width_in", "volume_l", "price",
                    "availability"]
    list_filter = ["is_active", "availability", "fin_system"]
    search_fields = ["sku", "model__name", "model__workshop__name"]
    readonly_fields = ["id", "model", *VARIANT_SPEC_FIELDS, "created_at", "updated_at"]

    def has_add_permission(self, request):
        return False

    def save_model(self, request, obj, form, change):
        from apps.boards.services.availability import refresh_variant_availability

        super().save_model(request, obj, form, change)
        refresh_variant_availability(obj)


@admin.register(BoardMedia)
class BoardMediaAdmin(admin.ModelAdmin):
    list_display = ["id", "model", "variant", "position", "is_cover"]
    list_filter = ["is_cover"]
    search_fields = ["model__name"]
    raw_id_fields = ["model", "variant", "media"]
