from django.test import SimpleTestCase

from apps.designer_studio.designer_fast_edit import (
    format_edit_target_hints,
    is_localized_edit_request,
    trim_execution_steps_for_request,
)
from apps.designer_studio.template_workspace import TemplateWorkspace


class DesignerFastEditTests(SimpleTestCase):
    def test_localized_request_detected(self):
        self.assertTrue(is_localized_edit_request("Fix header icons and nav links"))
        self.assertFalse(is_localized_edit_request("Create a new proposal from scratch"))

    def test_trim_plan_to_three_for_localized(self):
        steps = [
            {"id": "exec_1", "label": "Review header"},
            {"id": "exec_2", "label": "Add icons"},
            {"id": "exec_3", "label": "Fix map"},
            {"id": "exec_4", "label": "Polish spacing"},
            {"id": "exec_5", "label": "Extra review"},
        ]
        out = trim_execution_steps_for_request("Fix nav icons", steps, max_simple=3, max_standard=5)
        self.assertEqual(len(out), 3)

    def test_edit_target_hints_include_nav(self):
        ws = TemplateWorkspace(
            html_markup='<header class="nav"><nav class="nav-icons"><a class="icon-btn"></a></nav></header>',
            css_stylesheet=".nav-icons{display:flex}.icon-btn{width:2rem}",
            js_script="",
        )
        block = format_edit_target_hints(ws, message="Fix header icons")
        self.assertIn("EDIT TARGET HINTS", block)
        self.assertIn("icon", block.lower())
