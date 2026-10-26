"""Настройки ГДеволна 2.0. Все значения окружения читаются из переменных среды (см. docker-compose.yml)."""
import os
import sys
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def env(name, default=None):
    return os.environ.get(name, default)


def env_bool(name, default=False):
    return str(env(name, "1" if default else "0")).lower() in {"1", "true", "yes", "on"}


def env_list(name, default=""):
    return [v.strip() for v in env(name, default).split(",") if v.strip()]


TESTING = "pytest" in sys.modules or env_bool("TESTING")
APP_ENV = env("APP_ENV", "dev")  # dev | staging | prod
SECURE_ENV = APP_ENV in ("staging", "prod")  # HTTPS за nginx: secure-cookie, HSTS, редирект на https
DEBUG = env_bool("DJANGO_DEBUG", False)
_DEV_SECRET_KEY = "dev-insecure-secret-change-me"
SECRET_KEY = env("DJANGO_SECRET_KEY", _DEV_SECRET_KEY)
if SECURE_ENV and (DEBUG or SECRET_KEY in (_DEV_SECRET_KEY, "change-me-to-a-long-random-string") or len(SECRET_KEY) < 50):
    raise ImproperlyConfigured(
        f"APP_ENV={APP_ENV}: задайте DJANGO_SECRET_KEY (не короче 50 символов) и DJANGO_DEBUG=0.")
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,backend,nginx,testserver")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS", "http://localhost:8080")
SITE_URL = env("SITE_URL", "http://localhost:8080").rstrip("/")

INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "rest_framework",
    "drf_spectacular",
    "channels",
    "django_celery_beat",
    "apps.common",
    "apps.accounts",
    "apps.organizations",
    "apps.mediafiles",
    "apps.spots",
    "apps.learning",
    "apps.boards",
    "apps.inventory",
    "apps.commerce",
    "apps.messaging",
    "apps.trust",
    "apps.analytics",
    "apps.favorites",
    "apps.community",
    "apps.club",
    "apps.shop",
    "apps.search",
    "apps.demo",
]

MIDDLEWARE = [
    "apps.common.middleware.RequestIdMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.accounts.middleware.AdminTwoFactorMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
APPEND_SLASH = False  # API-пути без завершающего слэша
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": env("POSTGRES_HOST", "localhost"),
        "PORT": env("POSTGRES_PORT", "5432"),
        "NAME": env("POSTGRES_DB", "gdevolna"),
        "USER": env("POSTGRES_USER", "gdevolna"),
        "PASSWORD": env("POSTGRES_PASSWORD", "gdevolna"),
        "CONN_MAX_AGE": 0 if TESTING else 60,
        "CONN_HEALTH_CHECKS": not TESTING,
        # Отдельное имя тестовой БД позволяет запускать несколько прогонов pytest параллельно.
        "TEST": {"NAME": env("TEST_DB_NAME", "test_gdevolna")},
    }
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.Account"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
if TESTING:
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

LANGUAGE_CODE = "ru"
TIME_ZONE = "Europe/Moscow"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/django-static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

REDIS_URL = env("REDIS_URL", "redis://localhost:6379/0")
if TESTING:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
else:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": REDIS_URL}}

SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 60 * 60 * 24 * 30
CSRF_COOKIE_HTTPONLY = False  # SPA читает csrftoken и отправляет X-CSRFToken
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
if SECURE_ENV:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    # nginx/балансировщик передаёт X-Forwarded-Proto; health-check контейнера ходит по http внутри сети.
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
    SECURE_REDIRECT_EXEMPT = [r"^api/v1/health$"]
    SECURE_HSTS_SECONDS = int(env("SECURE_HSTS_SECONDS", str(60 * 60 * 24 * 365)))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", True)
    # Включение в preload-список браузеров — отдельное решение владельца домена (необратимо на месяцы).
    SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD", False)
    if not SECURE_HSTS_PRELOAD:
        SILENCED_SYSTEM_CHECKS = ["security.W021"]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["apps.common.authentication.CsrfSessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "apps.common.pagination.StandardPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "apps.common.exceptions.api_exception_handler",
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser", "rest_framework.parsers.MultiPartParser"],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.ScopedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": env("THROTTLE_ANON", "600/min"),
        "user": env("THROTTLE_USER", "1200/min"),
        "auth": env("THROTTLE_AUTH", "30/min"),
        "messages": env("THROTTLE_MESSAGES", "60/min"),
        "uploads": env("THROTTLE_UPLOADS", "120/min"),
        "reports": env("THROTTLE_REPORTS", "20/min"),
    },
    "DATETIME_FORMAT": "iso-8601",
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
}
if TESTING:
    REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] = []

SPECTACULAR_SETTINGS = {
    "TITLE": "ГДеволна API",
    "DESCRIPTION": "Единый API платформы ГДеволна 2.0 (/api/v1/).",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SCHEMA_PATH_PREFIX": r"/api/v1",
    # Одинаковые имена полей (status, kind, role…) с разными наборами значений — явные имена перечислений,
    # чтобы схема собиралась без предупреждений и имена не зависели от хешей (docs/openapi.yml).
    "ENUM_NAME_OVERRIDES": {
        "BookingStatusEnum": "apps.commerce.models.Booking.Status",
        "BookingKindEnum": "apps.commerce.models.Booking.Kind",
        "BookingActionEnum": ["confirm", "decline", "start", "complete", "no_show", "cancel"],
        "InquiryStatusEnum": "apps.commerce.models.Inquiry.Status",
        "InquiryKindEnum": "apps.commerce.models.Inquiry.Kind",
        "InquiryActionEnum": ["accept", "decline", "complete", "cancel"],
        "InquiryTargetTypeEnum": ["board_model", "board_variant", "inventory_item", "instructor_offer",
                                  "school_program", "lesson_session", "organization", "account"],
        "CommercePartyTypeEnum": ["account", "organization"],
        "MediaKindEnum": "apps.mediafiles.models.MediaAsset.Kind",
        "MediaPurposeEnum": "apps.mediafiles.models.MediaAsset.Purpose",
        "MediaStatusEnum": "apps.mediafiles.models.MediaAsset.Status",
        "MediaVisibilityEnum": "apps.mediafiles.models.MediaAsset.Visibility",
        "OrganizationKindEnum": "apps.organizations.models.Organization.Kind",
        "OrganizationStatusEnum": "apps.organizations.models.Organization.Status",
        "MembershipRoleEnum": "apps.organizations.models.Membership.Role",
        "MembershipStatusEnum": "apps.organizations.models.Membership.Status",
        "OrganizationInviteStatusEnum": "apps.organizations.models.OrganizationInvite.Status",
        "StaffRoleEnum": "apps.accounts.models.StaffRole.Role",
        "ConsentKindEnum": "apps.accounts.models.ConsentRecord.Kind",
        "RidingLevelEnum": "apps.accounts.models.UserProfile.Level",
        "BoardModelStatusEnum": "apps.boards.models.BoardModel.Status",
        "InventoryKindEnum": "apps.inventory.models.InventoryItem.Kind",
        "InventoryPurposeEnum": "apps.inventory.models.InventoryItem.Purpose",
        "InventoryManualStatusEnum": "apps.inventory.serializers.MANUAL_STATUS_CHOICES",
        "HandoverKindEnum": "apps.inventory.models.RentalHandover.Kind",
        "LessonSessionStatusEnum": "apps.learning.models.LessonSession.Status",
        "LessonSessionKindEnum": ["school", "private"],
        "InstructorCertificateStatusEnum": "apps.learning.models.InstructorCertificate.Status",
        "ConversationKindEnum": "apps.messaging.models.Conversation.Kind",
        "NotificationKindEnum": "apps.messaging.models.Notification.Kind",
        "ClubEventKindEnum": "apps.club.models.ClubEvent.Kind",
        "ClubEventStatusEnum": "apps.club.models.ClubEvent.Status",
        "EventRegistrationStatusEnum": "apps.club.models.EventRegistration.Status",
        "ProductStatusEnum": "apps.shop.models.Product.Status",
        "DiaryVisibilityEnum": "apps.community.models.SurfSession.Visibility",
        "FavoriteTargetTypeEnum": "apps.favorites.models.Favorite.Target",
        "ReviewTargetTypeEnum": "apps.trust.models.Review.Target",
        "RecommendationTypeEnum": ["spot", "instructor", "rental"],
    },
}

# Channels / WebSocket
if TESTING:
    CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
else:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [env("CHANNELS_REDIS_URL", "redis://localhost:6379/1")]},
        }
    }

# Celery
CELERY_BROKER_URL = env("CELERY_BROKER_URL", "amqp://guest:guest@localhost:5672//")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")
CELERY_TASK_ALWAYS_EAGER = TESTING
CELERY_TASK_EAGER_PROPAGATES = TESTING
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

# Объектное хранилище (MinIO / S3)
S3_ENDPOINT_URL = env("S3_ENDPOINT_URL", "http://localhost:9000")
S3_ACCESS_KEY = env("S3_ACCESS_KEY", "gdevolna")
S3_SECRET_KEY = env("S3_SECRET_KEY", "gdevolna-secret")
S3_BUCKET = env("S3_BUCKET", "gdevolna-media")
S3_REGION = env("S3_REGION", "us-east-1")
MEDIA_PUBLIC_PREFIX = "public/"
MEDIA_PRIVATE_PREFIX = "private/"
MEDIA_UPLOAD_URL_TTL = 15 * 60
MEDIA_PRIVATE_URL_TTL = 120
MEDIA_LIMITS = {
    "image": {"max_bytes": 15 * 1024 * 1024, "types": ["image/jpeg", "image/png", "image/webp"]},
    "video": {"max_bytes": 500 * 1024 * 1024, "types": ["video/mp4", "video/webm", "video/quicktime"]},
    "document": {"max_bytes": 20 * 1024 * 1024, "types": ["application/pdf", "image/jpeg", "image/png", "image/webp"]},
}
STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "endpoint_url": S3_ENDPOINT_URL,
            "access_key": S3_ACCESS_KEY,
            "secret_key": S3_SECRET_KEY,
            "bucket_name": S3_BUCKET,
            "region_name": S3_REGION,
            "addressing_style": "path",
            "signature_version": "s3v4",
            "default_acl": None,
            "querystring_auth": True,
            "file_overwrite": False,
        },
    },
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

# Почта (Mailpit в dev)
EMAIL_BACKEND = (
    "django.core.mail.backends.locmem.EmailBackend" if TESTING else "django.core.mail.backends.smtp.EmailBackend"
)
EMAIL_HOST = env("EMAIL_HOST", "localhost")
EMAIL_PORT = int(env("EMAIL_PORT", "1025"))
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", False)
EMAIL_USE_SSL = env_bool("EMAIL_USE_SSL", False)
EMAIL_TIMEOUT = int(env("EMAIL_TIMEOUT", "10"))
SERVER_EMAIL = env("SERVER_EMAIL", env("DEFAULT_FROM_EMAIL", "ГДеволна <noreply@gdevolna.local>"))
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "ГДеволна <noreply@gdevolna.local>")

# Бизнес-параметры (открытые решения DEC-08 и т.п. — значения по умолчанию)
BOOKING_REQUEST_TTL_HOURS = int(env("BOOKING_REQUEST_TTL_HOURS", "48"))
ACCOUNT_DELETION_GRACE_DAYS = int(env("ACCOUNT_DELETION_GRACE_DAYS", "14"))
INVITE_TTL_DAYS = int(env("INVITE_TTL_DAYS", "14"))
MODERATION_SLA_HOURS = int(env("MODERATION_SLA_HOURS", "48"))
FORECAST_PROVIDER = env("FORECAST_PROVIDER", "none")

# 2FA для модераторов и администраторов
OTP_ISSUER = "ГДеволна"
STAFF_2FA_REQUIRED = env_bool("STAFF_2FA_REQUIRED", True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"request_id": {"()": "apps.common.middleware.RequestIdLogFilter"}},
    "formatters": {
        "default": {"format": "%(asctime)s %(levelname)s %(name)s rid=%(request_id)s %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "default", "filters": ["request_id"]},
    },
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", "INFO")},
    "loggers": {"django.db.backends": {"level": "WARNING"}},
}
