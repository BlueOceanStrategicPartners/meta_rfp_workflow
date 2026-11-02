from django.test import SimpleTestCase

from apps.rfp_debate.muse_structured_schemas import (
    FIXTURE_STRUCTURED_SCHEMAS,
    structured_response_format,
    structured_response_format_for_fixture,
)


class MuseStructuredSchemasTests(SimpleTestCase):
    def test_tool_loop_fixture_maps_to_json_schema_format(self):
        fmt = structured_response_format_for_fixture("designer_tool_loop")
        self.assertIsNotNone(fmt)
        assert fmt is not None
        self.assertEqual(fmt["type"], "json_schema")
        self.assertEqual(fmt["json_schema"]["name"], "DesignerToolLoopStep")
        self.assertIn("kind", fmt["json_schema"]["schema"]["properties"])

    def test_all_designer_fixture_kinds_have_schemas(self):
        for kind in (
            "designer_tool_loop",
            "designer_execution_plan",
            "designer_chat",
            "designer_validate",
            "map_chat",
            "map_validate",
            "rfp_extraction",
            "rfp_critique",
            "voice_reply",
        ):
            self.assertIn(kind, FIXTURE_STRUCTURED_SCHEMAS)

    def test_structured_response_format_strict_default_false(self):
        fmt = structured_response_format(name="Test", schema={"type": "object", "properties": {}})
        self.assertFalse(fmt["json_schema"]["strict"])
