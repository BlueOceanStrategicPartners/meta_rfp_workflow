import pytest
from django.test import override_settings

from apps.designer_studio.design_agent import DesignerStudioAgent, resolve_designer_agent_mode
from apps.designer_studio.design_agent_tool_loop import DesignerToolLoopRunner
from apps.designer_studio.models import REQUIRED_PLACEHOLDERS
from apps.designer_studio.template_repair_hints import format_repair_brief, repair_search_hints


def _minimal_html(extra: str = "") -> str:
    tokens = " ".join(REQUIRED_PLACEHOLDERS)
    return f"<main>{extra} {tokens}</main>"


def test_repair_hints_for_cta_issue():
    hints = repair_search_hints(["Accept CTA hidden by display:none on .proposal-cta"])
    files = {h["file"] for h in hints}
    assert "css" in files


def test_format_repair_brief_lists_issues():
    text = format_repair_brief(original_message="fix nav", issues=["CTA not visible"])
    assert "CTA not visible" in text
    assert "search_template" in text.lower() or "Suggested searches" in text


@override_settings(DESIGNER_AGENT_MODE="full_document", DESIGNER_ALLOW_LEGACY_FULL_DOCUMENT=False)
def test_legacy_full_document_blocked_without_flag():
    assert resolve_designer_agent_mode() == "tool_loop"


@override_settings(DESIGNER_AGENT_MODE="full_document", DESIGNER_ALLOW_LEGACY_FULL_DOCUMENT=True)
def test_legacy_full_document_allowed_with_flag():
    assert resolve_designer_agent_mode() == "full_document"


@pytest.mark.django_db
@override_settings(USE_FIXTURE_DEBATE=True)
def test_run_repair_fixture_patches_css(designer_user):
    runner = DesignerToolLoopRunner()
    html = _minimal_html()
    css = ".proposal-cta{display:none}"
    out = runner.run_repair(
        original_message="ensure accept visible",
        issues=["Accept CTA hidden by display:none"],
        html_markup=html,
        css_stylesheet=css,
        js_script="",
    )
    assert out.get("repair_tool_pass") is True
    assert "display:none" not in out["css_stylesheet"] or "display:flex" in out["css_stylesheet"]


@pytest.mark.django_db
@override_settings(USE_FIXTURE_DEBATE=True, DESIGNER_SELF_CHECK_MAX_PASSES=2)
def test_self_check_uses_tool_repair(designer_user):
    agent = DesignerStudioAgent()
    html = _minimal_html()
    css = ".proposal-cta{display:none}"
    # Force validation failure then repair via tool loop in fixture mode
    result = agent.chat_turn(
        message="make sure accept button visible on desktop",
        history=[],
        html_markup=html,
        css_stylesheet=css,
        js_script="",
    )
    assert result.get("agent_mode") == "tool_loop"
    trace = result.get("tool_trace") or []
    assert any(t.get("tool") == "validate_template" for t in trace) or result.get("self_check")


@pytest.mark.django_db
@override_settings(USE_FIXTURE_DEBATE=True, DESIGNER_AGENT_MODE="tool_loop")
def test_tool_loop_mode_returns_patched_html(designer_user):
    agent = DesignerStudioAgent()
    html = _minimal_html('<a href="/rooms">Rooms</a>')
    result = agent.chat_turn(
        message="check route buttons urls use section focus not wrong external urls",
        history=[],
        html_markup=html,
        css_stylesheet=".x{}",
        js_script="",
    )
    assert result.get("agent_mode") == "tool_loop"
    assert result.get("tool_steps", 0) >= 1
    assert "#" in result["html_markup"] or "href=" in result["html_markup"]
    assert result["assistant_message"]


@pytest.mark.django_db
@override_settings(USE_FIXTURE_DEBATE=True, DESIGNER_TOOL_LOOP_MAX_TURNS=1)
def test_tool_loop_exhaustion_offers_continue(designer_user):
    agent = DesignerStudioAgent()
    result = agent.chat_turn(
        message="fix every nav href to section anchors across the whole proposal",
        history=[],
        html_markup=_minimal_html('<a href="/a">A</a>'),
        css_stylesheet="",
        js_script="",
    )
    assert result.get("tool_loop_exhausted") is True
    assert result.get("continuation_recommended") is True
    assert result.get("remaining_items")
    assert any("Continue" in o for o in (result.get("clarification_options") or []))
    assert result.get("progress_completed") is not None
    assert "progress card" in result["assistant_message"].lower()


@pytest.mark.django_db
@override_settings(USE_FIXTURE_DEBATE=True, DESIGNER_TOOL_LOOP_MAX_STEPS=24, DESIGNER_TOOL_LOOP_CONTINUATION_BONUS_STEPS=8)
def test_continuation_message_grants_bonus_steps(designer_user):
    agent = DesignerStudioAgent()
    result = agent.chat_turn(
        message="Continue — finish the remaining edits",
        history=[],
        html_markup=_minimal_html(),
        css_stylesheet="",
        js_script="",
    )
    assert result.get("agent_mode") == "tool_loop"
    assert result.get("assistant_message")


@pytest.mark.django_db
@override_settings(
    USE_FIXTURE_DEBATE=True,
    DESIGNER_AGENT_MODE="full_document",
    DESIGNER_ALLOW_LEGACY_FULL_DOCUMENT=True,
)
def test_full_document_mode_still_works(designer_user):
    agent = DesignerStudioAgent()
    result = agent.chat_turn(
        message="make a dark luxury hero",
        history=[],
        html_markup=_minimal_html(),
        css_stylesheet="",
        js_script="",
    )
    assert "html_markup" in result
    assert result["html_markup"]
    assert result.get("agent_mode") != "tool_loop" or "html_markup" in result
