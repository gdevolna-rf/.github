from django.urls import path

from apps.search import views

urlpatterns = [
    path("search", views.SearchView.as_view(), name="search"),
    path("assistant/board-size", views.BoardSizeView.as_view(), name="assistant-board-size"),
    path("assistant/recommend", views.RecommendView.as_view(), name="assistant-recommend"),
]
