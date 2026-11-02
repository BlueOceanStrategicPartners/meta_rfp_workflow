from apps.designer_studio.design_agent import DesignerStudioAgent


def _minimal_result(**overrides):
    base = {
        "assistant_message": "Updated layout.",
        "html_markup": "<div>{{event_dates}}</div>",
        "css_stylesheet": ".x{}",
        "js_script": "",
        "clarification_options": [],
        "model_id": "test",
    }
    base.update(overrides)
    return base


def test_self_check_loops_until_issues_cleared():
    agent = DesignerStudioAgent()
    gather_calls = {"n": 0}

    def gather(message, history, result):
        gather_calls["n"] += 1
        if gather_calls["n"] < 3:
            return ["synthetic validation issue"]
        return []

    agent._gather_validation_issues = gather  # type: ignore[method-assign]
    agent._repair_turn = lambda message, history, issues, draft: {  # type: ignore[method-assign]
        **draft,
        "assistant_message": draft.get("assistant_message", ""),
        "clarification_options": [],
    }

    out = agent._finalize_with_self_check(
        message="fix map",
        history=[],
        result=_minimal_result(),
    )
    assert out["self_check"]["valid"] is True
    assert out["self_check"]["repair_passes"] == 2
    assert "validation_warnings" not in out


def test_self_check_never_asks_user_to_validate():
    agent = DesignerStudioAgent()
    agent._gather_validation_issues = lambda *args: ["persistent issue"]  # type: ignore[method-assign]
    agent._repair_turn = lambda message, history, issues, draft: {  # type: ignore[method-assign]
        **draft,
        "assistant_message": "Applied fixes.",
        "clarification_options": [],
    }

    out = agent._finalize_with_self_check(
        message="fix layout",
        history=[],
        result=_minimal_result(),
    )
    assert out["self_check"]["valid"] is False
    assert out["self_check"]["repair_passes"] == 4
    assert "Validate" not in out["assistant_message"]
    assert "ask me to fix" not in out["assistant_message"].lower()
