from django.urls import re_path

from .consumers import AdminTelemetryConsumer

admin_ws_urlpatterns = [
    re_path(r"ws/admin/telemetry/$", AdminTelemetryConsumer.as_asgi()),
]
