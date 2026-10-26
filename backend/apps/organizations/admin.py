from django.contrib import admin

from apps.organizations.models import Membership, Organization, OrganizationInvite


class MembershipInline(admin.TabularInline):
    model = Membership
    fk_name = "organization"
    extra = 0
    raw_id_fields = ("account", "invited_by", "revoked_by")
    readonly_fields = ("joined_at", "revoked_at")


class InviteInline(admin.TabularInline):
    model = OrganizationInvite
    extra = 0
    fields = ("email", "role", "status", "invited_by", "expires_at", "responded_at")
    readonly_fields = ("invited_by", "expires_at", "responded_at")
    show_change_link = True


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "status", "verification_status", "owner", "region", "rating_avg",
                    "rating_count", "created_at", "is_demo")
    list_filter = ("kind", "status", "verification_status", "is_demo", "region")
    search_fields = ("name", "slug", "owner__email")
    prepopulated_fields = {"slug": ("name",)}
    raw_id_fields = ("owner", "logo", "cover", "region")
    filter_horizontal = ("spots", "gallery")
    readonly_fields = ("rating_avg", "rating_count", "published_at", "created_at", "updated_at")
    inlines = [MembershipInline, InviteInline]
    date_hierarchy = "created_at"

    def save_model(self, request, obj, form, change):
        from apps.trust.services.audit import record

        before = None
        if change:
            previous = Organization.objects.filter(pk=obj.pk).values("status", "verification_status", "owner_id").first()
            before = {k: str(v) for k, v in (previous or {}).items()}
        super().save_model(request, obj, form, change)
        record(request.user, "organization.changed_in_admin" if change else "organization.created_in_admin", obj,
               organization=obj, before=before,
               after={"status": obj.status, "verification_status": obj.verification_status,
                      "owner_id": str(obj.owner_id)}, request=request)


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("organization", "account", "role", "status", "joined_at", "revoked_at")
    list_filter = ("role", "status", "organization__kind")
    search_fields = ("organization__name", "account__email")
    raw_id_fields = ("organization", "account", "invited_by", "revoked_by")


@admin.register(OrganizationInvite)
class OrganizationInviteAdmin(admin.ModelAdmin):
    list_display = ("organization", "email", "role", "status", "invited_by", "expires_at", "responded_at")
    list_filter = ("status", "role")
    search_fields = ("organization__name", "email")
    raw_id_fields = ("organization", "account", "invited_by")
    readonly_fields = ("token", "created_at", "updated_at", "responded_at")
