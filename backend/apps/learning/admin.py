from django.contrib import admin

from apps.learning.models import (
    InstructorCertificate,
    InstructorMedia,
    InstructorOffer,
    InstructorProfile,
    LessonSession,
    SchoolProgram,
    StudentNote,
    WaitlistEntry,
)


class InstructorMediaInline(admin.TabularInline):
    model = InstructorMedia
    extra = 0
    raw_id_fields = ["media"]


class InstructorCertificateInline(admin.TabularInline):
    """Решение по сертификату принимается только через очередь модерации (BR-07): статус здесь только для чтения."""

    model = InstructorCertificate
    extra = 0
    fields = ["title", "issuer", "status", "valid_until", "allow_public_scan", "decided_at"]
    readonly_fields = ["status", "decided_at"]
    show_change_link = True


class InstructorOfferInline(admin.TabularInline):
    model = InstructorOffer
    extra = 0
    fields = ["title", "format", "level", "duration_min", "price", "currency", "capacity", "is_active"]
    show_change_link = True


@admin.register(InstructorProfile)
class InstructorProfileAdmin(admin.ModelAdmin):
    list_display = ["account", "status", "headline", "price_from", "rating_avg", "rating_count", "published_at", "is_demo"]
    list_filter = ["status", "is_demo", "regions"]
    search_fields = ["account__email", "account__profile__handle", "account__profile__first_name",
                     "account__profile__last_name", "headline"]
    raw_id_fields = ["account"]
    filter_horizontal = ["regions"]
    autocomplete_fields = []
    readonly_fields = ["rating_avg", "rating_count", "published_at", "created_at", "updated_at"]
    inlines = [InstructorOfferInline, InstructorCertificateInline, InstructorMediaInline]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("account")


@admin.register(InstructorCertificate)
class InstructorCertificateAdmin(admin.ModelAdmin):
    list_display = ["title", "instructor", "status", "issuer", "valid_until", "allow_public_scan", "created_at"]
    list_filter = ["status", "allow_public_scan"]
    search_fields = ["title", "issuer", "instructor__account__email"]
    raw_id_fields = ["instructor", "document", "moderator"]
    readonly_fields = ["status", "moderator", "moderator_comment", "decided_at", "created_at", "updated_at"]


@admin.register(InstructorOffer)
class InstructorOfferAdmin(admin.ModelAdmin):
    list_display = ["title", "instructor", "format", "level", "price", "currency", "capacity", "is_active"]
    list_filter = ["format", "is_active"]
    search_fields = ["title", "instructor__account__email"]
    raw_id_fields = ["instructor", "spot"]


@admin.register(SchoolProgram)
class SchoolProgramAdmin(admin.ModelAdmin):
    list_display = ["title", "organization", "level", "age_category", "format", "price", "max_group_size", "is_active"]
    list_filter = ["format", "age_category", "is_active"]
    search_fields = ["title", "organization__name"]
    raw_id_fields = ["organization"]


@admin.register(LessonSession)
class LessonSessionAdmin(admin.ModelAdmin):
    list_display = ["title", "starts_at", "ends_at", "status", "organization", "instructor", "capacity", "price"]
    list_filter = ["status", "allow_overlap"]
    search_fields = ["title", "organization__name", "instructor__email"]
    date_hierarchy = "starts_at"
    raw_id_fields = ["organization", "program", "offer", "instructor", "spot", "rescheduled_from", "created_by"]
    readonly_fields = ["completed_at", "cancelled_at", "created_at", "updated_at"]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("organization", "instructor")


@admin.register(WaitlistEntry)
class WaitlistEntryAdmin(admin.ModelAdmin):
    list_display = ["session", "account", "status", "created_at"]
    list_filter = ["status"]
    raw_id_fields = ["session", "account"]


@admin.register(StudentNote)
class StudentNoteAdmin(admin.ModelAdmin):
    list_display = ["student", "author", "organization", "level", "visible_to_student", "created_at"]
    list_filter = ["visible_to_student"]
    search_fields = ["student__email", "author__email", "comment"]
    raw_id_fields = ["student", "author", "organization", "session"]
