from django.test import SimpleTestCase

from apps.designer_studio.designer_user_labels import (
    format_user_tool_trace_summary,
    sanitize_user_visible_label,
    user_tool_label,
)


class DesignerUserLabelTests(SimpleTestCase):
    def test_tool_labels_are_plain_language(self):
        self.assertEqual(user_tool_label("read_template_lines"), "Review part of the proposal")
        self.assertEqual(user_tool_label("validate_template"), "Run quality checks")

    def test_trace_summary_hides_technical_detail(self):
        summary = format_user_tool_trace_summary(
            "search_template",
            {"ok": True, "hits": [{}, {}, {}]},
        )
        self.assertIn("Search the proposal", summary)
        self.assertNotIn("match(es)", summary.lower())

    def test_sanitize_strips_langgraph_jargon(self):
        raw = "Validator (LangGraph): checking template against brief…"
        cleaned = sanitize_user_visible_label(raw)
        self.assertNotIn("LangGraph", cleaned)
        self.assertTrue(cleaned)
