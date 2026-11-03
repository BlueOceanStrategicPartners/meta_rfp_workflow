from django.test import SimpleTestCase

from apps.designer_studio.layout_spacing_validation import (
    collect_trailing_whitespace_issues,
    preview_automation_trailing_gap_issue,
)
from apps.designer_studio.single_file_template import PROPOSAL_SINGLE_FILE_SCAFFOLD


class TrailingWhitespaceValidationTests(SimpleTestCase):
    def test_default_template_passes(self):
        issues = collect_trailing_whitespace_issues(PROPOSAL_SINGLE_FILE_SCAFFOLD, "")
        self.assertEqual(issues, [])

    def test_stacked_min_h_screen_flagged(self):
        html = """
        <body class="min-h-screen">
          <main class="min-h-screen"><section id="a">Hi</section></main>
        </body>
        """
        issues = collect_trailing_whitespace_issues(html, "")
        self.assertTrue(any("stacked min-h-screen" in i.lower() for i in issues))

    def test_trailing_empty_min_height_div(self):
        html = """
        <body>
          <section id="last">Done</section>
          <div class="min-h-[900px]"></div>
        </body>
        """
        issues = collect_trailing_whitespace_issues(html, "")
        self.assertTrue(any("min-h-[900px]" in i for i in issues))

    def test_preview_automation_gap_threshold(self):
        issue = preview_automation_trailing_gap_issue(
            {
                "viewport": {"h": 900},
                "scroll": {"trailingGapPx": 400, "docHeight": 2000},
            }
        )
        self.assertIsNotNone(issue)
        self.assertIn("400px", issue or "")

        ok = preview_automation_trailing_gap_issue(
            {
                "viewport": {"h": 900},
                "scroll": {"trailingGapPx": 80, "docHeight": 1200},
            }
        )
        self.assertIsNone(ok)
