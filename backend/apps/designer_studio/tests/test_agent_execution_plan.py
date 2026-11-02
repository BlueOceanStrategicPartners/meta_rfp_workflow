from django.test import SimpleTestCase, override_settings

from apps.designer_studio.agent_task_plan import AgentTodoTracker
from apps.designer_studio.agent_execution_plan import (
    generate_execution_plan,
    planning_placeholder_todos,
    sync_execution_plan_after_tool,
    uses_execution_plan_todos,
)
from apps.designer_studio.template_symbol_index import execute_list_template_symbols
from apps.designer_studio.template_workspace import TemplateWorkspace


@override_settings(USE_FIXTURE_DEBATE=True)
class AgentExecutionPlanTests(SimpleTestCase):
    def test_planning_wait_single_active_step(self):
        todos = planning_placeholder_todos()
        self.assertEqual(len(todos), 1)
        self.assertEqual(todos[0]["id"], "planning")
        self.assertEqual(todos[0]["status"], "active")

    def test_generate_execution_plan_uses_agent_steps_from_model(self):
        ws = TemplateWorkspace(html_markup="", css_stylesheet="", js_script="")
        todos = generate_execution_plan(
            message="Create an interactive proposal with blue header links",
            workspace=ws,
            context_prefix="Rule: use brand colors.",
        )
        self.assertTrue(uses_execution_plan_todos(todos))
        active = [t for t in todos if t.get("status") == "active"]
        self.assertEqual(len(active), 1)
        self.assertTrue(str(active[0]["id"]).startswith("exec_"))
        self.assertEqual(todos[-1]["id"], "finalize")
        labels = [str(t.get("label") or "") for t in todos if str(t.get("id", "")).startswith("exec_")]
        self.assertNotIn(
            "Inspect the template and locate files or symbols to change",
            labels,
        )

    def test_mutate_tool_advances_exec_step_when_no_validation_gate(self):
        todos = generate_execution_plan(
            message="Fix nav color",
            workspace=TemplateWorkspace(html_markup="<p>{{client_name}}</p>", css_stylesheet="a{}", js_script=""),
            context_prefix="",
        )
        tracker = AgentTodoTracker(todos)
        first_exec = next(t for t in tracker.snapshot() if t.get("status") == "active")
        sync_execution_plan_after_tool(
            tracker,
            tool_name="replace_exact",
            result={"ok": True, "replacements": 1},
            repair_mode=False,
        )
        self.assertEqual(tracker.status(str(first_exec["id"])), "done")

    def test_mutate_blocked_when_post_edit_validation_fails(self):
        todos = generate_execution_plan(
            message="Fix nav color",
            workspace=TemplateWorkspace(html_markup="<p>{{client_name}}</p>", css_stylesheet="a{}", js_script=""),
            context_prefix="",
        )
        tracker = AgentTodoTracker(todos)
        first_exec = next(t for t in tracker.snapshot() if t.get("status") == "active")
        sync_execution_plan_after_tool(
            tracker,
            tool_name="replace_exact",
            result={
                "ok": True,
                "replacements": 1,
                "validation_after_mutate": {"valid": False, "issues": ["Header nav is broken"]},
            },
            repair_mode=False,
        )
        self.assertEqual(tracker.status(str(first_exec["id"])), "active")

    def test_list_template_symbols_accepts_api_field_file_names(self):
        ws = TemplateWorkspace(
            html_markup='<header class="nav"><a class="icon-btn"></a></header>',
            css_stylesheet=".nav{display:flex}",
            js_script="",
        )
        out = execute_list_template_symbols(
            ws,
            {"file": "html_markup", "kind": "html_element", "max_items": 10},
        )
        self.assertTrue(out.get("ok"))
        self.assertEqual(out.get("file"), "html")
        out_css = execute_list_template_symbols(
            ws,
            {"file": "css_stylesheet", "kind": "css_rule", "max_items": 10},
        )
        self.assertTrue(out_css.get("ok"))
        self.assertEqual(out_css.get("file"), "css")
