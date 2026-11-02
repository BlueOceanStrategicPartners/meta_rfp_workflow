from apps.designer_studio.designer_chat_service import _assistant_action_state, _normalize_designer_chat_result


def test_normalize_clears_partial_when_todos_complete():
    result = {
        "assistant_message": "Updated the proposal template with targeted edits.",
        "partial_completion": True,
        "continuation_recommended": True,
        "model_api_error": True,
        "tool_steps": 3,
        "clarification_options": ["Retry the request", "Continue — finish the remaining edits"],
        "agent_todos": [
            {"id": "exec_1", "status": "done"},
            {"id": "finalize", "status": "done"},
        ],
    }
    normalized = _normalize_designer_chat_result(result)
    assert normalized.get("partial_completion") is False
    assert normalized.get("model_api_error") is None
    assert _assistant_action_state(normalized) == {}


def test_assistant_action_state_partial_completion():
    result = {
        "partial_completion": True,
        "continuation_recommended": True,
        "remaining_items": ["Fix nav links"],
        "progress_completed": [{"id": "1", "label": "Search template", "ok": True}],
        "clarification_options": ["Continue — finish the remaining edits"],
        "agent_todos": [{"id": "edit", "label": "Apply edits", "status": "active"}],
    }
    extra = _assistant_action_state(result)
    assert "action_state" in extra
    st = extra["action_state"]
    assert st["partial_completion"] is True
    assert st["remaining_items"] == ["Fix nav links"]
    assert st["clarification_options"]


def test_assistant_action_state_clarifications_only():
    extra = _assistant_action_state({"clarification_options": ["Option A"]})
    assert extra["action_state"]["clarification_options"] == ["Option A"]
