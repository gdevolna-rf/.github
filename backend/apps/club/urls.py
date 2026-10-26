from django.urls import path

from apps.club import views

urlpatterns = [
    path("club", views.ClubOverviewView.as_view(), name="club-overview"),
    path("club/events", views.ClubEventListView.as_view(), name="club-event-list"),
    path("club/events/<str:pk>/registration", views.ClubEventRegistrationView.as_view(), name="club-event-registration"),
    path("club/events/<str:slug>", views.ClubEventDetailView.as_view(), name="club-event-detail"),
    path("club/manage/events", views.ManageEventListView.as_view(), name="club-manage-events"),
    path("club/manage/events/<str:pk>", views.ManageEventDetailView.as_view(), name="club-manage-event"),
    path("club/manage/events/<str:pk>/registrations", views.ManageEventRegistrationsView.as_view(),
         name="club-manage-event-registrations"),
    path("club/manage/announcements", views.ManageAnnouncementListView.as_view(), name="club-manage-announcements"),
    path("club/manage/announcements/<str:pk>", views.ManageAnnouncementDetailView.as_view(),
         name="club-manage-announcement"),
]
