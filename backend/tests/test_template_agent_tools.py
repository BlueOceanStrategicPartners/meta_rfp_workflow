import pytest

from apps.designer_studio.template_agent_tools import execute_template_tool
from apps.designer_studio.template_workspace import TemplateWorkspace


@pytest.fixture
def sample_workspace():
    return TemplateWorkspace(
        html_markup=(
            "<header><a href='/rooms'>Rooms</a></header>"
            "<main>{{client_name}} {{event_dates}} {{verified_room_blocks}} "
            "{{selected_map_svg}} {{meeting_space_specs}} {{xgboost_quote_breakdown}} "
            "{{negotiated_concessions}} {{cta_accept_button}}</main>"
        ),
        css_stylesheet=".hero { color: blue; }",
        js_script="document.querySelector('.hero');",
    )


def test_overview_lists_placeholders(sample_workspace):
    result = execute_template_tool(sample_workspace, "get_template_overview", {})
    assert result["ok"] is True
    assert result["html_lines"] >= 1
    assert "{{client_name}}" in result["placeholders_present"]


def test_read_lines_numbered(sample_workspace):
    result = execute_template_tool(
        sample_workspace,
        "read_template_lines",
        {"file": "html", "start_line": 1, "end_line": 1},
    )
    assert result["ok"] is True
    assert "    1|" in result["content"]


def test_search_finds_href(sample_workspace):
    result = execute_template_tool(
        sample_workspace,
        "search_template",
        {"file": "html", "query": "href="},
    )
    assert result["ok"] is True
    assert len(result["hits"]) == 1


def test_replace_exact_single(sample_workspace):
    result = execute_template_tool(
        sample_workspace,
        "replace_exact",
        {
            "file": "html",
            "old_string": "href='/rooms'",
            "new_string": "href='#rooms'",
        },
    )
    assert result["ok"] is True
    assert 'href=\'#rooms\'' in sample_workspace.html_markup or 'href="#rooms"' in sample_workspace.html_markup


def test_replace_exact_not_found(sample_workspace):
    result = execute_template_tool(
        sample_workspace,
        "replace_exact",
        {"file": "html", "old_string": "NOT_THERE", "new_string": "x"},
    )
    assert result["ok"] is False


def test_validate_detects_missing_cta_class():
    ws = TemplateWorkspace(
        html_markup="{{client_name}} {{event_dates}} {{verified_room_blocks}} "
        "{{selected_map_svg}} {{meeting_space_specs}} {{xgboost_quote_breakdown}} "
        "{{negotiated_concessions}} {{cta_accept_button}}",
        css_stylesheet="",
        js_script="",
    )
    result = execute_template_tool(ws, "validate_template", {})
    assert result["ok"] is True
    assert result["valid"] is True
