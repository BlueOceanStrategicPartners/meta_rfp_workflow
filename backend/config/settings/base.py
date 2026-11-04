"""Shared Django settings."""
import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv
from corsheaders.defaults import default_headers

BASE_DIR = Path(__file__).resolve().parent.parent.parent

load_dotenv(BASE_DIR.parent / ".env")
load_dotenv(BASE_DIR / ".env")


def _meta_model_id(env_key: str, default: str) -> str:
    """Normalize legacy Muse Wonder slug to the Model API id."""
    raw = (os.getenv(env_key, default) or default).strip()
    if raw == "muse-wonder":
        return "muse-wonder-1.0"
    return raw


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
CORS_ALLOW_HEADERS = (
    *default_headers,
    "cache-control",
)

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
# Client RFP assistant: Muse Spark (fast). Override model id or use contributor tier via env.
META_MODEL_CLIENT_ASSISTANT = os.getenv("META_MODEL_CLIENT_ASSISTANT", "muse-spark-1.3-contributor")
META_MODEL_CLIENT_ASSISTANT_REASONING_EFFORT = os.getenv(
    "META_MODEL_CLIENT_ASSISTANT_REASONING_EFFORT", "low"
)
# Muse scaffold/repair JSON can exceed 120s; designer tool loop needs a longer read timeout.
META_MODEL_HTTP_TIMEOUT = float(os.getenv("META_MODEL_HTTP_TIMEOUT", "300"))
# Log truncated Muse request/response bodies to the console (local debugging).
META_MODEL_DEBUG = os.getenv("META_MODEL_DEBUG", "false").lower() in ("1", "true", "yes")
META_MODEL_DEBUG_MAX_CHARS = int(os.getenv("META_MODEL_DEBUG_MAX_CHARS", "4000"))
# Automatic layout/validation repair passes after each design-agent turn (no user prompts).
DESIGNER_SELF_CHECK_MAX_PASSES = int(os.getenv("DESIGNER_SELF_CHECK_MAX_PASSES", "4"))
DESIGNER_MAX_HISTORY_TURNS = int(os.getenv("DESIGNER_MAX_HISTORY_TURNS", "12"))
DESIGNER_MAX_TURN_CHARS = int(os.getenv("DESIGNER_MAX_TURN_CHARS", "2000"))
DESIGNER_MAX_AUTOMATION_CHARS = int(os.getenv("DESIGNER_MAX_AUTOMATION_CHARS", "2800"))
DESIGNER_PREVIEW_AUTOMATION_MAX_DEPTH = int(os.getenv("DESIGNER_PREVIEW_AUTOMATION_MAX_DEPTH", "1"))
# tool_loop = scoped template tools + iterate until finish; full_document = legacy whole-file JSON regen
DESIGNER_AGENT_MODE = os.getenv("DESIGNER_AGENT_MODE", "tool_loop").strip().lower()
DESIGNER_WORK_PLAN_LLM_LABELS = os.getenv("DESIGNER_WORK_PLAN_LLM_LABELS", "false").lower() in (
    "1",
    "true",
    "yes",
)
# LangGraph checkpoints: sqlite (file under BASE_DIR) or memory (tests)
DESIGNER_LANGGRAPH_CHECKPOINT_BACKEND = os.getenv(
    "DESIGNER_LANGGRAPH_CHECKPOINT_BACKEND", "sqlite"
).strip().lower()
# Stable LangGraph thread per proposal template (checkpoint survives chat turns; wider in-loop condense window).
DESIGNER_LANGGRAPH_THREAD_PER_TEMPLATE = os.getenv(
    "DESIGNER_LANGGRAPH_THREAD_PER_TEMPLATE", "true"
).lower() in ("1", "true", "yes")
DESIGNER_TOOL_LOOP_CHECKPOINT_KEEP_RECENT_PAIRS = int(
    os.getenv("DESIGNER_TOOL_LOOP_CHECKPOINT_KEEP_RECENT_PAIRS", "14")
)
DESIGNER_TOOL_LOOP_MAX_TURNS = int(
    os.getenv("DESIGNER_TOOL_LOOP_MAX_TURNS", os.getenv("DESIGNER_TOOL_LOOP_MAX_STEPS", "1000"))
)
# Deprecated alias — counts model turns, not individual tool calls
DESIGNER_TOOL_LOOP_MAX_STEPS = DESIGNER_TOOL_LOOP_MAX_TURNS
DESIGNER_TOOL_LOOP_REPAIR_MAX_TURNS = int(
    os.getenv(
        "DESIGNER_TOOL_LOOP_REPAIR_MAX_TURNS",
        os.getenv("DESIGNER_TOOL_LOOP_REPAIR_MAX_STEPS", "1000"),
    )
)
DESIGNER_TOOL_LOOP_REPAIR_MAX_STEPS = DESIGNER_TOOL_LOOP_REPAIR_MAX_TURNS
DESIGNER_TOOL_LOOP_CONTINUATION_BONUS_TURNS = int(
    os.getenv("DESIGNER_TOOL_LOOP_CONTINUATION_BONUS_TURNS", os.getenv("DESIGNER_TOOL_LOOP_CONTINUATION_BONUS_STEPS", "8"))
)
DESIGNER_TOOL_LOOP_CONTINUATION_BONUS_STEPS = DESIGNER_TOOL_LOOP_CONTINUATION_BONUS_TURNS
DESIGNER_TOOL_LOOP_MAX_TOOLS_PER_TURN = int(os.getenv("DESIGNER_TOOL_LOOP_MAX_TOOLS_PER_TURN", "48"))
DESIGNER_TOOL_LOOP_STUCK_REPEAT_THRESHOLD = int(os.getenv("DESIGNER_TOOL_LOOP_STUCK_REPEAT_THRESHOLD", "3"))
DESIGNER_TOOL_LOOP_CONDENSE_AFTER_PAIRS = int(os.getenv("DESIGNER_TOOL_LOOP_CONDENSE_AFTER_PAIRS", "10"))
DESIGNER_TOOL_LOOP_KEEP_RECENT_PAIRS = int(os.getenv("DESIGNER_TOOL_LOOP_KEEP_RECENT_PAIRS", "5"))
DESIGNER_TOOL_LOOP_TOOL_RESULT_CHARS = int(os.getenv("DESIGNER_TOOL_LOOP_TOOL_RESULT_CHARS", "9000"))
DESIGNER_TOOL_LOOP_MAX_ISSUES_IN_PAYLOAD = int(os.getenv("DESIGNER_TOOL_LOOP_MAX_ISSUES_IN_PAYLOAD", "16"))
DESIGNER_TOOL_LOOP_MAX_HITS_IN_PAYLOAD = int(os.getenv("DESIGNER_TOOL_LOOP_MAX_HITS_IN_PAYLOAD", "12"))
DESIGNER_TOOL_LOOP_MAX_READ_CONTENT_CHARS = int(os.getenv("DESIGNER_TOOL_LOOP_MAX_READ_CONTENT_CHARS", "12000"))
DESIGNER_TOOL_LOOP_MAX_SECTION_READ_CHARS = int(os.getenv("DESIGNER_TOOL_LOOP_MAX_SECTION_READ_CHARS", "24000"))
DESIGNER_TOOL_LOOP_MAX_SYMBOLS_IN_PAYLOAD = int(os.getenv("DESIGNER_TOOL_LOOP_MAX_SYMBOLS_IN_PAYLOAD", "32"))
DESIGNER_TOOL_LOOP_MESSAGE_BUDGET_CHARS = int(os.getenv("DESIGNER_TOOL_LOOP_MESSAGE_BUDGET_CHARS", "72000"))
DESIGNER_TOOL_LOOP_AUTO_FINISH = os.getenv("DESIGNER_TOOL_LOOP_AUTO_FINISH", "1").strip().lower() in (
    "1",
    "true",
    "yes",
)
DESIGNER_TOOL_LOOP_HISTORY_TURN_CHARS = int(os.getenv("DESIGNER_TOOL_LOOP_HISTORY_TURN_CHARS", "2400"))
# Post-executor: deterministic checks only; no Muse repair to-do loop (legacy: set both to false/0).
DESIGNER_VALIDATOR_DETERMINISTIC_ONLY = os.getenv(
    "DESIGNER_VALIDATOR_DETERMINISTIC_ONLY", "1"
).strip().lower() in ("1", "true", "yes")
DESIGNER_VALIDATOR_REPAIR_ENABLED = os.getenv("DESIGNER_VALIDATOR_REPAIR_ENABLED", "0").strip().lower() in (
    "1",
    "true",
    "yes",
)
DESIGNER_EXEC_PLAN_MAX_SIMPLE_STEPS = int(os.getenv("DESIGNER_EXEC_PLAN_MAX_SIMPLE_STEPS", "3"))
DESIGNER_EXEC_PLAN_MAX_STANDARD_STEPS = int(os.getenv("DESIGNER_EXEC_PLAN_MAX_STANDARD_STEPS", "5"))
DESIGNER_READONLY_BATCHES_BEFORE_EDIT_STEER = int(
    os.getenv("DESIGNER_READONLY_BATCHES_BEFORE_EDIT_STEER", "2")
)
DESIGNER_ALLOW_LEGACY_FULL_DOCUMENT = (
    os.getenv("DESIGNER_ALLOW_LEGACY_FULL_DOCUMENT", "false").lower() == "true"
)
DESIGNER_VALIDATE_AFTER_MUTATE = os.getenv("DESIGNER_VALIDATE_AFTER_MUTATE", "1").strip().lower() in (
    "1",
    "true",
    "yes",
)
DESIGNER_FINALIZE_VALIDATION_ENABLED = os.getenv(
    "DESIGNER_FINALIZE_VALIDATION_ENABLED", "1"
).strip().lower() in ("1", "true", "yes")
DESIGNER_FINALIZE_REJECT_MAX = int(os.getenv("DESIGNER_FINALIZE_REJECT_MAX", "3"))
META_MODEL_WONDER = _meta_model_id("META_MODEL_WONDER", "muse-wonder-1.0")
# Designer Panel chat agent (tool loop, repair, validation LLM, rules, media captions).
_meta_designer = (os.getenv("META_MODEL_DESIGNER", "") or "").strip()
META_MODEL_DESIGNER = _meta_model_id("META_MODEL_DESIGNER", _meta_designer) if _meta_designer else META_MODEL_WONDER
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
