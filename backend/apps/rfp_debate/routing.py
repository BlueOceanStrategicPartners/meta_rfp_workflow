from django.urls import re_path

from .consumers import RFPSessionConsumer

websocket_urlpatterns = [
    re_path(r"ws/rfp/(?P<session_id>[0-9a-f-]+)/$", RFPSessionConsumer.as_asgi()),
]
