from django.test import SimpleTestCase

from apps.rfp_debate.muse_completion import (
    MuseStructuredValidationError,
    infer_fixture_kind_from_prompt,
    validate_muse_structured_payload,
)
from apps.rfp_debate.muse_structured_schemas import FIXTURE_STRUCTURED_SCHEMAS


class MuseCompletionCheckmateTests(SimpleTestCase):
    def test_every_validator_has_structured_schema(self):
        from apps.rfp_debate.muse_completion import FIXTURE_VALIDATORS

        for kind in FIXTURE_VALIDATORS:
            self.assertIn(
                kind,
                FIXTURE_STRUCTURED_SCHEMAS,
                msg=f"Missing json_schema for {kind}",
            )

    def test_tool_loop_rejects_invalid_kind(self):
        with self.assertRaises(MuseStructuredValidationError) as ctx:
            validate_muse_structured_payload({"kind": "bogus"}, fixture_kind="designer_tool_loop")
        self.assertEqual(ctx.exception.code, "invalid_kind")

    def test_tool_loop_accepts_tools_batch(self):
        raw = validate_muse_structured_payload(
            {"kind": "tools", "tools": [{"tool": "append_template", "arguments": {"file": "html"}}]},
            fixture_kind="designer_tool_loop",
        )
        self.assertEqual(raw["kind"], "tools")

    def test_voice_reply_requires_text(self):
        with self.assertRaises(MuseStructuredValidationError):
            validate_muse_structured_payload({"reply": "  "}, fixture_kind="voice_reply")

    def test_infer_rfp_extraction_from_system_prompt(self):
        kind = infer_fixture_kind_from_prompt(
            fixture_kind=None,
            system_prompt="Extract RFP fields as JSON matching RFPExtractionPayload schema.",
            user_content="doc",
        )
        self.assertEqual(kind, "rfp_extraction")

    def test_infer_rfp_critique_from_system_prompt(self):
        kind = infer_fixture_kind_from_prompt(
            fixture_kind=None,
            system_prompt="Cross-examine extraction JSON against source. Return CritiqueResult JSON.",
            user_content="CROSS-EXAMINE",
        )
        self.assertEqual(kind, "rfp_critique")
