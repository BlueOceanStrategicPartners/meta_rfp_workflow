from django.urls import path

from .views import BookRFPView, NegotiationOfferView, VoiceAssistantChatStreamView, VoiceAssistantChatView

urlpatterns = [
    path("voice-chat/", VoiceAssistantChatView.as_view()),
    path("voice-chat/stream/", VoiceAssistantChatStreamView.as_view()),
    path("offer/", NegotiationOfferView.as_view()),
    path("book/", BookRFPView.as_view()),
]
