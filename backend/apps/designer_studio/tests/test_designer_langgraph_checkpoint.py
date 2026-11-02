from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from apps.designer_studio.designer_graph_checkpointer import reset_designer_graph_runtime_for_tests
from apps.designer_studio.designer_graph_state import build_graph_thread_id
from apps.designer_studio.designer_langgraph import DesignerAgentGraph, reset_compiled_designer_graph_for_tests


@override_settings(USE_FIXTURE_DEBATE=True, DESIGNER_LANGGRAPH_CHECKPOINT_BACKEND="memory")
class DesignerLangGraphCheckpointTests(SimpleTestCase):
    def setUp(self):
        reset_designer_graph_runtime_for_tests()
        reset_compiled_designer_graph_for_tests()
        self._compile_patch = patch(
            "apps.designer_studio.designer_validation.compile_template",
            return_value="<compiled-preview/>",
        )
        self._compile_patch.start()

    def tearDown(self):
        self._compile_patch.stop()
        reset_designer_graph_runtime_for_tests()

    def test_thread_id_stable_per_user_template(self):
        tid = build_graph_thread_id(user_id=42, template_id="abc-123")
        self.assertEqual(tid, "designer-42-abc-123")

    def test_invoke_persists_checkpoint_thread_metadata(self):
        graph = DesignerAgentGraph()
        thread = build_graph_thread_id(user_id=1, template_id="tpl-1")
        out = graph.run_edit_turn(
            message="Fix nav button URLs",
            history=[],
            html_markup="<p>{{client_name}}</p>",
            css_stylesheet="",
            js_script="",
            graph_thread_id=thread,
        )
        self.assertEqual(out.get("checkpoint_thread_id"), thread)
        state = graph.get_thread_state(thread)
        self.assertIsNotNone(state)
        self.assertTrue(state.get("execution_plan_todos") or state.get("result"))
