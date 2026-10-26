from rest_framework.permissions import SAFE_METHODS, BasePermission


class ReadOnlyOrAuthenticated(BasePermission):
    """Публичное чтение каталогов (BR-01), изменения — только после входа."""

    def has_permission(self, request, view):
        return request.method in SAFE_METHODS or bool(request.user and request.user.is_authenticated)


class IsModerator(BasePermission):
    """Серверная роль модератора (BR-04, TRUST-06) + подтверждённая 2FA в текущей сессии."""

    message = "Доступно только модераторам с подтверждённой двухфакторной аутентификацией."

    def has_permission(self, request, view):
        from apps.accounts.services.roles import has_verified_staff_role

        return has_verified_staff_role(request, "moderator")


class IsPlatformAdmin(BasePermission):
    message = "Доступно только администраторам с подтверждённой двухфакторной аутентификацией."

    def has_permission(self, request, view):
        from apps.accounts.services.roles import has_verified_staff_role

        return has_verified_staff_role(request, "admin")
