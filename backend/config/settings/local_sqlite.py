from .base import *  # noqa: F403

# Local dev: use `manage.py runserver` (Daphne + Django StatReloader). Do not pass --noreload.
# Edit `.env` requires a manual server restart (not watched by autoreload).

DB_ENGINE_MODE = "sqlite"
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",  # noqa: F405
    }
}

CHANNEL_LAYERS = {
    "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"},
}

CELERY_TASK_ALWAYS_EAGER = os.getenv("CELERY_TASK_ALWAYS_EAGER", "true").lower() == "true"  # noqa: F405
USE_SEAMLESS_FIXTURE = os.getenv("USE_SEAMLESS_FIXTURE", "true").lower() == "true"  # noqa: F405
