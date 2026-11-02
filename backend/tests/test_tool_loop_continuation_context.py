from apps.designer_studio.tool_loop_context import (
    remaining_work_items,
    resolve_original_user_request,
    user_wants_continuation,
)
from apps.designer_studio.template_workspace import TemplateWorkspace


def test_resolve_original_user_request_skips_continue_chip():
    history = [
        {"role": "user", "content": "Fix blue header links in CSS"},
        {"role": "assistant", "content": "partial"},
        {"role": "user", "content": "Continue — finish the remaining edits"},
    ]
    assert user_wants_continuation("Continue — finish the remaining edits")
    assert "blue header" in resolve_original_user_request("Continue — finish the remaining edits", history)


def test_remaining_work_items_uses_original_not_continue():
    ws = TemplateWorkspace(html_markup="{{client_name}}", css_stylesheet="", js_script="")
    items = remaining_work_items(
        ws,
        user_request="Continue — finish the remaining edits",
        tool_trace=[],
        history=[
            {"role": "user", "content": "Fix nav link colors"},
        ],
    )
    assert not any("Continue — finish" in i for i in items)
    assert any("Fix nav" in i for i in items) or any("placeholder" in i.lower() for i in items)
