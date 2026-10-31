from decimal import Decimal

from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts_rbac.permissions import IsAdminRole
from apps.guardrails.validators import enforce_floor_price, validate_negotiation_text
from apps.rfp_debate.models import RFPSubmission

from .models import DynamicPricingQuote
from .services import compute_dynamic_quote, train_and_save_model


class AdminPricingGuardrailView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request):
        from django.conf import settings

        return Response(
            {
                "walk_away_floor_margin_pct": settings.WALK_AWAY_FLOOR_MARGIN_PCT,
                "max_autonomous_discount_pct": settings.MAX_AUTONOMOUS_DISCOUNT_PCT,
            }
        )


class AdminPricingRetrainView(APIView):
    permission_classes = [IsAdminRole]

    def post(self, request):
        from apps.inventory.models import VenueProperty

        prop = VenueProperty.objects.first()
        if not prop:
            return Response({"status": "no_property"}, status=400)
        path = train_and_save_model(prop.id)
        return Response({"status": "ok", "artifact": path})


class QuoteDetailView(APIView):
    def get(self, request, rfp_id):
        quote = DynamicPricingQuote.objects.filter(rfp_id=rfp_id).order_by("-created_at").first()
        if not quote:
            return Response({"detail": "No quote"}, status=404)
        return Response(
            {
                "walk_away_floor_price": str(quote.walk_away_floor_price),
                "optimal_target_price": str(quote.optimal_target_price),
                "initial_anchor_price": str(quote.initial_anchor_price),
                "shap": quote.shap_explanations_json,
                "used_fallback": quote.used_fallback_engine,
            }
        )


class RenderProposalView(APIView):
    def post(self, request, rfp_id):
        from apps.designer_studio.models import ProposalTemplate
        from apps.dynamic_pricing.models import RenderedProposal

        rfp = RFPSubmission.objects.get(pk=rfp_id)
        template = ProposalTemplate.objects.filter(is_default=True).first()
        if not template:
            return Response({"detail": "No default template"}, status=400)
        quote = DynamicPricingQuote.objects.filter(rfp=rfp).order_by("-created_at").first()
        cards = rfp.active_ui_cards_json or {}
        html = template.html_markup
        replacements = {
            "{{client_name}}": str(cards.get("event_overview", {}).get("company_name", "")),
            "{{event_dates}}": f"{cards.get('event_overview', {}).get('check_in_date')} - {cards.get('event_overview', {}).get('check_out_date')}",
            "{{verified_room_blocks}}": str(cards.get("room_block", {})),
            "{{selected_map_svg}}": "",
            "{{meeting_space_specs}}": str(cards.get("meeting_space", {})),
            "{{xgboost_quote_breakdown}}": str(
                {
                    "floor": str(quote.walk_away_floor_price) if quote else "",
                    "target": str(quote.optimal_target_price) if quote else "",
                    "anchor": str(quote.initial_anchor_price) if quote else "",
                }
            ),
            "{{negotiated_concessions}}": "",
            "{{cta_accept_button}}": '<button type="button">Accept Proposal</button>',
        }
        for token, value in replacements.items():
            html = html.replace(token, value)
        rendered = RenderedProposal.objects.update_or_create(
            rfp=rfp,
            defaults={"template": template, "compiled_proposal_html": html},
        )[0]
        from apps.rfp_debate.models import RFPStatus

        rfp.status = RFPStatus.PROPOSAL_RENDERED
        rfp.save(update_fields=["status"])
        return Response({"html": rendered.compiled_proposal_html})
