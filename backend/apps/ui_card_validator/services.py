from __future__ import annotations

from decimal import Decimal

from apps.core.exceptions import CardMutationValidationError
from apps.dynamic_pricing.services import compute_dynamic_quote
from apps.inventory.models import SpaceInventory, VenueMapZone
from apps.rfp_debate.models import RFPSubmission, RFPStatus
from apps.rfp_debate.tasks import broadcast_rfp


def validate_card_mutation(session_id: str, payload: dict) -> dict:
    try:
        rfp = RFPSubmission.objects.get(pk=session_id)
    except RFPSubmission.DoesNotExist:
        return {"ok": False, "error": "RFP session not found"}

    meeting = payload.get("meeting_space") or rfp.active_ui_cards_json.get("meeting_space", {})
    headcount = meeting.get("headcount") or 0
    zone_id = meeting.get("selected_zone_id")
    seating_style = (meeting.get("seating_style") or "classroom").lower()

    if zone_id:
        try:
            zone = VenueMapZone.objects.select_related("space_inventory").get(pk=zone_id)
        except VenueMapZone.DoesNotExist:
            raise CardMutationValidationError("Selected map zone not found.")
        space = zone.space_inventory
        if space:
            capacities = space.capacities_json or {}
            cap = capacities.get(seating_style) or capacities.get("classroom") or 0
            if headcount and cap and headcount > cap:
                alternatives = _suggest_alternatives(headcount, seating_style, zone.venue_map_id)
                broadcast_rfp(
                    session_id,
                    "map_highlight",
                    {"zone_ids": [str(z.id) for z in alternatives], "reason": "capacity"},
                )
                exc = CardMutationValidationError(
                    f"Headcount {headcount} exceeds {space.name} capacity {cap}."
                )
                exc.alternatives = [str(z.id) for z in alternatives]
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
    rfp.save(update_fields=["active_ui_cards_json", "status"])
    broadcast_rfp(session_id, "cards_patch", {"cards": cards})

    return {
        "ok": True,
        "quote": {
            "walk_away_floor_price": str(quote.walk_away_floor_price),
            "optimal_target_price": str(quote.optimal_target_price),
            "initial_anchor_price": str(quote.initial_anchor_price),
            "shap": quote.shap_explanations_json,
        },
    }


def _suggest_alternatives(headcount: int, seating_style: str, venue_map_id) -> list[VenueMapZone]:
    zones = VenueMapZone.objects.filter(venue_map_id=venue_map_id).select_related(
        "space_inventory"
    )
    result = []
    for zone in zones:
        space = zone.space_inventory
        if not space:
            continue
        cap = (space.capacities_json or {}).get(seating_style) or (space.capacities_json or {}).get(
            "classroom", 0
        )
        if cap >= headcount:
            result.append(zone)
    return result[:3]
