from apps.designer_studio.agent_workflow_playbooks import (
    build_pool_calling_playbook,
    resolve_agent_workflow_mode,
)
from apps.designer_studio.template_workspace import TemplateWorkspace


def test_greenfield_mode():
    ws = TemplateWorkspace(html_markup="", css_stylesheet="", js_script="")
    assert resolve_agent_workflow_mode(ws, "Create a luxury proposal") == "greenfield_create"
    text = build_pool_calling_playbook("greenfield_create", message="luxury", workspace=ws)
    assert "append_template" in text
    assert "get_template_overview" in text


def test_update_mode():
    html = "<section id='a'>{{client_name}}</section>" + "".join(
        f"<div>{p}</div>" for p in [
            "{{event_dates}}",
            "{{verified_room_blocks}}",
            "{{meeting_space_specs}}",
            "{{xgboost_quote_breakdown}}",
            "{{negotiated_concessions}}",
            "{{cta_accept_button}}",
        ]
    )
    ws = TemplateWorkspace(html_markup=html, css_stylesheet="", js_script="")
    assert resolve_agent_workflow_mode(ws, "Make header darker") == "update_existing"
    text = build_pool_calling_playbook("update_existing", message="header", workspace=ws)
    assert "list_template_symbols" in text
    assert "replace_lines" in text
