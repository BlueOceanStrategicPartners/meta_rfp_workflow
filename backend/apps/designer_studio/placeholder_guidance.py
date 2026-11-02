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
        scan = _strip_tokens_for_scan(body)
        if _ISO_DATE.search(scan):
            issues.append(
                "Remove hardcoded ISO dates (YYYY-MM-DD) from visible template copy; "
                "use {{event_dates}} JSON binding and data-proposal-field hydration."
            )
        if _DOLLAR_AMOUNT.search(scan):
            tbody_bind = "data-proposal-bind" in body and "verified_room_blocks" in body
            if tbody_bind and len(re.findall(r"<tr\b", body, flags=re.I)) > 2:
                issues.append(
                    "Do not hardcode dollar amounts in static <tr> rows — "
                    "line_items[] JSON hydrates tbody via proposal_binding_runtime.js."
                )

    return issues


def clear_guidance_cache() -> None:
    read_guidance_file.cache_clear()
