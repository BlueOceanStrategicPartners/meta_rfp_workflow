from django.test import SimpleTestCase

from apps.designer_studio.designer_validation import filter_muse_validation_issues


class DesignerValidationFilterTests(SimpleTestCase):
    def test_filters_prompt_truncation_and_token_noise(self):
        raw = [
            "Compiled preview truncated: CSS ends mid-rule",
            "Placeholders not verifiable: {{client_name}} has no resolved values",
            "Header nav is broken: icon-btn elements are empty",
        ]
        kept = filter_muse_validation_issues(raw)
        self.assertEqual(kept, ["Header nav is broken: icon-btn elements are empty"])
