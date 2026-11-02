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
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"
