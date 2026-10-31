from apps.negotiation_agent.voice_scenario import build_autonomous_voice_intro
from apps.rfp_debate.models import RFPSubmission

__all__ = ["build_autonomous_voice_intro", "build_voice_intro_for_rfp"]


def build_voice_intro_for_rfp(rfp: RFPSubmission, *, partial: bool = False) -> str:
    return build_autonomous_voice_intro(rfp, partial=partial)
