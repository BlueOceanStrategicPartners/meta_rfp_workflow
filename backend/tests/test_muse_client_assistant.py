from django.test import override_settings

from apps.negotiation_agent.muse_client import (
    client_assistant_model_id,
    client_assistant_reasoning_effort,
)


@override_settings(
    META_MODEL_CLIENT_ASSISTANT="muse-spark-1.3-contributor",
    META_MODEL_CLIENT_ASSISTANT_REASONING_EFFORT="low",
    META_MODEL_SPARK="muse-spark-1.3",
)
def test_client_assistant_uses_dedicated_spark_settings():
    assert client_assistant_model_id() == "muse-spark-1.3-contributor"
    assert client_assistant_reasoning_effort() == "low"


@override_settings(
    META_MODEL_CLIENT_ASSISTANT="",
    META_MODEL_CLIENT_ASSISTANT_REASONING_EFFORT="none",
    META_MODEL_SPARK="muse-spark-1.3",
)
def test_client_assistant_falls_back_to_spark_without_reasoning():
    assert client_assistant_model_id() == "muse-spark-1.3"
    assert client_assistant_reasoning_effort() is None
