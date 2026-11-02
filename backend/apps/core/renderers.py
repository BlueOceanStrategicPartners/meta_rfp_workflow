"""DRF renderers for non-JSON responses."""
from rest_framework.renderers import BaseRenderer


class ServerSentEventsRenderer(BaseRenderer):
    """Allow Accept: text/event-stream on APIView stream endpoints (avoids 406 Not Acceptable)."""

    media_type = "text/event-stream"
    format = "event-stream"
    charset = "utf-8"

    def render(self, data, accepted_media_type=None, renderer_context=None):
        if data is None:
            return b""
        if isinstance(data, (bytes, bytearray)):
            return bytes(data)
        return str(data).encode(self.charset)
