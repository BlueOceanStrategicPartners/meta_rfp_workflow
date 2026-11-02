import json

import pytest

from apps.designer_studio.tool_loop_context import (
    condense_tool_loop_messages,
    filter_redundant_validate_tools,
    shrink_tool_result_for_model,
    structured_completed_items,
    should_auto_finish_tool_loop,
    truncate_history_turn_for_tool_loop,
    trim_tool_result_payload,
    _parse_tool_result_body,
)
from apps.designer_studio.agent_task_plan import AgentTodoTracker


def test_trim_always_valid_json():
    huge = {
        "ok": True,
        "content": "    1| " + ("x" * 20000),
        "hits": [{"line": i, "text": "y" * 500} for i in range(50)],
        "issues": [f"issue {i}" for i in range(30)],
    }
    text = trim_tool_result_payload(huge)
    parsed = json.loads(text)
    assert "ok" in parsed
    assert parsed.get("content_truncated") or parsed.get("context_note") or len(text) <= 5000


def test_shrink_preserves_error_and_ok():
    raw = {"ok": False, "error": "old_string not found", "file": "html"}
    out = shrink_tool_result_for_model(raw)
    assert out["ok"] is False
    assert "not found" in out["error"]
    assert json.loads(trim_tool_result_payload(raw)) == out


def test_shrink_caps_hits_with_omitted_count():
    raw = {"ok": True, "hits": [{"line": i, "text": "a"} for i in range(40)]}
    out = shrink_tool_result_for_model(raw)
    assert len(out["hits"]) <= 10
    assert out.get("hits_omitted", 0) >= 30


def test_shrink_caps_issues_not_dropped_entirely():
    raw = {"ok": True, "valid": False, "issues": [f"problem {i}" for i in range(25)]}
    out = shrink_tool_result_for_model(raw)
    assert len(out["issues"]) >= 1
    assert out.get("issues_omitted", 0) >= 1


def test_parse_tool_result_handles_truncated_legacy_gracefully():
    bad = 'Tool result:\n{"ok": true, "content": "broken'
    assert _parse_tool_result_body(bad) is not None
    assert _parse_tool_result_body(bad)["ok"] is False


def test_condense_tool_loop_messages_collapses_old_pairs():
    messages = [{"role": "system", "content": "sys"}]
    messages.append({"role": "user", "content": "Designer request:\nfix nav"})
    for i in range(10):
        messages.append({"role": "assistant", "content": f'{{"kind":"tool","tool":"search_template","step":{i}}}'})
        payload = trim_tool_result_payload({"ok": True, "hits": [{"line": 1, "text": "href="}]})
        messages.append({"role": "user", "content": "Tool result:\n" + payload})
    condensed = condense_tool_loop_messages(messages)
    assert len(condensed) < len(messages)
    assert any("Condensed earlier" in m.get("content", "") for m in condensed)


def test_condense_matches_tool_results_batch_prefix():
    messages = [{"role": "system", "content": "sys"}, {"role": "user", "content": "go"}]
    for i in range(12):
        messages.append({"role": "assistant", "content": '{"kind":"tools","tools":[]}'})
        messages.append(
            {
                "role": "user",
                "content": "Tool results (batch):\nTool `search_template` result:\n"
                + trim_tool_result_payload({"ok": True, "hits": [{"line": i, "text": "x"}]}),
            }
        )
    condensed = condense_tool_loop_messages(messages)
    assert len(condensed) < len(messages)


def test_filter_redundant_validate_drops_repeat_and_post_mutate():
    batch = [{"tool": "replace_exact", "arguments": {}}, {"tool": "validate_template", "arguments": {}}]
    out = filter_redundant_validate_tools(
        batch,
        repair_mode=False,
        batch_has_mutate=True,
        validated_workspace_fp=None,
        workspace_fp="abc",
    )
    assert all(t["tool"] != "validate_template" for t in out)

    batch2 = [{"tool": "validate_template", "arguments": {}}]
    out2 = filter_redundant_validate_tools(
        batch2,
        repair_mode=False,
        batch_has_mutate=False,
        validated_workspace_fp="abc",
        workspace_fp="abc",
    )
    assert out2 == []


def test_truncate_history_shortens_venue_map_block():
    long_map = "SYSTEM DEFAULT VENUE MAP (is_default=true):\n" + ("x" * 6000)
    out = truncate_history_turn_for_tool_loop(long_map, max_chars=900)
    assert len(out) < len(long_map)
    assert "omitted" in out


def test_should_auto_finish_when_todos_complete():
    tracker = AgentTodoTracker(
        [
            {"id": "edit", "label": "Edit", "status": "done"},
            {"id": "finalize", "label": "Finalize", "status": "done"},
        ]
    )
    assert should_auto_finish_tool_loop(
        repair_mode=False,
        session_has_edit=True,
        todo_tracker=tracker,
        last_batch_had_mutate=True,
        last_batch_gate_valid=True,
    )


def test_structured_completed_items_dedupes_repeated_validate():
    trace = [
        {"tool": "validate_template", "result": {"ok": True, "valid": True}},
        {"tool": "validate_template", "result": {"ok": True, "valid": True}},
        {"tool": "validate_template", "result": {"ok": True, "valid": True}},
        {"tool": "replace_exact", "result": {"ok": True, "replacements": 2}},
    ]
    items = structured_completed_items(trace)
    labels = [i["label"] for i in items]
    assert len(items) == 2
    assert sum("checks passed" in lb for lb in labels) == 1
    assert any("2 change" in lb for lb in labels)
