from django.test import SimpleTestCase

from apps.rfp_debate.meta_client import parse_model_json_content


class ParseModelJsonContentTests(SimpleTestCase):
    def test_plain_json(self):
        raw = parse_model_json_content('{"kind":"finish","assistant_message":"ok"}')
        self.assertEqual(raw["kind"], "finish")

    def test_prose_prefix_before_json(self):
        text = 'Building template now.{"kind":"tools","tools":[]}'
        raw = parse_model_json_content(text)
        self.assertEqual(raw["kind"], "tools")
