from django.test import SimpleTestCase

from apps.designer_studio.context_budget import trim_chat_history
from apps.designer_studio.preview_target_context import expand_user_turn_content_for_agent


class PreviewTargetContextTests(SimpleTestCase):
    def test_expand_user_turn_with_preview_target(self):
        turn = {
            "role": "user",
            "content": "use cards instead of table",
            "preview_target": {
                "sectionLabel": "Rooms",
                "sectionId": "rooms",
                "tag": "section",
                "selectorHint": "#rooms",
            },
        }
        expanded = expand_user_turn_content_for_agent(turn)
        self.assertIn("[Live preview target", expanded)
        self.assertIn("use cards instead of table", expanded)
        self.assertIn("#rooms", expanded)

    def test_trim_history_expands_preview_target(self):
        history = [
            {
                "role": "user",
                "content": "fix spacing",
                "preview_target": {"sectionId": "hero", "sectionLabel": "Hero", "tag": "section"},
            }
        ]
        trimmed = trim_chat_history(history)
        self.assertEqual(len(trimmed), 1)
        self.assertIn("[Live preview target", trimmed[0]["content"])
