from channels.generic.websocket import AsyncJsonWebsocketConsumer

ADMIN_TELEMETRY_GROUP = "admin_telemetry"
FORBIDDEN_CLOSE_CODE = 4403


class AdminTelemetryConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if not (user and user.is_authenticated and getattr(user, "role", None) == "ADMIN"):
            await self.close(code=FORBIDDEN_CLOSE_CODE)
            return
        self.group_name = ADMIN_TELEMETRY_GROUP
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if getattr(self, "group_name", None):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def telemetry_message(self, event):
        await self.send_json(event.get("payload", {}))
