from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer


def user_group(account_id):
    return f"user.{account_id}"


class EventsConsumer(AsyncJsonWebsocketConsumer):
    """Персональный канал событий пользователя: новые сообщения, уведомления, счётчики.

    Аутентификация — сессионная cookie (AuthMiddlewareStack). При подключении сразу отправляются
    актуальные счётчики, чтобы вкладка/устройство синхронизировались без отдельного REST-запроса.
    Клиент → сервер: ``{"type": "ping"}`` → ``pong``; ``{"type": "counters"}`` → свежие счётчики.
    """

    async def connect(self):
        user = self.scope.get("user")
        if not user or not user.is_authenticated or not user.is_active:
            await self.close(code=4401)
            return
        self.group = user_group(user.id)
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()
        await self._send_counters()

    async def disconnect(self, code):
        if hasattr(self, "group"):
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def receive_json(self, content, **kwargs):
        kind = content.get("type") if isinstance(content, dict) else None
        if kind == "ping":
            await self.send_json({"type": "pong"})
        elif kind == "counters":
            await self._send_counters()

    async def push_event(self, event):
        await self.send_json(event["payload"])

    async def _send_counters(self):
        counters = await _counters_for(self.scope["user"])
        await self.send_json({"type": "counters", "counters": counters})


@database_sync_to_async
def _counters_for(user):
    from apps.messaging.services.counters import get_counters

    return get_counters(user)
