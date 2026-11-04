from __future__ import annotations

from django.conf import settings
from pydantic import ValidationError

from .meta_client import MetaModelAPIError, MetaModelClient, parse_extraction
from .schemas import RFPExtractionPayload

# A real model call is retried once when the reply is malformed (seen with structured output).
LIVE_ATTEMPTS = 2


class ExtractorAgent:
    def __init__(self, client: MetaModelClient | None = None):
        self.client = client or MetaModelClient()

    @property
    def uses_fixtures(self) -> bool:
        return bool(getattr(self.client, "uses_fixtures", True))

    def extract(
        self,
        document_text: str,
        *,
        use_spark: bool = False,
        targeted_fields: list[str] | None = None,
    ) -> RFPExtractionPayload:
        if use_spark or targeted_fields:
            model_id = settings.META_MODEL_SPARK
            effort = None
        else:
            model_id = settings.META_MODEL_WONDER
            effort = "max"
        prompt = (
            "Extract RFP fields as JSON matching RFPExtractionPayload schema. "
            "Every field must include source_citation with page_number and verbatim_quote."
        )
        if targeted_fields:
            prompt += f" Re-extract only: {', '.join(targeted_fields)}."
        live = not self.uses_fixtures
        attempts = LIVE_ATTEMPTS if live else 1
        last_error: Exception | None = None
        for _ in range(attempts):
            try:
                raw = self.client.complete_json(
                    model_id=model_id,
                    system_prompt=prompt,
                    user_content=document_text,
                    reasoning_effort=effort,
                    fixture_kind="rfp_extraction",
                    # With a real key, a bad reply must never be replaced by the canned
                    # "Acme Corp, June 2026" sample: that would put fake data on a real request.
                    allow_fixture_fallback=not live,
                )
                return parse_extraction(raw)
            except (MetaModelAPIError, ValidationError) as exc:
                last_error = exc
        raise MetaModelAPIError(f"Extraction failed after {attempts} attempt(s): {last_error}", cause=last_error)
