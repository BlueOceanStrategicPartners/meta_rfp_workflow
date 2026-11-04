"""Handle interactive proposal events from the client iframe (postMessage → WebSocket)."""
from __future__ import annotations

from typing import Any

from apps.core.exceptions import CardMutationValidationError
from apps.negotiation_agent.client_session_memory import append_session_event
from apps.rfp_debate.models import RFPStatus, RFPSubmission
from apps.rfp_debate.tasks import broadcast_rfp

_ALLOWED_PATCH_SECTIONS = frozenset(
    {"event_overview", "room_block", "meeting_space", "catering_av"}
)


def filter_card_patch(raw: dict | None) -> dict:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, Any] = {}
    for section, fields in raw.items():
        if section not in _ALLOWED_PATCH_SECTIONS or not isinstance(fields, dict):
            continue
        cleaned = {k: v for k, v in fields.items() if v is not None and v != ""}
        if cleaned:
            out[section] = cleaned
    return out


def handle_proposal_interaction(session_id: str, payload: dict) -> dict:
    try:
        rfp = RFPSubmission.objects.get(pk=session_id)
    except RFPSubmission.DoesNotExist:
        return {"ok": False, "error": "RFP session not found"}

    action = str(payload.get("action") or "interaction")[:64]
    label = str(payload.get("label") or action)[:200]
    kind = str(payload.get("kind") or "event").lower()
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    card_patch = filter_card_patch(payload.get("cardPatch") or payload.get("card_patch"))

    if kind == "mutation" and card_patch:
        from apps.ui_card_validator.services import validate_card_mutation

        try:
            result = validate_card_mutation(session_id, card_patch)
        except CardMutationValidationError as exc:
            return {"ok": False, "error": str(exc)}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

        rfp.refresh_from_db(fields=["status", "client_session_json", "active_ui_cards_json"])
        append_session_event(
            rfp,
            event_type="proposal_mutation",
            summary=label,
            meta={"action": action, "source": "proposal", "patch_keys": list(card_patch.keys())},
        )
        rfp.save(update_fields=["client_session_json", "updated_at"])
        if rfp.status in (
            RFPStatus.NEGOTIATING,
            RFPStatus.PROPOSAL_RENDERED,
            RFPStatus.PRICING,
        ):
            from apps.negotiation_agent.proposal_render import render_proposal_for_rfp

            render_proposal_for_rfp(rfp)
        broadcast_rfp(
            session_id,
            "client_session_patch",
            {"session": rfp.client_session_json},
        )
        return {**result, "proposal_rerendered": True}

    append_session_event(
        rfp,
        event_type="proposal_interaction",
        summary=label,
        meta={"action": action, "source": "proposal", **meta},
    )
    rfp.save(update_fields=["client_session_json", "updated_at"])
    broadcast_rfp(
        session_id,
        "client_session_patch",
        {"session": rfp.client_session_json},
    )
    return {"ok": True, "event_only": True}
