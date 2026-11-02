"""Prompt-alignment and targeted template checks (designer agent self-check)."""
from __future__ import annotations

import re
from typing import Any

_ISO_DATE = re.compile(r"\b20\d{2}-\d{2}-\d{2}\b")


def _conversation_text(message: str, history: list[dict[str, Any]] | None) -> str:
    parts = [message or ""]
    for turn in (history or [])[-8:]:
        if turn.get("role") in ("user", "assistant"):
            parts.append(str(turn.get("content") or ""))
    return "\n".join(parts).lower()


def user_wants_us_dates(message: str, history: list[dict[str, Any]] | None = None) -> bool:
    text = _conversation_text(message, history)
    return any(
        k in text
        for k in (
            "u.s. style",
            "us style",
            "u.s. date",
            "us date",
            "mm/dd",
            "american date",
            "united states date",
        )
    )


def collect_alignment_issues(
    *,
    message: str,
    history: list[dict[str, Any]] | None,
    html: str,
    css: str = "",
) -> list[str]:
    """Heuristic checks that the output matches explicit user instructions."""
    issues: list[str] = []
    body = html or ""
    # Strip placeholder tokens before scanning for hardcoded dates
    scan = body
    for token in (
        "{{event_dates}}",
        "{{verified_room_blocks}}",
        "{{client_name}}",
        "{{selected_map_svg}}",
    ):
        scan = scan.replace(token, "")

    if user_wants_us_dates(message, history):
        if _ISO_DATE.search(scan):
            issues.append(
                "User requested U.S. date formatting (MM/DD/YYYY). Remove ISO "
                "YYYY-MM-DD literals from visible copy; use {{event_dates}} and "
                "{{verified_room_blocks}} only."
            )
        if re.search(r"example\s+20\d{2}-\d{2}-\d{2}", scan, re.I):
            issues.append("Example dates in the template must use MM/DD/YYYY when user asked for U.S. style.")

    cta_issue = cta_hidden_by_css_issue(css or "", body)
    if cta_issue:
        issues.append(cta_issue)

    return issues


def cta_hidden_by_css_issue(css: str, html: str = "") -> str | None:
    """
    Flag only when accept CTA selectors are explicitly hidden — not map popups
    or unrelated classes containing the letters 'cta'.
    """
    for selector, body in _iter_css_rules(css):
        sel = selector.lower()
        if not _selector_targets_accept_cta(sel):
            continue
        if re.search(r"display\s*:\s*none", body, re.I):
            return (
                "Accept CTA is hidden via display:none on .proposal-cta (or equivalent); "
                "keep the accept button visible at default viewport."
            )
    if re.search(
        r'class=["\'][^"\']*proposal-cta[^"\']*["\'][^>]*style=["\'][^"\']*display\s*:\s*none',
        html,
        re.I,
    ):
        return "Accept CTA uses inline display:none; remove it so {{cta_accept_button}} is visible."
    return None


def _selector_targets_accept_cta(selector: str) -> bool:
    return (
        "proposal-cta" in selector
        or "cta-accept" in selector
        or "cta_accept" in selector
        or "{{cta_accept_button}}" in selector
    )


def _iter_css_rules(css: str):
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", css or ""):
        yield match.group(1).strip(), match.group(2)
