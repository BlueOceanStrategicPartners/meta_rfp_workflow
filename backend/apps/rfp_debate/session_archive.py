"""Toggle client session archived flag on RFPSubmission.client_session_json."""
from __future__ import annotations

from apps.negotiation_agent.client_session_memory import normalize_session
from apps.rfp_debate.client_session_list import serialize_rfp_session_summary
from apps.rfp_debate.models import RFPSubmission


def parse_archived_flag(value) -> bool:
    if isinstance(value, str):
        return value.lower() in {"1", "true", "yes"}
    return bool(value)


def apply_session_archive(rfp: RFPSubmission, archived: bool) -> dict:
    session = normalize_session(rfp.client_session_json)
    session["archived"] = archived
    rfp.client_session_json = session
    rfp.save(update_fields=["client_session_json", "updated_at"])
    return serialize_rfp_session_summary(rfp)
