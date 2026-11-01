"""Shared Django settings."""
import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent

load_dotenv(BASE_DIR.parent / ".env")
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-insecure-change-in-production")
DEBUG = os.getenv("DJANGO_DEBUG", "true").lower() == "true"
ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "channels",
    "apps.accounts_rbac",
    "apps.inventory",
    "apps.rfp_debate",
    "apps.ui_card_validator",
    "apps.venue_map_studio",
    "apps.designer_studio",
    "apps.dynamic_pricing",
    "apps.negotiation_agent",
    "apps.voice_synthesis.apps.VoiceSynthesisConfig",
    "apps.guardrails",
    "apps.admin_command_center",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

AUTH_USER_MODEL = "accounts_rbac.CustomUser"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.BasicAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=14),
    "ROTATE_REFRESH_TOKENS": True,
    "UPDATE_LAST_LOGIN": True,
}

CORS_ALLOWED_ORIGINS = os.getenv(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173",
).split(",")
CORS_ALLOW_CREDENTIALS = True

CSRF_TRUSTED_ORIGINS = os.getenv(
    "CSRF_TRUSTED_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173",
).split(",")

REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)
CELERY_TASK_ALWAYS_EAGER = os.getenv("CELERY_TASK_ALWAYS_EAGER", "false").lower() == "true"

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [REDIS_URL]},
    },
}

# Meta Model API (Muse Spark 1.3 for all agent LLM calls). LLM_API_KEY is accepted as an alias.
META_MODEL_API_KEY = os.getenv("META_MODEL_API_KEY") or os.getenv("LLM_API_KEY", "")
META_MODEL_API_BASE = os.getenv("META_MODEL_API_BASE", "https://api.meta.ai/v1")
META_MODEL_SPARK = os.getenv("META_MODEL_SPARK", "muse-spark-1.3")
META_MODEL_WONDER = os.getenv("META_MODEL_WONDER", "muse-wonder")
USE_FIXTURE_DEBATE = os.getenv("USE_FIXTURE_DEBATE", "false").lower() == "true"

# SeamlessM4T v2 — compulsory voice assistant TTS (Meta Seamless Communication)
SEAMLESS_M4T_V2_MODEL = os.getenv(
    "SEAMLESS_M4T_V2_MODEL", "facebook/seamless-m4t-v2-large"
)
SEAMLESS_M4T_DEVICE = os.getenv("SEAMLESS_M4T_DEVICE", "cpu")
SEAMLESS_M4T_SRC_LANG = os.getenv("SEAMLESS_M4T_SRC_LANG", "eng")
SEAMLESS_M4T_TGT_LANG = os.getenv("SEAMLESS_M4T_TGT_LANG", "eng")
USE_SEAMLESS_FIXTURE = os.getenv("USE_SEAMLESS_FIXTURE", "false").lower() == "true"
# Natural neural speech when Seamless model is not loaded (Microsoft neural via edge-tts)
EDGE_NEURAL_TTS = os.getenv("EDGE_NEURAL_TTS", "true").lower() == "true"
EDGE_NEURAL_VOICE = os.getenv("EDGE_NEURAL_VOICE", "en-US-AriaNeural")

MUSE_VOICE_TRANSCRIBE_MODEL = os.getenv(
    "MUSE_VOICE_TRANSCRIBE_MODEL", "muse-voice-transcribe-1.0"
)
MUSE_ASR_MODE = os.getenv("MUSE_ASR_MODE", "ENDPOINTING")

# ASR: omniasr | faster_whisper | muse (cloud)
ASR_BACKEND = os.getenv("ASR_BACKEND", "faster_whisper").lower()
FASTER_WHISPER_MODEL = os.getenv("FASTER_WHISPER_MODEL", "small.en")
FASTER_WHISPER_DEVICE = os.getenv("FASTER_WHISPER_DEVICE", "cpu")
FASTER_WHISPER_COMPUTE_TYPE = os.getenv("FASTER_WHISPER_COMPUTE_TYPE", "int8")
FASTER_WHISPER_LANGUAGE = os.getenv("FASTER_WHISPER_LANGUAGE", "en")
OMNIASR_MODEL_HF = os.getenv("OMNIASR_MODEL_HF", "aadel4/omniASR-CTC-300M-v2")
OMNIASR_DEVICE = os.getenv("OMNIASR_DEVICE", "cpu")
# onnx = fast-omniasr + ONNX Runtime (no PyTorch; better alongside llama.cpp on GPU)
# torch = transformers + aadel4/omniASR-CTC-300M-v2
OMNIASR_RUNTIME = os.getenv("OMNIASR_RUNTIME", "onnx")
OMNIASR_ONNX_MODEL = os.getenv("OMNIASR_ONNX_MODEL", "EmreAkgul/omniASR-CTC-300M-v2-ONNX")
OMNIASR_ONNX_PRECISION = os.getenv("OMNIASR_ONNX_PRECISION", "fp16")
OMNIASR_ONNX_THREADS = int(os.getenv("OMNIASR_ONNX_THREADS", "4"))
OMNIASR_SPEECH_RMS = float(os.getenv("OMNIASR_SPEECH_RMS", "0.009"))
# Pause length before end-of-turn (local faster-whisper / OmniASR PCM endpointing).
OMNIASR_SILENCE_END_MS = int(os.getenv("OMNIASR_SILENCE_END_MS", "2400"))
OMNIASR_PARTIAL_MS = int(os.getenv("OMNIASR_PARTIAL_MS", "0"))
OMNIASR_MIN_UTTERANCE_MS = int(os.getenv("OMNIASR_MIN_UTTERANCE_MS", "400"))
OMNIASR_MAX_UTTERANCE_MS = int(os.getenv("OMNIASR_MAX_UTTERANCE_MS", "45000"))

MAX_DEBATE_ITERATIONS = int(os.getenv("MAX_DEBATE_ITERATIONS", "5"))

# Pricing guardrails (Admin-configurable defaults)
WALK_AWAY_FLOOR_MARGIN_PCT = float(os.getenv("WALK_AWAY_FLOOR_MARGIN_PCT", "0.12"))
MAX_AUTONOMOUS_DISCOUNT_PCT = float(os.getenv("MAX_AUTONOMOUS_DISCOUNT_PCT", "0.15"))

DB_ENGINE_MODE = os.getenv("DB_ENGINE_MODE", "sqlite")

if DB_ENGINE_MODE == "azuresql":
    DATABASES = {
        "default": {
            "ENGINE": "mssql",
            "NAME": os.environ["AZURE_SQL_DB_NAME"],
            "USER": os.environ["AZURE_SQL_USER"],
            "PASSWORD": os.environ["AZURE_SQL_PASSWORD"],
            "HOST": os.environ["AZURE_SQL_SERVER_HOST"],
            "PORT": "1433",
            "OPTIONS": {
                "driver": "ODBC Driver 18 for SQL Server",
                "extra_params": "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;",
            },
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
