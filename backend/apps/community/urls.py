from django.urls import path

from apps.community import views

urlpatterns = [
    path("surfers", views.SurferListView.as_view(), name="surfer-list"),
    path("surfers/<str:handle>", views.SurferDetailView.as_view(), name="surfer-detail"),
    path("surfers/<str:handle>/diary", views.SurferDiaryView.as_view(), name="surfer-diary"),
    path("me/diary", views.MyDiaryView.as_view(), name="my-diary"),
    path("me/diary/stats", views.MyDiaryStatsView.as_view(), name="my-diary-stats"),
    path("me/diary/<str:pk>", views.MyDiaryEntryView.as_view(), name="my-diary-entry"),
]
