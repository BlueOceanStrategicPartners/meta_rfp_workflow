"""DRF renderers for negotiation streaming endpoints."""
from rest_framework.renderers import BaseRenderer


class ServerSentEventsRenderer(BaseRenderer):
    """Allow Accept: text/event-stream on SSE chat stream (avoids 406)."""

    media_type = "text/event-stream"
    format = "event-stream"
    charset = "utf-8"
    render_style = "binary"

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return data
