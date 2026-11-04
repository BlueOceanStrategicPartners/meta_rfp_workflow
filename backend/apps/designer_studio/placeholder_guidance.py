"""Load Designer Studio placeholder guidance from Markdown (easy to edit without touching prompts)."""
from __future__ import annotations

import functools
import re
from pathlib import Path

from apps.designer_studio.models import MANDATORY_PLACEHOLDERS

_GUIDANCE_DIR = Path(__file__).resolve().parent / "guidance"
_TOKEN_LIST = ", ".join(MANDATORY_PLACEHOLDERS)
_ISO_DATE = re.compile(r"\b20\d{2}-\d{2}-\d{2}\b")
_DOLLAR_AMOUNT = re.compile(r"\$\s*\d[\d,]*")
# Marketing-style date ranges in visible copy (binding-driven fields must not use these as literals)
_MONTH_DATE_RANGE = re.compile(
    r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
    r"Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?"
    r"\s+\d{1,2}\s*[–—-]\s*(?:\d{1,2},?\s*)?(?:19|20)\d{2}\b",
    re.IGNORECASE,
)
_ROOM_KPI_HARDCODE = re.compile(
    r'(?:class="[^"]*room-block-(?:rooms-per-night|nights|room-nights)[^"]*"[^>]*>|'
    r'id="room-night-total"[^>]*>)\s*(?:<[^>]+>\s*)*(\d{2,})\s*<',
    re.IGNORECASE,
)
_PROPOSAL_FIELD_NEUTRAL = frozenset({"—", "-", "–", "0", "…", "..."})


def _visible_html_without_json_scripts(html: str) -> str:
    """Strip JSON script bodies so seed placeholders in scripts are not flagged."""
    out = re.sub(
        r'<script\b[^>]*\btype\s*=\s*[\'"]application/json[\'"][^>]*>.*?</script>',
        "",
        html or "",
        flags=re.IGNORECASE | re.DOTALL,
    )
    return _strip_tokens_for_scan(out)


def _hardcoded_proposal_field_copy(html: str) -> list[str]:
    issues: list[str] = []
    for m in re.finditer(
        r'data-proposal-field="([^"]+)"[^>]*>([^<]{4,200})</',
        html or "",
        flags=re.IGNORECASE,
    ):
        field, inner = m.group(1), m.group(2).strip()
        if inner in _PROPOSAL_FIELD_NEUTRAL:
            continue
        if field == "event_dates" and _MONTH_DATE_RANGE.search(inner):
            issues.append(
                f'[data-proposal-field="event_dates"] must not hardcode a sample date range '
                f'("{inner[:40]}…"); use neutral copy like "Your selected dates" — runtime hydrates from JSON.'
            )
        if field == "client_name" and re.search(r"[A-Za-z]{3,}", inner) and "{{client_name}}" not in inner:
            if inner.lower() not in ("your organization", "your company", "client name", "prepared for you"):
                issues.append(
                    f'[data-proposal-field="client_name"] must not hardcode "{inner[:48]}"; '
                    "use neutral copy or leave empty for JSON hydration."
                )
        if field == "xgboost_quote_breakdown" and _DOLLAR_AMOUNT.search(inner):
            issues.append(
                "[data-proposal-field=\"xgboost_quote_breakdown\"] must not hardcode dollar prices; "
                "use neutral copy — runtime hydrates from binding-xgboost-quote JSON."
            )
    return issues


@functools.lru_cache(maxsize=16)
def read_guidance_file(name: str) -> str:
    path = _GUIDANCE_DIR / name
    if not path.is_file():
        raise FileNotFoundError(f"Designer guidance missing: {path}")
    return path.read_text(encoding="utf-8")


def expand_guidance(name: str) -> str:
    text = read_guidance_file(name)
    return text.replace("{{MANDATORY_PLACEHOLDERS_LIST}}", _TOKEN_LIST)


def proposal_binding_schema_guidance() -> str:
    """Structured JSON binding knowledge for design + tool-loop agents."""
    return expand_guidance("proposal_binding_schema.md")


def design_agent_binding_guidance() -> str:
    return (
        expand_guidance("placeholder_binding.md")
        + "\n\n---\n\n"
        + proposal_binding_schema_guidance()
    )


def validation_placeholder_guidance() -> str:
    return (
        expand_guidance("placeholder_validation.md")
        + "\n\nBinding schema (validate template wiring against this):\n"
        + proposal_binding_schema_guidance()
    )


def repair_placeholder_guidance() -> str:
    return (
        "PLACEHOLDER REPAIR RULES:\n"
        + design_agent_binding_guidance()
    )


def save_validation_placeholder_guidance() -> str:
    return validation_placeholder_guidance()


def template_search_guidance() -> str:
    return expand_guidance("template_search.md")


def tool_loop_placeholder_guidance() -> str:
    return (
        "PROPOSAL JSON BINDINGS (default — override only if user explicitly requests another approach):\n"
        + proposal_binding_schema_guidance()
        + "\n\n---\n\n"
        + template_search_guidance()
    )


def _strip_tokens_for_scan(html: str) -> str:
    scan = html or ""
    for token in MANDATORY_PLACEHOLDERS:
        scan = scan.replace(token, "")
    return scan


def collect_placeholder_binding_issues(html: str) -> list[str]:
    """
    Deterministic checks aligned with guidance/placeholder_binding.md.
    """
    issues: list[str] = []
    body = html or ""
    is_proposal_template = (
        "{{verified_room_blocks}}" in body
        or "binding-event-dates" in body
        or "data-proposal-field" in body
        or "data-proposal-bind" in body
        or "proposal_binding_runtime" in body
        or "proposalBindingHydrate" in body
    )
    if is_proposal_template:
        if "proposal_client_bridge.js" not in body and "rfpProposalEmit" not in body:
            issues.append(
                "Include <script src=\"/proposal_client_bridge.js\"></script> once so client "
                "proposal clicks sync to the negotiation assistant (data-proposal-action / rfpProposalEmit)."
            )

    for token in MANDATORY_PLACEHOLDERS:
        count = body.count(token)
        if count > 1:
            issues.append(
                f"Placeholder {token} must appear exactly once (found {count})."
            )

    if "{{verified_room_blocks}}" in body:
        script_ok = (
            'id="binding-verified-room-blocks"' in body
            and "application/json" in body.lower()
        )
        if not script_ok:
            issues.append(
                "{{verified_room_blocks}} must be inside "
                '<script type="application/json" id="binding-verified-room-blocks">{{verified_room_blocks}}</script> '
                "(see guidance/proposal_binding_schema.md)."
            )
        if "data-proposal-bind=\"verified_room_blocks\"" not in body and "data-proposal-bind='verified_room_blocks'" not in body:
            issues.append(
                "Room block table needs an empty "
                '<tbody data-proposal-bind="verified_room_blocks"> for line_items[] hydration '
                "(see proposal_binding_schema.md)."
            )
        if "proposal_binding_runtime.js" not in body and "proposalBindingHydrate" not in body:
            issues.append(
                "Include <script src=\"/proposal_binding_runtime.js\"></script> once "
                "(unless user explicitly requested a custom JSON renderer)."
            )
        visible = _visible_html_without_json_scripts(body)
        if _ISO_DATE.search(visible):
            issues.append(
                "Remove hardcoded ISO dates (YYYY-MM-DD) from visible template copy; "
                "use {{event_dates}} JSON binding and data-proposal-field hydration."
            )
        if _MONTH_DATE_RANGE.search(visible):
            issues.append(
                "Remove hardcoded marketing date ranges (e.g. Nov 14 – 17, 2026) from visible HTML; "
                "event dates must come from {{event_dates}} JSON + [data-proposal-field=\"event_dates\"]."
            )
        if _ROOM_KPI_HARDCODE.search(visible):
            issues.append(
                "Room block KPI elements (.room-block-rooms-per-night, .room-block-nights, "
                ".room-block-room-nights, #room-night-total) must not hardcode sample counts "
                "(e.g. 120, 3) — use — or 0; proposal_binding_runtime.js hydrates from summary JSON."
            )
        issues.extend(_hardcoded_proposal_field_copy(body))
        if _DOLLAR_AMOUNT.search(visible):
            tbody_bind = "data-proposal-bind" in body and "verified_room_blocks" in body
            if tbody_bind and len(re.findall(r"<tr\b", body, flags=re.I)) > 2:
                issues.append(
                    "Do not hardcode dollar amounts in static <tr> rows — "
                    "line_items[] JSON hydrates tbody via proposal_binding_runtime.js."
                )

    return issues


def clear_guidance_cache() -> None:
    read_guidance_file.cache_clear()
