"""Страница TOTP-подтверждения для Django Admin (/admin/2fa/). Middleware перенаправляет сюда staff-сессии без 2FA.

- 2FA включена → форма кода → отметка сессии → редирект на ?next.
- 2FA не включена → показывается секрет и otpauth-ссылка; первый верный код включает 2FA и подтверждает сессию.
"""
from django import forms
from django.contrib import admin
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect

from apps.accounts.services import two_factor
from apps.accounts.services.roles import is_session_2fa_verified
from apps.common.exceptions import DomainError

SETUP_SESSION_KEY = "admin_2fa_setup_secret"


class CodeForm(forms.Form):
    code = forms.CharField(label="Код из приложения", max_length=12,
                           widget=forms.TextInput(attrs={"autocomplete": "one-time-code", "inputmode": "numeric",
                                                         "autofocus": True}))


def _safe_next(request):
    target = request.POST.get("next") or request.GET.get("next") or reverse("admin:index")
    if not url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()},
                                           require_https=request.is_secure()):
        return reverse("admin:index")
    if not target.startswith("/admin/") or target.startswith("/admin/2fa"):
        return reverse("admin:index")
    return target


@never_cache
@csrf_protect
def admin_two_factor_view(request):
    next_url = _safe_next(request)
    user = request.user
    if not user.is_authenticated or not user.is_staff:
        login_url = reverse("admin:login")
        return HttpResponseRedirect(f"{login_url}?next={request.get_full_path()}")
    if is_session_2fa_verified(request):
        return HttpResponseRedirect(next_url)

    setup_secret = None
    if not user.totp_enabled:
        # Секрет живёт в сессии до первого верного кода, чтобы перезагрузка страницы не меняла QR.
        setup_secret = request.session.get(SETUP_SESSION_KEY)
        if not setup_secret or user.totp_secret != setup_secret:
            setup_secret = two_factor.setup(user)["secret"]
            request.session[SETUP_SESSION_KEY] = setup_secret

    form = CodeForm(request.POST or None)
    error = None
    if request.method == "POST" and form.is_valid():
        code = form.cleaned_data["code"]
        try:
            if user.totp_enabled:
                two_factor.verify_session(user, code, request)
            else:
                two_factor.enable(user, code, request)
                request.session.pop(SETUP_SESSION_KEY, None)
        except DomainError as exc:
            error = exc.message
        else:
            return HttpResponseRedirect(next_url)

    context = {
        **admin.site.each_context(request),
        "title": "Двухфакторная аутентификация",
        "form": form,
        "error": error,
        "next": next_url,
        "setup_secret": setup_secret,
        "otpauth_uri": two_factor.provisioning_uri(user, setup_secret) if setup_secret else None,
    }
    return render(request, "accounts/admin_2fa.html", context, status=400 if error else 200)
