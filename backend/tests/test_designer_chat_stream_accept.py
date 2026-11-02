import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.designer_studio.views import DesignerChatStreamView


@pytest.mark.django_db
def test_designer_chat_stream_accepts_event_stream(client, designer_user):
    factory = APIRequestFactory()
    request = factory.post(
        "/api/designer/chat/stream/",
        {"message": "hello", "history": [], "html_markup": "", "css_stylesheet": "", "js_script": ""},
        format="json",
        HTTP_ACCEPT="text/event-stream",
    )
    force_authenticate(request, user=designer_user)
    response = DesignerChatStreamView.as_view()(request)
    assert response.status_code != 406
