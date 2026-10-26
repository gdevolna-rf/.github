from django.urls import path

from apps.messaging.consumers import EventsConsumer

websocket_urlpatterns = [
    path("ws/events/", EventsConsumer.as_asgi()),
]
