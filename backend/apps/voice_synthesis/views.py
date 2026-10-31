from rest_framework.response import Response
from rest_framework.views import APIView

from .seamless_m4t_v2 import synthesize_speech


class SeamlessM4TV2SynthesizeView(APIView):
    """Voice assistant TTS — Meta SeamlessM4T v2 (compulsory stack component)."""

    permission_classes = []
    authentication_classes = []

    def post(self, request):
        text = request.data.get("text", "")
        src_lang = request.data.get("src_lang")
        tgt_lang = request.data.get("tgt_lang")
        audio = synthesize_speech(text, src_lang=src_lang, tgt_lang=tgt_lang)
        from django.http import HttpResponse

        from django.conf import settings

        response = HttpResponse(audio.data, content_type=audio.content_type)
        response["Content-Disposition"] = 'inline; filename="seamless_m4t_v2.wav"'
        response["X-Voice-Engine"] = "SeamlessM4T-v2"
        if audio.browser_fallback:
            response["X-Voice-Fixture"] = "1"
        elif settings.USE_SEAMLESS_FIXTURE:
            response["X-Voice-Neural-Dev"] = "1"
        return response


class SeamlessM4TV2StatusView(APIView):
    permission_classes = []
    authentication_classes = []

    def get(self, request):
        from django.conf import settings

        return Response(
            {
                "engine": "SeamlessM4T-v2",
                "model": settings.SEAMLESS_M4T_V2_MODEL,
                "fixture_mode": settings.USE_SEAMLESS_FIXTURE,
                "required": True,
            }
        )


class OmniASRStatusView(APIView):
    """HTTP readiness for local ASR worker — open WebSocket only after ready=true."""

    permission_classes = []
    authentication_classes = []

    def get(self, request):
        from django.conf import settings

        backend = getattr(settings, "ASR_BACKEND", "omniasr").lower()

        if backend == "muse":
            return Response({"backend": "muse", "ready": True, "loading": False})

        if backend in {"faster_whisper", "whisper", "fast_whisper"}:
            from .faster_whisper_worker import ensure_worker_started, get_asr_worker

            ensure_worker_started()
            payload = get_asr_worker().status()
            payload["backend"] = "faster_whisper"
            payload["runtime"] = "ctranslate2"
            payload["model"] = getattr(settings, "FASTER_WHISPER_MODEL", "small.en")
            return Response(payload)

        if backend != "omniasr":
            return Response({"backend": backend, "ready": True, "loading": False})

        from .omniasr_worker import ensure_worker_started, get_asr_worker

        ensure_worker_started()
        payload = get_asr_worker().status()
        payload["backend"] = "omniasr"
        payload["runtime"] = getattr(settings, "OMNIASR_RUNTIME", "onnx")
        payload["model"] = getattr(
            settings, "OMNIASR_ONNX_MODEL", "EmreAkgul/omniASR-CTC-300M-v2-ONNX"
        )
        return Response(payload)
