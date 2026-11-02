from apps.designer_studio.template_agent_tools import execute_template_tool
from apps.designer_studio.template_workspace import TemplateWorkspace
from apps.venue_map_studio.map_knowledge_tools import execute_map_knowledge_tool


def test_get_map_knowledge_overview():
    result = execute_map_knowledge_tool("get_map_knowledge", {"topic": "overview"})
    assert result["ok"] is True
    assert "Interactive Venue Map" in result["content"] or "venue-map-root" in result["content"]


def test_get_map_reference_markers():
    result = execute_map_knowledge_tool("get_map_reference_code", {"part": "markers"})
    assert result["ok"] is True
    assert "map-marker" in result["content"]
    assert "data-location-id" in result["content"]
    assert "top:" in result["content"] and "left:" in result["content"]


def test_designer_tool_get_map_knowledge():
    ws = TemplateWorkspace(html_markup="<div></div>", css_stylesheet="", js_script="")
    result = execute_template_tool(ws, "get_map_knowledge", {"topic": "checklist"})
    assert result["ok"] is True
    assert "PRE-RETURN CHECKLIST" in result["content"]


def test_build_map_creation_context_includes_guide():
    from apps.venue_map_studio.map_knowledge_tools import build_map_creation_context

    block = build_map_creation_context(user_message="Build 7 zone map", floorplan_url="https://x/plan.png")
    assert "MAP SECTION CONTEXT" in block
    assert "https://x/plan.png" in block
    assert "Build 7 zone map" in block
