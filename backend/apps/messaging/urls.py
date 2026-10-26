from django.urls import path

from apps.messaging import views

urlpatterns = [
    path("conversations", views.ConversationListView.as_view(), name="conversations"),
    path("conversations/<uuid:pk>", views.ConversationDetailView.as_view(), name="conversation-detail"),
    path("conversations/<uuid:pk>/messages", views.MessageListCreateView.as_view(), name="conversation-messages"),
    path("conversations/<uuid:pk>/read", views.ConversationReadView.as_view(), name="conversation-read"),
    path("direct-conversations", views.DirectConversationView.as_view(), name="direct-conversations"),
    path("me/notifications", views.NotificationListView.as_view(), name="my-notifications"),
    path("me/notifications/read-all", views.NotificationReadAllView.as_view(), name="my-notifications-read-all"),
    path("me/notifications/<uuid:pk>/read", views.NotificationReadView.as_view(), name="my-notification-read"),
    path("me/notification-preferences", views.NotificationPreferencesView.as_view(), name="my-notification-prefs"),
    path("me/blocks", views.MyBlocksView.as_view(), name="my-blocks"),
    path("blocks", views.BlockCreateView.as_view(), name="blocks"),
    path("blocks/<uuid:account_id>", views.BlockDeleteView.as_view(), name="block-delete"),
    path("me/counters", views.CountersView.as_view(), name="my-counters"),
]
