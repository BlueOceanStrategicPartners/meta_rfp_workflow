"""Tool-calling loop for Designer Studio — scoped edits instead of full-document regen."""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Callable

from django.conf import settings

from apps.rfp_debate.meta_client import MetaModelAPIError, MetaModelClient

from .agent_execution_plan import (
    format_execution_plan_for_prompt,
    format_plan_focus_nudge,
    sync_execution_plan_after_tool,
)
from .agent_task_plan import (
    AgentTodoTracker,
    MUTATE_TOOLS,
    build_agent_todos,
    build_continuation_agent_todos,
    tool_mutated_template,
)
from .designer_user_labels import (
    format_user_tool_trace_summary,
    sanitize_user_visible_label,
    user_model_error_label,
    user_model_turn_label,
)
from .designer_validation import validate_template_deterministic_gate
from .template_agent_tools import execute_template_tool, human_tool_label, tool_catalog_for_prompt
from .template_repair_hints import format_repair_brief
from .template_workspace import TemplateWorkspace
from .tool_session_memory import (
    ToolSessionMemory,
    batch_is_read_only_only,
    inject_session_memory_message,
    workspace_fingerprint,
)
from .tool_loop_context import (
    build_exhaustion_user_message,
    build_readonly_loop_steer,
    build_tool_loop_user_intro,
    condense_tool_loop_messages,
    continuation_bonus_steps,
    filter_redundant_validate_tools,
    format_workspace_context_anchor,
    last_assistant_action_state,
    resolve_original_user_request,
    is_greenfield_template,
    should_auto_finish_tool_loop,
    trim_tool_result_payload,
    truncate_history_turn_for_tool_loop,
    user_wants_continuation,
    _trace_entry_summary,
)

logger = logging.getLogger(__name__)

WorkStepCallback = Callable[[str, str], None]
ToolEventCallback = Callable[[dict[str, Any]], None]
TodoEventCallback = Callable[[list[dict[str, Any]]], None]
PreviewEventCallback = Callable[[dict[str, str]], None]

TOOL_LOOP_SYSTEM = (
    "You are the Proposal Template Editor for a hospitality RFP designer panel. "
    "The template is THREE files: html (body markup with {{binding tokens}}), css, js.\n\n"
    "RULES:\n"
    "- Make changes ONLY via tools. Do not paste full file bodies in finish.\n"
    "- Required placeholders in html must appear exactly once each — never delete them.\n"
    "- Prefer list_template_symbols → read_template_symbol → replace_lines/replace_exact (AST-style, smallest context).\n"
    "- Tool argument `file` is always html, css, or js (never html_markup, css_stylesheet, js_script).\n"
    "- After search/list/read confirms what to change, batch replace_exact/replace_lines in the SAME turn — "
    "do not repeat list_template_symbols or read_template_lines on the next turn unless a patch failed.\n"
    "- For empty templates, use append_template to scaffold html/css/js before search or replace.\n"
    "- Call validate_template at most once before finish if you changed files — the server re-runs "
    "deterministic quality checks automatically after every edit.\n"
    "- Put interactivity in js; no inline onclick in html.\n"
    "- For nav links to on-page sections use href=\"#section-id\" not fake external URLs.\n\n"
    "MULTI-TOOL TURNS (important):\n"
    "- Each model turn may include MANY tools. Batch inspection and edits in one response.\n"
    "- There is NO limit on how many tools run inside one turn.\n"
    "- Do NOT repeat the same tool+arguments if the last batch returned ok without changing files.\n\n"
    "CONTEXT (important):\n"
    "- Each user message includes CURRENT TEMPLATE SNAPSHOT (line counts, placeholders, validation blockers).\n"
    "- Trust the snapshot; skip get_template_overview on continuation turns unless you are lost after edits.\n"
    "- On Continue sessions, finish the ORIGINAL request using remaining items — not another empty overview loop.\n"
    "- TOOL SESSION MEMORY messages list edits and completed investigations — obey DONE/skip lines.\n"
    "- When an EXECUTION PLAN block is present, work step-by-step: tools should advance the ACTIVE plan step.\n\n"
    "FAST EDIT PATH (three files only — html, css, js):\n"
    "- CURRENT TEMPLATE SNAPSHOT includes EDIT TARGET HINTS with symbol ids — start there.\n"
    "- Batch read_template_symbol + replace_exact/replace_lines in ONE turn when possible.\n"
    "- After ANY read-only batch, the next batch MUST include a mutating tool in the same response.\n"
    "- Do not call get_template_overview if the snapshot lists placeholders and structure.\n\n"
    "RESPONSE JSON (one object per model turn):\n"
    '- Multi-tool batch (preferred): {"kind":"tools","tools":[{"tool":"<name>","arguments":{...}}, ...]}\n'
    '- Single tool (legacy): {"kind":"tool","tool":"<name>","arguments":{...}}\n'
    '- Done: {"kind":"finish","assistant_message":"...","clarification_options":["optional short replies"]}\n\n'
    "TOOLS:\n"
    f"{tool_catalog_for_prompt()}"
)

REPAIR_TOOL_LOOP_SYSTEM = (
    "You are the Proposal Template Repair Editor. "
    "Fix ONLY the validation issues provided — use tools for every change.\n\n"
    + TOOL_LOOP_SYSTEM.split("RULES:\n", 1)[1]
)


def _tick(on_work_step: WorkStepCallback | None, step_id: str, status: str) -> None:
    if on_work_step:
        on_work_step(step_id, status)


def _emit_tool(
    on_tool_event: ToolEventCallback | None,
    *,
    tool: str,
    ok: bool,
    phase: str,
    label: str | None = None,
) -> None:
    if not on_tool_event:
        return
    on_tool_event(
        {
            "tool": tool,
            "label": sanitize_user_visible_label(label or human_tool_label(tool)),
            "ok": ok,
            "phase": phase,
        }
    )


def _emit_todos(on_todo_event: TodoEventCallback | None, tracker: AgentTodoTracker) -> None:
    if on_todo_event:
        on_todo_event(tracker.snapshot())


def _emit_preview(on_preview_event: PreviewEventCallback | None, workspace: TemplateWorkspace) -> None:
    if on_preview_event:
        on_preview_event(workspace.to_result_dict())


def _parse_agent_step(
    raw: dict[str, Any],
    *,
    continuation: bool = False,
    edit_focus: str = "",
) -> tuple[str, dict[str, Any] | list[dict[str, Any]]]:
    kind = str(raw.get("kind") or raw.get("type") or "").strip().lower()
    if kind == "finish":
        return "finish", raw
    if kind in ("tools", "tool_batch", "multi_tool"):
        batch = raw.get("tools") or raw.get("tool_calls") or []
        if isinstance(batch, list) and batch:
            return "tools", _normalize_tool_batch(batch)
    if isinstance(raw.get("tools"), list) and raw.get("tools"):
        return "tools", _normalize_tool_batch(raw["tools"])
    if kind == "tool":
        tool = str(raw.get("tool") or raw.get("tool_name") or "").strip()
        args = raw.get("arguments") or raw.get("tool_args") or {}
        if not isinstance(args, dict):
            args = {}
        return "tools", [{"tool": tool, "arguments": args}]
    if raw.get("html_markup") is not None:
        return "finish", raw
    if continuation:
        focus = (edit_focus or "").lower()
        tools: list[dict[str, Any]] = [
            {"tool": "search_template", "arguments": {"file": "css", "query": "a "}},
            {"tool": "search_template", "arguments": {"file": "html", "query": "href="}},
        ]
        if any(k in focus for k in ("header", "nav", "top")):
            tools.insert(0, {"tool": "search_template", "arguments": {"file": "css", "query": "header"}})
        return "tools", tools
    return "tools", [{"tool": "get_template_overview", "arguments": {}}]


def _normalize_tool_batch(batch: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in batch:
        if not isinstance(item, dict):
            continue
        tool = str(item.get("tool") or item.get("tool_name") or "").strip()
        if not tool:
            continue
        args = item.get("arguments") or item.get("tool_args") or {}
        if not isinstance(args, dict):
            args = {}
        out.append({"tool": tool, "arguments": args})
    return out or [{"tool": "get_template_overview", "arguments": {}}]


def _batch_signature(tool_batch: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for spec in tool_batch:
        tool = str(spec.get("tool") or "")
        args = spec.get("arguments") or {}
        try:
            args_key = json.dumps(args, sort_keys=True, ensure_ascii=False)
        except TypeError:
            args_key = str(args)
        parts.append(f"{tool}|{args_key}")
    return "||".join(parts)


def _stuck_in_loop(recent_signatures: list[str], threshold: int) -> bool:
    if threshold < 2 or len(recent_signatures) < threshold:
        return False
    window = recent_signatures[-threshold:]
    return len(set(window)) == 1


def _ensure_fixture_bootstrap(workspace: TemplateWorkspace, message: str) -> None:
    if "{{client_name}}" in (workspace.html_markup or ""):
        return
    payload = MetaModelClient._designer_fixture_html(message)
    workspace.html_markup = str(payload.get("html_markup") or workspace.html_markup)
    workspace.css_stylesheet = str(payload.get("css_stylesheet") or workspace.css_stylesheet)
    workspace.js_script = str(payload.get("js_script") or workspace.js_script)


def _fixture_tool_step(
    *,
    step_index: int,
    message: str,
    workspace: TemplateWorkspace,
    last_tool_result: dict[str, Any] | None,
    repair_mode: bool = False,
) -> dict[str, Any]:
    lower = (message or "").lower()
    if user_wants_continuation(message):
        if step_index == 0:
            return {
                "kind": "tools",
                "tools": [
                    {
                        "tool": "search_template",
                        "arguments": {"file": "css", "query": "a{"},
                    },
                    {
                        "tool": "replace_exact",
                        "arguments": {
                            "file": "css",
                            "old_string": "a {",
                            "new_string": "a {\n  color: inherit;",
                            "max_replacements": 3,
                        },
                    },
                ],
            }
        if step_index == 1:
            return {"kind": "tools", "tools": [{"tool": "validate_template", "arguments": {}}]}
        return {
            "kind": "finish",
            "assistant_message": "Continued from partial progress and applied the next batch of template fixes.",
            "clarification_options": [],
        }

    if repair_mode:
        if step_index == 0:
            return {"kind": "tool", "tool": "validate_template", "arguments": {}}
        if step_index == 1:
            return {"kind": "tool", "tool": "search_template", "arguments": {"file": "css", "query": "proposal-cta"}}
        if step_index == 2 and "display:none" in (workspace.css_stylesheet or ""):
            workspace.css_stylesheet = (workspace.css_stylesheet or "").replace(
                ".proposal-cta{display:none}",
                ".proposal-cta{display:flex}",
            )
            return {"kind": "tool", "tool": "validate_template", "arguments": {}}
        return {
            "kind": "finish",
            "assistant_message": "Repaired validation issues with targeted template edits.",
            "clarification_options": [],
        }

    if step_index >= 3:
        _ensure_fixture_bootstrap(workspace, message)
        return {
            "kind": "finish",
            "assistant_message": (
                "Updated the proposal template with targeted edits and required placeholders."
            ),
            "clarification_options": [],
        }

    if step_index == 0:
        if is_greenfield_template(workspace):
            _ensure_fixture_bootstrap(workspace, message)
            return {"kind": "tools", "tools": [{"tool": "validate_template", "arguments": {}}]}
        if "href" in lower or "url" in lower or "route" in lower or "redirect" in lower or "section" in lower:
            return {"kind": "tool", "tool": "search_template", "arguments": {"file": "html", "query": "href="}}
        return {"kind": "tool", "tool": "get_template_overview", "arguments": {}}

    if step_index == 1 and last_tool_result and last_tool_result.get("hits"):
        return {
            "kind": "tool",
            "tool": "replace_exact",
            "arguments": {
                "file": "html",
                "old_string": 'href="/rooms"',
                "new_string": 'href="#rooms"',
                "max_replacements": 5,
            },
        }

    if step_index == 2:
        html = workspace.html_markup
        if "href=" in html:
            workspace.html_markup = re.sub(
                r'href="(?!#|mailto:|tel:|javascript:)([^"]+)"',
                lambda m: f'href="#{m.group(1).strip("/").replace("/", "-")}"'
                if not m.group(1).startswith("#")
                else m.group(0),
                html,
                count=0,
            )
        return {"kind": "tool", "tool": "validate_template", "arguments": {}}

    _ensure_fixture_bootstrap(workspace, message)
    return {
        "kind": "finish",
        "assistant_message": (
            "Updated navigation to use on-page section anchors (#rooms, #meetings, etc.) "
            "instead of external URLs. Buttons now scroll/focus in-proposal sections."
        ),
        "clarification_options": [],
    }


class DesignerToolLoopRunner:
    def __init__(self, client: MetaModelClient | None = None):
        self.client = client or MetaModelClient()

    def run(
        self,
        *,
        message: str,
        history: list[dict[str, str]],
        html_markup: str,
        css_stylesheet: str,
        js_script: str,
        context_prefix: str = "",
        on_work_step: WorkStepCallback | None = None,
        on_tool_event: ToolEventCallback | None = None,
        on_todo_event: TodoEventCallback | None = None,
        on_preview_event: PreviewEventCallback | None = None,
    ) -> dict[str, Any]:
        _tick(on_work_step, "understand_brief", "done")
        _tick(on_work_step, "draft_proposal", "active")
        max_turns = int(getattr(settings, "DESIGNER_TOOL_LOOP_MAX_TURNS", 20))
        if user_wants_continuation(message):
            max_turns += continuation_bonus_steps()
        out = self._loop(
            system_prompt=TOOL_LOOP_SYSTEM,
            context_prefix=context_prefix,
            history=history,
            html_markup=html_markup,
            css_stylesheet=css_stylesheet,
            js_script=js_script,
            message_for_fixture=message,
            repair_mode=False,
            max_turns=max_turns,
            user_request=message,
            on_work_step=on_work_step,
            on_tool_event=on_tool_event,
            on_todo_event=on_todo_event,
            on_preview_event=on_preview_event,
            phase="edit",
        )
        _tick(on_work_step, "draft_proposal", "done")
        out["agent_mode"] = "tool_loop"
        return out

    def run_with_plan(
        self,
        *,
        message: str,
        history: list[dict[str, str]],
        html_markup: str,
        css_stylesheet: str,
        js_script: str,
        context_prefix: str = "",
        execution_plan_todos: list[dict[str, Any]],
        on_work_step: WorkStepCallback | None = None,
        on_tool_event: ToolEventCallback | None = None,
        on_todo_event: TodoEventCallback | None = None,
        on_preview_event: PreviewEventCallback | None = None,
    ) -> dict[str, Any]:
        """Executor entry: plan was produced by the planning agent; do not replan."""
        _tick(on_work_step, "understand_brief", "done")
        _tick(on_work_step, "draft_proposal", "active")
        max_turns = int(getattr(settings, "DESIGNER_TOOL_LOOP_MAX_TURNS", 20))
        if user_wants_continuation(message):
            max_turns += continuation_bonus_steps()
        out = self._loop(
            system_prompt=TOOL_LOOP_SYSTEM,
            context_prefix=context_prefix,
            history=history,
            html_markup=html_markup,
            css_stylesheet=css_stylesheet,
            js_script=js_script,
            message_for_fixture=message,
            repair_mode=False,
            max_turns=max_turns,
            user_request=message,
            execution_plan_todos=execution_plan_todos,
            on_work_step=on_work_step,
            on_tool_event=on_tool_event,
            on_todo_event=on_todo_event,
            on_preview_event=on_preview_event,
            phase="edit",
        )
        _tick(on_work_step, "draft_proposal", "done")
        out["agent_mode"] = "langgraph_executor"
        return out

    def run_repair(
        self,
        *,
        original_message: str,
        issues: list[str],
        html_markup: str,
        css_stylesheet: str,
        js_script: str,
        on_work_step: WorkStepCallback | None = None,
        on_tool_event: ToolEventCallback | None = None,
        on_todo_event: TodoEventCallback | None = None,
        on_preview_event: PreviewEventCallback | None = None,
    ) -> dict[str, Any]:
        brief = format_repair_brief(original_message=original_message, issues=issues)
        max_turns = max(4, int(getattr(settings, "DESIGNER_TOOL_LOOP_REPAIR_MAX_TURNS", 20)))
        out = self._loop(
            system_prompt=REPAIR_TOOL_LOOP_SYSTEM,
            context_prefix=brief,
            history=[],
            html_markup=html_markup,
            css_stylesheet=css_stylesheet,
            js_script=js_script,
            message_for_fixture=brief,
            repair_mode=True,
            max_turns=max_turns,
            user_request=original_message,
            on_work_step=on_work_step,
            on_tool_event=on_tool_event,
            on_todo_event=on_todo_event,
            on_preview_event=on_preview_event,
            phase="repair",
        )
        out["agent_mode"] = "tool_loop"
        out["repair_tool_pass"] = True
        return out

    def _loop(
        self,
        *,
        system_prompt: str,
        context_prefix: str,
        history: list[dict[str, str]],
        html_markup: str,
        css_stylesheet: str,
        js_script: str,
        message_for_fixture: str,
        repair_mode: bool,
        max_turns: int,
        on_work_step: WorkStepCallback | None,
        on_tool_event: ToolEventCallback | None,
        on_todo_event: TodoEventCallback | None = None,
        on_preview_event: PreviewEventCallback | None = None,
        phase: str,
        user_request: str = "",
        execution_plan_todos: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        workspace = TemplateWorkspace(
            html_markup=html_markup or "",
            css_stylesheet=css_stylesheet or "",
            js_script=js_script or "",
        )
        tool_trace: list[dict[str, Any]] = []
        effective_request = resolve_original_user_request(user_request, history)
        continuation_active = user_wants_continuation(user_request)
        execution_plan_block = ""
        if repair_mode:
            todo_tracker = AgentTodoTracker(build_agent_todos(effective_request, repair_mode=True))
            todo_tracker.activate_first_pending("triage")
            # Repair runs silently — do not replace the user's exec to-do list in the UI.
        elif continuation_active:
            todo_tracker = AgentTodoTracker(build_continuation_agent_todos())
            _emit_todos(on_todo_event, todo_tracker)
        elif execution_plan_todos is not None:
            todo_tracker = AgentTodoTracker([dict(t) for t in execution_plan_todos])
            _emit_todos(on_todo_event, todo_tracker)
            execution_plan_block = format_execution_plan_for_prompt(todo_tracker)
        else:
            todo_tracker = AgentTodoTracker([])
            execution_plan_block = ""
        session_memory = ToolSessionMemory.from_action_state(history)
        if continuation_active:
            session_memory.prepare_continuation(workspace)
        else:
            session_memory.bind_workspace(workspace)

        messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
        for turn in history[-int(getattr(settings, "DESIGNER_MAX_HISTORY_TURNS", 12)) :]:
            role = turn.get("role")
            if role in ("user", "assistant"):
                messages.append(
                    {
                        "role": role,
                        "content": truncate_history_turn_for_tool_loop(
                            str(turn.get("content", ""))
                        ),
                    }
                )
        if repair_mode:
            user_block = (context_prefix or "").strip()
            user_block += "\n\n" + format_workspace_context_anchor(workspace, message=user_request)
            messages.append({"role": "user", "content": user_block[:32000]})
        else:
            user_block = build_tool_loop_user_intro(
                message=user_request,
                history=history,
                context_prefix=context_prefix,
                workspace=workspace,
            )
            if execution_plan_block:
                user_block = f"{user_block}\n\n{execution_plan_block}"
            messages.append({"role": "user", "content": user_block[:32000]})

        last_tool_result: dict[str, Any] | None = None
        assistant_message = ""
        clarification_options: list[str] = []
        remaining_items: list[str] = []
        exhausted = False
        stuck_loop = False
        finished_cleanly = False
        progress_completed: list[dict[str, Any]] = []
        fixture_kind = "designer_tool_loop_repair" if repair_mode else "designer_tool_loop"
        max_tools_per_turn = int(getattr(settings, "DESIGNER_TOOL_LOOP_MAX_TOOLS_PER_TURN", 48))
        stuck_threshold = int(getattr(settings, "DESIGNER_TOOL_LOOP_STUCK_REPEAT_THRESHOLD", 3))
        readonly_loop_steers = 0
        greenfield_readonly_turns = 0
        must_mutate_after_readonly = False
        session_has_edit = False
        validated_workspace_fp: str | None = None
        last_batch_gate_valid = True
        last_batch_had_mutate = False
        model_api_failed = False
        prior_action = last_assistant_action_state(history) or {}
        continuation_remaining = list(prior_action.get("remaining_items") or [])[:8]

        def emit_agent_todos() -> None:
            if repair_mode:
                return
            _emit_todos(on_todo_event, todo_tracker)

        for turn in range(max_turns):
            inject_session_memory_message(messages, session_memory)

            _emit_tool(
                on_tool_event,
                tool="model_turn",
                ok=True,
                phase=phase,
                label=user_model_turn_label(turn=turn + 1, max_turns=max_turns),
            )

            if settings.USE_FIXTURE_DEBATE or not getattr(settings, "META_MODEL_API_KEY", ""):
                raw = _fixture_tool_step(
                    step_index=turn,
                    message=message_for_fixture,
                    workspace=workspace,
                    last_tool_result=last_tool_result,
                    repair_mode=repair_mode,
                )
            else:
                try:
                    raw = self.client.complete_json_messages(
                        model_id=settings.META_MODEL_SPARK,
                        messages=messages,
                        fixture_kind=fixture_kind,
                        allow_fixture_fallback=False,
                    )
                except MetaModelAPIError as exc:
                    model_api_failed = True
                    assistant_message = str(exc)
                    clarification_options = ["Retry the request", "Continue with partial progress"]
                    exhausted = True
                    logger.error("Designer tool loop model API failed: %s", exc)
                    _emit_tool(
                        on_tool_event,
                        tool="model_turn",
                        ok=False,
                        phase=phase,
                        label=user_model_error_label(str(exc)),
                    )
                    if (workspace.html_markup or workspace.css_stylesheet or workspace.js_script).strip():
                        _emit_preview(on_preview_event, workspace)
                    break

            kind, payload = _parse_agent_step(
                raw if isinstance(raw, dict) else {},
                continuation=continuation_active,
                edit_focus=effective_request,
            )
            if kind == "finish":
                finish_payload = payload if isinstance(payload, dict) else raw
                assistant_message = str(
                    finish_payload.get("assistant_message") or finish_payload.get("message") or ""
                ).strip()
                opts = finish_payload.get("clarification_options") or []
                if isinstance(opts, list):
                    clarification_options = [str(o) for o in opts if o][:6]
                if finish_payload.get("html_markup"):
                    workspace.html_markup = str(finish_payload.get("html_markup"))
                if finish_payload.get("css_stylesheet"):
                    workspace.css_stylesheet = str(finish_payload.get("css_stylesheet"))
                if finish_payload.get("js_script"):
                    workspace.js_script = str(finish_payload.get("js_script"))
                todo_tracker.mark_all_done()
                emit_agent_todos()
                _emit_preview(on_preview_event, workspace)
                finished_cleanly = True
                break

            tool_batch: list[dict[str, Any]] = (
                payload if isinstance(payload, list) else [payload]  # type: ignore[list-item]
            )
            tool_batch = tool_batch[:max_tools_per_turn]
            ws_fp = workspace_fingerprint(workspace)
            batch_has_mutate = any(
                str(spec.get("tool") or "") in MUTATE_TOOLS
                or str(spec.get("tool") or "") == "append_template"
                for spec in tool_batch
            )
            tool_batch = filter_redundant_validate_tools(
                tool_batch,
                repair_mode=repair_mode,
                batch_has_mutate=batch_has_mutate,
                validated_workspace_fp=validated_workspace_fp,
                workspace_fp=ws_fp,
            )
            turn_sig = _batch_signature(tool_batch)

            batch_raw = {"kind": "tools", "tools": tool_batch}
            batch_result_lines: list[str] = []
            preview_dirty = False
            all_from_cache = True
            batch_gate_valid = True
            last_batch_had_mutate = False
            last_batch_gate_valid = True

            greenfield_scaffold = is_greenfield_template(workspace) and not session_has_edit
            readonly_only = batch_is_read_only_only(tool_batch)
            if (
                must_mutate_after_readonly
                and not repair_mode
                and not greenfield_scaffold
                and readonly_only
            ):
                batch_result_lines.append(
                    "CONTROL: Previous batch was read-only only. This batch must include at least one "
                    "replace_exact, replace_lines, or append_template (combine reads/search with edits "
                    "in the same batch). validate_template alone does not count — quality checks run "
                    "automatically after each edit."
                )
            elif not tool_batch:
                batch_result_lines.append(
                    "CONTROL: Batch had no executable tools (redundant validate removed). "
                    "Use a multi-tool batch with at least one mutating tool."
                )
            else:
                for spec in tool_batch:
                    tool_name = str(spec.get("tool") or "get_template_overview")
                    arguments = spec.get("arguments") or {}
                    if not isinstance(arguments, dict):
                        arguments = {}
                    emitted_tool_progress = False
                    result, from_cache = session_memory.execute(
                        workspace,
                        tool_name,
                        arguments,
                        user_brief=effective_request,
                    )
                    if not from_cache and tool_mutated_template(tool_name, result):
                        last_batch_had_mutate = True
                        mutate_summary = _trace_entry_summary(tool_name, result)
                        _emit_tool(
                            on_tool_event,
                            tool=tool_name,
                            ok=bool(result.get("ok")),
                            phase=phase,
                            label=mutate_summary,
                        )
                        if getattr(settings, "DESIGNER_VALIDATE_AFTER_MUTATE", True):
                            gate_review = validate_template_deterministic_gate(
                                html=workspace.html_markup,
                                css=workspace.css_stylesheet,
                                js=workspace.js_script,
                                message=effective_request,
                                history=history,
                            )
                            result["validation_after_mutate"] = {
                                "valid": bool(gate_review.get("valid")),
                                "issues": list(gate_review.get("issues") or []),
                                "summary": str(gate_review.get("summary") or ""),
                            }
                            gate_ok = bool(gate_review.get("valid"))
                            batch_gate_valid = batch_gate_valid and gate_ok
                            last_batch_gate_valid = gate_ok
                            if gate_ok:
                                validated_workspace_fp = workspace_fingerprint(workspace)
                            if not gate_ok:
                                _emit_tool(
                                    on_tool_event,
                                    tool="post_edit_check",
                                    ok=False,
                                    phase=phase,
                                    label=format_user_tool_trace_summary(
                                        "validate_template",
                                        {
                                            "ok": True,
                                            "valid": False,
                                            "issues": gate_review.get("issues") or [],
                                        },
                                    ),
                                )
                        emitted_tool_progress = True
                    if tool_name == "validate_template" and not result.get("skipped"):
                        if result.get("valid"):
                            validated_workspace_fp = workspace_fingerprint(workspace)
                    if not from_cache:
                        all_from_cache = False
                    last_tool_result = result
                    tool_trace.append(
                        {
                            "turn": turn + 1,
                            "tool": tool_name,
                            "arguments": arguments,
                            "result": result,
                            "from_cache": from_cache,
                        }
                    )
                    summary = _trace_entry_summary(tool_name, result)
                    if from_cache:
                        summary = f"{summary} (session memory — already done)"
                    if not emitted_tool_progress:
                        _emit_tool(
                            on_tool_event,
                            tool=tool_name,
                            ok=bool(result.get("ok")),
                            phase=phase,
                            label=summary,
                        )
                    sync_execution_plan_after_tool(
                        todo_tracker,
                        tool_name=tool_name,
                        result=result,
                        repair_mode=repair_mode,
                    )
                    batch_result_lines.append(
                        f"Tool `{tool_name}` result:\n{trim_tool_result_payload(result)}"
                    )
                    gate = result.get("validation_after_mutate")
                    if isinstance(gate, dict) and gate.get("valid") is False:
                        issue_lines = gate.get("issues") or []
                        batch_result_lines.append(
                            "CONTROL: Post-edit validation failed (same rules as Check template). "
                            "Fix these issues before the execution plan advances:\n"
                            + "\n".join(f"- {item}" for item in issue_lines[:15])
                        )
                    if tool_mutated_template(tool_name, result):
                        preview_dirty = True

            plan_nudge = format_plan_focus_nudge(todo_tracker)
            if plan_nudge:
                batch_result_lines.append(plan_nudge)

            emit_agent_todos()
            session_memory.bind_workspace(workspace)
            session_memory.note_batch_outcome(
                turn_sig,
                all_from_cache=all_from_cache,
                any_mutated=preview_dirty,
            )

            if preview_dirty:
                _emit_preview(on_preview_event, workspace)
                session_memory.continuation_mode = False
                session_has_edit = True
                must_mutate_after_readonly = False

            readonly_only = batch_is_read_only_only(tool_batch) if tool_batch else True
            if readonly_only and not preview_dirty and not greenfield_scaffold:
                must_mutate_after_readonly = True
            elif preview_dirty:
                must_mutate_after_readonly = False

            if (
                is_greenfield_template(workspace)
                and readonly_only
                and not preview_dirty
                and not repair_mode
            ):
                greenfield_readonly_turns += 1
                if greenfield_readonly_turns >= 2:
                    batch_result_lines.append(
                        "CONTROL: GREENFIELD template — stop overview/search loops. "
                        "Your next batch MUST use append_template on html, css, and js."
                    )
                    must_mutate_after_readonly = True
            elif preview_dirty:
                greenfield_readonly_turns = 0

            if (
                continuation_active
                and readonly_only
                and not preview_dirty
                and all_from_cache
            ):
                batch_result_lines.append(
                    "CONTROL: Read-only batch changed no files. "
                    "Include replace_exact, replace_lines, or append_template in your next tools batch."
                )

            if should_auto_finish_tool_loop(
                repair_mode=repair_mode,
                session_has_edit=session_has_edit,
                todo_tracker=todo_tracker,
                last_batch_had_mutate=last_batch_had_mutate,
                last_batch_gate_valid=last_batch_gate_valid,
            ):
                assistant_message = (
                    "Updated the proposal template with targeted edits."
                )
                todo_tracker.mark_all_done()
                emit_agent_todos()
                _emit_preview(on_preview_event, workspace)
                finished_cleanly = True
                break

            if session_memory.stuck_on_cached_repeats(stuck_threshold):
                if readonly_loop_steers < 2 and readonly_only and not preview_dirty:
                    readonly_loop_steers += 1
                    session_memory.reset_stuck_tracking()
                    messages.append(
                        {"role": "assistant", "content": json.dumps(batch_raw, ensure_ascii=False)[:12000]}
                    )
                    messages.append(
                        {
                            "role": "user",
                            "content": "Tool results (batch):\n"
                            + "\n---\n".join(batch_result_lines)[:24000],
                        }
                    )
                    messages.append(
                        {
                            "role": "user",
                            "content": build_readonly_loop_steer(
                                original_request=effective_request,
                                remaining_items=continuation_remaining or None,
                            )[:12000],
                        }
                    )
                    messages[:] = condense_tool_loop_messages(messages)
                    continue

                stuck_loop = True
                exhausted = True
                (
                    assistant_message,
                    clarification_options,
                    remaining_items,
                    progress_completed,
                ) = build_exhaustion_user_message(
                    workspace=workspace,
                    tool_trace=tool_trace,
                    user_request=user_request or message_for_fixture,
                    max_turns=max_turns,
                    repair_mode=repair_mode,
                    reason="stuck_loop",
                    history=history,
                )
                logger.warning(
                    "Designer tool loop stuck (repeated read-only batch, repair=%s)", repair_mode
                )
                break

            messages.append(
                {"role": "assistant", "content": json.dumps(batch_raw, ensure_ascii=False)[:12000]}
            )
            messages.append(
                {
                    "role": "user",
                    "content": "Tool results (batch):\n" + "\n---\n".join(batch_result_lines)[:24000],
                }
            )
            messages[:] = condense_tool_loop_messages(messages)
        else:
            exhausted = True
            (
                assistant_message,
                clarification_options,
                remaining_items,
                progress_completed,
            ) = build_exhaustion_user_message(
                workspace=workspace,
                tool_trace=tool_trace,
                user_request=user_request or message_for_fixture,
                max_turns=max_turns,
                repair_mode=repair_mode,
                reason="turn_limit",
                history=history,
            )

        if not exhausted and not assistant_message:
            assistant_message = (
                "Repaired template validation issues."
                if repair_mode
                else "Updated the proposal template with targeted edits."
            )

        out = workspace.to_result_dict()
        out.update(
            {
                "assistant_message": assistant_message,
                "clarification_options": clarification_options,
                "model_id": settings.META_MODEL_SPARK,
                "tool_steps": len(tool_trace),
                "tool_turns": len({t.get("turn") for t in tool_trace if t.get("turn")}),
                "tool_trace": tool_trace[:60],
                "agent_todos": todo_tracker.snapshot(),
                "tool_session_graph": session_memory.to_dict(),
            }
        )
        _emit_preview(on_preview_event, workspace)
        if exhausted:
            out["tool_loop_exhausted"] = True
            out["continuation_recommended"] = True
            out["remaining_items"] = remaining_items
            out["progress_completed"] = progress_completed
            out["partial_completion"] = True
            if stuck_loop:
                out["tool_loop_stuck"] = True
            if model_api_failed:
                out["model_api_error"] = True
            logger.warning(
                "Designer tool loop exhausted (turns=%s, repair=%s, stuck=%s, model_api_failed=%s)",
                max_turns,
                repair_mode,
                stuck_loop,
                model_api_failed,
            )
        elif finished_cleanly:
            out["partial_completion"] = False
            out["continuation_recommended"] = False
            out.pop("model_api_error", None)
            out["remaining_items"] = []
            out["clarification_options"] = [
                o
                for o in (out.get("clarification_options") or [])
                if "retry the request" not in str(o).lower()
                and not str(o).lower().startswith("continue —")
            ]
        return out
