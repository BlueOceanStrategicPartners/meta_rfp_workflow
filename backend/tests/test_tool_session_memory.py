from apps.designer_studio.template_workspace import TemplateWorkspace
from apps.designer_studio.tool_session_memory import ToolSessionMemory


def test_session_memory_caches_overview():
    ws = TemplateWorkspace(html_markup="{{client_name}}", css_stylesheet="a{color:blue}", js_script="")
    mem = ToolSessionMemory()
    mem.bind_workspace(ws)
    r1, c1 = mem.execute(ws, "get_template_overview", {})
    r2, c2 = mem.execute(ws, "get_template_overview", {})
    assert r1.get("ok") and r2.get("ok")
    assert c1 is False
    assert c2 is True
    assert r2.get("session_note")


def test_stuck_only_after_identical_cached_batches():
    ws = TemplateWorkspace(html_markup="{{client_name}}", css_stylesheet="", js_script="")
    mem = ToolSessionMemory()
    mem.bind_workspace(ws)
    sig = "get_template_overview|{}"
    mem.note_batch_outcome(sig, all_from_cache=False, any_mutated=False)
    assert not mem.stuck_on_cached_repeats(3)
    mem.note_batch_outcome(sig, all_from_cache=True, any_mutated=False)
    mem.note_batch_outcome(sig, all_from_cache=True, any_mutated=False)
    assert not mem.stuck_on_cached_repeats(3)
    mem.note_batch_outcome(sig, all_from_cache=True, any_mutated=False)
    assert mem.stuck_on_cached_repeats(3)


def test_read_after_mutation_is_fresh_not_stale_cache():
    ws = TemplateWorkspace(html_markup="line-a", css_stylesheet="", js_script="")
    mem = ToolSessionMemory()
    mem.bind_workspace(ws)
    _, c1 = mem.execute(ws, "search_template", {"file": "html", "query": "line-a"})
    assert c1 is False
    ws.html_markup = "line-b"
    _, c2 = mem.execute(ws, "search_template", {"file": "html", "query": "line-a"})
    assert c2 is False


def test_persisted_graph_does_not_restore_read_cache():
    ws = TemplateWorkspace(html_markup="{{x}}", css_stylesheet="", js_script="")
    mem = ToolSessionMemory()
    mem.bind_workspace(ws)
    mem.execute(ws, "get_template_overview", {})
    saved = mem.to_dict()
    assert "cache" not in saved
    restored = ToolSessionMemory.from_dict({**saved, "cache": {"fake|get_template_overview|{}": {"ok": True}}})
    _, from_cache = restored.execute(ws, "get_template_overview", {})
    assert from_cache is False


def test_continuation_blocks_overview():
    ws = TemplateWorkspace(html_markup="{{x}}", css_stylesheet="", js_script="")
    mem = ToolSessionMemory()
    mem.prepare_continuation(ws)
    result, cached = mem.execute(ws, "get_template_overview", {})
    assert not result.get("ok")
    assert cached is False
    assert "blocked" in str(result.get("error") or "").lower()
