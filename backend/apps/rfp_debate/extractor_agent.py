from __future__ import annotations

from django.conf import settings

from .meta_client import MetaModelClient, parse_extraction
from .schemas import RFPExtractionPayload


class ExtractorAgent:
    def __init__(self, client: MetaModelClient | None = None):
        self.client = client or MetaModelClient()

    def extract(
        self,
        document_text: str,
        *,
        use_spark: bool = False,
        targeted_fields: list[str] | None = None,
    ) -> RFPExtractionPayload:
        model_id = settings.META_MODEL_SPARK
        effort = None
        prompt = (
            "Extract RFP fields as JSON matching RFPExtractionPayload schema. "
            "Every field must include source_citation with page_number and verbatim_quote."
        )
        if targeted_fields:
            prompt += f" Re-extract only: {', '.join(targeted_fields)}."
        raw = self.client.complete_json(
            model_id=model_id,
            system_prompt=prompt,
            user_content=document_text,
            reasoning_effort=effort,
        )
        return parse_extraction(raw)
