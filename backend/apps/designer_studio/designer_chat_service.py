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
from .designer_graph_state import resolve_template_langgraph_thread_id
from .designer_chat_guards import (
    build_preview_audit_block,
    try_floorplan_attachment_reminder,
    user_message_reports_preview_issue,
)
from .attachment_context import (
    AttachmentRole,
    classify_attachments,
    default_message_for_attachments,
    floorplan_image_urls,
    format_assets_for_agent,
    is_pasted_screenshot_name,
    patch_metadata_roles,
)
from .designer_work_plan import (
    WorkPlanTracker,
    build_work_plan,
)
from .designer_live_progress import (
    begin_live_progress,
    clear_designer_agent_cancel,
    end_live_progress,
    is_designer_agent_cancel_requested,
    patch_live_progress,
)
from .models import DesignerMediaAsset, ProposalTemplate
from .preview_automation_context import (
    format_preview_automation_for_agent,
    parse_automation_report,
    validate_automation_request,
)
from .preview_audit import audit_compiled_proposal_preview
from .proposal_template_normalize import normalize_proposal_template_fields
from .finalize_validation import run_systematic_finalize_validation
from .template_workspace import TemplateWorkspace
from .serializers import DesignerMediaAssetSerializer

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

    ledger = result.get("edit_ledger")
    todos = list(result.get("agent_todos") or [])[:16]
    graph = result.get("tool_session_graph") or {}
    msg = str(result.get("assistant_message") or "").strip()
    has_session = bool(ledger or todos or graph) or int(result.get("tool_steps") or 0) > 0
    if has_session:
        todos_complete = bool(todos) and all(
            str(t.get("status") or "") in ("done", "skipped") for t in todos
        )
        if todos_complete and not result.get("partial_completion"):
            todos = []
        state: dict[str, Any] = {
            "agent_todos": todos,
            "edit_ledger": ledger if isinstance(ledger, dict) else {},
            "tool_session_graph": graph if isinstance(graph, dict) else {},
            "last_assistant_message": msg[:500],
        }
        prior_user = str(result.get("prior_user_request") or "")[:2000]
        if prior_user:
            state["prior_user_request"] = prior_user
        return {"action_state": state}

    return {}


from .single_file_template import template_storage_mode


def _normalize_designer_chat_result(result: dict[str, Any]) -> dict[str, Any]:
    """Drop stale partial/retry UI when the template was updated successfully."""
    out = dict(result)
    html = str(out.get("html_markup") or "")
    if template_storage_mode(html, str(out.get("css_stylesheet") or ""), str(out.get("js_script") or "")) == "single":
        if html.strip():
            out["css_stylesheet"] = ""
            out["js_script"] = ""
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
    graph_thread_id = ""

    assets = list(
        DesignerMediaAsset.objects.filter(id__in=attachment_ids, designer=user)
    )
    patch_metadata_roles(assets, message)
    attachment_block = format_assets_for_agent(assets, message=message)
    effective_message = default_message_for_attachments(message, assets)
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

    include_audit = user_message_reports_preview_issue(effective_message) or bool(
        data.get("include_preview_audit")
    )

    template = None
    if template_id:
        template = ProposalTemplate.objects.filter(pk=template_id, designer=user).first()

    admin_result = None

    short_path = False
    reminder = None
    if message:
        reminder = try_floorplan_attachment_reminder(message=message, assets=assets)
        if reminder:
            short_path = True

    plan_steps = build_work_plan(
        message=effective_message or "Update the proposal template",
        include_preview_audit=include_audit and not short_path,
        short_path=short_path,
    )
    tracker = WorkPlanTracker(plan_steps)
    yield ("plan", {"steps": tracker.snapshot()})

    live_progress_user_id: int | None = None

    if reminder:
        yield _step_event(tracker, "understand_brief", "active")
        result = {
            **reminder,
            "html_markup": html_markup,
            "css_stylesheet": "",
            "js_script": "",
            "self_check": {"valid": True, "issues": []},
        }
        yield _step_event(tracker, "understand_brief", "done")
    else:
        preview_audit_block = ""
        if include_audit:
            preview_audit_block = build_preview_audit_block(
                html_markup, css_stylesheet, js_script
            )
        preview_automation_block = format_preview_automation_for_agent(automation_report)
        from apps.venue_map_studio.map_knowledge_tools import build_map_knowledge_for_proposal_agent

        floorplan_urls = floorplan_image_urls(effective_message, assets)
        map_knowledge_block = build_map_knowledge_for_proposal_agent(
            floorplan_urls=floorplan_urls or None
        )
        rules = retrieve_relevant_rules(user.id, effective_message or "Update proposal template")
        agent_rules_block = format_rules_for_agent(rules)

        agent = DesignerStudioAgent()
        if template_id:
            stored = ""
            if template:
                stored = str(getattr(template, "langgraph_thread_id", "") or "").strip()
            graph_thread_id = resolve_template_langgraph_thread_id(
                user_id=getattr(user, "pk", None),
                template_id=str(template_id),
                stored_thread_id=stored or None,
            )
        progress_queue: queue.Queue[tuple[str, dict[str, Any]]] = queue.Queue()
        preview_last_mono = 0.0
        uid = getattr(user, "pk", None)
        live_progress_user_id = uid
        begin_live_progress(user_id=uid)
        try:
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
                        message=effective_message or "Update the proposal template.",
                        history=history,
                        html_markup=html_markup,
                        css_stylesheet=css_stylesheet,
                        js_script=js_script,
                        attachment_block=attachment_block,
                        map_knowledge_block=map_knowledge_block,
                        preview_audit_block=preview_audit_block,
                        preview_automation_block=preview_automation_block,
                        agent_rules_block=agent_rules_block,
                        user_id=getattr(user, "pk", None),
                        template_id=str(template_id) if template_id else None,
                        graph_thread_id=graph_thread_id or None,
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
                if uid is not None and is_designer_agent_cancel_requested(user_id=uid):
                    break
                try:
                    yield progress_queue.get(timeout=0.25)
                    last_progress = time.monotonic()
                except queue.Empty:
                    if worker.is_alive() and time.monotonic() - last_progress >= _SSE_HEARTBEAT_SECONDS:
                        yield ("heartbeat", {"ts": time.time()})
                        last_progress = time.monotonic()
                    continue
            worker.join(timeout=0.5)
            cancelled = uid is not None and is_designer_agent_cancel_requested(user_id=uid)
            if cancelled:
                clear_designer_agent_cancel(user_id=uid)
                yield ("cancelled", {"message": "Design agent stopped."})
                return
            if chat_error:
                raise chat_error[0]
            result = chat_result["value"]
            result = _normalize_designer_chat_result(result)
            if result.get("agent_cancelled"):
                if uid is not None:
                    clear_designer_agent_cancel(user_id=uid)
                yield ("cancelled", {"message": "Design agent stopped."})
                return
        finally:
            end_live_progress(user_id=uid)

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

    norm_html, norm_css, norm_js = normalize_proposal_template_fields(
        str(result.get("html_markup") or html_markup),
        str(result.get("css_stylesheet") or css_stylesheet),
        str(result.get("js_script") or js_script),
    )
    result["html_markup"] = norm_html
    result["css_stylesheet"] = norm_css
    result["js_script"] = norm_js

    if getattr(settings, "DESIGNER_FINALIZE_VALIDATION_ENABLED", True):
        finalize_ws = TemplateWorkspace(
            html_markup=norm_html,
            css_stylesheet=norm_css,
            js_script=norm_js,
        )
        finalize_review = run_systematic_finalize_validation(
            workspace=finalize_ws,
            message=effective_message,
            history=history,
        )
        result["finalize_validation"] = finalize_review
        yield (
            "status",
            {
                "kind": "finalize_validation",
                "valid": bool(finalize_review.get("valid")),
                "issue_count": len(finalize_review.get("issues") or []),
                "summary": str(finalize_review.get("summary") or "")[:500],
            },
        )
        if not finalize_review.get("valid"):
            blockers = list(finalize_review.get("issues") or [])[:16]
            result["validation_blockers"] = blockers
            result["partial_completion"] = True
            result["continuation_recommended"] = True
            remaining = list(result.get("remaining_items") or [])
            remaining.append("Fix finalize validation issues (pool edit pass)")
            result["remaining_items"] = remaining[:12]

    preview_target = data.get("preview_target")
    has_preview_target = isinstance(preview_target, dict) and bool(preview_target)
    display_message = (data.get("display_message") or "").strip()
    if not display_message and not has_preview_target:
        display_message = effective_message
    if assets:
        roles = classify_attachments(effective_message, assets)
        role_bits = []
        for a in assets:
            r = roles.get(str(a.id), AttachmentRole.PROPOSAL_MEDIA)
            role_bits.append(f"{a.original_name} ({r.value})")
        names = ", ".join(role_bits)
        attachment_line = f"[Attachments: {names}]"
        display_message = (
            f"{display_message}\n{attachment_line}".strip()
            if display_message
            else attachment_line
        )

    new_history = list(history)
    now = timezone.now().isoformat()
    if display_message or has_preview_target:
        user_turn: dict[str, Any] = {"role": "user", "content": display_message, "ts": now}
        if has_preview_target:
            user_turn["preview_target"] = preview_target
        new_history.append(user_turn)
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
            template.html_markup = norm_html
            template.css_stylesheet = norm_css
            template.js_script = norm_js
            ck_thread = str(result.get("checkpoint_thread_id") or graph_thread_id or "").strip()
            ck_id = str(result.get("graph_checkpoint_id") or "").strip()
            if ck_thread:
                template.langgraph_thread_id = ck_thread[:160]
            if ck_id:
                template.langgraph_checkpoint_id = ck_id[:128]
            update_fields = [
                "chat_history_json",
                "html_markup",
                "css_stylesheet",
                "js_script",
                "updated_at",
            ]
            if ck_thread:
                update_fields.append("langgraph_thread_id")
            if ck_id:
                update_fields.append("langgraph_checkpoint_id")
            template.save(update_fields=update_fields)

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
