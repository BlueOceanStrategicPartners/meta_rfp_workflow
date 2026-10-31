from django.urls import path

from .views import OmniASRStatusView, SeamlessM4TV2StatusView, SeamlessM4TV2SynthesizeView

urlpatterns = [
    path("seamless-m4t-v2/synthesize/", SeamlessM4TV2SynthesizeView.as_view()),
    path("seamless-m4t-v2/status/", SeamlessM4TV2StatusView.as_view()),
    path("asr-status/", OmniASRStatusView.as_view()),
]
