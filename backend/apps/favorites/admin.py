from django.contrib import admin

from apps.favorites.models import Favorite


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ("id", "account", "target_type", "target_label", "created_at")
    list_filter = ("target_type",)
    search_fields = ("account__email", "account__profile__handle")
    raw_id_fields = ("account", "spot", "instructor", "organization", "board_model", "inventory_item")
    date_hierarchy = "created_at"
    list_select_related = ("account", "spot", "instructor", "organization", "board_model", "inventory_item")

    @admin.display(description="Объект")
    def target_label(self, obj):
        return str(obj.target) if obj.target is not None else "—"
