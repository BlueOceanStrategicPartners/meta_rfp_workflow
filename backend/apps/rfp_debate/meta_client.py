"""Meta Model API client with fixture mode for tests and demos."""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

import httpx
from django.conf import settings

from .muse_completion import (
    MuseStructuredValidationError,
    infer_fixture_kind_from_prompt,
    validate_muse_structured_payload,
)
from .muse_structured_schemas import structured_response_format_for_fixture
from .schemas import CritiqueResult, DiscrepancyFlag, RFPExtractionPayload, SourceCitation

logger = logging.getLogger(__name__)


def _muse_debug_enabled() -> bool:
    return bool(getattr(settings, "META_MODEL_DEBUG", False))


def _muse_debug_max_chars() -> int:
    return int(getattr(settings, "META_MODEL_DEBUG_MAX_CHARS", 4000))


def _truncate_debug_text(text: str, *, max_chars: int | None = None) -> str:
    limit = max_chars if max_chars is not None else _muse_debug_max_chars()
    raw = text or ""
    if len(raw) <= limit:
        return raw
    return f"{raw[:limit]}\n…[+{len(raw) - limit} chars truncated]"


def _summarize_messages_for_log(messages: Any) -> list[dict[str, Any]]:
    if not isinstance(messages, list):
        return []
    preview_each = min(800, max(200, _muse_debug_max_chars() // max(len(messages), 1)))
    out: list[dict[str, Any]] = []
    for msg in messages[:24]:
        if not isinstance(msg, dict):
            continue
        content = str(msg.get("content") or "")
        out.append(
            {
                "role": msg.get("role"),
                "chars": len(content),
                "preview": _truncate_debug_text(content, max_chars=preview_each),
            }
        )
    if len(messages) > 24:
        out.append({"role": "…", "chars": 0, "preview": f"+{len(messages) - 24} more messages omitted"})
    return out


def _log_muse_request(
    *,
    fixture_kind: str | None,
    model_id: str,
    payload: dict[str, Any],
) -> float:
    if not _muse_debug_enabled():
        return time.monotonic()
    messages = payload.get("messages")
    summary = _summarize_messages_for_log(messages)
    logger.info(
        "MUSE → request model=%s fixture_kind=%s message_count=%s response_format=%s\n%s",
        model_id,
        fixture_kind,
        len(messages) if isinstance(messages, list) else 0,
        payload.get("response_format"),
        json.dumps(summary, indent=2, ensure_ascii=False)[: _muse_debug_max_chars()],
    )
    return time.monotonic()


def _log_muse_response(
    *,
    started: float,
    fixture_kind: str | None,
    model_id: str,
    raw_content: str,
    parsed: dict[str, Any] | None,
    error: str | None = None,
) -> None:
    if not _muse_debug_enabled():
        return
    elapsed_ms = int((time.monotonic() - started) * 1000)
    if error:
        logger.info(
            "MUSE ← error model=%s fixture_kind=%s elapsed_ms=%s error=%s",
            model_id,
            fixture_kind,
            elapsed_ms,
            _truncate_debug_text(error, max_chars=1200),
        )
        return
    parsed_keys = sorted(parsed.keys()) if isinstance(parsed, dict) else []
    logger.info(
        "MUSE ← response model=%s fixture_kind=%s elapsed_ms=%s parsed_keys=%s\nraw_content:\n%s\nparsed_preview:\n%s",
        model_id,
        fixture_kind,
        elapsed_ms,
        parsed_keys,
        _truncate_debug_text(raw_content),
        _truncate_debug_text(json.dumps(parsed, ensure_ascii=False) if parsed else "{}", max_chars=2000),
    )


class MetaModelAPIError(RuntimeError):
    """Raised when the Meta/Muse chat API fails and fixture fallback is disabled."""

    def __init__(self, message: str, *, cause: Exception | None = None):
        super().__init__(message)
        self.cause = cause


def parse_model_json_content(content: str) -> dict[str, Any]:
    """
    Parse JSON from model message.content.
    Prefer Meta structured output (json_schema) — content is pure JSON; keep prose fallback
    for legacy json_object responses.
    """
    text = (content or "").strip()
    if not text:
        raise ValueError("empty model content")
    decoder = json.JSONDecoder()
    try:
        obj, _end = decoder.raw_decode(text)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass
    idx = text.find("{")
    while idx >= 0:
        try:
            obj, _end = decoder.raw_decode(text, idx)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            idx = text.find("{", idx + 1)
    raise ValueError("no JSON object in model content")


class MetaModelClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self.api_key = api_key or settings.META_MODEL_API_KEY
        self.base_url = base_url or settings.META_MODEL_API_BASE

    @property
    def uses_fixtures(self) -> bool:
        """True when every call returns canned sample answers (USE_FIXTURE_DEBATE or no API key)."""
        return bool(settings.USE_FIXTURE_DEBATE or not self.api_key)

    def complete_json(
        self,
        *,
        model_id: str,
        system_prompt: str,
        user_content: str,
        reasoning_effort: str | None = None,
        fixture_kind: str | None = None,
        allow_fixture_fallback: bool = True,
    ) -> dict[str, Any]:
        if settings.USE_FIXTURE_DEBATE or not self.api_key:
            return self._fixture_response(
                model_id, user_content, system_prompt=system_prompt, fixture_kind=fixture_kind
            )
        effective_kind = infer_fixture_kind_from_prompt(
            fixture_kind=fixture_kind,
            system_prompt=system_prompt,
            user_content=user_content,
        )
        structured = structured_response_format_for_fixture(effective_kind)
        payload: dict[str, Any] = {
            "model": model_id,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "response_format": structured
            or {"type": "json_object"},
        }
        if reasoning_effort:
            payload["reasoning_effort"] = reasoning_effort
        return self._post_chat_completion(
            payload,
            model_id,
            user_content,
            system_prompt,
            effective_kind,
            allow_fixture_fallback=allow_fixture_fallback,
        )

    def complete_json_messages(
        self,
        *,
        model_id: str,
        messages: list[dict[str, str]],
        reasoning_effort: str | None = None,
        fixture_kind: str | None = None,
        allow_fixture_fallback: bool = True,
    ) -> dict[str, Any]:
        system_prompt = next(
            (m.get("content", "") for m in messages if m.get("role") == "system"),
            "",
        )
        user_content = messages[-1].get("content", "") if messages else ""
        if settings.USE_FIXTURE_DEBATE or not self.api_key:
            return self._fixture_response(
                model_id,
                user_content,
                system_prompt=system_prompt,
                fixture_kind=fixture_kind,
            )
        effective_kind = infer_fixture_kind_from_prompt(
            fixture_kind=fixture_kind,
            system_prompt=system_prompt,
            user_content=user_content,
        )
        structured = structured_response_format_for_fixture(effective_kind)
        payload: dict[str, Any] = {
            "model": model_id,
            "messages": messages,
            "response_format": structured
            or {"type": "json_object"},
        }
        if reasoning_effort:
            payload["reasoning_effort"] = reasoning_effort
        return self._post_chat_completion(
            payload,
            model_id,
            user_content,
            system_prompt,
            effective_kind,
            allow_fixture_fallback=allow_fixture_fallback,
        )

    def _post_chat_completion(
        self,
        payload: dict[str, Any],
        model_id: str,
        user_content: str,
        system_prompt: str,
        fixture_kind: str | None,
        *,
        allow_fixture_fallback: bool = True,
    ) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        http_timeout = float(getattr(settings, "META_MODEL_HTTP_TIMEOUT", 300.0))
        started = _log_muse_request(fixture_kind=fixture_kind, model_id=model_id, payload=payload)
        try:
            with httpx.Client(timeout=http_timeout) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions", json=payload, headers=headers
                )
                if response.status_code >= 400:
                    logger.error(
                        "Meta model HTTP %s (model=%s, fixture_kind=%s): %s",
                        response.status_code,
                        model_id,
                        fixture_kind,
                        (response.text or "")[:800],
                    )
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                raw_content = content if isinstance(content, str) else str(content)
                parsed = parse_model_json_content(raw_content)
                validated = validate_muse_structured_payload(parsed, fixture_kind=fixture_kind)
                _log_muse_response(
                    started=started,
                    fixture_kind=fixture_kind,
                    model_id=model_id,
                    raw_content=raw_content,
                    parsed=validated,
                )
                return validated
        except MuseStructuredValidationError as exc:
            _log_muse_response(
                started=started,
                fixture_kind=fixture_kind,
                model_id=model_id,
                raw_content="",
                parsed=None,
                error=f"structured validation ({exc.code}): {exc}",
            )
            logger.warning(
                "Meta structured validation failed (model=%s, fixture_kind=%s, code=%s): %s",
                model_id,
                fixture_kind,
                exc.code,
                exc,
            )
            if not allow_fixture_fallback:
                raise MetaModelAPIError(
                    f"Design model returned invalid structured output ({exc.code}): {exc}",
                    cause=exc,
                ) from exc
            return self._fixture_response(
                model_id, user_content, system_prompt=system_prompt, fixture_kind=fixture_kind
            )
        except (httpx.HTTPError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            _log_muse_response(
                started=started,
                fixture_kind=fixture_kind,
                model_id=model_id,
                raw_content="",
                parsed=None,
                error=str(exc),
            )
            logger.warning(
                "Meta model API failed (model=%s, fixture_kind=%s, fallback=%s): %s",
                model_id,
                fixture_kind,
                allow_fixture_fallback,
                exc,
            )
            if not allow_fixture_fallback:
                raise MetaModelAPIError(
                    f"Design model API call failed: {exc}. Check META_MODEL_API_KEY and network.",
                    cause=exc,
                ) from exc
            return self._fixture_response(
                model_id, user_content, system_prompt=system_prompt, fixture_kind=fixture_kind
            )

    def stream_text(
        self,
        *,
        model_id: str,
        system_prompt: str,
        user_content: str,
        reasoning_effort: str | None = None,
    ):
        """Yield spoken text fragments (plain text, not JSON)."""
        if settings.USE_FIXTURE_DEBATE or not self.api_key:
            reply = str(self._fixture_response(model_id, user_content).get("reply", ""))
            for word in reply.split():
                yield word + " "
            return

        payload: dict[str, Any] = {
            "model": model_id,
            "stream": True,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
        }
        if reasoning_effort:
            payload["reasoning_effort"] = reasoning_effort
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            with httpx.Client(timeout=120.0) as client:
                with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                ) as response:
                    response.raise_for_status()
                    for line in response.iter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        chunk = line[6:].strip()
                        if chunk == "[DONE]":
                            break
                        try:
                            data = json.loads(chunk)
                        except json.JSONDecodeError:
                            continue
                        choices = data.get("choices") or []
                        if not choices:
                            continue
                        delta = choices[0].get("delta") or {}
                        text = delta.get("content")
                        if text:
                            yield text
        except httpx.HTTPError:
            reply = str(self._fixture_response(model_id, user_content).get("reply", ""))
            for word in reply.split():
                yield word + " "

    @staticmethod
    def _designer_fixture_html(instruction: str = "") -> dict[str, Any]:
        from apps.designer_studio.models import ALL_BINDING_PLACEHOLDERS

        dark = "dark" in instruction.lower() or "luxury" in instruction.lower()
        bg = "#0f0f12" if dark else "#fafafa"
        accent = "#c9a227" if dark else "#1a56db"
        sections = "".join(
            f"<section class='block'><h2>{p}</h2><div>{p}</div></section>"
            for p in ALL_BINDING_PLACEHOLDERS
        )
        media_block = ""
        if "url=" in instruction:
            import re

            urls = re.findall(r"url=(https?://[^\s]+)", instruction)
            if urls:
                media_block = "<section class='media-gallery'>"
                for url in urls[:4]:
                    if any(url.lower().endswith(ext) for ext in (".mp4", ".webm", ".mov")):
                        media_block += f"<video controls src='{url}' class='hero-video'></video>"
                    else:
                        media_block += f"<img src='{url}' alt='Property visual' class='hero-img'/>"
                media_block += "</section>"
        html = (
            f"<header class='hero'><h1>{{{{client_name}}}}</h1><p>{{{{event_dates}}}}</p>{media_block}</header>"
            f"<main class='grid'>{sections}</main>"
            f"<footer>{{{{cta_accept_button}}}}</footer>"
        )
        css = (
            f"body{{margin:0;font-family:system-ui,sans-serif;background:{bg};color:{'#f5f5f5' if dark else '#111'};}}"
            f".hero{{padding:2rem;border-bottom:3px solid {accent};}}"
            f".hero-img,.hero-video{{max-width:100%;border-radius:12px;margin-top:1rem;}}"
            f".grid{{display:grid;gap:1rem;padding:1.5rem;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));}}"
            f".block{{padding:1rem;border-radius:12px;border:1px solid {accent}33;}}"
            f"footer{{padding:1.5rem;text-align:center;}}"
            f".proposal-cta{{background:{accent};color:#fff;border:0;padding:0.75rem 1.5rem;border-radius:8px;cursor:pointer;}}"
        )
        js = (
            "document.querySelectorAll('.proposal-cta, button').forEach(function(btn){"
            "btn.addEventListener('click',function(){btn.classList.add('pulse');});"
            "});"
        )
        msg = (
            "Applied a luxury dark-mode proposal shell with gold accents and embedded media."
            if dark
            else "Applied a clean corporate proposal layout with responsive grid sections and media."
        )
        return {
            "assistant_message": msg,
            "html_markup": html,
            "css_stylesheet": css,
            "js_script": js,
        }

    def _fixture_response(
        self,
        model_id: str,
        user_content: str,
        *,
        system_prompt: str = "",
        fixture_kind: str | None = None,
    ) -> dict[str, Any]:
        if fixture_kind == "rfp_extraction" or "rfpextractionpayload" in system_prompt.lower():
            return self._sample_extraction(
                mismatch="MISMATCH_FIXTURE" in user_content and "resolved" not in user_content.lower()
            )
        if fixture_kind == "rfp_critique" or (
            "critic" in user_content.lower() and "cross-examine" in user_content.lower()
        ):
            if (
                "MISMATCH_FIXTURE" in user_content
                and "resolved" not in user_content.lower()
            ):
                return {
                    "discrepancy_flags": [
                        {
                            "field_path": "total_room_nights",
                            "severity": "high",
                            "message": "Daily blocks do not sum to total",
                            "expected": "180",
                            "actual": "150",
                        }
                    ],
                    "consensus_score": 0.5,
                }
            return {"discrepancy_flags": [], "consensus_score": 1.0}
        if fixture_kind == "voice_reply" or (
            "User:" in user_content and "RFP session" in user_content
        ):
            user_msg = user_content.split("User:", 1)[-1].strip()
            return {
                "reply": f"Got it. {user_msg[:100]}. You can edit the summary cards or tell me meeting space details here.",
            }
        if fixture_kind == "voice_intake_classify":
            return {
                "confidence": 0.92,
                "intent": "clarify",
                "reply": "Thanks — how many nights will your group stay?",
            }
        if fixture_kind == "designer_asset_meta" or "media for a hospitality proposal" in system_prompt:
            return {
                "description": "Premium hospitality visual suitable for hero or gallery placement.",
                "suggested_placement": "hero",
                "dominant_mood": "luxury",
                "embed_hint": "Use full-width responsive img or muted autoplay video with controls.",
            }
        if fixture_kind == "designer_execution_plan" or "plan how a hospitality proposal template editor" in system_prompt:
            return {
                "steps": [
                    {"id": "exec_1", "label": "Inspect template structure and locate edit targets"},
                    {"id": "exec_2", "label": "Apply HTML, CSS, and JS updates for the brief"},
                ],
                "summary": "Fixture execution plan.",
            }
        if fixture_kind == "designer_work_plan" or (
            "progress labels for a hospitality proposal design agent" in system_prompt
        ):
            return {"labels": {}}
        if fixture_kind == "designer_tool_loop_repair" or "Template Repair Editor" in system_prompt:
            return {"kind": "tool", "tool": "validate_template", "arguments": {}}
        if fixture_kind == "designer_tool_loop" or "Proposal Template Editor" in system_prompt:
            return {"kind": "tool", "tool": "get_template_overview", "arguments": {}}
        if fixture_kind == "designer_chat" or "Proposal Template Architect" in system_prompt:
            instruction = user_content.split("Designer request:")[-1] if "Designer request:" in user_content else user_content
            return self._designer_fixture_html(instruction)
        if fixture_kind == "designer_validate" or fixture_kind == "designer_save_validate" or "validate compiled hospitality" in system_prompt.lower() or "before save" in system_prompt.lower():
            return {"valid": True, "issues": [], "summary": "Fixture validation passed."}
        if "re-extract" in user_content.lower() or "iteration" in user_content.lower():
            return self._sample_extraction(mismatch=False)
        if "critic" in user_content.lower() or "cross-examine" in user_content.lower():
            if (
                "MISMATCH_FIXTURE" in user_content
                and "resolved" not in user_content.lower()
            ):
                return {
                    "discrepancy_flags": [
                        {
                            "field_path": "total_room_nights",
                            "severity": "high",
                            "message": "Daily blocks do not sum to total",
                            "expected": "180",
                            "actual": "150",
                        }
                    ],
                    "consensus_score": 0.5,
                }
            return {"discrepancy_flags": [], "consensus_score": 1.0}
        if "User:" in user_content and "RFP session" in user_content:
            user_msg = user_content.split("User:", 1)[-1].strip()
            return {
                "reply": f"Got it. {user_msg[:100]}. You can edit the summary cards or tell me meeting space details here.",
            }
        return self._sample_extraction(
            mismatch="MISMATCH_FIXTURE" in user_content and "resolved" not in user_content.lower()
        )

    @staticmethod
    def _sample_extraction(mismatch: bool = False) -> dict[str, Any]:
        cite = {
            "page_number": 1,
            "bounding_box": [0, 0, 100, 20],
            "verbatim_quote": "Sample quote",
        }

        def field(value):
            return {"value": value, "source_citation": cite}

        per_night = 90 if mismatch else 60
        total_nights = 150 if mismatch else 180
        block = {
            "date": "2026-06-01",
            "single": per_night,
            "double": 0,
            "deluxe": 0,
            "suite": 0,
        }
        return {
            "company_name": field("Acme Corp"),
            "event_type": field("Corporate Summit"),
            "check_in_date": field("2026-06-01"),
            "check_out_date": field("2026-06-04"),
            "total_room_nights": field(total_nights),
            "room_blocks": [
                {**block, "date": "2026-06-01"},
                {**block, "date": "2026-06-02"},
                {**block, "date": "2026-06-03"},
            ],
            "meeting_headcount": field(250),
            "seating_style": field("classroom"),
            "catering_notes": field("Breakfast buffet"),
            "av_specs": field("Dual 4K projectors"),
            "historical_discount_pct": field(8),
        }


def parse_extraction(data: dict[str, Any]) -> RFPExtractionPayload:
    return RFPExtractionPayload.model_validate(data)


def parse_critique(data: dict[str, Any]) -> CritiqueResult:
    flags = [DiscrepancyFlag.model_validate(f) for f in data.get("discrepancy_flags", [])]
    return CritiqueResult(
        discrepancy_flags=flags,
        consensus_score=float(data.get("consensus_score", 1.0 if not flags else 0.5)),
    )
