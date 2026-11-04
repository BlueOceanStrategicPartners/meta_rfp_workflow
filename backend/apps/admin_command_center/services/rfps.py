"""RFP list/detail for the Debate Observatory, and admin field overrides."""
from __future__ import annotations

from datetime import date

from django.db.models import Count, Q

from apps.admin_command_center import audit
from apps.admin_command_center.models import AdminAuditEvent
from apps.core.exceptions import CardMutationValidationError
from apps.dynamic_pricing.models import DynamicPricingQuote
from apps.rfp_debate.models import RFPStatus, RFPSubmission

from . import AdminInputError

SEATING_STYLES = ("banquet", "classroom", "theater", "u_shape", "cocktail")

# Override field -> (card section, card key)
OVERRIDE_FIELDS = {
    "company_name": ("event_overview", "company_name"),
    "event_type": ("event_overview", "event_type"),
    "check_in_date": ("event_overview", "check_in_date"),
    "check_out_date": ("event_overview", "check_out_date"),
    "total_room_nights": ("room_block", "total_room_nights"),
    "headcount": ("meeting_space", "headcount"),
    "seating_style": ("meeting_space", "seating_style"),
}
# Critic field paths that an override resolves (amber highlight is cleared).
AMBER_ALIASES = {"headcount": {"headcount", "meeting_headcount"}}


def company_name(rfp: RFPSubmission) -> str:
    overview = (rfp.active_ui_cards_json or {}).get("event_overview") or {}
    return overview.get("company_name") or ""


def _fallback_label(reason: str) -> str:
    from apps.dynamic_pricing.services import FALLBACK_REASON_LABELS

    return FALLBACK_REASON_LABELS.get(reason or "", reason or "")


def quote_to_dict(quote: DynamicPricingQuote, *, with_rfp: bool = False) -> dict:
    data = {
        "id": str(quote.id),
        "floor": str(quote.walk_away_floor_price),
        "target": str(quote.optimal_target_price),
        "anchor": str(quote.initial_anchor_price),
        "agreed": str(quote.agreed_final_price) if quote.agreed_final_price is not None else None,
        "used_fallback": quote.used_fallback_engine,
        "engine": quote.engine,
        "model_version": quote.model_version,
        "fallback_reason": quote.fallback_reason,
        "fallback_reason_label": _fallback_label(quote.fallback_reason),
        "created_at": quote.created_at.isoformat(),
    }
    if with_rfp:
        data["rfp_id"] = str(quote.rfp_id)
        data["company_name"] = company_name(quote.rfp)
    return data


def _sla(rfp: RFPSubmission) -> dict:
    duration = None
    if rfp.sla_started_at and rfp.sla_completed_at:
        duration = round((rfp.sla_completed_at - rfp.sla_started_at).total_seconds(), 2)
    return {
        "started_at": rfp.sla_started_at.isoformat() if rfp.sla_started_at else None,
        "completed_at": rfp.sla_completed_at.isoformat() if rfp.sla_completed_at else None,
        "duration_seconds": duration,
    }


def rfp_list(*, status: str | None = None, q: str | None = None, limit: int = 100) -> list[dict]:
    qs = (
        RFPSubmission.objects.select_related("client")
        .annotate(rounds=Count("debate_logs"))
        .order_by("-updated_at")
    )
    if status:
        qs = qs.filter(status=status)
    rows = []
    needle = (q or "").strip().lower()
    for rfp in qs[: limit * 3 if needle else limit]:
        name = company_name(rfp)
        if needle and needle not in name.lower() and not str(rfp.id).startswith(needle):
            continue
        latest = rfp.debate_logs.order_by("-iteration_number").first()
        rows.append(
            {
                "id": str(rfp.id),
                "company_name": name,
                "client_email": rfp.client.email,
                "status": rfp.status,
                "rounds": rfp.rounds,
                "latest_consensus": latest.arbiter_consensus_score if latest else None,
                "amber_fields": list(rfp.amber_conflict_fields_json or []),
                "created_at": rfp.created_at.isoformat(),
                "updated_at": rfp.updated_at.isoformat(),
            }
        )
        if len(rows) >= limit:
            break
    return rows


def rfp_detail(rfp: RFPSubmission) -> dict:
    rounds = [
        {
            "iteration": log.iteration_number,
            "extractor_model_id": log.extractor_model_id,
            "critic_model_id": log.critic_model_id,
            "consensus": log.arbiter_consensus_score,
            "duration_ms": log.duration_ms,
            "flags": log.discrepancy_flags_json or [],
            "extraction": log.extractor_output_json or {},
        }
        for log in rfp.debate_logs.order_by("iteration_number")
    ]
    quotes = [quote_to_dict(q) for q in rfp.pricing_quotes.order_by("-created_at")[:50]]
    events = AdminAuditEvent.objects.select_related("actor").filter(
        target_type="rfp", target_id=str(rfp.id)
    )[:50]
    return {
        "id": str(rfp.id),
        "status": rfp.status,
        "client_email": rfp.client.email,
        "company_name": company_name(rfp),
        "source_document_text": rfp.source_document_text,
        "cards": rfp.active_ui_cards_json or {},
        "amber_fields": list(rfp.amber_conflict_fields_json or []),
        "sla": _sla(rfp),
        "rounds": rounds,
        "quotes": quotes,
        "audit": [audit.serialize_event(e) for e in events],
        "created_at": rfp.created_at.isoformat(),
        "updated_at": rfp.updated_at.isoformat(),
    }


def _clean_override_fields(fields: dict) -> dict:
    if not isinstance(fields, dict) or not fields:
        raise AdminInputError("Choose at least one field to correct.")
    unknown = sorted(set(fields) - set(OVERRIDE_FIELDS))
    if unknown:
        raise AdminInputError(f"These fields can't be corrected here: {', '.join(unknown)}.")
    cleaned: dict = {}
    for key, value in fields.items():
        if key in ("check_in_date", "check_out_date"):
            try:
                cleaned[key] = date.fromisoformat(str(value)[:10]).isoformat()
            except ValueError:
                raise AdminInputError(f"{key.replace('_', ' ').capitalize()} must be a date like 2026-12-01.")
        elif key in ("total_room_nights", "headcount"):
            try:
                number = int(value)
            except (TypeError, ValueError):
                raise AdminInputError(f"{key.replace('_', ' ').capitalize()} must be a whole number.")
            if number < 0:
                raise AdminInputError(f"{key.replace('_', ' ').capitalize()} cannot be negative.")
            cleaned[key] = number
        elif key == "seating_style":
            style = str(value).strip().lower()
            if style not in SEATING_STYLES:
                raise AdminInputError(f"Seating style must be one of: {', '.join(SEATING_STYLES)}.")
            cleaned[key] = style
        else:
            text = str(value).strip()
            if not text or len(text) > 255:
                raise AdminInputError(f"{key.replace('_', ' ').capitalize()} must be 1-255 characters.")
            cleaned[key] = text
    if "check_in_date" in cleaned and "check_out_date" in cleaned:
        if cleaned["check_out_date"] < cleaned["check_in_date"]:
            raise AdminInputError("Check-out can't be before check-in.")
    return cleaned


def apply_override(rfp: RFPSubmission, fields: dict, note: str, actor) -> dict:
    """Correct extracted fields, then reuse the client card validator (capacity, dates, reprice, broadcast)."""
    from apps.ui_card_validator.services import validate_card_mutation

    cleaned = _clean_override_fields(fields)
    resolved: set[str] = set()
    for key in cleaned:
        resolved |= AMBER_ALIASES.get(key, {key})

    cards = rfp.active_ui_cards_json or {}
    payload: dict = {}
    for key, value in cleaned.items():
        section, card_key = OVERRIDE_FIELDS[key]
        payload.setdefault(section, dict(cards.get(section) or {}))[card_key] = value
    for section in payload:
        amber = (cards.get(section) or {}).get("amber_fields") or []
        payload[section]["amber_fields"] = [f for f in amber if f not in resolved]

    before = {key: (cards.get(OVERRIDE_FIELDS[key][0]) or {}).get(OVERRIDE_FIELDS[key][1]) for key in cleaned}
    try:
        result = validate_card_mutation(str(rfp.id), payload)
    except CardMutationValidationError as exc:
        raise AdminInputError(
            exc.messages[0] if exc.messages else str(exc),
            extra={"alternatives": getattr(exc, "alternatives", [])},
        )
    if not result.get("ok"):
        raise AdminInputError(result.get("error") or "The correction could not be applied.")

    rfp.refresh_from_db()
    remaining = [f for f in (rfp.amber_conflict_fields_json or []) if f not in resolved]
    if remaining != list(rfp.amber_conflict_fields_json or []):
        rfp.amber_conflict_fields_json = remaining
        rfp.save(update_fields=["amber_conflict_fields_json", "updated_at"])

    audit.record(actor, "debate.override", "rfp", rfp.id, before=before, after=cleaned, note=note or "")
    return {"ok": True, "quote": result.get("quote")}


def attention_items(limit: int = 10) -> list[dict]:
    qs = (
        RFPSubmission.objects.filter(
            Q(status=RFPStatus.ESCALATED)
            | (~Q(amber_conflict_fields_json=[]) & ~Q(status=RFPStatus.BOOKED))
        )
        .order_by("-updated_at")[:limit]
    )
    items = []
    for rfp in qs:
        items.append(
            {
                "rfp_id": str(rfp.id),
                "company_name": company_name(rfp),
                "status": rfp.status,
                "reason": "escalated" if rfp.status == RFPStatus.ESCALATED else "amber_fields",
            }
        )
    return items
