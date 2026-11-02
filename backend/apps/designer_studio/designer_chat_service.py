"""Design Agent chat orchestration with optional work-plan progress events."""
from __future__ import annotations

import json
import logging
import queue
import threading
import time
from collections.abc import Iterator
from typing import Any

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser
from django.utils import timezone

from .agent_rules import format_rules_for_agent, retrieve_relevant_rules
from .design_agent import DesignerStudioAgent
from .designer_chat_guards import (
    build_preview_audit_block,
    try_floorplan_attachment_reminder,
    user_message_reports_preview_issue,
)
from .designer_map_orchestration import merge_clarification_options, run_map_stage_if_needed
from .designer_work_plan import (
    WorkPlanTracker,
    build_work_plan,
    guess_include_venue_map,
)
from .designer_live_progress import (
    begin_live_progress,
    end_live_progress,
    patch_live_progress,
)
from .media_service import format_assets_for_agent
from .models import DesignerMediaAsset, ProposalTemplate
from .preview_automation_context import (
    format_preview_automation_for_agent,
    parse_automation_report,
    validate_automation_request,
)
from .preview_audit import audit_compiled_proposal_preview
from .serializers import DesignerMediaAssetSerializer
from .venue_map_admin import try_handle_venue_map_admin_message
from .venue_map_context import build_default_map_agent_context

logger = logging.getLogger(__name__)

_SSE_HEARTBEAT_SECONDS = 5.0


def _step_event(tracker: WorkPlanTracker, step_id: str, status: str) -> tuple[str, dict[str, Any]]:
    return ("step", {"steps": tracker.set_status(step_id, status)})


def _patch_finalize_agent_todo(result: dict[str, Any], status: str) -> list[dict[str, Any]] | None:
    todos = result.get("agent_todos")
    if not isinstance(todos, list) or not todos:
        return None
    updated = [dict(t) for t in todos]
    for todo in updated:
        if todo.get("id") == "finalize":
            todo["status"] = status
            result["agent_todos"] = updated
            return updated
    return None


def _yield_finalize_todo_events(
    result: dict[str, Any],
    *,
    status: str,
    live_progress_user_id: int | None,
) -> Iterator[tuple[str, dict[str, Any]]]:
    patched = _patch_finalize_agent_todo(result, status)
    if not patched:
        return
    yield ("todo", {"todos": patched})
    if live_progress_user_id is not None:
        patch_live_progress(user_id=live_progress_user_id, agent_todos=patched)


def _assistant_action_state(result: dict[str, Any]) -> dict[str, Any]:
    """Persist UI action cards on the assistant chat turn (survives refresh)."""
    result = _normalize_designer_chat_result(result)
    opts = result.get("clarification_options") or []
    if not isinstance(opts, list):
        opts = []
    opts = [str(o) for o in opts if o][:8]

    if result.get("model_api_error"):
        retry_opts = opts or ["Retry the request", "Continue — finish the remaining edits"]
        return {
            "action_state": {
                "partial_completion": True,
                "continuation_recommended": True,
                "remaining_items": list(result.get("remaining_items") or [])[:12]
                or ["Complete or retry your last design request"],
                "progress_completed": list(result.get("progress_completed") or [])[:16],
                "clarification_options": retry_opts,
                "agent_todos": list(result.get("agent_todos") or [])[:16],
            }
        }

    if result.get("partial_completion") and result.get("continuation_recommended"):
        return {
            "action_state": {
                "partial_completion": True,
                "continuation_recommended": True,
                "remaining_items": list(result.get("remaining_items") or [])[:12],
                "progress_completed": list(result.get("progress_completed") or [])[:16],
                "clarification_options": opts,
                "agent_todos": list(result.get("agent_todos") or [])[:16],
                "tool_session_graph": result.get("tool_session_graph") or {},
            }
        }

    if opts:
        return {"action_state": {"clarification_options": opts}}

    return {}


def _normalize_designer_chat_result(result: dict[str, Any]) -> dict[str, Any]:
    """Drop stale partial/retry UI when the template was updated successfully."""
    out = dict(result)
    msg = str(out.get("assistant_message") or "").strip()
    todos = out.get("agent_todos") or []
    todos_complete = bool(todos) and all(
        str(t.get("status") or "") in ("done", "skipped") for t in todos
    )
    has_edits = int(out.get("tool_steps") or 0) > 0 or bool(out.get("tool_trace"))
    success_line = msg in (
        "Updated the proposal template with targeted edits.",
        "Repaired template validation issues.",
        "Design agent finished.",
    ) or msg.startswith("Updated the proposal")

    if success_line and has_edits and todos_complete:
        out["partial_completion"] = False
        out["continuation_recommended"] = False
        out.pop("tool_loop_exhausted", None)
        out.pop("model_api_error", None)
        out["remaining_items"] = []
        out["clarification_options"] = [
            o
            for o in (out.get("clarification_options") or [])
            if "retry the request" not in str(o).lower()
            and not str(o).lower().startswith("continue —")
        ]

    if out.get("self_check", {}).get("valid") is True and success_line:
        out["partial_completion"] = False
        out["continuation_recommended"] = False
        out.pop("model_api_error", None)

    return out

def iter_designer_chat(
    *,
    user: AbstractBaseUser,
    data: dict[str, Any],
    request: Any | None = None,
) -> Iterator[tuple[str, dict[str, Any]]]:
    """Yield (event, payload) pairs: plan, step, done."""
    message = (data.get("message") or "").strip()
    attachment_ids = data.get("attachment_ids") or []
    history = data.get("history") or []
    html_markup = data.get("html_markup") or ""
    css_stylesheet = data.get("css_stylesheet") or ""
    js_script = data.get("js_script") or ""
    template_id = data.get("template_id")

    assets = list(
        DesignerMediaAsset.objects.filter(id__in=attachment_ids, designer=user)
    )
    attachment_block = format_assets_for_agent(assets)
    automation_report = parse_automation_report(data.get("preview_automation_report"))
    automation_depth = int(data.get("preview_automation_depth") or 0)
    automation_err = validate_automation_request(
        preview_automation_depth=automation_depth,
        preview_automation_report=automation_report,
        message=message or "",
    )
    if automation_err:
        yield ("error", {"message": automation_err})
        return

    include_audit = user_message_reports_preview_issue(message or "") or bool(
        data.get("include_preview_audit")
    )
    include_map_guess = guess_include_venue_map(message, bool(assets))

    template = None
    if template_id:
        template = ProposalTemplate.objects.filter(pk=template_id, designer=user).first()

    admin_result = None
    if message:
        admin_result = try_handle_venue_map_admin_message(
            message=message,
            user=user,
            html_markup=html_markup,
            css_stylesheet=css_stylesheet,
        )

    short_path = bool(admin_result)
    reminder = None
    if not admin_result and message:
        reminder = try_floorplan_attachment_reminder(message=message, assets=assets)
        if reminder:
            short_path = True

    plan_steps = build_work_plan(
        message=message or "Update the proposal template",
        include_preview_audit=include_audit and not short_path,
        include_venue_map=include_map_guess and not short_path,
        short_path=short_path,
    )
    tracker = WorkPlanTracker(plan_steps)
    yield ("plan", {"steps": tracker.snapshot()})

    live_progress_user_id: int | None = None

    if admin_result:
        yield _step_event(tracker, "understand_brief", "active")
        result = {**admin_result, "js_script": js_script}
        map_result = None
        venue_map = None
        map_ran = False
        yield _step_event(tracker, "understand_brief", "done")
    elif reminder:
        yield _step_event(tracker, "understand_brief", "active")
        result = {
            **reminder,
            "html_markup": html_markup,
            "css_stylesheet": css_stylesheet,
            "js_script": js_script,
            "map_stage_applied": False,
            "self_check": {"valid": True, "issues": []},
        }
        map_result = None
        venue_map = None
        map_ran = False
        yield _step_event(tracker, "understand_brief", "done")
    else:
        preview_audit_block = ""
        if include_audit:
            preview_audit_block = build_preview_audit_block(
                html_markup, css_stylesheet, js_script
            )
        preview_automation_block = format_preview_automation_for_agent(automation_report)
        venue_map_block = build_default_map_agent_context(user)
        rules = retrieve_relevant_rules(user.id, message or "Update proposal template")
        agent_rules_block = format_rules_for_agent(rules)

        agent = DesignerStudioAgent()
        progress_queue: queue.Queue[tuple[str, dict[str, Any]]] = queue.Queue()
        preview_last_mono = 0.0
        uid = getattr(user, "pk", None)
        live_progress_user_id = uid
        begin_live_progress(user_id=uid)

        def on_work_step(step_id: str, status: str) -> None:
            evt = _step_event(tracker, step_id, status)
            progress_queue.put(evt)
            patch_live_progress(user_id=uid, work_plan=evt[1]["steps"])

        def on_tool_event(evt: dict[str, Any]) -> None:
            progress_queue.put(("tool", evt))
            patch_live_progress(user_id=uid, tool_step=evt)

        def on_todo_event(todos: list[dict[str, Any]]) -> None:
            progress_queue.put(("todo", {"todos": todos}))
            patch_live_progress(user_id=uid, agent_todos=todos)

        def on_preview_event(snap: dict[str, str]) -> None:
            nonlocal preview_last_mono
            now = time.monotonic()
            if now - preview_last_mono < 2.5:
                return
            preview_last_mono = now
            progress_queue.put(("preview", snap))
            patch_live_progress(user_id=uid, preview=snap)

        chat_result: dict[str, Any] = {}
        chat_error: list[BaseException] = []

        def run_chat() -> None:
            try:
                chat_result["value"] = agent.chat_turn(
                    message=message or "Use the attached media in the proposal design.",
                    history=history,
                    html_markup=html_markup,
                    css_stylesheet=css_stylesheet,
                    js_script=js_script,
                    attachment_block=attachment_block,
                    venue_map_block=venue_map_block,
                    preview_audit_block=preview_audit_block,
                    preview_automation_block=preview_automation_block,
                    agent_rules_block=agent_rules_block,
                    user_id=getattr(user, "pk", None),
                    template_id=str(template_id) if template_id else None,
                    on_work_step=on_work_step,
                    on_tool_event=on_tool_event,
                    on_todo_event=on_todo_event,
                    on_preview_event=on_preview_event,
                )
            except BaseException as exc:  # pragma: no cover
                chat_error.append(exc)
                progress_queue.put(("error", {"message": str(exc)}))

        worker = threading.Thread(target=run_chat, daemon=True)
        worker.start()
        last_progress = time.monotonic()
        while worker.is_alive() or not progress_queue.empty():
            try:
                yield progress_queue.get(timeout=0.25)
                last_progress = time.monotonic()
            except queue.Empty:
                if worker.is_alive() and time.monotonic() - last_progress >= _SSE_HEARTBEAT_SECONDS:
                    yield ("heartbeat", {"ts": time.time()})
                    last_progress = time.monotonic()
                continue
        worker.join()
        end_live_progress(user_id=uid)
        if chat_error:
            raise chat_error[0]
        result = chat_result["value"]
        result = _normalize_designer_chat_result(result)

        map_result, venue_map = run_map_stage_if_needed(
            message=message or "",
            design_result=result,
            assets=assets,
            attachment_block=attachment_block,
            template=template,
            user=user,
        )
        map_ran = map_result is not None

        if "preview_audit" in {s["id"] for s in tracker.snapshot()}:
            if include_audit and preview_audit_block:
                yield _step_event(tracker, "preview_audit", "active")
                if result.get("preview_audit_findings") is None:
                    result["preview_audit_findings"] = [
                        {"code": f.code, "message": f.message, "severity": f.severity}
                        for f in audit_compiled_proposal_preview(
                            result.get("html_markup") or html_markup,
                            result.get("css_stylesheet") or css_stylesheet,
                            result.get("js_script") or js_script,
                        )
                    ]
                yield _step_event(tracker, "preview_audit", "done")
            else:
                yield _step_event(tracker, "preview_audit", "skipped")

        if "venue_map" in {s["id"] for s in tracker.snapshot()}:
            if map_ran:
                yield _step_event(tracker, "venue_map", "active")
                if map_result and venue_map:
                    map_note = map_result.get("assistant_message") or "Interactive venue map updated."
                    result["assistant_message"] = (
                        f"{result['assistant_message']}\n\n— Map stage —\n{map_note}".strip()
                    )
                yield _step_event(tracker, "venue_map", "done")
            else:
                yield _step_event(tracker, "venue_map", "skipped")

        result["clarification_options"] = merge_clarification_options(
            result, map_result, map_ran=map_ran
        )
        result["map_stage_applied"] = map_ran
        if venue_map:
            result["venue_map_id"] = str(venue_map.id)
            result["venue_map_title"] = venue_map.title

    if admin_result:
        result.setdefault("map_stage_applied", False)
        result.setdefault("clarification_options", [])

    if result.get("model_api_error"):
        yield (
            "status",
            {
                "kind": "model_api_error",
                "message": (
                    "Design model API failed or timed out. "
                    "The live preview reflects the last successful edit when available."
                ),
                "partial": True,
            },
        )

    yield _step_event(tracker, "finalize", "active")
    yield from _yield_finalize_todo_events(
        result,
        status="active",
        live_progress_user_id=live_progress_user_id,
    )

    display_message = message
    if assets:
        names = ", ".join(a.original_name for a in assets)
        display_message = f"{message}\n[Attachments: {names}]".strip()

    new_history = list(history)
    now = timezone.now().isoformat()
    if display_message:
        new_history.append({"role": "user", "content": display_message, "ts": now})
    new_history.append(
        {
            "role": "assistant",
            "content": result["assistant_message"],
            "ts": timezone.now().isoformat(),
            **(_assistant_action_state(result)),
        }
    )

    yield from _yield_finalize_todo_events(
        result,
        status="done",
        live_progress_user_id=live_progress_user_id,
    )
    yield _step_event(tracker, "finalize", "done")

    if template_id:
        if template is None:
            template = ProposalTemplate.objects.filter(pk=template_id, designer=user).first()
        if template:
            template.chat_history_json = new_history
            template.html_markup = result["html_markup"]
            template.css_stylesheet = result["css_stylesheet"]
            template.js_script = result.get("js_script", js_script)
            template.save(
                update_fields=[
                    "chat_history_json",
                    "html_markup",
                    "css_stylesheet",
                    "js_script",
                    "updated_at",
                ]
            )

    yield (
        "done",
        {
            **result,
            "history": new_history,
            "preview_automation_used": bool(automation_report),
            "request_preview_automation": False,
            "work_plan": tracker.snapshot(),
            "agent_todos": result.get("agent_todos") or [],
            "attachments": DesignerMediaAssetSerializer(
                assets, many=True, context={"request": request} if request else {}
            ).data,
            "used_fixture": bool(settings.USE_FIXTURE_DEBATE or not settings.META_MODEL_API_KEY),
        },
    )


def run_designer_chat_sync(
    *, user: AbstractBaseUser, data: dict[str, Any], request: Any | None = None
) -> dict[str, Any]:
    final: dict[str, Any] | None = None
    for event, payload in iter_designer_chat(user=user, data=data, request=request):
        if event == "error":
            raise ValueError(payload.get("message") or "Chat failed")
        if event == "done":
            final = payload
    if not final:
        raise ValueError("Chat produced no response")
    return final


_SSE_PAD = ": " + ("." * 2048) + "\n"


def sse_preamble() -> str:
    """Opening bytes so browsers/proxies start streaming immediately (not after full response)."""
    return f"{_SSE_PAD}\n"


def sse_line(event: str, payload: dict[str, Any]) -> str:
    line = f": flush {time.time()}\nevent: {event}\ndata: {json.dumps(payload, separators=(',', ':'))}\n\n"
    if getattr(settings, "META_MODEL_DEBUG", False):
        preview = json.dumps(payload, ensure_ascii=False)
        if len(preview) > 500:
            preview = preview[:500] + "…"
        logger.debug("SSE emit event=%s payload=%s", event, preview)
    return line
