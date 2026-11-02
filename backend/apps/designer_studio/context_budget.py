"""Context window budgeting for Designer Studio agent calls."""
from __future__ import annotations

from django.conf import settings

DEFAULT_MAX_HISTORY_TURNS = 12
DEFAULT_MAX_TURN_CHARS = 2000
DEFAULT_MAX_HTML_CHARS = 10000
DEFAULT_MAX_CSS_CHARS = 6000
DEFAULT_MAX_JS_CHARS = 6000
DEFAULT_MAX_BLOCK_CHARS = 4000
DEFAULT_MAX_AUTOMATION_CHARS = 2800
DEFAULT_MAX_ATTACHMENT_BLOCK_CHARS = 2400
DEFAULT_MAX_MAP_KNOWLEDGE_CHARS = 3500
DEFAULT_MAX_CONTEXT_PREFIX_CHARS = 14000


def _int_setting(name: str, default: int) -> int:
    return int(getattr(settings, name, default))


def trim_chat_history(history: list[dict]) -> list[dict[str, str]]:
    max_turns = _int_setting("DESIGNER_MAX_HISTORY_TURNS", DEFAULT_MAX_HISTORY_TURNS)
    max_chars = _int_setting("DESIGNER_MAX_TURN_CHARS", DEFAULT_MAX_TURN_CHARS)
    trimmed: list[dict[str, str]] = []
    for turn in history[-max_turns:]:
        role = turn.get("role", "user")
        if role not in {"user", "assistant"}:
            continue
        content = str(turn.get("content", ""))[:max_chars]
        if len(content) < len(str(turn.get("content", ""))):
            content = content.rstrip() + "…"
        trimmed.append({"role": role, "content": content})
    return trimmed


def trim_template_fields(
    html: str,
    css: str,
    js: str,
) -> tuple[str, str, str]:
    h_max = _int_setting("DESIGNER_MAX_HTML_CHARS", DEFAULT_MAX_HTML_CHARS)
    c_max = _int_setting("DESIGNER_MAX_CSS_CHARS", DEFAULT_MAX_CSS_CHARS)
    j_max = _int_setting("DESIGNER_MAX_JS_CHARS", DEFAULT_MAX_JS_CHARS)
    return html[:h_max], css[:c_max], js[:j_max]


def trim_context_block(text: str, *, kind: str = "block") -> str:
    if not text:
        return ""
    limit = _int_setting("DESIGNER_MAX_BLOCK_CHARS", DEFAULT_MAX_BLOCK_CHARS)
    if kind == "automation":
        limit = _int_setting("DESIGNER_MAX_AUTOMATION_CHARS", DEFAULT_MAX_AUTOMATION_CHARS)
    elif kind == "attachment":
        limit = _int_setting("DESIGNER_MAX_ATTACHMENT_BLOCK_CHARS", DEFAULT_MAX_ATTACHMENT_BLOCK_CHARS)
    elif kind == "map":
        limit = _int_setting("DESIGNER_MAX_MAP_KNOWLEDGE_CHARS", DEFAULT_MAX_MAP_KNOWLEDGE_CHARS)
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def assemble_context_prefix(sections: list[str], *, max_total: int | None = None) -> str:
    """
    Join context sections without a single 4k cap on the whole blob (prevents attachment intent loss).
    Drops lowest-priority sections from the end when over max_total.
    """
    parts = [s.strip() for s in sections if s and s.strip()]
    if not parts:
        return ""
    total_limit = max_total or _int_setting(
        "DESIGNER_MAX_CONTEXT_PREFIX_CHARS", DEFAULT_MAX_CONTEXT_PREFIX_CHARS
    )
    combined = "\n\n".join(parts)
    if len(combined) <= total_limit:
        return combined
    # Priority: keep earlier sections (callers order: attachment, audit, automation, rules, map)
    while len(parts) > 1 and len("\n\n".join(parts)) > total_limit:
        parts.pop()
    combined = "\n\n".join(parts)
    if len(combined) <= total_limit:
        return combined
    return combined[: total_limit - 1].rstrip() + "…"
