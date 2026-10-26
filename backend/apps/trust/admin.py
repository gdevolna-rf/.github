"""Django Admin для trust. Основной поток решений — API модерации; правки в админке тоже пишут аудит."""
from django.contrib import admin

from apps.trust.models import AccountRestriction, AuditEvent, Complaint, ModerationCase, Review
from apps.trust.services.audit import record
from apps.trust.services.ratings import recalculate_for_review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ["id", "target_type", "author", "rating", "status", "has_pending_revision", "published_at", "is_demo"]
    list_filter = ["status", "target_type", "has_pending_revision", "is_demo"]
    search_fields = ["author__email", "text", "spot__name", "organization__name"]
    raw_id_fields = ["author", "spot", "instructor", "organization", "booking", "inquiry", "moderator"]
    filter_horizontal = ["photos", "pending_photos"]
    readonly_fields = ["created_at", "updated_at"]

    def save_model(self, request, obj, form, change):
        before = None
        if change:
            old = Review.objects.filter(pk=obj.pk).values("status", "rating", "text").first()
            before = old
        super().save_model(request, obj, form, change)
        record(request.user, "review.admin_updated" if change else "review.admin_created", obj, before=before,
               after={"status": obj.status, "rating": obj.rating, "text": obj.text}, request=request)
        recalculate_for_review(obj)

    def delete_model(self, request, obj):
        record(request.user, "review.admin_deleted", obj, before={"status": obj.status, "rating": obj.rating},
               request=request)
        super().delete_model(request, obj)
        recalculate_for_review(obj)

    def delete_queryset(self, request, queryset):
        reviews = list(queryset)
        super().delete_queryset(request, queryset)
        for review in reviews:
            record(request.user, "review.admin_deleted", object_type="trust.review", object_id=review.pk,
                   before={"status": review.status, "rating": review.rating}, request=request)
            recalculate_for_review(review)


@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    list_display = ["id", "target_type", "target_id", "reason", "status", "action_taken", "reporter", "created_at"]
    list_filter = ["status", "target_type", "reason", "action_taken"]
    search_fields = ["target_id", "reporter__email", "text"]
    raw_id_fields = ["reporter", "target_owner"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(ModerationCase)
class ModerationCaseAdmin(admin.ModelAdmin):
    list_display = ["kind", "status", "summary", "due_at", "assigned_to", "resolution", "resolved_at", "created_at"]
    list_filter = ["kind", "status"]
    search_fields = ["summary"]
    raw_id_fields = ["spot_change_request", "review", "certificate", "complaint", "organization", "assigned_to",
                     "resolved_by"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(AccountRestriction)
class AccountRestrictionAdmin(admin.ModelAdmin):
    list_display = ["account", "kind", "reason", "expires_at", "lifted_at", "created_by", "created_at"]
    list_filter = ["kind"]
    search_fields = ["account__email", "reason"]
    raw_id_fields = ["account", "created_by"]
    readonly_fields = ["created_at", "updated_at"]

    def save_model(self, request, obj, form, change):
        if not change and obj.created_by_id is None:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
        record(request.user, "account.restriction_admin_updated" if change else "account.restricted", obj.account,
               after={"kind": obj.kind, "reason": obj.reason,
                      "expires_at": obj.expires_at.isoformat() if obj.expires_at else None,
                      "lifted_at": obj.lifted_at.isoformat() if obj.lifted_at else None},
               metadata={"restriction_id": str(obj.pk), "via": "admin"}, request=request)


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    """Журнал неизменяем (DATA-09): только просмотр, без добавления, правки и удаления."""

    list_display = ["created_at", "action", "object_type", "object_id", "actor", "ip", "request_id"]
    list_filter = ["action", "object_type"]
    search_fields = ["object_id", "action", "actor__email", "request_id"]
    date_hierarchy = "created_at"
    readonly_fields = [f.name for f in AuditEvent._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
