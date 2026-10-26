from django.conf import settings
from django.shortcuts import redirect

from apps.accounts.services.roles import is_session_2fa_verified

_EXEMPT = ("/admin/login/", "/admin/logout/", "/admin/2fa/", "/admin/jsi18n/")


class AdminTwoFactorMiddleware:
    """Django Admin доступен только после TOTP-подтверждения в текущей сессии (11, 34)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        if (
            settings.STAFF_2FA_REQUIRED
            and path.startswith("/admin/")
            and not path.startswith(_EXEMPT)
            and request.user.is_authenticated
            and request.user.is_staff
            and not is_session_2fa_verified(request)
        ):
            return redirect(f"/admin/2fa/?next={path}")
        return self.get_response(request)
