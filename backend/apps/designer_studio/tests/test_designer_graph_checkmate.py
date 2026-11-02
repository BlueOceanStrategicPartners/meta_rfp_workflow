from django.test import SimpleTestCase

from apps.designer_studio.designer_graph_checkmate import (
    DesignerGraphTerminal,
    resolve_planner_terminal,
    route_after_planner,
    route_graph_start,
)


class DesignerGraphCheckmateTests(SimpleTestCase):
    def test_start_routes_continuation_to_executor_only(self):
        self.assertEqual(route_graph_start("Continue — finish the remaining edits"), "executor_continuation")
        self.assertEqual(route_graph_start("Fix nav links"), "planner")

    def test_planner_happy_path(self):
        terminal = resolve_planner_terminal(plan_source="llm", todos=[{"id": "exec_1"}], error=None)
        self.assertEqual(terminal, DesignerGraphTerminal.PLAN_READY)
        self.assertEqual(route_after_planner(terminal), "executor")

    def test_planner_worst_case_aborts_graph(self):
        terminal = resolve_planner_terminal(plan_source="", todos=[], error=None)
        self.assertEqual(terminal, DesignerGraphTerminal.PLAN_FAILED)
        self.assertEqual(route_after_planner(terminal), "end_abort")

    def test_planner_structured_validation_uses_fallback(self):
        from apps.rfp_debate.muse_completion import MuseStructuredValidationError

        terminal = resolve_planner_terminal(
            plan_source="",
            todos=[],
            error=MuseStructuredValidationError("empty_steps", "no steps", fixture_kind="designer_execution_plan"),
        )
        self.assertEqual(terminal, DesignerGraphTerminal.PLAN_FALLBACK)

    def test_validator_routes_repair_then_end(self):
        from django.test import override_settings

        from apps.designer_studio.designer_graph_checkmate import route_after_validator

        self.assertEqual(
            route_after_validator(
                {
                    "terminal": DesignerGraphTerminal.VALIDATION_PASSED.value,
                    "validation_repair_passes": 0,
                }
            ),
            "end",
        )
        self.assertEqual(
            route_after_validator(
                {
                    "terminal": DesignerGraphTerminal.VALIDATION_NEEDS_REPAIR.value,
                    "validation_repair_passes": 0,
                }
            ),
            "end",
        )

        with override_settings(DESIGNER_VALIDATOR_REPAIR_ENABLED=True):
            self.assertEqual(
                route_after_validator(
                    {
                        "terminal": DesignerGraphTerminal.VALIDATION_NEEDS_REPAIR.value,
                        "validation_repair_passes": 0,
                    }
                ),
                "validator_repair",
            )
