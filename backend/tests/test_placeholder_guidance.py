from apps.designer_studio.models import MANDATORY_PLACEHOLDERS
from apps.designer_studio.placeholder_guidance import (
    clear_guidance_cache,
    collect_placeholder_binding_issues,
    design_agent_binding_guidance,
    expand_guidance,
    validation_placeholder_guidance,
)
from apps.designer_studio.services import deterministic_template_checks


def test_design_agent_guidance_includes_binding_schema():
    clear_guidance_cache()
    text = design_agent_binding_guidance()
    assert "line_items" in text
    assert "data-proposal-bind" in text
    assert "DEFAULT BEHAVIOR" in text.upper() or "Default behavior" in text
    assert "negotiated_concessions" in text
    assert "items" in text


def test_guidance_files_load_and_expand_mandatory_list():
    clear_guidance_cache()
    binding = design_agent_binding_guidance()
    validation = validation_placeholder_guidance()
    assert "{{MANDATORY_PLACEHOLDERS_LIST}}" not in binding
    assert "{{MANDATORY_PLACEHOLDERS_LIST}}" not in validation
    for token in MANDATORY_PLACEHOLDERS:
        assert token in binding
    assert "verified_room_blocks" in binding.lower()
    assert "Do not flag" in validation or "false positive" in validation.lower()


def test_expand_guidance_unknown_file_raises():
    clear_guidance_cache()
    try:
        expand_guidance("missing_file.md")
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("expected FileNotFoundError")


def test_collect_placeholder_binding_requires_json_wiring():
    html = (
        "<script type=\"application/json\" id=\"binding-verified-room-blocks\">"
        "{{verified_room_blocks}}</script>"
        "<table><thead><tr><th>Cat</th></tr></thead>"
        "<tbody data-proposal-bind=\"verified_room_blocks\"></tbody></table>"
        "<script src=\"/proposal_binding_runtime.js\"></script>"
    )
    issues = collect_placeholder_binding_issues(html)
    assert not any("binding-verified-room-blocks" in i and "must" in i for i in issues)


def test_collect_placeholder_binding_flags_missing_json_script():
    html = "<div>{{verified_room_blocks}}</div>"
    issues = collect_placeholder_binding_issues(html)
    assert any("application/json" in i for i in issues)


def test_deterministic_checks_include_duplicate_placeholder():
    token = MANDATORY_PLACEHOLDERS[0]
    html = f"<div>{token}</div><div>{token}</div>" + "".join(
        t for t in MANDATORY_PLACEHOLDERS[1:]
    )
    issues = deterministic_template_checks(html, "", "")
    assert any("exactly once" in i for i in issues)
