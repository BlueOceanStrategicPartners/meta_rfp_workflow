from __future__ import annotations

import re
import time
from typing import Any

from django.conf import settings
from django.utils import timezone

from apps.core.exceptions import MaxDebateIterationsExceededError
from apps.designer_studio.proposal_bindings import (
    line_items_from_legacy_blocks,
    resolve_verified_room_blocks_payload,
)

from .critic_agent import CriticAgent
from .extractor_agent import ExtractorAgent
from .meta_client import MetaModelAPIError
from .models import DebateIterationLog, RFPSubmission, RFPStatus
from .schemas import RFPExtractionPayload


# Fields that are only meaningful together: a flag on one re-checks the whole group
# (e.g. "daily blocks don't sum to the total" can mean either number is wrong).
LINKED_FIELDS = (
    {"total_room_nights", "room_blocks"},
    {"check_in_date", "check_out_date"},
)


def _is_empty(value) -> bool:
    return value is None or value == []


def merge_reextraction(
    previous: RFPExtractionPayload, fresh: RFPExtractionPayload, field_paths: list[str]
) -> RFPExtractionPayload:
    """Apply a targeted re-extraction on top of the previous answer.

    Flagged fields take the fresh value when the model returned one; every other field keeps
    the previous value (a targeted reply leaves them empty, which must not erase good data).
    Empty slots in the previous answer are filled from the fresh one.
    """
    fields = list(RFPExtractionPayload.model_fields)
    targets = {re.split(r"[.\[]", path, maxsplit=1)[0] for path in field_paths if path} & set(fields)
    for group in LINKED_FIELDS:
        if targets & group:
            targets |= group
    update = {}
    for name in fields:
        old, new = getattr(previous, name), getattr(fresh, name)
        if _is_empty(new):
            continue
        if not targets or name in targets or _is_empty(old):
            update[name] = new
    return previous.model_copy(update=update)


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
        sample_mode = bool(getattr(self.extractor, "uses_fixtures", True))
        extraction = self.extractor.extract(document_text, use_spark=False)
        iteration = 1
        field_paths: list[str] = []
        while True:
            started = time.perf_counter()
            critique = self.critic.critique(document_text, extraction)
            duration_ms = int((time.perf_counter() - started) * 1000)
            DebateIterationLog.objects.create(
                rfp=rfp,
                iteration_number=iteration,
                extractor_model_id=(
                    settings.META_MODEL_WONDER if iteration == 1 else settings.META_MODEL_SPARK
                ),
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
            if iteration >= self.MAX_ITERATIONS:
                break  # lock the last *checked* answer; never one the critic has not seen
            if sample_mode:
                # Test/demo hook for the canned critic; never added to a real client's text.
                document_text = document_text + "\nMISMATCH_FIXTURE resolved"
            try:
                fresh = self.extractor.extract(
                    document_text,
                    use_spark=True,
                    targeted_fields=field_paths,
                )
            except MetaModelAPIError:
                break  # keep the last good answer; the flagged fields stay amber for the client
            extraction = merge_reextraction(extraction, fresh, field_paths)
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

        overview = {
            "check_in_date": val(extraction.check_in_date),
            "check_out_date": val(extraction.check_out_date),
        }
        room_block_base = {
            "blocks": [b.model_dump() for b in extraction.room_blocks],
            "total_room_nights": val(extraction.total_room_nights),
            "amber_fields": [f for f in amber if f == "total_room_nights"],
        }
        line_items = line_items_from_legacy_blocks(room_block_base, event_overview=overview)
        if line_items:
            room_block_base["line_items"] = line_items
            payload = resolve_verified_room_blocks_payload(room_block_base, event_overview=overview)
            if payload.get("summary"):
                room_block_base["summary"] = payload["summary"]

        return {
            "event_overview": {
                "company_name": val(extraction.company_name),
                "event_type": val(extraction.event_type),
                "check_in_date": val(extraction.check_in_date),
                "check_out_date": val(extraction.check_out_date),
                "amber_fields": [f for f in amber if f in {"check_in_date", "check_out_date"}],
            },
            "room_block": room_block_base,
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
