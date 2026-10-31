from django.apps import AppConfig


class VoiceSynthesisConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.voice_synthesis"
    label = "voice_synthesis"

    def ready(self) -> None:
        import os
        import sys
        import threading

        if "runserver" not in sys.argv and "daphne" not in sys.argv:
            return
        if "runserver" in sys.argv and os.environ.get("RUN_MAIN") != "true":
            return

        from django.conf import settings

        backend = getattr(settings, "ASR_BACKEND", "omniasr").lower()
        if backend not in {"omniasr", "faster_whisper", "whisper", "fast_whisper"}:
            return

        def boot() -> None:
            if backend in {"faster_whisper", "whisper", "fast_whisper"}:
                from apps.voice_synthesis.faster_whisper_worker import ensure_worker_started

                ensure_worker_started()
            else:
                from apps.voice_synthesis.omniasr_worker import ensure_worker_started

                ensure_worker_started()

        threading.Thread(target=boot, daemon=True, name="local-asr-worker-boot").start()
