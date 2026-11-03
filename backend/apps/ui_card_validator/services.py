from __future__ import annotations

from decimal import Decimal

from apps.core.exceptions import CardMutationValidationError
from apps.dynamic_pricing.services import compute_dynamic_quote
from apps.inventory.models import SpaceInventory
from apps.rfp_debate.models import RFPSubmission, RFPStatus
from apps.negotiation_agent.client_session_memory import (
    append_session_event,
    build_card_mutation_ack,
    sync_clarifications_from_cards,
)
from apps.rfp_debate.tasks import broadcast_rfp

from .inventory_suggest import _suggest_alternative_spaces


def _stay_complete(cards: dict) -> bool:
    overview = cards.get("event_overview") or {}
    room = cards.get("room_block") or {}
    cin = (overview.get("check_in_date") or "").strip()
    cout = (overview.get("check_out_date") or "").strip()
    nights = room.get("total_room_nights")
    if not cin or cin.upper() == "TBD":
        return False
    if nights:
        try:
            return int(nights) > 0
        except (TypeError, ValueError):
            pass
    if cout and cout.upper() != "TBD" and cout != cin:
        return True
    return False


def validate_card_mutation(session_id: str, payload: dict) -> dict:
    try:
        rfp = RFPSubmission.objects.get(pk=session_id)
    except RFPSubmission.DoesNotExist:
        return {"ok": False, "error": "RFP session not found"}

    meeting = payload.get("meeting_space") or rfp.active_ui_cards_json.get("meeting_space", {})
    headcount = meeting.get("headcount") or 0
    seating_style = (meeting.get("seating_style") or "classroom").lower()
    zone_id = meeting.get("selected_zone_id") or meeting.get("selected_space_id")

    if zone_id:
        try:
            space = SpaceInventory.objects.get(pk=zone_id)
        except SpaceInventory.DoesNotExist:
            raise CardMutationValidationError("Selected meeting space not found.")
        capacities = space.capacities_json or {}
        cap = capacities.get(seating_style) or capacities.get("classroom") or 0
        if headcount and cap and headcount > cap:
            alternatives = _suggest_alternative_spaces(
                headcount, seating_style, space.property_id
            )
            broadcast_rfp(
                session_id,
                "map_highlight",
                {"zone_ids": [str(s.id) for s in alternatives], "reason": "capacity"},
            )
            exc = CardMutationValidationError(
                f"Headcount {headcount} exceeds {space.name} capacity {cap}."
            )
            exc.alternatives = [str(s.id) for s in alternatives]
            raise exc

    cards = dict(rfp.active_ui_cards_json or {})
    for key, val in payload.items():
        if isinstance(val, dict) and isinstance(cards.get(key), dict):
            cards[key] = {**cards[key], **val}
        else:
            cards[key] = val

    overview = cards.get("event_overview") or {}
    cin = (overview.get("check_in_date") or "").strip()
    if cin and cin.upper() != "TBD":
        from datetime import date as date_cls

        from apps.negotiation_agent.voice_dates import validate_stay_not_in_past, voice_today

        try:
            check_in = date_cls.fromisoformat(cin[:10])
            cout = (overview.get("check_out_date") or "").strip()
            check_out = date_cls.fromisoformat(cout[:10]) if cout else check_in
        except ValueError:
            check_in = None
            check_out = None
        if check_in:
            err = validate_stay_not_in_past(check_in, check_out)
            if err:
                raise CardMutationValidationError(err)
            if check_in < voice_today():
                raise CardMutationValidationError(
                    f"Check-in cannot be before today ({voice_today().isoformat()})."
                )
    rfp.active_ui_cards_json = cards

    if not _stay_complete(cards):
        rfp.save(update_fields=["active_ui_cards_json", "updated_at"])
        sync_clarifications_from_cards(rfp)
        rfp.save(
            update_fields=[
                "active_ui_cards_json",
                "client_session_json",
                "updated_at",
            ]
        )
        broadcast_rfp(session_id, "cards_patch", {"cards": cards})
        broadcast_rfp(
            session_id,
            "client_session_patch",
            {"session": rfp.client_session_json},
        )
        return {"ok": True, "quote": None, "incomplete_stay": True}

    rfp.status = RFPStatus.PRICING
    rfp.save(update_fields=["active_ui_cards_json", "status", "updated_at"])

    quote = compute_dynamic_quote(rfp)
    cards["live_quote"] = {
        "anchor_price": str(quote.initial_anchor_price),
        "floor_price": str(quote.walk_away_floor_price),
        "target_price": str(quote.optimal_target_price),
    }
    rfp.active_ui_cards_json = cards
    rfp.status = RFPStatus.NEGOTIATING
    append_session_event(
        rfp,
        event_type="card_edit",
        summary=build_card_mutation_ack(payload, cards).replace("Got it — I updated ", "Updated "),
        meta={"source": "ui_or_voice"},
    )
    sync_clarifications_from_cards(rfp)
    rfp.save(
        update_fields=[
            "active_ui_cards_json",
            "status",
            "client_session_json",
            "updated_at",
        ]
    )
    broadcast_rfp(session_id, "cards_patch", {"cards": cards})
    utterance = build_card_mutation_ack(payload, cards)
    broadcast_rfp(session_id, "agent_utterance", {"text": utterance})
    broadcast_rfp(
        session_id,
        "client_session_patch",
        {"session": rfp.client_session_json},
    )

    return {
        "ok": True,
        "quote": {
            "walk_away_floor_price": str(quote.walk_away_floor_price),
            "optimal_target_price": str(quote.optimal_target_price),
            "initial_anchor_price": str(quote.initial_anchor_price),
            "shap": quote.shap_explanations_json,
        },
    }

