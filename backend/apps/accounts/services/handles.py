"""Публичный handle: латинский slug 3–40, уникален, старые значения ведут на аккаунт через HandleRedirect (5.1)."""
import re
import uuid

from django.db import IntegrityError, transaction

from apps.accounts.models import HandleRedirect, UserProfile
from apps.common.exceptions import DomainError
from apps.common.text import slugify_ru

HANDLE_MIN, HANDLE_MAX = 3, 40
HANDLE_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")

RESERVED_HANDLES = frozenset({
    "about", "account", "accounts", "admin", "administrator", "api", "app", "assistant", "auth", "blog", "boards",
    "club", "contact", "contacts", "dashboard", "deleted", "docs", "edit", "events", "favorites", "gdevolna", "gg",
    "help", "home", "inbox", "instructor", "instructors", "invites", "login", "logout", "me", "media", "messages",
    "moderation", "moderator", "new", "news", "notifications", "null", "orgs", "organizations", "privacy",
    "profile", "profiles", "register", "rentals", "reset-password", "root", "schools", "search", "sessions",
    "settings", "shapers", "shop", "signup", "spots", "staff", "static", "support", "surfers", "system", "terms",
    "undefined", "user", "users", "verify-email", "ws", "www",
})


def normalize(handle):
    return (handle or "").strip().lower()


def handle_error(handle):
    """Текст ошибки для недопустимого handle или None."""
    if not (HANDLE_MIN <= len(handle) <= HANDLE_MAX):
        return f"Длина адреса профиля — от {HANDLE_MIN} до {HANDLE_MAX} символов."
    if not HANDLE_RE.match(handle) or "--" in handle:
        return "Только латинские буквы, цифры и дефис (не в начале и не в конце)."
    if handle in RESERVED_HANDLES or handle.startswith("deleted-"):
        return "Этот адрес зарезервирован."
    return None


def is_taken(handle, account=None):
    profiles = UserProfile.objects.filter(handle=handle)
    redirects = HandleRedirect.objects.filter(old_handle=handle)
    if account is not None:
        profiles = profiles.exclude(account=account)
        redirects = redirects.exclude(account=account)
    return profiles.exists() or redirects.exists()


def generate_handle(first_name="", last_name="", email=""):
    """Уникальный handle из имени (slugify_ru), иначе из email; base, base-2, base-3…"""
    source = f"{first_name} {last_name}".strip() or (email.split("@")[0] if email else "")
    base = re.sub(r"-{2,}", "-", slugify_ru(source, max_length=HANDLE_MAX - 4)).strip("-") if source else ""
    if len(base) < HANDLE_MIN:
        base = f"{base}-surfer" if base else "surfer"
    if base in RESERVED_HANDLES or base.startswith("deleted"):
        base = f"{base}-surfer"
    base = base[:HANDLE_MAX - 4].strip("-")
    candidate, n = base, 2
    while is_taken(candidate) or handle_error(candidate):
        candidate, n = f"{base}-{n}", n + 1
        if n > 200:
            candidate = f"{base[:20].strip('-')}-{uuid.uuid4().hex[:8]}"
            break
    return candidate


def validate_new_handle(handle, account):
    handle = normalize(handle)
    error = handle_error(handle)
    if error:
        raise DomainError("handle_invalid", error, fields={"handle": [error]})
    if is_taken(handle, account):
        raise DomainError("handle_taken", "Этот адрес профиля уже занят.", fields={"handle": ["Адрес уже занят."]})
    return handle


def change_handle(profile, new_handle):
    """Меняет handle; старый сохраняется как редирект. Возврат собственного старого handle удаляет редирект."""
    new_handle = validate_new_handle(new_handle, profile.account)
    old = profile.handle
    if new_handle == old:
        return profile
    try:
        with transaction.atomic():
            HandleRedirect.objects.filter(old_handle=new_handle, account=profile.account).delete()
            profile.handle = new_handle
            profile.save(update_fields=["handle", "updated_at"])
            HandleRedirect.objects.update_or_create(old_handle=old, defaults={"account": profile.account})
    except IntegrityError as exc:
        raise DomainError("handle_taken", "Этот адрес профиля уже занят.",
                          fields={"handle": ["Адрес уже занят."]}) from exc
    return profile
