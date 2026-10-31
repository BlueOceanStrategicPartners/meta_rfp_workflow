"""Meta Model API client with fixture mode for tests and demos."""
from __future__ import annotations

import json
import os
from typing import Any

import httpx
from django.conf import settings

from .schemas import CritiqueResult, DiscrepancyFlag, RFPExtractionPayload, SourceCitation


class MetaModelClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self.api_key = api_key or settings.META_MODEL_API_KEY
        self.base_url = base_url or settings.META_MODEL_API_BASE

    def complete_json(
        self,
        *,
        model_id: str,
        system_prompt: str,
        user_content: str,
        reasoning_effort: str | None = None,
    ) -> dict[str, Any]:
        if settings.USE_FIXTURE_DEBATE or not self.api_key:
            return self._fixture_response(model_id, user_content)
        payload: dict[str, Any] = {
            "model": model_id,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "response_format": {"type": "json_object"},
        }
        if reasoning_effort:
            payload["reasoning_effort"] = reasoning_effort
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            with httpx.Client(timeout=120.0) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions", json=payload, headers=headers
                )
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                return json.loads(content)
        except (httpx.HTTPError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            return self._fixture_response(model_id, user_content)

    def stream_text(
        self,
        *,
        model_id: str,
        system_prompt: str,
        user_content: str,
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

    def _fixture_response(self, model_id: str, user_content: str) -> dict[str, Any]:
        if "User:" in user_content and "RFP session" in user_content:
            user_msg = user_content.split("User:", 1)[-1].strip()
            return {
                "reply": f"Got it. {user_msg[:100]}. You can edit the cards or open the venue map.",
            }
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
        if "re-extract" in user_content.lower() or "iteration" in user_content.lower():
            return self._sample_extraction(mismatch=False)
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
