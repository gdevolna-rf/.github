from django.urls import path

from apps.accounts import admin_2fa

urlpatterns = [path("", admin_2fa.admin_two_factor_view, name="admin-2fa")]
