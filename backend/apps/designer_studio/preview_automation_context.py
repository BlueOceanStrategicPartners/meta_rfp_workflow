"""Format client-side Live preview automation reports for the design agent."""
from __future__ import annotations

import json
from typing import Any

from .context_budget import trim_context_block

from django.conf import settings

from .context_budget import trim_context_block

MAX_AUTOMATION_DEPTH = int(getattr(settings, "DESIGNER_PREVIEW_AUTOMATION_MAX_DEPTH", 1))


def validate_automation_request(
    *,
    preview_automation_depth: int,
    preview_automation_report: dict[str, Any] | None,
    message: str,
) -> str | None:
    """Return error message if automation chain is invalid (loop guard)."""
    depth = max(0, int(preview_automation_depth or 0))
    if depth > MAX_AUTOMATION_DEPTH:
        return "Preview automation depth exceeded — send a normal message to continue."
    if depth >= 1 and not (message or "").strip():
        return "Automation follow-up requires a user message; automation-only turns are blocked."
    if preview_automation_report and depth > MAX_AUTOMATION_DEPTH:
        return "Too many preview automation passes for one request."
    return None


def should_run_preview_automation(
    *,
    message: str,
    include_preview_audit: bool,
    preview_automation_report: dict[str, Any] | None,
) -> bool:
    if preview_automation_report:
        return False
    if include_preview_audit:
        return True
    from .designer_chat_guards import user_message_reports_preview_issue

    return user_message_reports_preview_issue(message)


def format_preview_automation_for_agent(report: dict[str, Any] | None) -> str:
    if not report:
        return ""
    if report.get("error"):
        body = (
            "LIVE PREVIEW AUTOMATION (client panel — error):\n"
            f"- {report.get('error')}\n"
            "Fix layout/map issues using deterministic audit; do not request another automation pass."
        )
        return trim_context_block(body, kind="automation")

    interactions = report.get("interactions") or []
    lines = [
        "LIVE PREVIEW AUTOMATION (client panel — scroll/click probes on compiled preview):",
        f"- ok: {report.get('ok', False)} · duration_ms: {report.get('duration_ms', 0)}",
    ]
    vp = report.get("viewport") or {}
    if vp:
        lines.append(f"- viewport: {vp.get('w')}×{vp.get('h')}")
    scroll = report.get("scroll") or {}
    if scroll:
        gap = scroll.get("trailingGapPx")
        lines.append(
            f"- document height: {scroll.get('docHeight')} · can_scroll: {scroll.get('canScroll')}"
        )
        if gap is not None:
            lines.append(
                f"- trailing gap below content: {gap}px "
                f"(content_bottom: {scroll.get('contentBottom', '—')})"
            )
    elements = report.get("elements") or {}
    if elements:
        lines.append(
            "- elements: "
            f"hero_visible={elements.get('heroVisible')} "
            f"cta_visible={elements.get('ctaVisible')} "
            f"map_popup_open_on_load={elements.get('mapPopupOpenOnLoad')} "
            f"map_zones={elements.get('mapZoneCount')}"
        )
    for step in interactions[:8]:
        if not isinstance(step, dict):
            continue
        flag = "ok" if step.get("ok") else "FAIL"
        lines.append(f"- [{flag}] {step.get('action')}: {step.get('detail') or ''}".strip())

    lines.append(
        "Use these probe results to fix html/css/js. Do not ask the user to run preview tools."
    )
    text = "\n".join(lines)
    return trim_context_block(text, kind="automation")


def parse_automation_report(raw: Any) -> dict[str, Any] | None:
    if not raw:
        return None
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            return None
    return None
