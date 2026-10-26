from django.urls import path

from apps.mediafiles import views

urlpatterns = [
    path("media/uploads", views.UploadCreateView.as_view(), name="media-upload"),
    path("media/<uuid:pk>", views.MediaDetailView.as_view(), name="media-detail"),
    path("media/<uuid:pk>/complete", views.UploadCompleteView.as_view(), name="media-complete"),
    path("media/<uuid:pk>/url", views.MediaUrlView.as_view(), name="media-url"),
]
