from apps.designer_studio.models import ALL_BINDING_PLACEHOLDERS
from apps.designer_studio.template_agent_tools import execute_template_tool
from apps.designer_studio.template_workspace import TemplateWorkspace


def _minimal_html(extra: str = "") -> str:
    tokens = " ".join(ALL_BINDING_PLACEHOLDERS)
    return f"<main>{extra} {tokens}</main>"


def test_validate_template_returns_pool_hints_when_invalid():
    ws = TemplateWorkspace(
        html_markup=_minimal_html(),
        css_stylesheet=".proposal-cta{display:none}",
        js_script="",
    )
    result = execute_template_tool(ws, "validate_template", {"scope": "systematic"})
    assert result["ok"] is True
    assert result["valid"] is False
    assert result["issues"]
    assert result.get("pool_repair_hints")
    assert "agent_workflow" in result
    assert "replace_lines" in result["agent_workflow"]
