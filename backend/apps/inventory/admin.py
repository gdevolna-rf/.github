from django.contrib import admin

from apps.inventory.models import InventoryItem, InventoryItemPhoto, RentalHandover


class InventoryItemPhotoInline(admin.TabularInline):
    model = InventoryItemPhoto
    extra = 0
    raw_id_fields = ["media"]


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    """Сохранение через админку тоже пересчитывает наличие варианта (сигналы apps.inventory.signals)."""

    list_display = ["title", "kind", "purpose", "status", "owner_account", "owner_organization", "variant", "region",
                    "rental_price_per_day", "is_published", "is_demo"]
    list_filter = ["kind", "purpose", "status", "is_published", "is_demo", "condition"]
    search_fields = ["title", "serial_number", "variant__sku", "owner_account__email", "owner_organization__name"]
    raw_id_fields = ["owner_account", "owner_organization", "variant", "region", "spot"]
    readonly_fields = ["id", "created_at", "updated_at"]
    inlines = [InventoryItemPhotoInline]


@admin.register(RentalHandover)
class RentalHandoverAdmin(admin.ModelAdmin):
    list_display = ["booking", "kind", "condition", "damage_reported", "recorded_by", "created_at"]
    list_filter = ["kind", "damage_reported", "condition"]
    search_fields = ["booking__id", "notes", "damage_description"]
    raw_id_fields = ["booking", "recorded_by", "photos"]
    readonly_fields = ["id", "created_at", "updated_at"]

    def has_delete_permission(self, request, obj=None):
        return False  # акты — часть истории аренды (RENT-06)
