import json

from channels.generic.websocket import AsyncJsonWebsocketConsumer


class RFPSessionConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.session_id = self.scope["url_route"]["kwargs"]["session_id"]
        self.group_name = f"rfp_{self.session_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        snapshot = await self._load_snapshot()
        if snapshot:
            await self.send_json({"type": "session_snapshot", "payload": snapshot})

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        message_type = content.get("type")
        if message_type == "card_mutation_submit":
            result = await self._validate_cards(content.get("payload", {}))
            if result.get("ok"):
                await self.send_json({"type": "pricing_quote", "payload": result["quote"]})
            else:
                await self.send_json(
                    {
                        "type": "validation_error",
                        "payload": result,
                    }
                )

    async def _validate_cards(self, payload):
        from asgiref.sync import sync_to_async
        from apps.ui_card_validator.services import validate_card_mutation

        return await sync_to_async(validate_card_mutation)(self.session_id, payload)

    async def _load_snapshot(self):
        from asgiref.sync import sync_to_async
        from apps.rfp_debate.models import RFPSubmission
        from apps.rfp_debate.voice_intro import build_voice_intro_for_rfp

        def load():
            try:
                rfp = RFPSubmission.objects.get(pk=self.session_id)
            except RFPSubmission.DoesNotExist:
                return None
            from apps.rfp_debate.card_normalize import normalize_cards_for_ui

            normalize_cards_for_ui(rfp)
            partial = bool(rfp.amber_conflict_fields_json)
            return {
                "cards": rfp.active_ui_cards_json,
                "status": rfp.status,
                "voice_intro": build_voice_intro_for_rfp(rfp, partial=partial),
            }

        return await sync_to_async(load)()

    async def rfp_message(self, event):
        await self.send_json(
            {"type": event["message_type"], "payload": event.get("payload", {})}
        )
