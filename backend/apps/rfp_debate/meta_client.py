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
        fixture_kind: str | None = None,
    ) -> dict[str, Any]:
        if settings.USE_FIXTURE_DEBATE or not self.api_key:
            return self._fixture_response(
                model_id, user_content, system_prompt=system_prompt, fixture_kind=fixture_kind
            )
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
        return self._post_chat_completion(payload, model_id, user_content, system_prompt, fixture_kind)

    def complete_json_messages(
        self,
        *,
        model_id: str,
        messages: list[dict[str, str]],
        reasoning_effort: str | None = None,
        fixture_kind: str | None = None,
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
        payload: dict[str, Any] = {
            "model": model_id,
            "messages": messages,
            "response_format": {"type": "json_object"},
        }
        if reasoning_effort:
            payload["reasoning_effort"] = reasoning_effort
        return self._post_chat_completion(payload, model_id, user_content, system_prompt, fixture_kind)

    def _post_chat_completion(
        self,
        payload: dict[str, Any],
        model_id: str,
        user_content: str,
        system_prompt: str,
        fixture_kind: str | None,
    ) -> dict[str, Any]:
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
            return self._fixture_response(
                model_id, user_content, system_prompt=system_prompt, fixture_kind=fixture_kind
            )

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

    @staticmethod
    def _designer_fixture_html(instruction: str = "") -> dict[str, Any]:
        from apps.designer_studio.models import REQUIRED_PLACEHOLDERS

        dark = "dark" in instruction.lower() or "luxury" in instruction.lower()
        bg = "#0f0f12" if dark else "#fafafa"
        accent = "#c9a227" if dark else "#1a56db"
        sections = "".join(
            f"<section class='block'><h2>{p}</h2><div>{p}</div></section>"
            for p in REQUIRED_PLACEHOLDERS
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

    @staticmethod
    def _map_fixture_interactive(instruction: str = "") -> dict[str, Any]:
        import re

        urls = re.findall(r"url=(https?://[^\s]+)", instruction)
        photo = urls[0] if urls else "https://placehold.co/640x360/png?text=Ballroom"
        locations = [
            {
                "id": "grand-ballroom",
                "label": "Grand Sapphire Ballroom",
                "description": "Main event hall with dual 4K projection and divisible airwalls.",
                "image_urls": [photo],
            },
            {
                "id": "lotus-pavilion",
                "label": "Lotus Pavilion",
                "description": "Garden-facing breakout space with natural light.",
                "image_urls": [photo],
            },
        ]
        html = (
            "<div class='venue-map-root' id='venue-map'>"
            "<img class='floorplan' src='https://placehold.co/800x500/png?text=Floorplan' alt='Floorplan'/>"
            "<button type='button' class='zone' data-location-id='grand-ballroom'>Grand Ballroom</button>"
            "<button type='button' class='zone' data-location-id='lotus-pavilion'>Lotus Pavilion</button>"
            "<div id='map-popup' class='map-popup hidden' role='dialog' aria-hidden='true'></div>"
            "</div>"
        )
        css = (
            ".venue-map-root{position:relative;max-width:100%;}"
            ".floorplan{width:100%;border-radius:12px;display:block;}"
            ".zone{position:absolute;padding:0.5rem 0.75rem;border:2px solid #0af;background:rgba(0,180,255,0.25);"
            "color:#fff;border-radius:8px;cursor:pointer;}"
            ".zone:nth-of-type(1){top:28%;left:18%;}"
            ".zone:nth-of-type(2){top:55%;left:58%;}"
            ".map-popup{position:fixed;inset:20% 15%;background:#0f172a;color:#f8fafc;padding:1rem;border-radius:16px;"
            "box-shadow:0 20px 60px rgba(0,0,0,0.45);overflow:auto;z-index:50;}"
            ".map-popup.hidden{display:none;}"
            ".map-popup img{max-width:100%;border-radius:8px;margin-top:0.75rem;}"
        )
        js = (
            "var LOCS={grand-ballroom:{label:'Grand Sapphire Ballroom',description:'Main event hall.',"
            "imageUrls:['"
            + photo
            + "']},lotus-pavilion:{label:'Lotus Pavilion',description:'Garden breakout.',imageUrls:['"
            + photo
            + "']}};"
            "function showPopup(id){var d=LOCS[id];if(!d)return;var p=document.getElementById('map-popup');"
            "p.classList.remove('hidden');p.innerHTML='<h2>'+d.label+'</h2><p>'+d.description+'</p>'+"
            "(d.imageUrls||[]).map(function(u){return '<img src=\"'+u+'\" alt=\"\"/>';}).join('');"
            "window.parent.postMessage({type:'venue-map-select',locationId:id,label:d.label,"
            "description:d.description,imageUrls:d.imageUrls||[]},'*');}"
            "document.querySelectorAll('[data-location-id]').forEach(function(el){"
            "el.addEventListener('click',function(){showPopup(el.getAttribute('data-location-id'));});});"
        )
        return {
            "assistant_message": "Built an interactive floorplan with labeled zones, photo popups, and parent postMessage hooks.",
            "html_markup": html,
            "css_stylesheet": css,
            "js_script": js,
            "locations": locations,
        }

    def _fixture_response(
        self,
        model_id: str,
        user_content: str,
        *,
        system_prompt: str = "",
        fixture_kind: str | None = None,
    ) -> dict[str, Any]:
        if fixture_kind == "designer_asset_meta" or "media for a hospitality proposal" in system_prompt:
            return {
                "description": "Premium hospitality visual suitable for hero or gallery placement.",
                "suggested_placement": "hero",
                "dominant_mood": "luxury",
                "embed_hint": "Use full-width responsive img or muted autoplay video with controls.",
            }
        if fixture_kind == "designer_chat" or "Proposal Template Architect" in system_prompt:
            instruction = user_content.split("Designer request:")[-1] if "Designer request:" in user_content else user_content
            return self._designer_fixture_html(instruction)
        if fixture_kind == "designer_validate" or "validate compiled hospitality" in system_prompt.lower():
            return {"valid": True, "issues": [], "summary": "Fixture validation passed."}
        if fixture_kind == "map_chat" or "Interactive Venue Map Architect" in system_prompt:
            instruction = (
                user_content.split("Map design request:")[-1]
                if "Map design request:" in user_content
                else user_content
            )
            return self._map_fixture_interactive(instruction)
        if fixture_kind == "map_validate" or "validate compiled interactive hospitality venue" in system_prompt.lower():
            return {"valid": True, "issues": [], "summary": "Fixture map validation passed."}
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
