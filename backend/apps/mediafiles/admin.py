from django.contrib import admin, messages
from django.utils.html import format_html

from apps.mediafiles.models import MediaAsset


@admin.register(MediaAsset)
class MediaAssetAdmin(admin.ModelAdmin):
    list_display = ("id", "purpose", "kind", "visibility", "status", "owner", "size_bytes", "created_at", "preview")
    list_filter = ("status", "visibility", "kind", "purpose", "is_demo")
    search_fields = ("id", "storage_key", "original_filename", "owner__email")
    raw_id_fields = ("owner", "organization")
    readonly_fields = ("id", "storage_key", "thumbnail_key", "poster_key", "checksum_sha256", "content_type",
                       "size_bytes", "width", "height", "duration_seconds", "upload_expires_at", "processed_at",
                       "created_at", "updated_at", "preview")
    date_hierarchy = "created_at"
    actions = ["reprocess", "mark_deleted"]

    @admin.display(description="Превью")
    def preview(self, obj):
        if obj.thumbnail_url:
            return format_html('<img src="{}" style="max-height:60px;max-width:120px" alt="">', obj.thumbnail_url)
        return "—"

    @admin.action(description="Обработать повторно")
    def reprocess(self, request, queryset):
        from apps.mediafiles.services.uploads import enqueue_processing

        count = 0
        for asset in queryset.exclude(status__in=[MediaAsset.Status.DELETED, MediaAsset.Status.PENDING]):
            asset.status = MediaAsset.Status.PROCESSING
            asset.save(update_fields=["status", "updated_at"])
            enqueue_processing(asset.id)
            count += 1
        self.message_user(request, f"Поставлено в обработку: {count}", messages.SUCCESS)

    @admin.action(description="Удалить файл из хранилища (статус «удалено»)")
    def mark_deleted(self, request, queryset):
        from apps.mediafiles.services.uploads import _delete_objects

        count = 0
        for asset in queryset.exclude(status=MediaAsset.Status.DELETED):
            asset.status = MediaAsset.Status.DELETED
            asset.save(update_fields=["status", "updated_at"])
            _delete_objects(asset)
            count += 1
        self.message_user(request, f"Удалено: {count}", messages.SUCCESS)
