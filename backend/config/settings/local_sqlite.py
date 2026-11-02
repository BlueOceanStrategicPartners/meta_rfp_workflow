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

# SPA dev (Vite :5173 → Django :8000): session must not require HTTPS.
SESSION_COOKIE_SECURE = False
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = False
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14

if META_MODEL_DEBUG:  # noqa: F405
    LOGGING = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "console": {"format": "%(levelname)s %(name)s: %(message)s"},
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "console",
            },
        },
        "root": {"handlers": ["console"], "level": "INFO"},
        "loggers": {
            "apps.rfp_debate.meta_client": {
                "handlers": ["console"],
                "level": "DEBUG",
                "propagate": False,
            },
            "apps.designer_studio": {
                "handlers": ["console"],
                "level": "DEBUG",
                "propagate": False,
            },
            "django.server": {
                "handlers": ["console"],
                "level": "INFO",
                "propagate": False,
            },
        },
    }
