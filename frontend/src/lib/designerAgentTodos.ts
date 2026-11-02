import type { AgentWorkPlanStep } from "./designerChatStream";

/** Shown immediately on send until SSE `todo` events arrive. */
export const PLANNING_WAIT_TODOS: AgentWorkPlanStep[] = [
  {
    id: "planning",
    label: "Creating your to-do list from this request…",
    status: "active",
  },
];

export function isPlanningOnlyTodos(todos: AgentWorkPlanStep[]): boolean {
  return todos.length === 1 && todos[0]?.id === "planning";
}

export function isExecutionTodoList(todos: AgentWorkPlanStep[]): boolean {
  return todos.some((t) => t.id.startsWith("exec_") || t.id === "finalize");
}
