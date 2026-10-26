from django import forms
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import BaseUserCreationForm, UserChangeForm

from apps.accounts.models import (
    Account,
    AccountDeletionRequest,
    ConsentRecord,
    DataExportRequest,
    HandleRedirect,
    Specialty,
    StaffRole,
    UserProfile,
    UserSpecialty,
)


class AccountCreationForm(BaseUserCreationForm):
    class Meta:
        model = Account
        fields = ("email",)

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if Account.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Аккаунт с таким email уже существует.")
        return email


class AccountChangeForm(UserChangeForm):
    class Meta:
        model = Account
        fields = "__all__"


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    raw_id_fields = ("avatar", "region")
    filter_horizontal = ("favorite_spots",)
    extra = 0


class UserSpecialtyInline(admin.TabularInline):
    model = UserSpecialty
    extra = 0
    readonly_fields = ("activated_at", "disabled_at")


class StaffRoleInline(admin.TabularInline):
    model = StaffRole
    fk_name = "account"
    extra = 0
    readonly_fields = ("granted_at", "granted_by")


@admin.register(Account)
class AccountAdmin(UserAdmin):
    form = AccountChangeForm
    add_form = AccountCreationForm
    ordering = ("-date_joined",)
    list_display = ("email", "display_name", "is_active", "email_verified_at", "totp_enabled", "is_staff",
                    "date_joined", "anonymized_at", "is_demo")
    list_filter = ("is_active", "is_staff", "is_superuser", "totp_enabled", "is_demo",
                   ("anonymized_at", admin.EmptyFieldListFilter), ("email_verified_at", admin.EmptyFieldListFilter))
    search_fields = ("email", "profile__handle", "profile__first_name", "profile__last_name")
    readonly_fields = ("id", "date_joined", "last_login", "anonymized_at", "deletion_requested_at", "totp_enabled")
    fieldsets = (
        (None, {"fields": ("id", "email", "password")}),
        ("Статус", {"fields": ("is_active", "email_verified_at", "totp_enabled", "deletion_requested_at",
                               "anonymized_at", "is_demo")}),
        ("Django Admin", {"fields": ("is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Даты", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("email", "password1", "password2")}),)
    filter_horizontal = ("groups", "user_permissions")
    inlines = [UserProfileInline, UserSpecialtyInline, StaffRoleInline]
    actions = ["reset_two_factor"]

    def get_inlines(self, request, obj):
        return self.inlines if obj is not None else []

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not change:  # аккаунт из админки — тот же инвариант: профиль + направление «сёрфер»
            from apps.accounts.services.handles import generate_handle
            from apps.accounts.services.specialties import grant_specialty

            UserProfile.objects.get_or_create(account=obj, defaults={"handle": generate_handle(email=obj.email)})
            grant_specialty(obj, Specialty.SURFER, primary=True)

    @admin.display(description="Имя")
    def display_name(self, obj):
        profile = getattr(obj, "profile", None)
        return profile.display_name if profile else "—"

    @admin.action(description="Сбросить 2FA (пользователь настроит заново)")
    def reset_two_factor(self, request, queryset):
        from apps.trust.services.audit import record

        for account in queryset:
            account.totp_enabled = False
            account.totp_secret = ""
            account.save(update_fields=["totp_enabled", "totp_secret"])
            record(request.user, "account.2fa_reset_by_admin", account, request=request)
        self.message_user(request, f"2FA сброшена: {queryset.count()}", messages.SUCCESS)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("handle", "display_name", "account", "region", "gg_surfer_enabled", "updated_at")
    list_filter = ("gg_surfer_enabled", "riding_level", "region")
    search_fields = ("handle", "first_name", "last_name", "account__email")
    raw_id_fields = ("account", "avatar", "region")
    filter_horizontal = ("favorite_spots",)


@admin.register(Specialty)
class SpecialtyAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "sort_order")
    ordering = ("sort_order",)


@admin.register(UserSpecialty)
class UserSpecialtyAdmin(admin.ModelAdmin):
    list_display = ("account", "specialty", "status", "is_primary", "activated_at", "disabled_at")
    list_filter = ("specialty", "status", "is_primary")
    search_fields = ("account__email", "account__profile__handle")
    raw_id_fields = ("account",)


@admin.register(StaffRole)
class StaffRoleAdmin(admin.ModelAdmin):
    list_display = ("account", "role", "granted_by", "granted_at", "revoked_at")
    list_filter = ("role", ("revoked_at", admin.EmptyFieldListFilter))
    search_fields = ("account__email",)
    raw_id_fields = ("account", "granted_by")
    readonly_fields = ("granted_at",)

    def save_model(self, request, obj, form, change):
        from apps.trust.services.audit import record

        if not change and obj.granted_by_id is None:
            obj.granted_by = request.user
        super().save_model(request, obj, form, change)
        record(request.user, "staff_role.changed_in_admin" if change else "staff_role.granted", obj,
               after={"account": str(obj.account_id), "role": obj.role,
                      "revoked_at": obj.revoked_at.isoformat() if obj.revoked_at else None}, request=request)


@admin.register(HandleRedirect)
class HandleRedirectAdmin(admin.ModelAdmin):
    list_display = ("old_handle", "account", "created_at")
    search_fields = ("old_handle", "account__email", "account__profile__handle")
    raw_id_fields = ("account",)


@admin.register(ConsentRecord)
class ConsentRecordAdmin(admin.ModelAdmin):
    """Журнал согласий неизменяем (TRUST-09)."""

    list_display = ("account", "kind", "granted", "ip", "created_at")
    list_filter = ("kind", "granted")
    search_fields = ("account__email",)
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DataExportRequest)
class DataExportRequestAdmin(admin.ModelAdmin):
    list_display = ("account", "status", "created_at", "completed_at")
    list_filter = ("status",)
    search_fields = ("account__email",)
    raw_id_fields = ("account", "file")
    readonly_fields = ("created_at", "updated_at", "completed_at")


@admin.register(AccountDeletionRequest)
class AccountDeletionRequestAdmin(admin.ModelAdmin):
    list_display = ("account", "status", "scheduled_for", "created_at", "completed_at")
    list_filter = ("status",)
    search_fields = ("account__email",)
    raw_id_fields = ("account",)
    readonly_fields = ("created_at", "updated_at", "completed_at")
    actions = ["process_now"]

    @admin.action(description="Анонимизировать сейчас (без ожидания отсрочки)")
    def process_now(self, request, queryset):
        from apps.accounts.services.deletion import anonymize_account

        count = 0
        for deletion in queryset.filter(status=AccountDeletionRequest.Status.REQUESTED).select_related("account"):
            anonymize_account(deletion.account, deletion)
            count += 1
        self.message_user(request, f"Анонимизировано: {count}", messages.SUCCESS)
