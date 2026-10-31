from __future__ import annotations

from django.conf import settings

from .meta_client import MetaModelClient, parse_critique
from .schemas import CritiqueResult, RFPExtractionPayload


class CriticAgent:
    def __init__(self, client: MetaModelClient | None = None):
        self.client = client or MetaModelClient()

    def critique(self, document_text: str, extraction: RFPExtractionPayload) -> CritiqueResult:
        # Deterministic math check before model critique
        flags = []
        if extraction.total_room_nights and extraction.room_blocks:
            block_sum = sum(
                b.single + b.double + b.deluxe + b.suite for b in extraction.room_blocks
            )
            total = extraction.total_room_nights.value
            if isinstance(total, (int, float)) and block_sum != total:
                from .schemas import DiscrepancyFlag

                flags.append(
                    DiscrepancyFlag(
                        field_path="total_room_nights",
                        severity="high",
                        message="Daily room blocks do not sum to stated total room nights",
                        expected=str(block_sum),
                        actual=str(total),
                    )
                )
        raw = self.client.complete_json(
            model_id=settings.META_MODEL_SPARK,
            system_prompt=(
                "Cross-examine extraction JSON against source. "
                "Return CritiqueResult JSON with discrepancy_flags."
            ),
            user_content=(
                f"CROSS-EXAMINE\nSource:\n{document_text}\n\nExtraction:\n{extraction.model_dump_json()}"
            ),
        )
        result = parse_critique(raw)
        if flags:
            merged = {f.field_path: f for f in result.discrepancy_flags}
            for f in flags:
                merged[f.field_path] = f
            result.discrepancy_flags = list(merged.values())
            result.consensus_score = 0.0 if result.discrepancy_flags else 1.0
        return result
