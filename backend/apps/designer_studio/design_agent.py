"""Designer Studio — Muse Spark 1.3 for generation and validation."""
from __future__ import annotations

import logging
from typing import Any, Callable

from django.conf import settings

from apps.designer_studio.models import REQUIRED_PLACEHOLDERS
from apps.designer_studio.services import compile_template, deterministic_template_checks
from apps.rfp_debate.meta_client import MetaModelClient

from .context_budget import trim_chat_history, trim_context_block, trim_template_fields
from .design_agent_tool_loop import (
    DesignerToolLoopRunner,
    PreviewEventCallback,
    TodoEventCallback,
    ToolEventCallback,
)
from .designer_langgraph import DesignerAgentGraph
from .template_alignment import collect_alignment_issues

logger = logging.getLogger(__name__)

DESIGNER_SYSTEM_PROMPT = (
    "You are the Proposal Template Architect for a hospitality RFP platform. "
    "You own BOTH the proposal HTML/CSS/JS AND coordinating the interactive venue map "
    "(users do not use a separate Map Studio — everything happens in this chat).\n\n"
    "WORKFLOW (two stages in one conversation):\n"
    "1) Proposal — layout, tokens, branding, media embeds.\n"
    "2) Venue map — after the proposal has {{selected_map_svg}} in a .venue-map-slot, "
    "guide the user to upload a floorplan image OR say they want a generic map. "
    "The platform may auto-build the interactive map on the next turn when they attach an image "
    "or say 'skip questions / just create'.\n\n"
    "FOLLOW-UP QUESTIONS (clarification_options):\n"
    "- Ask ONLY when a decision blocks progress (missing floorplan, ambiguous zone names, "
    "conflicting layout requests).\n"
    "- Do NOT ask about styling trivia if defaults are fine.\n"
    "- Offer 2–4 short clickable options; always include something like "
    "'Skip questions — just create it' when map-related.\n"
    "- If the user says skip / no questions / just create: do NOT ask more questions; "
    "produce the best template (and map slot) with reasonable defaults.\n\n"
    "MAP ATTRIBUTES YOU MAY NEED (only ask if missing and user did not say skip):\n"
    "- Floorplan image (upload) OR permission to use a generic schematic map.\n"
    "- Key zones to label (ballrooms, breakouts, foyer, outdoor).\n"
    "- Optional: capacity notes or photo galleries per zone.\n\n"
    "MAP LIBRARY:\n"
    "- Saved venue maps, default selection, delete, and remove-from-proposal are handled by the platform "
    "(Live preview → Venue maps, or chat commands like list maps / set default / delete map).\n"
    "- Do not direct users to a separate Map Studio.\n\n"
    "Return JSON only with keys: assistant_message (string), html_markup (string), "
    "css_stylesheet (string), js_script (string), "
    "clarification_options (optional string array of short clickable replies when you need input). "
    f"html_markup MUST include every binding token exactly once: "
    f"{', '.join(REQUIRED_PLACEHOLDERS)}. "
    "For {{selected_map_svg}}: use a venue-map-proposal section with "
    "<div class='venue-map-slot'>{{selected_map_svg}}</div> — the platform injects the "
    "interactive map at preview time; never replace the token with inline SVG only. "
    "Put interactivity in js_script (no inline onclick). "
    "Embed uploaded images/videos using the absolute URLs provided in the attachments block. "
    "Use semantic HTML5, responsive CSS Grid/Flexbox, and {{cta_accept_button}} for accept CTA.\n\n"
    "DATES & COPY:\n"
    "- Put all event dates in {{event_dates}} and rooming in {{verified_room_blocks}} — "
    "do not hardcode calendar dates in marketing copy.\n"
    "- If the user asks for U.S. style (MM/DD/YYYY), confirm in assistant_message but keep tokens; "
    "never show ISO YYYY-MM-DD in visible text or example badges.\n"
    "- Never hide .proposal-cta with display:none at default/desktop breakpoints "
    "(map popups may use .hidden{display:none} on non-CTA elements).\n\n"
    "VALIDATION (automatic — never delegate to the user):\n"
    "- The platform runs layout and template checks after every turn.\n"
    "- Fix placeholder, CTA visibility, date format, and responsive layout issues in your output.\n"
    "- Never tell the user to click Validate, run checks themselves, or ask them to fix validation errors.\n\n"
    "LIVE PREVIEW AUTOMATION:\n"
    "- The platform may attach scroll/click probe results from the Live preview panel — treat them as ground truth for layout/map bugs.\n"
    "- Never request another automation pass in the same turn; fix html/css/js from the report provided."
)

REPAIR_SYSTEM_PROMPT = (
    "You repair hospitality proposal HTML/CSS/JS templates before delivery. "
    "Return JSON only: assistant_message, html_markup, css_stylesheet, js_script, "
    "clarification_options (optional, usually empty). "
    f"Preserve every required placeholder exactly once: {', '.join(REQUIRED_PLACEHOLDERS)}. "
    "Fix all listed validation issues while honoring the user's original request."
)

VALIDATION_SYSTEM_PROMPT = (
    "You validate compiled hospitality proposal HTML/CSS/JS templates against the user's brief. "
    "Return JSON only: valid (boolean), issues (string array), summary (string). "
    "Check placeholders, media embeds, CTA visibility (accept button must not use display:none), "
    "responsive layout, JS safety, and that visible dates match the requested locale/format "
    "(U.S. MM/DD/YYYY vs ISO) when the brief mentions it."
)

SAVE_VALIDATION_SYSTEM_PROMPT = (
    "You validate hospitality proposal templates BEFORE SAVE to the template library. "
    "Return JSON only: valid (boolean), issues (string array), summary (string). "
    f"Source html_markup MUST keep each binding token exactly once: {', '.join(REQUIRED_PLACEHOLDERS)}. "
    "Tokens in source HTML are required — never flag them as missing or unresolved. "
    "Judge layout, CTA visibility (accept control visible at desktop), responsive CSS, and JS safety "
    "using the compiled preview (sample data already substituted). "
    "Only list REAL blockers that would break client preview or accept flow."
)

_SAVE_SPURIOUS_ISSUE_PHRASES = (
    "unresolved token",
    "compilation is incomplete",
    "no rendered dates to validate",
    "no media/map embed",
    "no media embed",
    "no map embed",
)


def _filter_save_muse_issues(issues: list[str]) -> list[str]:
    from .designer_validation import filter_muse_validation_issues

    return filter_muse_validation_issues(issues)


SAVE_REPAIR_BRIEF = (
    "Prepare this hospitality proposal template for save. "
    f"Preserve every required placeholder exactly once: {', '.join(REQUIRED_PLACEHOLDERS)}. "
    "Fix CTA visibility, responsive layout, token placement, and JS safety only."
)

WorkStepCallback = Callable[[str, str], None]


def _tick(on_work_step: WorkStepCallback | None, step_id: str, status: str) -> None:
    if on_work_step:
        on_work_step(step_id, status)


def resolve_designer_agent_mode() -> str:
    """Return effective agent mode; legacy full_document requires explicit opt-in."""
    requested = getattr(settings, "DESIGNER_AGENT_MODE", "tool_loop").strip().lower()
    if requested != "full_document":
        return "tool_loop"
    if getattr(settings, "DESIGNER_ALLOW_LEGACY_FULL_DOCUMENT", False):
        logger.warning(
            "DESIGNER_AGENT_MODE=full_document is deprecated and will be removed in a future release."
        )
        return "full_document"
    logger.warning(
        "DESIGNER_AGENT_MODE=full_document blocked (deprecated). Using tool_loop. "
        "Set DESIGNER_ALLOW_LEGACY_FULL_DOCUMENT=true to temporarily re-enable."
    )
    return "tool_loop"


def _merge_tool_traces(into: dict[str, Any], patch: dict[str, Any]) -> None:
    combined = list(into.get("tool_trace") or []) + list(patch.get("tool_trace") or [])
    if combined:
        into["tool_trace"] = combined[-40:]
        into["tool_steps"] = len(into["tool_trace"])


class DesignerStudioAgent:
    def __init__(self, client: MetaModelClient | None = None):
        self.client = client or MetaModelClient()
        self._tool_runner = DesignerToolLoopRunner(client=self.client)
        self._agent_graph = DesignerAgentGraph(client=self.client)

    def chat_turn(
        self,
        *,
        message: str,
        history: list[dict[str, str]],
        html_markup: str,
        css_stylesheet: str,
        js_script: str = "",
        attachment_block: str = "",
        venue_map_block: str = "",
        preview_audit_block: str = "",
        preview_automation_block: str = "",
        agent_rules_block: str = "",
        on_work_step: WorkStepCallback | None = None,
        on_tool_event: ToolEventCallback | None = None,
        on_todo_event: TodoEventCallback | None = None,
        on_preview_event: PreviewEventCallback | None = None,
        user_id: int | str | None = None,
        template_id: str | None = None,
    ) -> dict[str, Any]:
        mode = resolve_designer_agent_mode()
        if mode != "full_document":
            context_prefix = self._build_context_prefix(
                venue_map_block=venue_map_block,
                attachment_block=attachment_block,
                agent_rules_block=agent_rules_block,
                preview_audit_block=preview_audit_block,
                preview_automation_block=preview_automation_block,
            )
            _tick(on_work_step, "understand_brief", "active")
            result = self._agent_graph.run_edit_turn(
                message=message,
                history=history,
                html_markup=html_markup,
                css_stylesheet=css_stylesheet,
                js_script=js_script,
                context_prefix=context_prefix,
                user_id=user_id,
                template_id=template_id,
                on_work_step=on_work_step,
                on_tool_event=on_tool_event,
                on_todo_event=on_todo_event,
                on_preview_event=on_preview_event,
            )
            return result
        return self._chat_turn_full_document(
            message=message,
            history=history,
            html_markup=html_markup,
            css_stylesheet=css_stylesheet,
            js_script=js_script,
            attachment_block=attachment_block,
            venue_map_block=venue_map_block,
            preview_audit_block=preview_audit_block,
            preview_automation_block=preview_automation_block,
            agent_rules_block=agent_rules_block,
            on_work_step=on_work_step,
        )

    def _build_context_prefix(
        self,
        *,
        venue_map_block: str,
        attachment_block: str,
        agent_rules_block: str,
        preview_audit_block: str,
        preview_automation_block: str,
    ) -> str:
        venue_map_block = trim_context_block(venue_map_block)
        attachment_block = trim_context_block(attachment_block)
        rules_section = trim_context_block(agent_rules_block) if agent_rules_block else ""
        audit_section = trim_context_block(preview_audit_block) if preview_audit_block else ""
        automation_section = (
            trim_context_block(preview_automation_block, kind="automation")
            if preview_automation_block
            else ""
        )
        parts = [venue_map_block, attachment_block, rules_section, audit_section, automation_section]
        return trim_context_block("\n\n".join(p for p in parts if p.strip()))

    def _chat_turn_full_document(
        self,
        *,
        message: str,
        history: list[dict[str, str]],
        html_markup: str,
        css_stylesheet: str,
        js_script: str = "",
        attachment_block: str = "",
        venue_map_block: str = "",
        preview_audit_block: str = "",
        preview_automation_block: str = "",
        agent_rules_block: str = "",
        on_work_step: WorkStepCallback | None = None,
    ) -> dict[str, Any]:
        _tick(on_work_step, "understand_brief", "active")
        html_markup, css_stylesheet, js_script = trim_template_fields(
            html_markup, css_stylesheet, js_script
        )
        venue_map_block = trim_context_block(venue_map_block)
        attachment_block = trim_context_block(attachment_block)
        audit_section = trim_context_block(preview_audit_block) if preview_audit_block else ""
        rules_section = trim_context_block(agent_rules_block) if agent_rules_block else ""
        automation_section = (
            trim_context_block(preview_automation_block, kind="automation")
            if preview_automation_block
            else ""
        )
        user_payload = (
            f"{venue_map_block}\n\n"
            f"{attachment_block}\n\n"
            f"{rules_section}\n\n" if rules_section else ""
        ) + (
            f"{audit_section}\n\n" if audit_section else ""
        ) + (
            f"{automation_section}\n\n" if automation_section else ""
        ) + (
            f"Current html_markup:\n{html_markup or '<empty>'}\n\n"
            f"Current css_stylesheet:\n{css_stylesheet or '<empty>'}\n\n"
            f"Current js_script:\n{js_script or '<empty>'}\n\n"
            f"Designer request:\n{message.strip()[:4000]}"
        )
        user_payload = trim_context_block(user_payload)
        messages: list[dict[str, str]] = [
            {"role": "system", "content": DESIGNER_SYSTEM_PROMPT},
        ]
        for turn in trim_chat_history(history):
            messages.append({"role": turn["role"], "content": turn["content"]})
        messages.append({"role": "user", "content": user_payload})

        _tick(on_work_step, "understand_brief", "done")
        _tick(on_work_step, "draft_proposal", "active")
        raw = self.client.complete_json_messages(
            model_id=settings.META_MODEL_SPARK,
            messages=messages,
            fixture_kind="designer_chat",
        )
        _tick(on_work_step, "draft_proposal", "done")
        assistant = str(raw.get("assistant_message") or raw.get("message") or "").strip()
        html = str(raw.get("html_markup") or html_markup or "").strip()
        css = str(raw.get("css_stylesheet") or css_stylesheet or "").strip()
        js = str(raw.get("js_script") or js_script or "").strip()
        if not assistant:
            assistant = "Updated the proposal template layout, styles, and interactions."
        options = raw.get("clarification_options") or []
        if isinstance(options, list):
            clarification_options = [str(o) for o in options if o][:6]
        else:
            clarification_options = []
        if not clarification_options and "?" in assistant:
            lower = assistant.lower()
            if "floorplan" in lower or "floor plan" in lower or "venue map" in lower:
                clarification_options = [
                    "I'll upload a floorplan image",
                    "Use a generic layout — skip questions",
                    "Skip the map for now",
                ]
            else:
                clarification_options = [
                    "Use hero placement",
                    "Use gallery grid",
                    "Skip questions — just create it",
                ]
        result = {
            "assistant_message": assistant,
            "html_markup": html,
            "css_stylesheet": css,
            "js_script": js,
            "clarification_options": clarification_options,
            "model_id": settings.META_MODEL_SPARK,
        }
        return self._finalize_with_self_check(
            message=message,
            history=history,
            result=result,
            on_work_step=on_work_step,
        )

    def _finalize_with_self_check(
        self,
        *,
        message: str,
        history: list[dict[str, str]],
        result: dict[str, Any],
        on_work_step: WorkStepCallback | None = None,
        on_tool_event: ToolEventCallback | None = None,
        on_todo_event: TodoEventCallback | None = None,
        on_preview_event: PreviewEventCallback | None = None,
    ) -> dict[str, Any]:
        """Deterministic + Muse validation; repair loop until clean or max passes."""
        if result.get("model_api_error") or (
            result.get("tool_loop_exhausted") and not (result.get("tool_trace") or [])
        ):
            _tick(on_work_step, "validate_repair", "skipped")
            return result
        max_passes = max(1, int(getattr(settings, "DESIGNER_SELF_CHECK_MAX_PASSES", 4)))
        current = dict(result)
        repair_passes = 0
        _tick(on_work_step, "validate_repair", "active")

        for _ in range(max_passes):
            issues = self._gather_validation_issues(message, history, current)
            if not issues:
                current["self_check"] = {"valid": True, "issues": [], "repair_passes": repair_passes}
                current.pop("validation_warnings", None)
                _tick(on_work_step, "validate_repair", "done")
                return current

            current = self._repair_turn(
                message,
                history,
                issues,
                current,
                on_tool_event=on_tool_event,
                on_todo_event=on_todo_event,
                on_preview_event=on_preview_event,
            )
            current["clarification_options"] = []
            repair_passes += 1

        remaining = self._gather_validation_issues(message, history, current)
        current["self_check"] = {
            "valid": not remaining,
            "issues": remaining,
            "repair_passes": repair_passes,
        }
        if remaining:
            current["validation_warnings"] = remaining
        else:
            current.pop("validation_warnings", None)
        _tick(on_work_step, "validate_repair", "done")
        return current

    def _gather_validation_issues(
        self,
        message: str,
        history: list[dict[str, str]],
        result: dict[str, Any],
    ) -> list[str]:
        from .designer_validation import gather_chat_validation_issues

        return gather_chat_validation_issues(
            message=message,
            history=history,
            result=result,
            client=self.client,
        )

    def _collect_all_issues(
        self,
        message: str,
        history: list[dict[str, str]],
        result: dict[str, Any],
    ) -> list[str]:
        html = result.get("html_markup") or ""
        css = result.get("css_stylesheet") or ""
        js = result.get("js_script") or ""
        issues = deterministic_template_checks(html, css, js)
        issues.extend(
            collect_alignment_issues(message=message, history=history, html=html, css=css)
        )
        # de-dupe preserving order
        seen: set[str] = set()
        unique: list[str] = []
        for item in issues:
            if item not in seen:
                seen.add(item)
                unique.append(item)
        return unique

    def _repair_turn(
        self,
        message: str,
        history: list[dict[str, str]],
        issues: list[str],
        draft: dict[str, Any],
        on_tool_event: ToolEventCallback | None = None,
        on_todo_event: TodoEventCallback | None = None,
        on_preview_event: PreviewEventCallback | None = None,
    ) -> dict[str, Any]:
        if resolve_designer_agent_mode() != "full_document":
            repaired = self._tool_runner.run_repair(
                original_message=message,
                issues=issues,
                html_markup=draft.get("html_markup") or "",
                css_stylesheet=draft.get("css_stylesheet") or "",
                js_script=draft.get("js_script") or "",
                on_tool_event=on_tool_event,
                on_todo_event=None,
                on_preview_event=on_preview_event,
            )
            assistant = str(repaired.get("assistant_message") or draft.get("assistant_message") or "").strip()
            merged = {
                **draft,
                "assistant_message": assistant,
                "html_markup": repaired.get("html_markup") or draft.get("html_markup") or "",
                "css_stylesheet": repaired.get("css_stylesheet") or draft.get("css_stylesheet") or "",
                "js_script": repaired.get("js_script") or draft.get("js_script") or "",
                "clarification_options": [],
            }
            _merge_tool_traces(merged, repaired)
            if repaired.get("model_api_error"):
                merged["model_api_error"] = True
                prior = str(draft.get("assistant_message") or "").strip()
                if prior and not prior.lower().startswith("design model api"):
                    merged["assistant_message"] = (
                        f"{prior}\n\n"
                        "(Automatic validation repair timed out — preview shows your last successful edit.)"
                    ).strip()
                elif (merged.get("html_markup") or "").strip():
                    merged["assistant_message"] = (
                        "Your proposal template was updated. "
                        "Automatic validation repair timed out; you can Continue or edit manually."
                    )
            return merged

        brief = (
            f"Original user request:\n{message.strip()}\n\n"
            f"Issues to fix:\n" + "\n".join(f"- {i}" for i in issues[:12]) + "\n\n"
            f"Current html_markup:\n{draft.get('html_markup', '')[:12000]}\n\n"
            f"Current css_stylesheet:\n{draft.get('css_stylesheet', '')[:8000]}\n\n"
            f"Current js_script:\n{draft.get('js_script', '')[:6000]}\n"
        )
        messages: list[dict[str, str]] = [
            {"role": "system", "content": REPAIR_SYSTEM_PROMPT},
            {"role": "user", "content": brief},
        ]
        raw = self.client.complete_json_messages(
            model_id=settings.META_MODEL_SPARK,
            messages=messages,
            fixture_kind="designer_chat",
        )
        assistant = str(raw.get("assistant_message") or draft.get("assistant_message") or "").strip()
        return {
            **draft,
            "assistant_message": assistant,
            "html_markup": str(raw.get("html_markup") or draft.get("html_markup") or ""),
            "css_stylesheet": str(raw.get("css_stylesheet") or draft.get("css_stylesheet") or ""),
            "js_script": str(raw.get("js_script") or draft.get("js_script") or ""),
            "clarification_options": [],
        }

    def prepare_for_save(
        self,
        html_markup: str,
        css_stylesheet: str,
        js_script: str = "",
    ) -> dict[str, Any]:
        """Deterministic gate before persisting — LangGraph validator already ran on chat turns."""
        issues = deterministic_template_checks(html_markup, css_stylesheet, js_script)
        if issues:
            raise ValueError("; ".join(issues[:8]))
        return {
            "assistant_message": "",
            "html_markup": html_markup,
            "css_stylesheet": css_stylesheet,
            "js_script": js_script,
            "repair_passes": 0,
        }

    def _gather_save_issues(self, draft: dict[str, Any]) -> list[str]:
        html = draft.get("html_markup") or ""
        css = draft.get("css_stylesheet") or ""
        js = draft.get("js_script") or ""
        review = self.validate_layout_for_save(
            html_markup=html,
            css_stylesheet=css,
            js_script=js,
        )
        return review.get("issues") or []

    def validate_layout_for_save(
        self,
        *,
        html_markup: str,
        css_stylesheet: str,
        js_script: str = "",
    ) -> dict[str, Any]:
        deterministic_issues = deterministic_template_checks(html_markup, css_stylesheet, js_script)
        if deterministic_issues:
            return {
                "valid": False,
                "issues": deterministic_issues,
                "summary": "; ".join(deterministic_issues),
            }

        compiled = compile_template(html_markup, css_stylesheet, js_script=js_script)
        messages = [
            {"role": "system", "content": SAVE_VALIDATION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Template HTML (with binding tokens):\n{html_markup[:10000]}\n\n"
                    f"CSS:\n{css_stylesheet[:6000]}\n\n"
                    f"JS:\n{js_script[:6000]}\n\n"
                    f"Compiled preview (sample data applied):\n{compiled[:10000]}"
                ),
            },
        ]
        raw = self.client.complete_json_messages(
            model_id=settings.META_MODEL_SPARK,
            messages=messages,
            fixture_kind="designer_save_validate",
        )
        muse_issues = _filter_save_muse_issues([str(i) for i in (raw.get("issues") or []) if i])
        summary = str(raw.get("summary") or "").strip()
        if summary and not muse_issues and not raw.get("valid", True):
            if not any(p in summary.lower() for p in _SAVE_SPURIOUS_ISSUE_PHRASES):
                muse_issues = [summary]
            else:
                summary = ""

        valid = not muse_issues
        return {
            "valid": valid,
            "issues": muse_issues,
            "summary": summary or ("Template passes save validation." if valid else "Template needs fixes."),
        }

    def validate_layout(
        self,
        *,
        html_markup: str,
        css_stylesheet: str,
        js_script: str = "",
        compiled_html: str | None = None,
        user_brief: str = "",
    ) -> dict[str, Any]:
        from .designer_validation import muse_validate_chat_layout

        _ = compiled_html  # compiled inside muse_validate_chat_layout
        return muse_validate_chat_layout(
            html_markup=html_markup,
            css_stylesheet=css_stylesheet,
            js_script=js_script,
            user_brief=user_brief,
            client=self.client,
        )
