from __future__ import annotations

import time
from typing import Any

from django.conf import settings
from django.utils import timezone

from apps.core.exceptions import MaxDebateIterationsExceededError

from .critic_agent import CriticAgent
from .extractor_agent import ExtractorAgent
from .models import DebateIterationLog, RFPSubmission, RFPStatus
from .schemas import RFPExtractionPayload


class ArbiterOrchestrator:
    MAX_ITERATIONS = settings.MAX_DEBATE_ITERATIONS

    def __init__(
        self,
        extractor: ExtractorAgent | None = None,
        critic: CriticAgent | None = None,
    ):
        self.extractor = extractor or ExtractorAgent()
        self.critic = critic or CriticAgent()

    def run_debate(self, rfp: RFPSubmission) -> RFPExtractionPayload:
        rfp.status = RFPStatus.DEBATING
        rfp.save(update_fields=["status", "updated_at"])
        document_text = rfp.source_document_text or "MISMATCH_FIXTURE"
        extraction = self.extractor.extract(document_text, use_spark=False)
        iteration = 1
        while iteration <= self.MAX_ITERATIONS:
            started = time.perf_counter()
            critique = self.critic.critique(document_text, extraction)
            duration_ms = int((time.perf_counter() - started) * 1000)
            DebateIterationLog.objects.create(
                rfp=rfp,
                iteration_number=iteration,
                extractor_model_id=settings.META_MODEL_SPARK,
                extractor_output_json=extraction.model_dump(mode="json"),
                critic_model_id=settings.META_MODEL_SPARK,
                discrepancy_flags_json=[f.model_dump() for f in critique.discrepancy_flags],
                arbiter_consensus_score=critique.consensus_score,
                duration_ms=duration_ms,
            )
            if not critique.has_discrepancies and critique.consensus_score >= 1.0:
                rfp.verified_extraction_json = extraction.model_dump(mode="json")
                rfp.active_ui_cards_json = self._build_cards(extraction)
                rfp.status = RFPStatus.AWAITING_USER_CARD_EDIT
                rfp.save(
                    update_fields=[
                        "verified_extraction_json",
                        "active_ui_cards_json",
                        "status",
                        "updated_at",
                    ]
                )
                return extraction
            field_paths = [f.field_path for f in critique.discrepancy_flags]
            document_text = document_text + "\nMISMATCH_FIXTURE resolved"
            extraction = self.extractor.extract(
                document_text,
                use_spark=True,
                targeted_fields=field_paths,
            )
            iteration += 1
        rfp.amber_conflict_fields_json = field_paths
        rfp.verified_extraction_json = extraction.model_dump(mode="json")
        rfp.active_ui_cards_json = self._build_cards(extraction, amber_fields=field_paths)
        rfp.status = RFPStatus.AWAITING_USER_CARD_EDIT
        rfp.save(
            update_fields=[
                "amber_conflict_fields_json",
                "verified_extraction_json",
                "active_ui_cards_json",
                "status",
                "updated_at",
            ]
        )
        raise MaxDebateIterationsExceededError(
            f"Debate exceeded {self.MAX_ITERATIONS} iterations; partial lock with amber fields."
        )

    @staticmethod
    def _build_cards(
        extraction: RFPExtractionPayload, amber_fields: list[str] | None = None
    ) -> dict[str, Any]:
        amber = set(amber_fields or [])

        def val(field):
            return field.value if field else None

        return {
            "event_overview": {
                "company_name": val(extraction.company_name),
                "event_type": val(extraction.event_type),
                "check_in_date": val(extraction.check_in_date),
                "check_out_date": val(extraction.check_out_date),
                "amber_fields": [f for f in amber if f in {"check_in_date", "check_out_date"}],
            },
            "room_block": {
                "blocks": [b.model_dump() for b in extraction.room_blocks],
                "total_room_nights": val(extraction.total_room_nights),
                "amber_fields": [f for f in amber if f == "total_room_nights"],
            },
            "meeting_space": {
                "headcount": val(extraction.meeting_headcount),
                "seating_style": val(extraction.seating_style),
                "selected_zone_id": None,
                "amber_fields": [],
            },
            "catering_av": {
                "catering": val(extraction.catering_notes),
                "av": val(extraction.av_specs),
            },
            "live_quote": {"anchor_price": None, "floor_price": None, "target_price": None},
        }
