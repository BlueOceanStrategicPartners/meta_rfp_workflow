from django.test import override_settings

from apps.designer_studio.muse_client import designer_agent_model_id


@override_settings(
    META_MODEL_DESIGNER="muse-wonder-custom",
    META_MODEL_WONDER="muse-wonder",
)
def test_designer_agent_model_id_prefers_designer_env():
    assert designer_agent_model_id() == "muse-wonder-custom"


@override_settings(
    META_MODEL_DESIGNER="",
    META_MODEL_WONDER="muse-wonder-1.0",
)
def test_designer_agent_model_id_defaults_to_wonder():
    assert designer_agent_model_id() == "muse-wonder-1.0"


@override_settings(
    META_MODEL_DESIGNER="muse-wonder",
    META_MODEL_WONDER="muse-wonder-1.0",
)
def test_designer_agent_model_id_normalizes_legacy_wonder_slug():
    assert designer_agent_model_id() == "muse-wonder-1.0"
