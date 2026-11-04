"""Compile default proposal template for client approval and push over websocket."""
from __future__ import annotations

import logging

from apps.designer_studio.models import ProposalTemplate
from apps.designer_studio.services import compile_template
from apps.dynamic_pricing.models import DynamicPricingQuote, RenderedProposal
from apps.rfp_debate.models import RFPStatus, RFPSubmission
from apps.rfp_debate.tasks import broadcast_rfp

logger = logging.getLogger(__name__)


def render_proposal_for_rfp(rfp: RFPSubmission) -> str | None:
    template = ProposalTemplate.objects.filter(is_default=True).first()
    if not template:
        logger.warning("render_proposal_for_rfp: no default template")
        return None
    quote = DynamicPricingQuote.objects.filter(rfp=rfp).order_by("-created_at").first()
    cards = dict(rfp.active_ui_cards_json or {})
    catering_av = cards.get("catering_av") or {}
    meeting = dict(cards.get("meeting_space") or {})
    if catering_av.get("av") and not meeting.get("av"):
        meeting["av"] = catering_av.get("av")
        cards["meeting_space"] = meeting
    compiled = compile_template(
        template.html_markup,
        template.css_stylesheet,
        js_script=template.js_script,
        cards=cards,
        quote=quote,
        use_seed_if_empty=False,
    )
    RenderedProposal.objects.update_or_create(
        rfp=rfp,
        defaults={"template": template, "compiled_proposal_html": compiled},
    )
    rfp.status = RFPStatus.PROPOSAL_RENDERED
    rfp.save(update_fields=["status", "updated_at"])
    broadcast_rfp(str(rfp.id), "proposal_html", {"html": compiled})
    return compiled
