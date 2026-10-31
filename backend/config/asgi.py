import os

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local_sqlite")

django_asgi_app = get_asgi_application()

from apps.rfp_debate.routing import websocket_urlpatterns as rfp_ws  # noqa: E402
from apps.admin_command_center.routing import admin_ws_urlpatterns  # noqa: E402
from apps.voice_synthesis.routing import websocket_urlpatterns as voice_ws  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AuthMiddlewareStack(
            URLRouter(rfp_ws + admin_ws_urlpatterns + voice_ws)
        ),
    }
)
