from apps.designer_studio.tool_loop_context import build_actionable_edit_hints, build_readonly_loop_steer


def test_actionable_hints_for_link_and_header():
    hints = build_actionable_edit_hints("Fix blue header links and URL colors in CSS")
    joined = " ".join(hints).lower()
    assert "href" in joined or "html" in joined
    assert "css" in joined


def test_readonly_steer_includes_original_request():
    steer = build_readonly_loop_steer(
        original_request="Fix nav link colors",
        remaining_items=["validation issue"],
    )
    assert "replace_exact" in steer.lower()
    assert "Fix nav link colors" in steer
