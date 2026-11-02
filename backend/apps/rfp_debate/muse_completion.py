"""Checkmate-style validation for Muse structured JSON payloads (terminal states per fixture_kind).

Happy path: parsed dict passes schema + kind-specific validator.
Edge: empty/partial fields → validation error → fixture fallback or MetaModelAPIError.
Worst case: HTTP/parse failure handled in meta_client before this layer runs.
"""
from __future__ import annotations

import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)


class MuseStructuredValidationError(ValueError):
    """Model returned JSON that does not satisfy the expected contract."""

    def __init__(self, code: str, message: str, *, fixture_kind: str | None = None):
        super().__init__(message)
        self.code = code
        self.fixture_kind = fixture_kind


Validator = Callable[[dict[str, Any]], dict[str, Any]]


def _require_keys(raw: dict[str, Any], keys: tuple[str, ...], *, fixture_kind: str) -> None:
    missing = [k for k in keys if k not in raw]
    if missing:
        raise MuseStructuredValidationError(
            "missing_keys",
            f"Missing required keys {missing} for {fixture_kind}",
            fixture_kind=fixture_kind,
        )


def _validate_tool_loop(raw: dict[str, Any], *, fixture_kind: str) -> dict[str, Any]:
    kind = str(raw.get("kind") or "").strip().lower()
    if kind not in ("finish", "tools", "tool"):
        raise MuseStructuredValidationError(
            "invalid_kind",
            f"Tool loop kind must be finish|tools|tool, got {kind!r}",
            fixture_kind=fixture_kind,
        )
    if kind == "finish":
        return raw
    if kind == "tool":
        if not str(raw.get("tool") or "").strip():
            raise MuseStructuredValidationError(
                "missing_tool",
                "Single-tool response missing tool name",
                fixture_kind=fixture_kind,
            )
        return raw
    tools = raw.get("tools")
    if not isinstance(tools, list) or not tools:
        raise MuseStructuredValidationError(
            "empty_tools_batch",
            "tools kind requires non-empty tools array",
            fixture_kind=fixture_kind,
        )
    for idx, item in enumerate(tools):
        if not isinstance(item, dict) or not str(item.get("tool") or "").strip():
            raise MuseStructuredValidationError(
                "invalid_tool_spec",
                f"tools[{idx}] must be an object with tool name",
                fixture_kind=fixture_kind,
            )
    return raw


def _validate_execution_plan(raw: dict[str, Any], *, fixture_kind: str) -> dict[str, Any]:
    _require_keys(raw, ("steps",), fixture_kind=fixture_kind)
    steps = raw.get("steps")
    if not isinstance(steps, list) or not steps:
        raise MuseStructuredValidationError(
            "empty_steps",
            "Execution plan must include at least one step",
            fixture_kind=fixture_kind,
        )
    return raw


def _validate_work_plan_labels(raw: dict[str, Any], *, fixture_kind: str) -> dict[str, Any]:
    labels = raw.get("labels")
    if not isinstance(labels, dict):
        raise MuseStructuredValidationError(
            "invalid_labels",
            "Work plan labels must be an object",
            fixture_kind=fixture_kind,
        )
    return raw


def _validate_designer_chat(raw: dict[str, Any], *, fixture_kind: str) -> dict[str, Any]:
    _require_keys(
        raw,
        ("assistant_message", "html_markup", "css_stylesheet", "js_script"),
        fixture_kind=fixture_kind,
    )
    return raw


def _validate_validation_result(raw: dict[str, Any], *, fixture_kind: str) -> dict[str, Any]:
    _require_keys(raw, ("valid", "issues"), fixture_kind=fixture_kind)
    if not isinstance(raw.get("issues"), list):
        raise MuseStructuredValidationError(
            "invalid_issues",
            "issues must be an array",
            fixture_kind=fixture_kind,
        )
    return raw


def _validate_rule_conflict(raw: dict[str, Any], *, fixture_kind: str) -> dict[str, Any]:
    if "has_conflict" not in raw:
        raise MuseStructuredValidationError(
            "missing_has_conflict",
            "Rule conflict response requires has_conflict",
            fixture_kind=fixture_kind,
        )
    return raw


def _validate_asset_meta(raw: dict[str, Any], *, fixture_kind: str) -> dict[str, Any]:
    if not str(raw.get("description") or "").strip():
        raise MuseStructuredValidationError(
            "missing_description",
            "Asset meta requires description",
            fixture_kind=fixture_kind,
        )
    return raw


def _validate_voice_reply(raw: dict[str, Any], *, fixture_kind: str) -> dict[str, Any]:
    reply = raw.get("reply") or raw.get("message")
    if not isinstance(reply, str) or not reply.strip():
        raise MuseStructuredValidationError(
            "missing_reply",
            "Voice reply JSON requires non-empty reply string",
            fixture_kind=fixture_kind,
        )
    return raw


def _validate_rfp_extraction(raw: dict[str, Any], *, fixture_kind: str) -> dict[str, Any]:
    from .meta_client import parse_extraction

    if not isinstance(raw, dict) or not raw:
        raise MuseStructuredValidationError(
            "empty_extraction",
            "RFP extraction must be a non-empty object",
            fixture_kind=fixture_kind,
        )
    try:
        parse_extraction(raw)
    except Exception as exc:
        raise MuseStructuredValidationError(
            "extraction_schema",
            f"RFP extraction failed Pydantic validation: {exc}",
            fixture_kind=fixture_kind,
        ) from exc
    return raw


def _validate_rfp_critique(raw: dict[str, Any], *, fixture_kind: str) -> dict[str, Any]:
    from .meta_client import parse_critique

    _require_keys(raw, ("discrepancy_flags",), fixture_kind=fixture_kind)
    if not isinstance(raw.get("discrepancy_flags"), list):
        raise MuseStructuredValidationError(
            "invalid_flags",
            "discrepancy_flags must be an array",
            fixture_kind=fixture_kind,
        )
    try:
        parse_critique(raw)
    except Exception as exc:
        raise MuseStructuredValidationError(
            "critique_schema",
            f"Critique failed validation: {exc}",
            fixture_kind=fixture_kind,
        ) from exc
    return raw


FIXTURE_VALIDATORS: dict[str, Validator] = {
    "designer_tool_loop": lambda r: _validate_tool_loop(r, fixture_kind="designer_tool_loop"),
    "designer_tool_loop_repair": lambda r: _validate_tool_loop(
        r, fixture_kind="designer_tool_loop_repair"
    ),
    "designer_execution_plan": lambda r: _validate_execution_plan(
        r, fixture_kind="designer_execution_plan"
    ),
    "designer_work_plan": lambda r: _validate_work_plan_labels(r, fixture_kind="designer_work_plan"),
    "designer_chat": lambda r: _validate_designer_chat(r, fixture_kind="designer_chat"),
    "designer_validate": lambda r: _validate_validation_result(r, fixture_kind="designer_validate"),
    "designer_save_validate": lambda r: _validate_validation_result(
        r, fixture_kind="designer_save_validate"
    ),
    "designer_rule_validate": lambda r: _validate_rule_conflict(r, fixture_kind="designer_rule_validate"),
    "designer_asset_meta": lambda r: _validate_asset_meta(r, fixture_kind="designer_asset_meta"),
    "voice_reply": lambda r: _validate_voice_reply(r, fixture_kind="voice_reply"),
    "rfp_extraction": lambda r: _validate_rfp_extraction(r, fixture_kind="rfp_extraction"),
    "rfp_critique": lambda r: _validate_rfp_critique(r, fixture_kind="rfp_critique"),
}


def validate_muse_structured_payload(
    raw: dict[str, Any],
    *,
    fixture_kind: str | None,
) -> dict[str, Any]:
    """Validate parsed Muse JSON; raise MuseStructuredValidationError on contract breach."""
    if not fixture_kind:
        return raw
    validator = FIXTURE_VALIDATORS.get(fixture_kind)
    if not validator:
        return raw
    try:
        return validator(raw)
    except MuseStructuredValidationError:
        raise
    except Exception as exc:
        raise MuseStructuredValidationError(
            "validator_crash",
            f"Unexpected validator error for {fixture_kind}: {exc}",
            fixture_kind=fixture_kind,
        ) from exc


def infer_fixture_kind_from_prompt(
    *,
    fixture_kind: str | None,
    system_prompt: str,
    user_content: str,
) -> str | None:
    """Resolve fixture_kind when callers omit it (legacy paths)."""
    if fixture_kind:
        return fixture_kind
    sp = (system_prompt or "").lower()
    uc = (user_content or "").lower()
    if "extract rfp fields" in sp or "rfpextractionpayload" in sp:
        return "rfp_extraction"
    if "cross-examine extraction" in sp or "critiqueresult" in sp:
        return "rfp_critique"
    if '"reply"' in sp and "voice call" in sp:
        return "voice_reply"
    if "media for a hospitality proposal" in sp or "analyze media for a hospitality" in sp:
        return "designer_asset_meta"
    if "critic" in uc and "cross-examine" in uc:
        return "rfp_critique"
    return None
