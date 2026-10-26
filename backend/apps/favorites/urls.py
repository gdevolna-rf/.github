from django.urls import path

from apps.favorites import views

urlpatterns = [
    path("favorites", views.FavoriteCreateView.as_view(), name="favorite-create"),
    path("favorites/<str:target_type>/<str:target_id>", views.FavoriteDeleteView.as_view(), name="favorite-delete"),
    path("me/favorites", views.MyFavoritesView.as_view(), name="my-favorites"),
    path("me/favorites/ids", views.MyFavoriteIdsView.as_view(), name="my-favorite-ids"),
]
