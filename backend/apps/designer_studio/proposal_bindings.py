"""Proposal binding JSON — seed data, resolution from cards, placeholder serialization."""
from __future__ import annotations

import json
import re
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

_SAMPLES_DIR = Path(__file__).resolve().parent / "samples"
_SEED_PATH = _SAMPLES_DIR / "proposal_binding_seed.json"
_RUNTIME_PATH = _SAMPLES_DIR / "proposal_binding_runtime.js"
_CLIENT_BRIDGE_PATH = _SAMPLES_DIR / "proposal_client_bridge.js"

CTA_BUTTON_HTML = (
    '<button type="button" class="proposal-cta" data-proposal-action="accept" '
    'data-proposal-label="Accept proposal">Accept Proposal</button>'
)

# Universal registry: token → payload key (seed / cards JSON). Schema can grow without prompt rewrites.
BINDING_TOKEN_REGISTRY: dict[str, str] = {
    "{{client_name}}": "client_name",
    "{{event_dates}}": "event_dates",
    "{{verified_room_blocks}}": "verified_room_blocks",
    "{{meeting_space_specs}}": "meeting_space_specs",
    "{{xgboost_quote_breakdown}}": "xgboost_quote_breakdown",
    "{{negotiated_concessions}}": "negotiated_concessions",
}

BINDING_SCRIPT_IDS = {
    "verified_room_blocks": "binding-verified-room-blocks",
    "event_dates": "binding-event-dates",
    "client_name": "binding-client-name",
    "xgboost_quote_breakdown": "binding-xgboost-quote",
    "meeting_space_specs": "binding-meeting-space",
    "negotiated_concessions": "binding-negotiated-concessions",
}

_JSON_SCRIPT_RE = re.compile(
    r"(<script\b[^>]*\btype\s*=\s*['\"]application/json['\"][^>]*>)(.*?)(</script>)",
    re.IGNORECASE | re.DOTALL,
)


@lru_cache(maxsize=1)
def load_proposal_binding_seed() -> dict[str, Any]:
    if not _SEED_PATH.is_file():
        raise FileNotFoundError(f"Missing proposal binding seed: {_SEED_PATH}")
    return json.loads(_SEED_PATH.read_text(encoding="utf-8"))


def load_proposal_binding_runtime_js() -> str:
    return _RUNTIME_PATH.read_text(encoding="utf-8")


def clear_binding_seed_cache() -> None:
    load_proposal_binding_seed.cache_clear()


def _parse_iso_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _format_event_display_range(check_in: Any, check_out: Any) -> str:
    d0 = _parse_iso_date(check_in)
    d1 = _parse_iso_date(check_out)
    if d0 and d1:
        if d0.year == d1.year:
            if d0.month == d1.month:
                return f"{d0.strftime('%b %d')} – {d1.strftime('%d, %Y')}"
            return f"{d0.strftime('%b %d')} – {d1.strftime('%b %d, %Y')}"
        return f"{d0.strftime('%b %d, %Y')} – {d1.strftime('%b %d, %Y')}"
    if d0:
        return d0.strftime("%b %d, %Y")
    if d1:
        return d1.strftime("%b %d, %Y")
    parts = [str(x) for x in (check_in, check_out) if x]
    return " — ".join(parts) if parts else ""


def line_items_from_peak_and_nights(
    room_block: dict[str, Any],
    *,
    event_overview: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Voice/card UI often sets peak_rooms + total_room_nights without nightly blocks[]."""
    peak = int(room_block.get("peak_rooms") or 0)
    nights = int(room_block.get("total_room_nights") or 0)
    if peak <= 0:
        return []
    nights = max(nights, 1)
    overview = event_overview or {}
    ci = overview.get("check_in_date") or ""
    co = overview.get("check_out_date") or ""
    date_range = _format_event_display_range(ci, co) or (
        f"{ci} – {co}".strip(" –") if ci or co else "Your dates"
    )
    rack = 189
    return [
        {
            "category_name": "Guest room block",
            "category_subtitle": f"{peak} rooms per night · {nights} night(s)",
            "badge": "",
            "date_range": date_range,
            "nights": nights,
            "quantity": peak,
            "rate_per_night": rack,
            "estimated_total": peak * nights * rack,
        }
    ]


def _normalize_line_item(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "category_name": str(raw.get("category_name") or raw.get("category") or "Room category"),
        "category_subtitle": str(raw.get("category_subtitle") or raw.get("subtitle") or ""),
        "badge": str(raw.get("badge") or ""),
        "date_range": str(raw.get("date_range") or raw.get("dates") or ""),
        "nights": int(raw.get("nights") or 0),
        "quantity": int(raw.get("quantity") or raw.get("qty") or 0),
        "rate_per_night": raw.get("rate_per_night"),
        "estimated_total": raw.get("estimated_total"),
    }


def line_items_from_legacy_blocks(
    room_block: dict[str, Any],
    *,
    event_overview: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    blocks = room_block.get("blocks") or []
    if not blocks:
        return []
    overview = event_overview or {}
    check_in = overview.get("check_in_date") or blocks[0].get("date") or ""
    check_out = overview.get("check_out_date") or blocks[-1].get("date") or ""
    date_range = f"{check_in} – {check_out}".strip(" –") if check_in or check_out else "Event dates"
    nights = len(blocks) or int(room_block.get("total_room_nights") or 1)
    totals = {"single": 0, "double": 0, "deluxe": 0, "suite": 0}
    for b in blocks:
        for key in totals:
            totals[key] += int(b.get(key) or 0)
    per_night = max(nights, 1)
    catalog = [
        ("deluxe", "Deluxe Ocean View", "King + balcony · Sleeps 2", 189),
        ("suite", "Azure Executive Suite", "Lounge + club access", 329),
        ("single", "Standard King", "King · Sleeps 2", 149),
        ("double", "Standard Double", "Two queens · Sleeps 4", 169),
    ]
    items: list[dict[str, Any]] = []
    for key, name, subtitle, rack in catalog:
        qty = totals[key]
        if qty <= 0:
            continue
        qty_per_night = max(qty // per_night, 1)
        items.append(
            {
                "category_name": name,
                "category_subtitle": subtitle,
                "badge": "",
                "date_range": date_range,
                "nights": per_night,
                "quantity": qty_per_night,
                "rate_per_night": rack,
                "estimated_total": qty_per_night * per_night * rack,
            }
        )
    return items


def resolve_verified_room_blocks_payload(
    room_block: dict[str, Any] | None,
    *,
    event_overview: dict[str, Any] | None = None,
    use_seed_if_empty: bool = False,
) -> dict[str, Any]:
    rb = dict(room_block or {})
    raw_items = rb.get("line_items")
    if isinstance(raw_items, list) and raw_items:
        line_items = [_normalize_line_item(dict(x)) for x in raw_items if isinstance(x, dict)]
    else:
        line_items = line_items_from_legacy_blocks(rb, event_overview=event_overview)
    if not line_items:
        line_items = line_items_from_peak_and_nights(rb, event_overview=event_overview)
    if not line_items and use_seed_if_empty:
        seed = load_proposal_binding_seed()
        return dict(seed.get("verified_room_blocks") or {})
    summary = rb.get("summary")
    if not isinstance(summary, dict) or not summary:
        if line_items:
            rooms_per_night = sum(int(i.get("quantity") or 0) for i in line_items)
            nights = max(int(line_items[0].get("nights") or 1), 1)
            room_nights = rooms_per_night * nights
            grand = sum(int(i.get("estimated_total") or 0) for i in line_items)
            summary = {
                "rooms_per_night": rooms_per_night,
                "nights": nights,
                "room_nights": room_nights,
                "avg_rate_per_night": int(grand / max(room_nights, 1)) if room_nights else 0,
                "grand_total": grand,
                "policy_notes": rb.get("policy_notes") or "",
            }
        else:
            summary = {}
    return {
        "schema_version": 1,
        "line_items": line_items,
        "summary": summary,
        "blocks": rb.get("blocks") or [],
    }


def json_for_script_tag(data: Any) -> str:
    """Safe JSON text for inside <script type=\"application/json\"> (no HTML table markup)."""
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def infer_binding_structure_kind(data: Any) -> str:
    """
    Universal structure identification (agent + compile use the same rules).
    line_items_table | string_list | object | empty
    """
    if not isinstance(data, dict):
        return "empty"
    if isinstance(data.get("line_items"), list):
        return "line_items_table"
    if isinstance(data.get("items"), list):
        return "string_list"
    if data:
        return "object"
    return "empty"


def _money_display(value: Any) -> str:
    if value is None or value == "":
        return ""
    try:
        n = float(value)
        if n == int(n):
            return f"${int(n):,}"
        return f"${n:,.2f}"
    except (TypeError, ValueError):
        return str(value)


def format_binding_display(payload_key: str, data: Any) -> str:
    """Human-readable text for placeholders left in visible HTML (never raw JSON)."""
    kind = infer_binding_structure_kind(data)
    if payload_key == "verified_room_blocks":
        return ""
    if kind == "string_list":
        return " · ".join(str(x) for x in (data.get("items") or []) if x)
    if payload_key == "client_name" and isinstance(data, dict):
        return str(data.get("company_name") or "")
    if payload_key == "event_dates" and isinstance(data, dict):
        if data.get("display_range"):
            return str(data["display_range"])
        parts = [data.get("check_in"), data.get("check_out")]
        return " — ".join(str(p) for p in parts if p)
    if payload_key == "meeting_space_specs" and isinstance(data, dict):
        bits: list[str] = []
        if data.get("name"):
            bits.append(str(data["name"]))
        if data.get("seating_style"):
            bits.append(str(data["seating_style"]))
        if data.get("headcount"):
            bits.append(f"{data['headcount']} guests")
        if data.get("av"):
            bits.append(str(data["av"]))
        return " · ".join(bits)
    if payload_key == "xgboost_quote_breakdown" and isinstance(data, dict):
        parts = []
        if data.get("walk_away_floor_price") is not None:
            parts.append(f"Floor {_money_display(data['walk_away_floor_price'])}")
        if data.get("optimal_target_price") is not None:
            parts.append(f"Target {_money_display(data['optimal_target_price'])}")
        if data.get("initial_anchor_price") is not None:
            parts.append(f"Anchor {_money_display(data['initial_anchor_price'])}")
        return " · ".join(parts)
    if payload_key == "negotiated_concessions" and isinstance(data, dict):
        return format_binding_display(payload_key, {"items": data.get("items") or []})
    return ""


def substitute_bindings_in_html(html: str, payloads: dict[str, Any]) -> str:
    """
    Context-aware substitution:
    - Inside <script type=\"application/json\"> → inject JSON payloads
    - Everywhere else → inject format_binding_display (never JSON.stringify in copy)
    """
    if not html:
        return html

    def _script_inner_repl(match: re.Match[str]) -> str:
        opening, inner, closing = match.group(1), match.group(2), match.group(3)
        for token, key in BINDING_TOKEN_REGISTRY.items():
            if token in inner and key in payloads:
                inner = inner.replace(token, json_for_script_tag(payloads[key]))
        return opening + inner + closing

    out = _JSON_SCRIPT_RE.sub(_script_inner_repl, html)
    for token, key in BINDING_TOKEN_REGISTRY.items():
        if key not in payloads:
            continue
        display = format_binding_display(key, payloads[key])
        out = out.replace(token, display)
    return out


def empty_binding_payloads() -> dict[str, Any]:
    """Neutral payloads for Designer preview with sample data off (matches empty client cards)."""
    return {
        "verified_room_blocks": {
            "schema_version": 1,
            "line_items": [],
            "summary": {},
            "blocks": [],
        },
        "event_dates": {
            "check_in": "",
            "check_out": "",
            "display_range": "",
            "nights": 0,
        },
        "client_name": {"company_name": ""},
        "meeting_space_specs": {
            "name": "",
            "seating_style": None,
            "headcount": None,
            "av": None,
        },
        "xgboost_quote_breakdown": {},
        "negotiated_concessions": {"items": []},
    }


def build_binding_payloads_from_cards(
    cards: dict[str, Any],
    *,
    quote: Any | None = None,
    use_seed_if_empty: bool = True,
) -> dict[str, Any]:
    seed = load_proposal_binding_seed()
    overview = cards.get("event_overview") or {}
    meeting = cards.get("meeting_space") or {}
    room_block = cards.get("room_block") or {}

    event_dates = dict(seed["event_dates"])
    ci = overview.get("check_in_date")
    co = overview.get("check_out_date")
    if ci or co:
        nights = int(room_block.get("total_room_nights") or 0)
        if not nights:
            d0 = _parse_iso_date(ci)
            d1 = _parse_iso_date(co)
            if d0 and d1 and d1 > d0:
                nights = max((d1 - d0).days, 1)
            else:
                nights = 1
        event_dates = {
            "check_in": ci,
            "check_out": co,
            "display_range": _format_event_display_range(ci, co),
            "nights": nights,
        }

    verified_room_blocks = resolve_verified_room_blocks_payload(
        room_block,
        event_overview=overview,
        use_seed_if_empty=use_seed_if_empty,
    )

    meeting_specs = seed["meeting_space_specs"]
    if meeting:
        catering_av = cards.get("catering_av") or {}
        meeting_specs = {
            "name": meeting.get("name") or meeting_specs.get("name"),
            "seating_style": meeting.get("seating_style"),
            "headcount": meeting.get("headcount"),
            "av": meeting.get("av") or catering_av.get("av"),
        }

    xgboost = seed["xgboost_quote_breakdown"]
    if quote and hasattr(quote, "walk_away_floor_price"):
        xgboost = {
            "walk_away_floor_price": float(quote.walk_away_floor_price),
            "optimal_target_price": float(quote.optimal_target_price),
            "initial_anchor_price": float(quote.initial_anchor_price),
            "currency": "USD",
        }

    client = {
        "company_name": overview.get("company_name") or seed["event_overview"]["company_name"]
    }

    concessions = cards.get("negotiated_concessions") or seed["negotiated_concessions"]

    return {
        "verified_room_blocks": verified_room_blocks,
        "event_dates": event_dates,
        "client_name": client,
        "meeting_space_specs": meeting_specs,
        "xgboost_quote_breakdown": xgboost,
        "negotiated_concessions": concessions,
    }


def sample_binding_payloads() -> dict[str, Any]:
    """Full binding map keyed by payload name (matches compile / cards resolution)."""
    seed = load_proposal_binding_seed()
    return build_binding_payloads_from_cards(
        {
            "event_overview": seed.get("event_overview") or {},
            "room_block": {},
            "meeting_space": seed.get("meeting_space_specs") or {},
        },
        use_seed_if_empty=True,
    )


def build_binding_replacements(
    cards: dict[str, Any],
    *,
    quote: Any | None = None,
    use_seed_if_empty: bool = True,
) -> dict[str, str]:
    """Legacy flat map — prefer substitute_bindings_in_html on full template HTML."""
    payloads = build_binding_payloads_from_cards(
        cards, quote=quote, use_seed_if_empty=use_seed_if_empty
    )
    out = {
        token: format_binding_display(key, payloads[key])
        for token, key in BINDING_TOKEN_REGISTRY.items()
        if key in payloads
    }
    out["{{cta_accept_button}}"] = CTA_BUTTON_HTML
    return out


def compile_html_with_bindings(
    html: str,
    cards: dict[str, Any] | None = None,
    *,
    quote: Any | None = None,
    use_seed_if_empty: bool = True,
) -> str:
    cards = cards or {}
    if not cards and not use_seed_if_empty:
        payloads = empty_binding_payloads()
    else:
        if not cards and use_seed_if_empty:
            seed = load_proposal_binding_seed()
            cards = {
                "event_overview": seed.get("event_overview") or {},
                "room_block": {},
                "meeting_space": seed.get("meeting_space_specs") or {},
            }
        payloads = build_binding_payloads_from_cards(
            cards, quote=quote, use_seed_if_empty=use_seed_if_empty
        )
    body = substitute_bindings_in_html(html or "", payloads)
    body = body.replace("{{cta_accept_button}}", CTA_BUTTON_HTML)
    return body


def inject_proposal_binding_runtime(html_document: str) -> str:
    """Append hydrate runtime once for compiled preview / client render."""
    if "proposalBindingHydrate" in html_document:
        return inject_proposal_client_bridge(html_document)
    script = load_proposal_binding_runtime_js()
    block = f'<script data-proposal-binding-runtime="1">\n{script}\n</script>'
    if "</body>" in html_document.lower():
        idx = html_document.lower().rfind("</body>")
        html_document = html_document[:idx] + block + html_document[idx:]
    else:
        html_document = html_document + block
    return inject_proposal_client_bridge(html_document)


@lru_cache(maxsize=1)
def load_proposal_client_bridge_js() -> str:
    return _CLIENT_BRIDGE_PATH.read_text(encoding="utf-8")


def inject_proposal_client_bridge(html_document: str) -> str:
    """Append client↔parent postMessage bridge for live proposal interactions."""
    if "rfpProposalEmit" in html_document or "data-proposal-client-bridge" in html_document:
        return html_document
    script = load_proposal_client_bridge_js()
    block = f'<script data-proposal-client-bridge="1">\n{script}\n</script>'
    if "</body>" in html_document.lower():
        idx = html_document.lower().rfind("</body>")
        return html_document[:idx] + block + html_document[idx:]
    return html_document + block


def ensure_client_bridge_script_tag(html_markup: str) -> str:
    """Designer template storage: add script src if bridge not present."""
    if not html_markup or "rfpProposalEmit" in html_markup or "proposal_client_bridge.js" in html_markup:
        return html_markup
    tag = '<script src="/proposal_client_bridge.js" data-proposal-client-bridge="1"></script>'
    if "</body>" in html_markup.lower():
        idx = html_markup.lower().rfind("</body>")
        return html_markup[:idx] + tag + html_markup[idx:]
    return html_markup + tag
