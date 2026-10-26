from django.urls import path

from apps.analytics import views

urlpatterns = [
    path("analytics/views", views.ViewsView.as_view(), name="analytics-views"),
    path("me/metrics", views.MetricsView.as_view(), name="my-metrics"),
]
