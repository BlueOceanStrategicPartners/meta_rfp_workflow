"""Designer Studio Muse model selection (isolated from client Spark defaults)."""
from django.conf import settings


def designer_agent_model_id() -> str:
    explicit = (getattr(settings, "META_MODEL_DESIGNER", "") or "").strip()
    if explicit:
        model_id = explicit
    else:
        model_id = settings.META_MODEL_WONDER
    if model_id == "muse-wonder":
        return "muse-wonder-1.0"
    return model_id
