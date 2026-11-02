from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from apps.designer_studio.designer_langgraph import DesignerAgentGraph
from apps.designer_studio.designer_planner_agent import DesignerPlannerAgent
from apps.designer_studio.template_workspace import TemplateWorkspace


@override_settings(USE_FIXTURE_DEBATE=True)
class DesignerPlannerAgentTests(SimpleTestCase):
    def test_planner_returns_exec_todos_one_shot(self):
        planner = DesignerPlannerAgent()
        emitted: list[list] = []

        def on_todo(todos):
            emitted.append(list(todos))

        ws = TemplateWorkspace(html_markup="", css_stylesheet="", js_script="")
        result = planner.create_plan(
            message="Fix invalid button URLs in the proposal nav",
            workspace=ws,
            context_prefix="",
            on_todo_event=on_todo,
        )
        self.assertIn(result.source, ("llm", "fallback"))
        self.assertTrue(result.todos)
        self.assertEqual(emitted[0][0]["id"], "planning")
        self.assertTrue(any(str(t.get("id", "")).startswith("exec_") for t in result.todos))
        self.assertEqual(result.todos[-1]["id"], "finalize")


@override_settings(USE_FIXTURE_DEBATE=True, DESIGNER_LANGGRAPH_CHECKPOINT_BACKEND="memory")
class DesignerAgentGraphTests(SimpleTestCase):
    def setUp(self):
        from apps.designer_studio.designer_graph_checkpointer import reset_designer_graph_runtime_for_tests
        from apps.designer_studio.designer_langgraph import reset_compiled_designer_graph_for_tests

        reset_designer_graph_runtime_for_tests()
        reset_compiled_designer_graph_for_tests()
        self._compile_patch = patch(
            "apps.designer_studio.designer_validation.compile_template",
            return_value="<compiled-preview/>",
        )
        self._compile_patch.start()

    def tearDown(self):
        self._compile_patch.stop()

    def test_graph_runs_planner_then_executor(self):
        graph = DesignerAgentGraph()
        nodes_seen: list[str] = []

        def on_tool(evt):
            if evt.get("tool") in (
                "planner_agent",
                "executor_agent",
                "validator_agent",
                "validator_repair",
            ):
                nodes_seen.append(str(evt["tool"]))

        out = graph.run_edit_turn(
            message="Fix header links that go to wrong pages",
            history=[],
            html_markup="<div>{{client_name}}</div>",
            css_stylesheet="body{}",
            js_script="",
            context_prefix="",
            on_tool_event=on_tool,
        )
        self.assertIn("planner_agent", out.get("graph_nodes") or [])
        self.assertIn("executor_agent", out.get("graph_nodes") or [])
        self.assertEqual(out.get("agent_mode"), "langgraph")
        self.assertIn("planner_agent", nodes_seen)
        self.assertIn("executor_agent", nodes_seen)
        self.assertIn("validator_agent", nodes_seen)
        self.assertTrue(out.get("agent_todos") is not None or out.get("html_markup"))
