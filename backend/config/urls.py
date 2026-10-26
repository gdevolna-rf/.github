from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.common.views import health

# Каждое доменное приложение публикует свои маршруты в apps/<app>/urls.py (без префикса /api/v1/).
API_APPS = [
    "accounts",
    "organizations",
    "mediafiles",
    "spots",
    "learning",
    "boards",
    "inventory",
    "commerce",
    "messaging",
    "trust",
    "analytics",
    "favorites",
    "community",
    "club",
    "shop",
    "search",
]

api_v1 = [
    path("health", health, name="health"),
    path("schema", SpectacularAPIView.as_view(), name="schema"),
    path("docs", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
] + [path("", include(f"apps.{name}.urls")) for name in API_APPS]

urlpatterns = [
    path("admin/2fa/", include("apps.accounts.admin_2fa_urls")),
    path("admin/", admin.site.urls),
    path("api/v1/", include(api_v1)),
]

admin.site.site_header = "ГДеволна — администрирование"
admin.site.site_title = "ГДеволна"
