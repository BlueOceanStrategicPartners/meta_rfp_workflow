from apps.designer_studio.template_workspace import TemplateWorkspace
from apps.designer_studio.tool_loop_context import (
    build_edit_ledger_from_tool_trace,
    build_prior_turn_session_block,
    detect_likely_unmet_request,
    user_follow_up_is_correction,
)


def test_follow_up_correction_detected():
    assert user_follow_up_is_correction("Still, we have that last row.")


def test_unmet_remove_total_row():
    gaps = detect_likely_unmet_request(
        "remove last row from table no need total row",
        TemplateWorkspace(
            html_markup='<tr class="room-block-total-row">Total block</tr>',
            css_stylesheet="",
            js_script="",
        ),
    )
    assert gaps


def test_prior_turn_block_includes_ledger():
    history = [
        {
            "role": "user",
            "content": "Remove the last table row — we already show totals in the black bar.",
        },
        {
            "role": "assistant",
            "content": "Updated the proposal template with targeted edits.",
            "action_state": {
                "edit_ledger": {
                    "mutations": [
                        {
                            "tool": "replace_lines",
                            "file": "html",
                            "start_line": 10,
                            "end_line": 12,
                            "ok": True,
                            "post_edit_valid": True,
                        }
                    ]
                },
                "last_assistant_message": "Updated the proposal template with targeted edits.",
            },
        },
    ]
    block = build_prior_turn_session_block(
        history=history,
        workspace=TemplateWorkspace(
            html_markup='<tr class="room-block-total-row"></tr>',
            css_stylesheet="",
            js_script="",
        ),
        current_message="Still, we have that last row.",
    )
    assert "PRIOR TURN CONTEXT" in block
    assert "replace_lines" in block
    assert "LIKELY STILL BROKEN" in block
    assert "FOLLOW-UP CORRECTION" in block


def test_edit_ledger_from_trace():
    ledger = build_edit_ledger_from_tool_trace(
        [
            {
                "tool": "replace_lines",
                "turn": 1,
                "result": {
                    "ok": True,
                    "file": "html",
                    "start_line": 5,
                    "end_line": 8,
                    "validation_after_mutate": {"valid": False, "issues": ["x"]},
                },
            }
        ]
    )
    assert ledger["mutation_count"] == 1
    assert ledger["mutations"][0]["post_edit_valid"] is False
