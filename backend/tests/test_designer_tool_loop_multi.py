from apps.designer_studio.design_agent_tool_loop import (
    _batch_signature,
    _normalize_tool_batch,
    _parse_agent_step,
    _stuck_in_loop,
)


def test_parse_multi_tool_batch():
    kind, payload = _parse_agent_step(
        {
            "kind": "tools",
            "tools": [
                {"tool": "search_template", "arguments": {"file": "css", "query": "a"}},
                {"tool": "validate_template", "arguments": {}},
            ],
        }
    )
    assert kind == "tools"
    assert isinstance(payload, list)
    assert len(payload) == 2


def test_stuck_in_loop_detects_repeated_batches():
    sig = _batch_signature(_normalize_tool_batch([{"tool": "validate_template", "arguments": {}}]))
    assert _stuck_in_loop([sig, sig, sig], 3) is True
    assert _stuck_in_loop([sig, sig + "x", sig], 3) is False
