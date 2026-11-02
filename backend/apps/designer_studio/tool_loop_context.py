"""Context condensing and exhaustion messaging for designer tool loops.

Tool results sent back to the model are shrunk with ``shrink_tool_result_for_model`` so the
payload is always **valid JSON** (never mid-string truncation). Critical control fields
(ok, error, valid, issues) are preserved; bulky fields (line dumps, search hits) are capped
with explicit ``*_omitted`` / ``content_truncated`` markers.
"""
from __future__ import annotations

import json
import re
from typing import Any

from django.conf import settings

from apps.designer_studio.services import deterministic_template_checks
from apps.designer_studio.template_agent_tools import human_tool_label

from .designer_map_intent import message_has_map_intent
from .designer_user_labels import format_user_tool_trace_summary

from .designer_fast_edit import format_edit_target_hints
from .agent_workflow_playbooks import (
    build_designer_request_footer,
    build_pool_calling_playbook,
    resolve_agent_workflow_mode,
)
from .template_symbol_index import compact_structure_outline
from .template_workspace import TemplateWorkspace

DEFAULT_CONDENSE_AFTER_PAIRS = 10
DEFAULT_KEEP_RECENT_PAIRS = 5
DEFAULT_TOOL_RESULT_CHARS = 9000
DEFAULT_LOOP_MESSAGE_BUDGET = 72000
DEFAULT_MAX_ISSUES_IN_PAYLOAD = 16
DEFAULT_MAX_HITS_IN_PAYLOAD = 12
DEFAULT_MAX_READ_CONTENT_CHARS = 12000
DEFAULT_MAX_SYMBOLS_IN_PAYLOAD = 32
DEFAULT_MAX_SECTION_READ_CHARS = 24000


def _int(name: str, default: int) -> int:
    return int(getattr(settings, name, default))


def user_wants_continuation(message: str) -> bool:
    lower = (message or "").lower().strip()
    if not lower:
        return False
    triggers = (
        "continue — finish",
        "continue - finish",
        "continue finishing",
        "pick up where",
        "keep working",
        "finish the remaining",
    )
    if any(t in lower for t in triggers):
        return True
    if lower.startswith("continue") and len(lower) < 80:
        return True
    return False


def continuation_bonus_steps() -> int:
    return max(4, _int("DESIGNER_TOOL_LOOP_CONTINUATION_BONUS_TURNS", 8))


def last_assistant_action_state(history: list[dict] | None) -> dict[str, Any] | None:
    for turn in reversed(history or []):
        if turn.get("role") == "assistant" and isinstance(turn.get("action_state"), dict):
            return turn["action_state"]
    return None


def user_follow_up_is_correction(message: str) -> bool:
    """User says the prior edit did not work (still broken, still there, etc.)."""
    lower = (message or "").lower().strip()
    if len(lower) < 4:
        return False
    cues = (
        "still ",
        "still,",
        "still have",
        "still we",
        "doesn't work",
        "didn't work",
        "not fixed",
        "not removed",
        "you didn't",
        "you did not",
        "same issue",
        "same problem",
        "no change",
        "nothing changed",
    )
    return any(c in lower for c in cues)


def prior_user_message_from_history(
    history: list[dict] | None,
    *,
    skip_continue: bool = True,
) -> str:
    """Most recent user turn before the current request (history excludes current message)."""
    for turn in reversed(history or []):
        if turn.get("role") != "user":
            continue
        content = str(turn.get("content") or "").strip()
        if not content:
            continue
        if skip_continue and user_wants_continuation(content):
            continue
        return content[:4000]
    return ""


def build_edit_ledger_from_tool_trace(tool_trace: list[dict[str, Any]]) -> dict[str, Any]:
    """Compact record of executor mutations — persisted on the assistant turn for the next message."""
    from .agent_task_plan import MUTATE_TOOLS

    mutations: list[dict[str, Any]] = []
    for entry in tool_trace or []:
        tool = str(entry.get("tool") or "")
        result = entry.get("result") if isinstance(entry.get("result"), dict) else {}
        if tool not in MUTATE_TOOLS and tool != "append_template":
            continue
        row: dict[str, Any] = {"tool": tool, "turn": entry.get("turn"), "ok": bool(result.get("ok"))}
        if not result.get("ok"):
            row["error"] = str(result.get("error") or "")[:200]
            mutations.append(row)
            continue
        if tool == "replace_lines":
            row["file"] = result.get("file")
            row["start_line"] = result.get("start_line")
            row["end_line"] = result.get("end_line")
        elif tool == "replace_exact":
            row["file"] = result.get("file")
            row["replacements"] = result.get("replacements")
        elif tool == "append_template":
            row["appended_chars"] = result.get("appended_chars")
        gate = result.get("validation_after_mutate")
        if isinstance(gate, dict):
            row["post_edit_valid"] = bool(gate.get("valid"))
            if not gate.get("valid"):
                row["post_edit_issues"] = list(gate.get("issues") or [])[:6]
                diags = gate.get("diagnostics") or []
                if diags:
                    row["post_edit_diagnostics"] = diags[:4]
        mutations.append(row)
    ok_count = sum(1 for m in mutations if m.get("ok"))
    return {
        "mutation_count": ok_count,
        "mutations": mutations[-20:],
        "tools_run": len(tool_trace or []),
    }


def detect_likely_unmet_request(prior_user_message: str, workspace: TemplateWorkspace) -> list[str]:
    """Heuristic: user asked for X but template still contains contradictory markup."""
    gaps: list[str] = []
    prior = (prior_user_message or "").lower()
    html = workspace.html_markup or ""
    if not prior or not html:
        return gaps
    if "remove" in prior and (
        "last row" in prior
        or "last table" in prior
        or "total row" in prior
        or "no need" in prior
    ):
        if "room-block-total-row" in html or re.search(r"Total block", html, re.I):
            gaps.append(
                "Prior request was to REMOVE the duplicate table total/summary row — "
                "markup still contains room-block-total-row or a Total block table row. "
                "Delete that <tr> (runtime summary footer is enough); do not restyle the row."
            )
    return gaps


def build_prior_turn_session_block(
    *,
    history: list[dict] | None,
    workspace: TemplateWorkspace,
    current_message: str,
) -> str:
    """
    Tool-loop intro block: prior user intent + mutations from last turn (not in chat history text).
    """
    prior_user = prior_user_message_from_history(history)
    if not prior_user and not history:
        return ""

    st = last_assistant_action_state(history) or {}
    ledger = st.get("edit_ledger") if isinstance(st.get("edit_ledger"), dict) else {}
    mutations = ledger.get("mutations") or []
    last_claim = str(st.get("last_assistant_message") or "")[:400]
    correction = user_follow_up_is_correction(current_message)

    lines = ["PRIOR TURN CONTEXT (authoritative — do not ignore on follow-ups):"]
    if prior_user:
        lines.append(f"- Previous user request:\n{prior_user[:2000]}")
    if last_claim:
        lines.append(f"- Assistant told the user: {last_claim!r}")
    if mutations:
        lines.append("- Template mutations applied that turn:")
        for m in mutations[-8:]:
            if m.get("tool") == "replace_lines":
                lines.append(
                    f"  • replace_lines {m.get('file')} lines {m.get('start_line')}-{m.get('end_line')} "
                    f"ok={m.get('ok')} post_edit_valid={m.get('post_edit_valid')}"
                )
            elif m.get("tool") == "replace_exact":
                lines.append(
                    f"  • replace_exact on {m.get('file')} ({m.get('replacements')} hit(s)) ok={m.get('ok')}"
                )
            elif m.get("tool") == "append_template":
                lines.append(f"  • append_template ok={m.get('ok')}")
            else:
                lines.append(f"  • {m}")
            for issue in m.get("post_edit_issues") or []:
                lines.append(f"    lint: {issue[:180]}")
    else:
        lines.append(
            "- No mutation ledger on last assistant turn — prior response may have auto-finished "
            "without replace_lines/replace_exact, or session state was not saved."
        )

    for gap in detect_likely_unmet_request(prior_user, workspace):
        lines.append(f"- LIKELY STILL BROKEN: {gap}")

    if correction:
        lines.append(
            "- FOLLOW-UP CORRECTION: User reports the last edit did NOT work. "
            "Do NOT polish/layout the same element — implement the prior intent "
            "(DELETE when they said remove). search_template → read_template_symbol → replace_lines."
        )

    return "\n".join(lines)


def build_actionable_edit_hints(*texts: str) -> list[str]:
    """Pool-calling hints derived from user request (semantic section list, not search loops)."""
    blob = " ".join(t for t in texts if t).strip()
    if not blob:
        return [
            'list_template_symbols(file=html, kind=proposal_section, query="<topic>") → '
            "read_template_symbol → replace_lines in one batch."
        ]
    q = blob[:120].replace('"', "'")
    hints = [
        f'list_template_symbols(file=html, kind=proposal_section, query="{q}") — semantic rank, then read top section.',
        "read_template_symbol(symbol_id) + replace_lines(same line range) in the SAME tools response.",
    ]
    if any(k in blob.lower() for k in ("map", "floor", "venue", "floorplan")):
        hints.append(
            "Map: get_map_knowledge + get_map_reference_code once, then pool-edit .venue-map-proposal section."
        )
    if any(k in blob.lower() for k in ("nav", "href", "link", "header")):
        hints.append(
            'Small nav fix: replace_exact on href inside the section you already read — not search_template first.'
        )
    return hints[:5]


def build_readonly_loop_steer(
    *,
    original_request: str,
    remaining_items: list[str] | None = None,
) -> str:
    remaining_blob = " ".join(remaining_items or [])
    hints = build_actionable_edit_hints(original_request, remaining_blob)
    lines = [
        "CONTROL (read-only loop — template unchanged):",
        "You repeated investigation tools without replace_exact/replace_lines/append_template.",
        "The next response MUST be a multi-tool batch that includes at least one mutating tool.",
        f"Original design goal:\n{original_request[:1800]}",
    ]
    if remaining_items:
        lines.append("Remaining items:")
        for item in remaining_items[:6]:
            lines.append(f"  • {item}")
    lines.append("Suggested edit sequence:")
    for h in hints:
        lines.append(f"  • {h}")
    return "\n".join(lines)


def shrink_tool_result_for_model(result: dict[str, Any]) -> dict[str, Any]:
    """
    Shrink a tool result dict for the LLM context window.

    Never returns invalid JSON (use via ``trim_tool_result_payload``).
    """
    if not isinstance(result, dict):
        return {"ok": False, "error": "invalid tool result type", "context_note": "not a dict"}

    out: dict[str, Any] = dict(result)
    char_budget = _int("DESIGNER_TOOL_LOOP_TOOL_RESULT_CHARS", DEFAULT_TOOL_RESULT_CHARS)
    max_issues = _int("DESIGNER_TOOL_LOOP_MAX_ISSUES_IN_PAYLOAD", DEFAULT_MAX_ISSUES_IN_PAYLOAD)
    max_hits = _int("DESIGNER_TOOL_LOOP_MAX_HITS_IN_PAYLOAD", DEFAULT_MAX_HITS_IN_PAYLOAD)
    max_read = _int("DESIGNER_TOOL_LOOP_MAX_READ_CONTENT_CHARS", DEFAULT_MAX_READ_CONTENT_CHARS)
    sym = out.get("symbol")
    if isinstance(sym, dict) and sym.get("kind") == "proposal_section":
        max_read = _int(
            "DESIGNER_TOOL_LOOP_MAX_SECTION_READ_CHARS",
            DEFAULT_MAX_SECTION_READ_CHARS,
        )
    max_symbols = _int("DESIGNER_TOOL_LOOP_MAX_SYMBOLS_IN_PAYLOAD", DEFAULT_MAX_SYMBOLS_IN_PAYLOAD)

    symbols = out.get("symbols")
    if isinstance(symbols, list) and len(symbols) > max_symbols:
        out["symbols"] = symbols[:max_symbols]
        out["symbols_omitted"] = len(symbols) - max_symbols

    issues = out.get("issues")
    if isinstance(issues, list) and len(issues) > max_issues:
        out["issues"] = [str(i) for i in issues[:max_issues]]
        out["issues_omitted"] = len(issues) - max_issues

    hits = out.get("hits")
    if isinstance(hits, list) and len(hits) > max_hits:
        out["hits"] = hits[:max_hits]
        out["hits_omitted"] = len(hits) - max_hits

    content = out.get("content")
    if isinstance(content, str) and len(content) > max_read:
        # Keep numbered line prefix region when possible (read_template_lines)
        head = content[:max_read]
        if "\n" in head:
            head = head.rsplit("\n", 1)[0]
        out["content"] = head + "\n… [truncated — use read_template_symbol on a smaller section or narrow line range]"
        out["content_truncated"] = True
        out["content_total_chars"] = len(content)

    text = json.dumps(out, ensure_ascii=False)
    if len(text) <= char_budget:
        return out

    # Still too large: minimal control plane (always valid JSON)
    minimal: dict[str, Any] = {}
    for key in ("ok", "error", "valid", "file", "query", "start_line", "end_line", "replacements"):
        if key in out:
            minimal[key] = out[key]
    if out.get("issues"):
        iss = out["issues"]
        minimal["issues"] = iss[:6] if isinstance(iss, list) else iss
        if isinstance(iss, list) and len(iss) > 6:
            minimal["issues_omitted"] = len(iss) - 6
    if out.get("hits_omitted"):
        minimal["hits_omitted"] = out["hits_omitted"]
    minimal["context_note"] = (
        "Result too large for context; repeat this tool with a narrower line range or search query."
    )
    return minimal


def trim_tool_result_payload(result: dict[str, Any]) -> str:
    """JSON string for the tool-loop message stream — always parseable."""
    return json.dumps(shrink_tool_result_for_model(result), ensure_ascii=False)


def _tool_result_user_prefix(content: str) -> bool:
    text = str(content or "")
    return text.startswith("Tool result:") or text.startswith("Tool results (batch):")


def _parse_tool_result_body(tool_content: str) -> dict[str, Any] | None:
    text = str(tool_content or "")
    if not _tool_result_user_prefix(text):
        return None
    if text.startswith("Tool results (batch):"):
        return {"ok": True, "context_note": "multi-tool batch (summary only)"}
    body = text.split("Tool result:", 1)[-1].strip()
    if not body:
        return None
    try:
        parsed = json.loads(body)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        # Legacy / corrupted chunk from old string truncation — do not crash condensing
        return {"ok": False, "error": "unparseable tool result in history", "context_note": "condensed"}


def _summarize_tool_pair(assistant_content: str, tool_content: str) -> str:
    tool_name = "tool"
    try:
        if assistant_content.strip().startswith("{"):
            parsed = json.loads(assistant_content)
            tool_name = str(parsed.get("tool") or tool_name)
    except json.JSONDecodeError:
        pass

    res = _parse_tool_result_body(tool_content)
    if not res:
        return f"- {human_tool_label(tool_name)} (unknown)"

    ok = "ok" if res.get("ok") else "failed"
    if res.get("error"):
        return f"- {human_tool_label(tool_name)} ({ok}): {str(res.get('error'))[:160]}"
    if res.get("issues") and not res.get("valid", True):
        n = len(res["issues"]) if isinstance(res["issues"], list) else 1
        extra = res.get("issues_omitted")
        suffix = f" (+{extra} more)" if extra else ""
        return f"- {human_tool_label(tool_name)} ({ok}): {n} issue(s){suffix}"
    if res.get("hits"):
        n = len(res["hits"]) if isinstance(res["hits"], list) else 0
        extra = res.get("hits_omitted")
        suffix = f" (+{extra} omitted)" if extra else ""
        return f"- {human_tool_label(tool_name)} ({ok}): {n} hit(s){suffix}"
    if res.get("replacements"):
        return f"- {human_tool_label(tool_name)} ({ok}): {res['replacements']} replacement(s)"
    if res.get("content_truncated"):
        return f"- {human_tool_label(tool_name)} ({ok}): line read truncated"
    return f"- {human_tool_label(tool_name)} ({ok})"


def build_tool_trace_digest(tool_trace: list[dict[str, Any]], *, max_lines: int = 24) -> str:
    """Human-readable tool history for checkpoint re-hydration (survives in-loop condensation)."""
    lines: list[str] = []
    for entry in (tool_trace or [])[-max_lines:]:
        tool = str(entry.get("tool") or "tool")
        result = entry.get("result") if isinstance(entry.get("result"), dict) else {}
        summary = _trace_entry_summary(tool, result)
        turn = entry.get("turn")
        prefix = f"turn {turn}" if turn else "step"
        args = entry.get("arguments") or {}
        arg_hint = ""
        if isinstance(args, dict) and args.get("query"):
            arg_hint = f" query={args.get('query')!r}"
        elif isinstance(args, dict) and args.get("start_line"):
            arg_hint = f" lines {args.get('start_line')}-{args.get('end_line')}"
        lines.append(f"- {prefix}: {tool}{arg_hint} — {summary}")
    return "\n".join(lines)


def build_executor_session_from_result(
    result: dict[str, Any],
    workspace: TemplateWorkspace,
    *,
    graph_thread_id: str = "",
) -> dict[str, Any]:
    from .tool_session_memory import workspace_fingerprint

    trace = result.get("tool_trace") or []
    return {
        "tool_session_graph": result.get("tool_session_graph") or {},
        "edit_ledger": result.get("edit_ledger") or {},
        "tool_trace_digest": build_tool_trace_digest(trace),
        "workspace_fp": workspace_fingerprint(workspace),
        "graph_thread_id": graph_thread_id or result.get("checkpoint_thread_id") or "",
    }


def build_langgraph_checkpoint_context_block(
    *,
    graph_thread_id: str | None,
    executor_session: dict[str, Any] | None,
) -> str:
    if not graph_thread_id and not executor_session:
        return ""
    lines = [
        "LANGGRAPH CHECKPOINT (one thread per proposal template — industry durable session):",
        f"- thread_id: {graph_thread_id or '(pending)'}",
    ]
    if executor_session:
        digest = str(executor_session.get("tool_trace_digest") or "").strip()
        if digest:
            lines.append(
                "- Prior tool steps (checkpointed — do not repeat read-only loops; "
                "fix remaining intent from PRIOR TURN CONTEXT):"
            )
            lines.append(digest[:12000])
        ledger = executor_session.get("edit_ledger")
        if isinstance(ledger, dict) and ledger.get("mutations"):
            lines.append(f"- Last turn mutations recorded: {ledger.get('mutation_count', 0)}")
    return "\n".join(lines)


def condense_tool_loop_messages(
    messages: list[dict[str, str]],
    *,
    graph_thread_id: str | None = None,
) -> list[dict[str, str]]:
    """
    Keep system + anchor user intro; condense older assistant/tool-result pairs into a summary.
    """
    if len(messages) < 4:
        return messages

    budget = _int("DESIGNER_TOOL_LOOP_MESSAGE_BUDGET_CHARS", DEFAULT_LOOP_MESSAGE_BUDGET)
    condense_after = _int("DESIGNER_TOOL_LOOP_CONDENSE_AFTER_PAIRS", DEFAULT_CONDENSE_AFTER_PAIRS)

    system = messages[0]
    rest = messages[1:]

    prefix: list[dict[str, str]] = []
    pairs: list[tuple[dict[str, str], dict[str, str]]] = []
    i = 0
    while i < len(rest):
        msg = rest[i]
        if (
            i + 1 < len(rest)
            and msg.get("role") == "assistant"
            and rest[i + 1].get("role") == "user"
            and _tool_result_user_prefix(str(rest[i + 1].get("content", "")))
        ):
            pairs.append((msg, rest[i + 1]))
            i += 2
        else:
            prefix.append(msg)
            i += 1

    total = sum(len(m.get("content", "")) for m in messages)
    if len(pairs) <= condense_after and total <= budget:
        return messages

    keep_recent = _int("DESIGNER_TOOL_LOOP_KEEP_RECENT_PAIRS", DEFAULT_KEEP_RECENT_PAIRS)
    if graph_thread_id and getattr(settings, "DESIGNER_LANGGRAPH_THREAD_PER_TEMPLATE", True):
        keep_recent = max(
            keep_recent,
            int(getattr(settings, "DESIGNER_TOOL_LOOP_CHECKPOINT_KEEP_RECENT_PAIRS", 14)),
        )
    while keep_recent >= 2:
        old_pairs = pairs[: max(0, len(pairs) - keep_recent)]
        recent_pairs = pairs[max(0, len(pairs) - keep_recent) :]

        summary_lines = ["Condensed earlier tool steps (details omitted to save context):"]
        for a_msg, u_msg in old_pairs[-24:]:
            summary_lines.append(_summarize_tool_pair(a_msg.get("content", ""), u_msg.get("content", "")))

        condensed: list[dict[str, str]] = [system]
        condensed.extend(prefix)
        if old_pairs:
            condensed.append({"role": "user", "content": "\n".join(summary_lines)[:8000]})
        for a_msg, u_msg in recent_pairs:
            condensed.append(a_msg)
            condensed.append(u_msg)

        new_total = sum(len(m.get("content", "")) for m in condensed)
        if new_total <= budget or keep_recent <= 2:
            return condensed
        keep_recent -= 1

    return messages


def _trace_entry_summary(tool: str, result: dict[str, Any]) -> str:
    return format_user_tool_trace_summary(tool, result)


def structured_completed_items(
    tool_trace: list[dict[str, Any]], max_items: int = 12
) -> list[dict[str, Any]]:
    """Deduped completed tool steps for structured UI (not repeated validate lines)."""
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in tool_trace:
        tool = str(entry.get("tool") or "tool")
        result = entry.get("result") or {}
        if not isinstance(result, dict):
            result = {}
        summary = _trace_entry_summary(tool, result)
        key = f"{tool}|{summary}"
        if key in seen:
            continue
        seen.add(key)
        items.append(
            {
                "id": f"tool-{len(items)}",
                "label": summary,
                "ok": bool(result.get("ok")),
            }
        )
    if len(items) > max_items:
        items = items[-max_items:]
    return items


def completed_work_summary(tool_trace: list[dict[str, Any]], max_items: int = 8) -> list[str]:
    structured = structured_completed_items(tool_trace, max_items=max_items)
    return [str(item.get("label") or "") for item in structured if item.get("label")]


def resolve_combined_planner_brief(message: str, history: list[dict] | None) -> str:
    """Planner + executor brief when user sends a short follow-up correction."""
    current = (message or "").strip()
    prior = prior_user_message_from_history(history)
    if not prior or prior == current:
        return current[:4000]
    if user_follow_up_is_correction(current) or len(current) < 120:
        return (
            f"ORIGINAL REQUEST:\n{prior[:2500]}\n\n"
            f"FOLLOW-UP (do this now — prior attempt failed or incomplete):\n{current[:800]}"
        )[:4000]
    return current[:4000]


def resolve_original_user_request(message: str, history: list[dict[str, str]] | list[dict]) -> str:
    """When the user tapped Continue, recover the real design brief from chat history."""
    text = (message or "").strip()
    if text and not user_wants_continuation(text):
        return text[:4000]
    for turn in reversed(history or []):
        if turn.get("role") != "user":
            continue
        content = str(turn.get("content") or "").strip()
        if not content:
            continue
        if user_wants_continuation(content):
            continue
        return content[:4000]
    return "Complete the remaining template edits from the previous session."


def is_greenfield_template(workspace: TemplateWorkspace) -> bool:
    """True when the designer has no scaffold yet (create-from-scratch requests)."""
    html = (workspace.html_markup or "").strip()
    css = (workspace.css_stylesheet or "").strip()
    js = (workspace.js_script or "").strip()
    if not html and not css and not js:
        return True
    report = workspace.placeholder_report()
    missing = report.get("missing") or []
    present = report.get("present") or []
    return len(present) == 0 and len(missing) >= 3


def format_workspace_context_anchor(
    workspace: TemplateWorkspace,
    *,
    message: str = "",
    repair_mode: bool = False,
) -> str:
    """Stable snapshot so the model knows current template state without re-running overview."""
    mode = resolve_agent_workflow_mode(workspace, message, repair_mode=repair_mode)
    report = workspace.placeholder_report()
    missing = report.get("missing") or []
    present = report.get("present") or []
    checks = deterministic_template_checks(
        workspace.html_markup,
        workspace.css_stylesheet,
        workspace.js_script,
    )
    lines = [
        "CURRENT TEMPLATE SNAPSHOT (trust this — do not call get_template_overview unless you lost sync after edits):",
        f"- html lines: {workspace.line_count('html')}, css lines: {workspace.line_count('css')}, js lines: {workspace.line_count('js')}",
        f"- placeholders present: {len(present)}, missing: {', '.join(missing) if missing else 'none'}",
    ]
    if checks:
        lines.append("- validation blockers still open:")
        for issue in checks[:8]:
            lines.append(f"  • {issue}")
    else:
        lines.append("- deterministic validation: no blockers (server re-checks automatically after each edit).")
    lines.append(build_pool_calling_playbook(mode, message=message, workspace=workspace))
    if mode == "greenfield_create":
        lines.append(
            "- GREENFIELD detected: first response MUST mutate via append_template(file=html) — "
            "no list/search/read prelude."
        )
    try:
        lines.append(compact_structure_outline(workspace, max_per_file=12))
    except (ValueError, TypeError):
        pass
    hints = format_edit_target_hints(workspace, message=message)
    if hints:
        lines.append(hints)
    return "\n".join(lines)


def build_continuation_context_block(
    *,
    workspace: TemplateWorkspace,
    history: list[dict[str, str]] | list[dict],
    message: str,
) -> str:
    original = resolve_original_user_request(message, history)
    lines = [
        "CONTINUATION SESSION (user chose Continue after partial progress):",
        f"- Original request still in effect:\n{original[:2500]}",
        "- Obey AGENT MODE + FOLLOW-UP STEPS in the snapshot — pool-calling only.",
        "- Turn 1: list_template_symbols(proposal_section, query=remaining topic) → read → replace_lines.",
        "- Do not repeat get_template_overview or the same list query after a successful read.",
    ]
    last_assistant = ""
    for turn in reversed(history or []):
        if turn.get("role") == "assistant":
            last_assistant = str(turn.get("content") or "")[:1200]
            break
    if last_assistant and ("step limit" in last_assistant.lower() or "repeating" in last_assistant.lower()):
        lines.append(
            "- Prior turn stopped early; prioritize open validation issues and the original styling/layout request."
        )
    st = None
    for turn in reversed(history or []):
        if turn.get("role") == "assistant" and isinstance(turn.get("action_state"), dict):
            st = turn["action_state"]
            break
    if st is None:
        st = last_assistant_action_state(history)
    if st and st.get("tool_session_graph"):
        lines.append("- Prior tool session graph restored — see TOOL SESSION MEMORY; do not redo DONE read-only steps.")
    if st and st.get("remaining_items"):
        lines.append("- Remaining from last progress card:")
        for item in (st.get("remaining_items") or [])[:6]:
            lines.append(f"  • {item}")
    hints = build_actionable_edit_hints(original, " ".join((st or {}).get("remaining_items") or []))
    if hints:
        lines.append("- Actionable edit hints (use in your next tools batch):")
        for h in hints:
            lines.append(f"  • {h}")
    return "\n".join(lines)


def build_tool_loop_user_intro(
    *,
    message: str,
    history: list[dict[str, str]] | list[dict],
    context_prefix: str,
    workspace: TemplateWorkspace,
    repair_mode: bool = False,
) -> str:
    original = resolve_original_user_request(message, history)
    continuation = user_wants_continuation(message)
    mode = resolve_agent_workflow_mode(workspace, original, repair_mode=repair_mode)
    parts: list[str] = []
    if context_prefix.strip():
        parts.append(context_prefix.strip())
    parts.append(format_workspace_context_anchor(workspace, message=original, repair_mode=repair_mode))
    if message_has_map_intent(message) or "venue-map-proposal" in (workspace.html_markup or ""):
        parts.append(
            "MAP WORK: If the user wants a floorplan / interactive map, call get_map_knowledge(topic=checklist) "
            "and get_map_reference_code(part=structure) once, then pool-edit the .venue-map-proposal section."
        )
    if continuation:
        parts.append(build_continuation_context_block(workspace=workspace, history=history, message=message))
    prior_block = build_prior_turn_session_block(
        history=history,
        workspace=workspace,
        current_message=message,
    )
    if prior_block:
        parts.append(prior_block)
    parts.append(build_designer_request_footer(mode, continuation=continuation, original_request=original))
    return "\n\n".join(parts)


def truncate_history_turn_for_tool_loop(content: str, *, max_chars: int | None = None) -> str:
    """Keep chat history in the tool loop small (venue-map system blocks, long attachments)."""
    limit = max_chars or _int("DESIGNER_TOOL_LOOP_HISTORY_TURN_CHARS", 900)
    text = str(content or "")
    if "[Attachments:" in text and "layout_reference" in text:
        limit = max(limit, 1400)
    if len(text) <= limit:
        return text
    if "INTERACTIVE VENUE MAP" in text or text.lstrip().startswith("SYSTEM "):
        head = text[:420].rstrip()
        return (
            f"{head}\n…[+{len(text) - 420} chars omitted — map knowledge is in the current request; "
            "edit the map section inside html_markup via tools.]"
        )
    return text[:limit].rstrip() + f"\n…[+{len(text) - limit} chars truncated]"


def filter_redundant_validate_tools(
    tool_batch: list[dict[str, Any]],
    *,
    repair_mode: bool,
    batch_has_mutate: bool,
    validated_workspace_fp: str | None,
    workspace_fp: str,
) -> list[dict[str, Any]]:
    """Drop duplicate validate_template calls in the same batch only (agent may validate anytime)."""
    _ = repair_mode, batch_has_mutate, validated_workspace_fp, workspace_fp
    if not tool_batch:
        return tool_batch
    out: list[dict[str, Any]] = []
    kept_validate = False
    for spec in tool_batch:
        tool = str(spec.get("tool") or "").strip()
        if tool != "validate_template":
            out.append(spec)
            continue
        if kept_validate:
            continue
        kept_validate = True
        out.append(spec)
    return out


def skipped_validate_tool_result(*, valid: bool, reason: str) -> dict[str, Any]:
    return {
        "ok": True,
        "valid": valid,
        "skipped": True,
        "reason": reason,
        "issues": [],
        "summary": "Skipped redundant validate_template — server already ran quality checks.",
    }


def should_auto_finish_tool_loop(
    *,
    repair_mode: bool,
    session_has_edit: bool,
    todo_tracker: Any,
    last_batch_had_mutate: bool,
    last_batch_gate_valid: bool,
) -> bool:
    if repair_mode or not session_has_edit:
        return False
    if not getattr(settings, "DESIGNER_TOOL_LOOP_AUTO_FINISH", True):
        return False
    if last_batch_had_mutate and not last_batch_gate_valid:
        return False
    complete = getattr(todo_tracker, "all_work_complete", None)
    if not callable(complete):
        return False
    return bool(complete())


def remaining_work_items(
    workspace: TemplateWorkspace,
    *,
    user_request: str,
    tool_trace: list[dict[str, Any]],
    history: list[dict] | None = None,
) -> list[str]:
    items: list[str] = []
    effective_request = resolve_original_user_request(user_request, history or [])

    validation = deterministic_template_checks(
        workspace.html_markup,
        workspace.css_stylesheet,
        workspace.js_script,
    )
    items.extend(validation[:6])

    last_val = None
    for entry in reversed(tool_trace):
        if entry.get("tool") == "validate_template":
            last_val = entry.get("result")
            break
    if last_val and not last_val.get("valid"):
        for issue in last_val.get("issues") or []:
            if issue not in items:
                items.append(str(issue))

    if not items and effective_request.strip():
        items.append(f"Remaining work from original request: {effective_request.strip()[:200]}")

    if not items:
        items.append("Additional polish or validation passes may still be needed.")

    return items[:8]


def build_exhaustion_user_message(
    *,
    workspace: TemplateWorkspace,
    tool_trace: list[dict[str, Any]],
    user_request: str,
    max_turns: int,
    repair_mode: bool,
    reason: str = "turn_limit",
    history: list[dict] | None = None,
) -> tuple[str, list[str], list[str], list[dict[str, Any]]]:
    """Return assistant_message, clarification_options, remaining_items, progress_completed."""
    progress_completed = structured_completed_items(tool_trace)
    remaining = remaining_work_items(
        workspace,
        user_request=user_request,
        tool_trace=tool_trace,
        history=history,
    )

    phase = "repair" if repair_mode else "edit"
    if reason == "stuck_loop":
        assistant_message = (
            "I repeated the same read-only tool batch several times without changing the template, "
            "so I paused to avoid spinning. Your template still has all edits applied so far. "
            "Use the progress card below — then Continue with multi-tool batches (search + read + replace) "
            "toward the remaining items, not another overview pass."
        )
    else:
        assistant_message = (
            f"I reached the {phase} agent turn limit ({max_turns} model turns) before finishing. "
            "Tool calls within each turn are unlimited — use multi-tool batches on Continue. "
            "Your template includes all changes applied so far. "
            "Use the progress card below to review completed vs remaining work, then tap Continue to resume."
        )

    clarification_options = [
        "Continue — finish the remaining edits",
        "Continue — focus on validation issues only",
        "Stop here — I'll adjust manually",
    ]

    return assistant_message, clarification_options, remaining, progress_completed
